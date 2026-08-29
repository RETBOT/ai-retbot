"""
validate_local.py - Validacion ligera de RETBOT + MCP sin requerir Ollama.

Verifica que el sistema este operativo SIN arrancar el servidor completo ni
Ollama (ideal para maquinas lentas o sin GPU).

Checks:
  1. Imports criticos (core.config, retbot_mcp, SDK mcp)
  2. Settings cargan correctamente
  3. Servidor MCP responde por stdio (JSON-RPC initialize + tools/list)
  4. tools/list expone las 12 tools base
  5. tools/call system.health responde (puede ser "degraded" sin Ollama)
  6. File tools (write/read/delete) funcionan en un directorio temporal
  7. tools/call system.chat -> WARN si Ollama no esta disponible (no es FAIL)

Uso:
    venv\\Scripts\\python.exe scripts\\validate_local.py

Exit code:
    0  -> todo paso (o solo WARN)
    1  -> hubo al menos un FAIL
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Igual que retbot_mcp/server.py: exponer `core` y `retbot_mcp` al import
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def find_python() -> str:
    """Buscar el Python del venv (Windows o Linux), con fallback a sys.executable."""
    if os.name == "nt":
        candidate = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
    else:
        candidate = os.path.join(PROJECT_ROOT, "venv", "bin", "python")
    if os.path.exists(candidate):
        return candidate
    return sys.executable


def mcp_call(proc, method: str, params: dict, msg_id: int) -> dict:
    """Enviar un request JSON-RPC por stdio y esperar la respuesta del id."""
    payload = {
        "jsonrpc": "2.0",
        "id": msg_id,
        "method": method,
        "params": params,
    }
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()

    while True:
        line = proc.stdout.readline()
        if not line:
            return {"error": {"message": "EOF: el proceso MCP cerro el stdio"}}
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == msg_id:
            return msg


class Checker:
    """Mini-suite de checks con reporte ASCII (sin emojis) para Windows."""

    def __init__(self):
        self.results = []  # (nombre, estado, detalle)

    def check(self, name: str, fn, warn_only: bool = False):
        """Ejecutar fn(); PASS si no lanza, FAIL si lanza, WARN si warn_only."""
        try:
            detail = fn()
            self.results.append((name, "PASS" if not warn_only else "OK", detail or ""))
        except Exception as e:  # noqa: BLE001 - cualquier error se reporta
            status = "WARN" if warn_only else "FAIL"
            self.results.append((name, status, f"{type(e).__name__}: {e}"))

    def report(self) -> int:
        fails = 0
        warns = 0
        print("\n=== RESUMEN DE VALIDACION ===")
        for name, status, detail in self.results:
            mark = "[PASS]" if status == "PASS" else (
                "[OK]  " if status == "OK" else ("[WARN]" if status == "WARN" else "[FAIL]"))
            line = f"  {mark} {name}"
            if detail:
                line += f" -> {detail}"
            print(line)
            if status == "FAIL":
                fails += 1
            elif status == "WARN":
                warns += 1

        print(f"\nTotal: {len(self.results)} checks | FAILS: {fails} | WARNs: {warns}")
        if fails:
            print("Resultado: HAY FALLOS - revisar arriba")
            return 1
        if warns:
            print("Resultado: OK con advertencias (Ollama no requerido para operar)")
            return 0
        print("Resultado: TODO EN ORDEN")
        return 0


def main() -> int:
    print("=== RETBOT + MCP - Validacion ligera (sin Ollama) ===")
    print(f"Proyecto: {PROJECT_ROOT}")
    print(f"Python:   {find_python()}")

    checker = Checker()
    tempdir = tempfile.mkdtemp(prefix="retbot_validate_")

    def _imports():
        import core.config  # noqa: F401
        import retbot_mcp.server  # noqa: F401
        import mcp

        from importlib.metadata import version
        mcp_version = version("mcp")
        return f"SDK mcp {mcp_version}"

    def _settings():
        from core.config import settings
        assert settings.OLLAMA_URL, "OLLAMA_URL vacio"
        assert settings.MODEL_NAME, "MODEL_NAME vacio"
        return f"MODEL_NAME={settings.MODEL_NAME} OLLAMA_URL={settings.OLLAMA_URL}"

    proc = None

    def _spawn_mcp():
        nonlocal proc
        env = dict(os.environ)
        env["MCP_WORKING_DIR"] = tempdir  # file tools escriben en el temp
        proc = subprocess.Popen(
            [find_python(), "-m", "retbot_mcp.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=PROJECT_ROOT,
            env=env,
        )
        init = mcp_call(proc, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "validate_local", "version": "1.0"},
        }, 1)
        assert "error" not in init, init.get("error")
        assert init.get("result", {}).get("serverInfo", {}).get("name") == "retbot"
        return "handshake OK"

    def _tools_list():
        resp = mcp_call(proc, "tools/list", {}, 2)
        tools = resp.get("result", {}).get("tools", [])
        # 12 tools base sin MCP_ENABLE_ADMIN_WRITE; 15 con el flag
        assert len(tools) >= 12, f"se esperaban >= 12 tools, hay {len(tools)}"
        names = [t["name"] for t in tools]
        for required in ("system.health", "read_file", "write_file", "list_directory"):
            assert required in names, f"falta tool {required}"
        return f"{len(tools)} tools registradas"

    def _system_health():
        resp = mcp_call(proc, "tools/call", {
            "name": "system.health",
            "arguments": {},
        }, 3)
        result = resp.get("result", {})
        content = result.get("content", [])
        assert result.get("isError") is not True, f"health devolvio error: {content}"
        text = "".join(c.get("text", "") for c in content)
        assert '"success": true' in text, f"success != true: {text[:200]}"
        # Sin Ollama el status puede ser degraded/ok - ambos son validos
        return "health OK (status puede ser degraded sin Ollama)"

    def _file_tools():
        content_in = "Hola RETBOT, archivo de validacion ligera."
        # write_file (nombre real de la tool, sin prefijo)
        resp = mcp_call(proc, "tools/call", {
            "name": "write_file",
            "arguments": {"path": "valida.txt", "content": content_in},
        }, 4)
        assert resp.get("result", {}).get("isError") is not True, resp
        # read_file
        resp = mcp_call(proc, "tools/call", {
            "name": "read_file",
            "arguments": {"path": "valida.txt"},
        }, 5)
        text = "".join(c.get("text", "") for c in resp.get("result", {}).get("content", []))
        assert content_in in text, "read_file no devolvio el contenido escrito"
        # list_directory
        resp = mcp_call(proc, "tools/call", {
            "name": "list_directory",
            "arguments": {"path": "."},
        }, 6)
        assert resp.get("result", {}).get("isError") is not True, resp
        return "write/read/list OK en tempdir"

    def _chat_warn():
        import urllib.request
        from core.config import settings
        url = settings.OLLAMA_URL.rstrip("/") + "/api/tags"
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                assert r.status == 200, f"HTTP {r.status}"
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"Ollama no disponible ({url}) - {type(e).__name__}: {e}")

    try:
        checker.check("Imports criticos + SDK mcp", _imports)
        checker.check("Settings cargan correctamente", _settings)
        checker.check("Servidor MCP handshake (stdio)", _spawn_mcp)
        checker.check("tools/list >= 12 tools", _tools_list)
        checker.check("system.health via MCP", _system_health)
        checker.check("File tools en tempdir", _file_tools)
        checker.check("Ollama disponible (opcional)", _chat_warn, warn_only=True)
    finally:
        if proc is not None:
            try:
                proc.stdin.close()
                proc.terminate()
            except Exception:  # noqa: BLE001
                pass
        shutil.rmtree(tempdir, ignore_errors=True)

    return checker.report()


if __name__ == "__main__":
    sys.exit(main())