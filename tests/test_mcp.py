"""
Tests del MCP Server de RETBOT (retbot_mcp)

Cubre:
1. Registro correcto de tools (12 default + 3 bajo flag)
2. File tools vía MCP (reutilizan ToolExecutor)
3. Tools de sistema/modelos/cache
4. Tools de DB (usuarios, logs, API keys)
5. Validación de parámetros (Pydantic)
6. E2E transporte stdio (protocolo MCP real vía subprocess)

Notas:
- No requieren Ollama corriendo (health/model_manager capturan errores y
  devuelven fallback -- misma tolerancia que el server real).
- Mantienen compatibilidad con el uso manual: las file tools pasan por
  ToolExecutor, que ya está cubierto por tests/test_tools.py.
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent

# Las 12 tools que SIEMPRE deben estar registradas
DEFAULT_TOOLS = {
    "read_file", "write_file", "edit_file", "list_directory", "execute_command",
    "system.health", "system.info", "models.list", "cache.stats",
    "admin.list_users", "admin.audit_logs", "apikey.list",
}

# Las 3 tools SOLO habilitadas con MCP_ENABLE_ADMIN_WRITE=true
ADMIN_WRITE_TOOLS = {"cache.clear", "apikey.create", "apikey.revoke"}


# ---------- Helpers ----------

def _extract_payload(result):
    """Extraer la payload (dict) de un resultado de call_tool.

    FastMCP devuelve Sequence[ContentBlock] (lista de TextContent) o dict
    según la versión; en el protocolo stdio el JSON trae result.content.
    """
    data = result.data if hasattr(result, "data") else result
    if isinstance(data, (list, tuple)):
        # Sequence[ContentBlock]
        texts = [b.text for b in data if hasattr(b, "text")]
        data = "\n".join(texts) if texts else str(data)
    if isinstance(data, str):
        try:
            return json.loads(data)
        except (json.JSONDecodeError, ValueError):
            return {"raw": data}
    return data


def _is_error(result) -> bool:
    if hasattr(result, "isError"):
        return bool(result.isError)
    return False


# ---------- 1. Registro de tools ----------

@pytest.mark.asyncio
async def test_registration_default_tools():
    """Con flag off: exactamente las 12 tools default, sin las de admin write."""
    import retbot_mcp.server as server_module
    server_module.ADMIN_WRITE = False  # garantizar flag apagado

    server = server_module.create_server()
    tools = await server.list_tools()
    names = {t.name for t in tools}

    assert names == DEFAULT_TOOLS
    assert not (names & ADMIN_WRITE_TOOLS)
    assert len(tools) == 12

    # Las descriptions no deben estar vacías (el agente las necesita)
    for tool in tools:
        assert tool.description.strip()


@pytest.mark.asyncio
async def test_registration_admin_write_flag():
    """Con flag on: 15 tools (default + 3 de admin write)."""
    import retbot_mcp.server as server_module
    server_module.ADMIN_WRITE = True

    server = server_module.create_server()
    tools = await server.list_tools()
    names = {t.name for t in tools}

    assert names == DEFAULT_TOOLS | ADMIN_WRITE_TOOLS
    assert len(tools) == 15


# ---------- 2. File tools vía MCP ----------

@pytest.mark.asyncio
async def test_file_tools_read_write_list(monkeypatch):
    """Flujo completo: write -> list -> read vía MCP (working dir aislado)."""
    import retbot_mcp.server as server_module
    server_module.ADMIN_WRITE = False

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(server_module, "WORKING_DIR", tmpdir)
        server = server_module.create_server()

        # write_file
        res = await server.call_tool("write_file", {
            "path": "archivo.txt", "content": "Hola RETBOT MCP"
        })
        payload = _extract_payload(res)
        assert not _is_error(res)
        assert payload.get("success") is True

        # Verificar que el executor lo escribió en el working_dir
        assert (Path(tmpdir) / "archivo.txt").read_text(encoding="utf-8") == "Hola RETBOT MCP"

        # list_directory
        res = await server.call_tool("list_directory", {"path": "."})
        payload = _extract_payload(res)
        assert not _is_error(res)
        assert payload.get("success") is True
        assert "archivo.txt" in payload.get("content", "")

        # read_file
        res = await server.call_tool("read_file", {"path": "archivo.txt"})
        payload = _extract_payload(res)
        assert not _is_error(res)
        assert payload.get("success") is True
        assert payload.get("content") == "Hola RETBOT MCP"


@pytest.mark.asyncio
async def test_edit_file_via_mcp(monkeypatch):
    """edit_file reemplaza strings vía MCP."""
    import retbot_mcp.server as server_module
    server_module.ADMIN_WRITE = False

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(server_module, "WORKING_DIR", tmpdir)
        (Path(tmpdir) / "editame.txt").write_text("El texto viejo", encoding="utf-8")

        server = server_module.create_server()
        res = await server.call_tool("edit_file", {
            "path": "editame.txt",
            "old_string": "viejo",
            "new_string": "nuevo",
        })
        payload = _extract_payload(res)
        assert not _is_error(res)
        assert payload.get("success") is True
        assert (Path(tmpdir) / "editame.txt").read_text(encoding="utf-8") == "El texto nuevo"


@pytest.mark.asyncio
async def test_read_file_not_found(monkeypatch):
    """read_file con archivo inexistente -> success False (no excepción)."""
    import retbot_mcp.server as server_module
    server_module.ADMIN_WRITE = False

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(server_module, "WORKING_DIR", tmpdir)
        server = server_module.create_server()

        res = await server.call_tool("read_file", {"path": "no_existe.txt"})
        payload = _extract_payload(res)
        assert not _is_error(res)  # el server devuelve estructura, no excepción
        assert payload.get("success") is False
        assert "error" in payload


@pytest.mark.asyncio
async def test_execute_command_not_allowed(monkeypatch):
    """execute_command rechaza comandos fuera de la whitelist."""
    import retbot_mcp.server as server_module
    server_module.ADMIN_WRITE = False

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(server_module, "WORKING_DIR", tmpdir)
        server = server_module.create_server()

        res = await server.call_tool("execute_command", {"command": "sudo rm -rf /"})
        payload = _extract_payload(res)
        assert not _is_error(res)
        assert payload.get("success") is False


# ---------- 3. Sistema / modelos / cache ----------

@pytest.mark.asyncio
async def test_system_health():
    """system.health no requiere Ollama corriendo (check tolerante a errores)."""
    import retbot_mcp.server as server_module
    server_module.ADMIN_WRITE = False
    server = server_module.create_server()

    res = await server.call_tool("system.health", {})
    payload = _extract_payload(res)
    assert not _is_error(res)
    assert payload.get("success") is True
    assert payload["health"]["status"] in ("ok", "degraded")
    assert "ollama" in payload["health"]


@pytest.mark.asyncio
async def test_system_info():
    """system.info devuelve la configuración del servidor."""
    import retbot_mcp.server as server_module
    server_module.ADMIN_WRITE = False
    server = server_module.create_server()

    res = await server.call_tool("system.info", {})
    payload = _extract_payload(res)
    assert not _is_error(res)
    assert payload.get("success") is True
    assert "model" in payload
    assert "ollama_url" in payload
    assert "port" in payload


@pytest.mark.asyncio
async def test_models_list():
    """models.list devuelve estructura válida.

    NOTA: si Ollama está caído devuelve [] con success=True (comportamiento
    real de core/model_manager, el mismo que expone la API REST). El test
    valida estructura, no la cantidad de modelos.
    """
    import retbot_mcp.server as server_module
    server_module.ADMIN_WRITE = False
    server = server_module.create_server()

    res = await server.call_tool("models.list", {})
    payload = _extract_payload(res)
    assert not _is_error(res)
    assert payload.get("success") is True
    assert isinstance(payload.get("models"), list)
    assert payload["count"] == len(payload["models"])
    assert "default" in payload  # el modelo configurado en el sistema


@pytest.mark.asyncio
async def test_cache_stats():
    """cache.stats devuelve métricas del cache (in-memory, sin Redis)."""
    import retbot_mcp.server as server_module
    server_module.ADMIN_WRITE = False
    server = server_module.create_server()

    res = await server.call_tool("cache.stats", {})
    payload = _extract_payload(res)
    assert not _is_error(res)
    assert payload.get("success") is True


# ---------- 4. Tools de DB ----------

@pytest.mark.asyncio
async def test_db_read_tools():
    """admin.list_users, admin.audit_logs y apikey.list responden con la DB real."""
    from core.database import init_db
    await init_db()  # garantizar que existen las tablas

    import retbot_mcp.server as server_module
    server_module.ADMIN_WRITE = False
    server = server_module.create_server()

    res = await server.call_tool("admin.list_users", {})
    payload = _extract_payload(res)
    assert not _is_error(res), f"admin.list_users falló: {payload}"
    assert payload.get("success") is True
    assert "users" in payload and "count" in payload

    res = await server.call_tool("admin.audit_logs", {"limit": 5})
    payload = _extract_payload(res)
    assert not _is_error(res), f"admin.audit_logs falló: {payload}"
    assert payload.get("success") is True
    assert isinstance(payload.get("logs"), list)

    res = await server.call_tool("apikey.list", {})
    payload = _extract_payload(res)
    assert not _is_error(res), f"apikey.list falló: {payload}"
    assert payload.get("success") is True
    # Las keys no deben exponer key_hash
    for key in payload.get("keys", []):
        assert "key_hash" not in key
        assert "key" not in key


# ---------- 5. Validación de parámetros ----------

@pytest.mark.asyncio
async def test_parameter_validation_missing_args(monkeypatch):
    """call_tool con argumentos faltantes -> error de validación (Pydantic).

    In-process, FastMCP lanza ToolError; por el protocolo (E2E) eso se
    convierte en isError=true en la respuesta de tools/call.
    """
    import retbot_mcp.server as server_module
    server_module.ADMIN_WRITE = False

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(server_module, "WORKING_DIR", tmpdir)
        server = server_module.create_server()

        # write_file sin "content" -> debe fallar la validación Pydantic
        with pytest.raises(Exception) as excinfo:
            await server.call_tool("write_file", {"path": "x.txt"})
        assert "validation" in str(excinfo.value).lower() or "missing" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_admin_write_tools_not_available():
    """Con flag off, apikey.create/revoke no deben existir (seguridad)."""
    import retbot_mcp.server as server_module
    server_module.ADMIN_WRITE = False
    server = server_module.create_server()

    with pytest.raises(Exception):
        await server.call_tool("apikey.create", {"username": "x", "name": "test"})


@pytest.mark.asyncio
async def test_apikey_create_revoke_roundtrip(monkeypatch):
    """Con flag on: crear y revocar API key (roundtrip completo contra la DB)."""
    from core.database import init_db
    await init_db()

    import retbot_mcp.server as server_module
    server_module.ADMIN_WRITE = True
    server = server_module.create_server()

    # Crear una key para el usuario admin que crea init_db
    res = await server.call_tool("apikey.create", {
        "username": "admin", "name": "test-mcp",
    })
    payload = _extract_payload(res)
    assert not _is_error(res), f"apikey.create falló: {payload}"
    assert payload.get("success") is True
    assert payload.get("key", "").startswith("key_")
    key_id = payload.get("id")
    assert key_id

    # Revocar
    res = await server.call_tool("apikey.revoke", {"key_id": str(key_id)})
    payload = _extract_payload(res)
    assert not _is_error(res), f"apikey.revoke falló: {payload}"
    assert payload.get("success") is True


# ---------- 6. E2E transporte stdio ----------

async def _mcp_stdio_roundtrip(env_extra: dict):
    """Arrancar el server real como subprocess y hacer el handshake MCP stdio.

    Devuelve (tools_names, respuestas) tras initialize + tools/list.
    """
    server_path = PROJECT_DIR / "retbot_mcp" / "server.py"

    env = dict(os.environ)
    env.update(env_extra)

    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(server_path),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(PROJECT_DIR),
        env=env,
    )

    try:
        # initialize
        init_msg = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "pytest-mcp", "version": "1.0"},
            },
        }
        proc.stdin.write((json.dumps(init_msg) + "\n").encode())
        await proc.stdin.drain()

        line = await asyncio.wait_for(proc.stdout.readline(), timeout=20)
        init_resp = json.loads(line)
        assert "result" in init_resp, f"initialize falló: {init_resp}"

        # notificación initialized (no genera respuesta)
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        proc.stdin.write((json.dumps(notif) + "\n").encode())
        await proc.stdin.drain()

        # tools/list
        list_msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        proc.stdin.write((json.dumps(list_msg) + "\n").encode())
        await proc.stdin.drain()

        line = await asyncio.wait_for(proc.stdout.readline(), timeout=20)
        list_resp = json.loads(line)
        tools = list_resp.get("result", {}).get("tools", [])
        return {t["name"] for t in tools}, proc
    except Exception:
        proc.kill()
        raise


@pytest.mark.asyncio
async def test_e2e_stdio_registers_tools():
    """El server real arranca vía stdio y registra las 12 tools default."""
    tools, proc = await _mcp_stdio_roundtrip({})
    try:
        assert tools == DEFAULT_TOOLS
        assert len(tools) == 12
    finally:
        proc.kill()
        await proc.wait()


@pytest.mark.asyncio
async def test_e2e_stdio_admin_write_flag():
    """Con MCP_ENABLE_ADMIN_WRITE=true el server registra 15 tools."""
    tools, proc = await _mcp_stdio_roundtrip({"MCP_ENABLE_ADMIN_WRITE": "true"})
    try:
        assert tools == DEFAULT_TOOLS | ADMIN_WRITE_TOOLS
        assert len(tools) == 15
    finally:
        proc.kill()
        await proc.wait()


@pytest.mark.asyncio
async def test_e2e_stdio_tool_call():
    """E2E: llamar read_file vía el protocolo real (tools/call)."""
    server_path = PROJECT_DIR / "retbot_mcp" / "server.py"

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "hola.txt").write_text("hola desde stdio", encoding="utf-8")

        env = dict(os.environ)
        env["MCP_WORKING_DIR"] = tmpdir

        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(server_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_DIR),
            env=env,
        )

        try:
            def frame(_id, method, params=None):
                msg = {"jsonrpc": "2.0", "id": _id, "method": method}
                if params is not None:
                    msg["params"] = params
                return json.dumps(msg) + "\n"

            def notification(method, params=None):
                msg = {"jsonrpc": "2.0", "method": method}
                if params is not None:
                    msg["params"] = params
                return json.dumps(msg) + "\n"

            # Handshake
            proc.stdin.write(frame(1, "initialize", {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "pytest-mcp", "version": "1.0"},
            }).encode())
            await proc.stdin.drain()
            assert "result" in json.loads(await asyncio.wait_for(proc.stdout.readline(), timeout=20))

            proc.stdin.write(notification("notifications/initialized").encode())
            await proc.stdin.drain()

            # tools/call read_file
            proc.stdin.write(frame(3, "tools/call", {
                "name": "read_file", "arguments": {"path": "hola.txt"},
            }).encode())
            await proc.stdin.drain()

            line = await asyncio.wait_for(proc.stdout.readline(), timeout=20)
            resp = json.loads(line)
            result = resp.get("result", {})
            assert result.get("isError") is False, f"read_file falló: {resp}"
            content = json.dumps(result.get("content", []))
            assert "hola desde stdio" in content
        finally:
            proc.kill()
            await proc.wait()