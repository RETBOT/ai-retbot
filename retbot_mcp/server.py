"""
RETBOT MCP Server - Capa de herramientas para el agente

Este servidor expone las funcionalidades EXISTENTES de RETBOT como
MCP Tools que el agente (OpenCode + Ollama) puede descubrir y llamar
automáticamente según la solicitud del usuario.

Diseño:
- Cada tool DELEGA en la lógica existente del proyecto (core/).
- NO se duplica código: se reutiliza ToolExecutor, health, model_manager,
  cache y las queries de core/database.py.
- El uso manual (CLI, API, Web UI) NO se toca.

Ejecución:
    python retbot_mcp/server.py     # transport stdio (para OpenCode)

Variables de entorno (opcionales):
    MCP_WORKING_DIR            directorio base de trabajo (default: cwd)
    MCP_ENABLE_ADMIN_WRITE     "true" habilita apikey.create/revoke y cache.clear
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional
from mcp.server.fastmcp import FastMCP

# Asegurar que la raíz del proyecto esté en sys.path sin importar cómo
# se invoque el script (python retbot_mcp/server.py desde cualquier cwd).
# Al ejecutar un script por ruta, Python agrega el dir del script, no la raíz.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# Configuración del servidor
# ============================================================

WORKING_DIR = (
    os.environ.get("MCP_WORKING_DIR")
    or settings.MCP_WORKING_DIR
    or "."
)

ADMIN_WRITE = str(
    os.environ.get("MCP_ENABLE_ADMIN_WRITE") or settings.MCP_ENABLE_ADMIN_WRITE
).lower() in ("1", "true", "yes", "on")

# ============================================================
# Creación del servidor
# ============================================================


def create_server() -> FastMCP:
    """Construir y registrar todas las MCP Tools."""
    from core.tools.executor import ToolExecutor

    mcp = FastMCP(
        "retbot",
        instructions=(
            "Servidor MCP de RETBOT: expone las capacidades del proyecto "
            "(file operations, sistema, modelos, cache, usuarios y API keys) "
            "como herramientas. Utiliza estas tools cuando necesites leer/escribir "
            "archivos del proyecto, diagnosticar el sistema, consultar modelos "
            "disponibles o revisar usuarios/logs/API keys."
        ),
    )

    # Ejecutor compartido para file tools (misma lógica que core/tools/)
    executor = ToolExecutor(WORKING_DIR)

    # ---------- Helpers de resultado estructurado ----------
    def _ok(**data):
        return {"success": True, **data}

    def _err(error: str, details: str = ""):
        return {"success": False, "error": error, "details": details}

    # =========================================================
    # FILE TOOLS (reutilizan core.tools.executor.ToolExecutor)
    # =========================================================

    @mcp.tool()
    async def read_file(path: str) -> dict:
        """Lee el contenido de un archivo de texto del proyecto.

        Úsala antes de editar, refactorizar o entender cualquier archivo.
        Respeta el path-traversal protection: solo puede acceder a archivos
        dentro del working directory configurado.
        """
        result = await executor.read_file(path)
        if not result.success:
            return _err(result.error or "No se pudo leer el archivo",
                        details=f"path={path}")
        return _ok(content=result.content, path=path)

    @mcp.tool()
    async def write_file(path: str, content: str) -> dict:
        """Escribe contenido en un archivo (lo crea si no existe, lo sobrescribe si existe).

        Úsala para crear archivos nuevos o reescribir archivos completos.
        Crea los directorios padre automáticamente.
        """
        result = await executor.write_file(path, content)
        if not result.success:
            return _err(result.error or "No se pudo escribir el archivo",
                        details=f"path={path}")
        return _ok(message=result.content, path=path)

    @mcp.tool()
    async def edit_file(path: str, old_string: str, new_string: str) -> dict:
        """Edita un archivo reemplazando la primera ocurrencia de old_string por new_string.

        Úsala para cambios pequeños y precisos (preferida sobre write_file
        para modificaciones puntuales). old_string debe coincidir exactamente,
        incluyendo espacios y saltos de línea.
        """
        result = await executor.edit_file(path, old_string, new_string)
        if not result.success:
            return _err(result.error or "No se pudo editar el archivo",
                        details="El string a reemplazar debe coincidir exactamente "
                                "(incluyendo espacios y saltos de línea)")
        return _ok(message=result.content, path=path)

    @mcp.tool()
    async def list_directory(path: str = ".") -> dict:
        """Lista el contenido de un directorio del proyecto (archivos y subdirectorios).

        Úsala para explorar la estructura del proyecto antes de modificar código.
        """
        result = await executor.list_directory(path)
        if not result.success:
            return _err(result.error or "No se pudo listar el directorio",
                        details=f"path={path}")
        return _ok(content=result.content, path=path)

    @mcp.tool()
    async def execute_command(command: str, timeout: int = 30) -> dict:
        """Ejecuta un comando shell con whitelist de seguridad.

        Úsala para correr tests (pytest), linters, comandos git (status,
        log, diff, show), instalar dependencias (pip/npm), o ejecutar
        el proyecto. Solo comandos de la whitelist están permitidos.
        Timeout en segundos (default 30, máx 300).
        """
        result = await executor.execute_command(command, timeout)
        if not result.success:
            return _err(result.error or "El comando falló",
                        details=f"command={command}")
        return _ok(output=result.content, command=command)

    # =========================================================
    # SYSTEM TOOLS (reutilizan core/health.py y core/config.py)
    # =========================================================

    @mcp.tool(name="system.health")
    async def system_health() -> dict:
        """Verifica el estado de salud de RETBOT (Ollama y base de datos).

        Úsala para diagnosticar si el servidor de modelos o la base de
        datos están caídos cuando el sistema no responde.
        """
        from core.health import health_check_simple
        return _ok(health=await health_check_simple())

    @mcp.tool(name="system.info")
    async def system_info() -> dict:
        """Muestra información general del servidor RETBOT.

        Modelo configurado, tipo, URL de Ollama, puerto, uptime y estado
        del cache. Úsala para entender la configuración actual del sistema.
        """
        from core.health import get_uptime
        return _ok(
            version="1.0.0",
            model=settings.MODEL_NAME,
            model_type=settings.MODEL_TYPE,
            ollama_url=settings.OLLAMA_URL,
            port=settings.PORT,
            public_url=settings.PUBLIC_URL or "(auto)",
            uptime=get_uptime(),
        )

    # =========================================================
    # MODELS TOOL (reutiliza core/model_manager.py)
    # =========================================================

    @mcp.tool(name="models.list")
    async def models_list() -> dict:
        """Lista los modelos disponibles en Ollama.

        Úsala para saber qué modelos existen antes de recomendar cuál usar
        o verificar si un modelo está instalado.
        """
        from core.model_manager import model_manager
        from core.config import settings as s
        models = await model_manager.get_available_models(force_refresh=True)
        return _ok(models=models, count=len(models), default=s.MODEL_NAME)

    # =========================================================
    # CACHE TOOL (reutiliza core/cache.py)
    # =========================================================

    @mcp.tool(name="cache.stats")
    async def cache_stats() -> dict:
        """Muestra estadísticas del cache de respuestas (hits, misses, hit rate).

        Úsala para diagnosticar el rendimiento del cache. Solo lectura.
        """
        from core.cache import cache
        stats = await cache.get_stats()
        return _ok(**stats)

    # =========================================================
    # ADMIN TOOLS (reutilizan core/database.py - mismas queries
    # que api/admin.py; NO exponen passwords ni hashes)
    # =========================================================

    @mcp.tool(name="admin.list_users")
    async def admin_list_users() -> dict:
        """Lista los usuarios registrados del sistema (sin passwords).

        Úsala para diagnóstico: saber quién tiene acceso, quién está activo
        y quién es admin. Solo lectura.
        """
        from core.database import async_session, User
        from sqlalchemy import select
        async with async_session() as session:
            result = await session.execute(
                select(User).order_by(User.created_at.desc())
            )
            users = result.scalars().all()
        return _ok(users=[u.to_dict() for u in users], count=len(users))

    @mcp.tool(name="admin.audit_logs")
    async def admin_audit_logs(limit: int = 20) -> dict:
        """Muestra los logs de auditoría recientes (acciones admin, keys, jobs).

        Úsala para investigar qué acciones se realizaron y por quién.
        Solo lectura. limit: máximo de registros (1-100).
        """
        from core.database import async_session, AuditLog
        from sqlalchemy import select
        limit = max(1, min(int(limit), 100))
        async with async_session() as session:
            result = await session.execute(
                select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
            )
            logs = result.scalars().all()
        return _ok(logs=[l.to_dict() for l in logs], count=len(logs))

    # =========================================================
    # API KEYS TOOL (reutiliza core/database.py; NO expone el hash)
    # =========================================================

    @mcp.tool(name="apikey.list")
    async def apikey_list() -> dict:
        """Lista las API Keys del sistema (sin mostrar el valor de la key).

        Úsala para verificar qué keys existen, su nombre, estado y a qué
        usuario pertenecen. Solo lectura.
        """
        from core.database import async_session, APIKey, User
        from sqlalchemy import select

        async with async_session() as session:
            result = await session.execute(
                select(APIKey).order_by(APIKey.created_at.desc())
            )
            keys = result.scalars().all()

            # Mapa de user_id -> username
            user_ids = {k.user_id for k in keys if k.user_id}
            users = {}
            if user_ids:
                uresult = await session.execute(
                    select(User).where(User.id.in_(user_ids))
                )
                users = {u.id: u.username for u in uresult.scalars().all()}

        safe_keys = []
        for k in keys:
            d = k.to_dict()
            d.pop("key_hash", None)  # nunca exponer el valor de la key
            d["username"] = users.get(k.user_id, "(sin dueño)")
            safe_keys.append(d)

        return _ok(keys=safe_keys, count=len(safe_keys))

    # =========================================================
    # ADMIN WRITE TOOLS (solo si MCP_ENABLE_ADMIN_WRITE=true)
    # =========================================================

    if ADMIN_WRITE:
        @mcp.tool(name="cache.clear")
        async def cache_clear() -> dict:
            """Limpia todo el cache de respuestas.

            Solo disponible si MCP_ENABLE_ADMIN_WRITE=true. Úsala cuando el
            cache esté devolviendo respuestas obsoletas.
            """
            from core.cache import cache
            deleted = await cache.clear_all()
            return _ok(message="Cache limpiado", keys_deleted=deleted)

        @mcp.tool(name="apikey.create")
        async def apikey_create(username: str, name: str) -> dict:
            """Crea una nueva API Key para un usuario existente.

            Solo disponible si MCP_ENABLE_ADMIN_WRITE=true. Requiere el
            username (consúltalo con admin.list_users) y un nombre descriptivo.
            La key completa se devuelve UNA sola vez.
            """
            import secrets
            from core.database import async_session, APIKey, User
            from core.auth import hash_api_key
            from sqlalchemy import select

            async with async_session() as session:
                result = await session.execute(
                    select(User).where(User.username == username)
                )
                user = result.scalar_one_or_none()
                if not user:
                    return _err(f"Usuario '{username}' no encontrado",
                                details="Usa admin.list_users para ver los usuarios")

                random_part = secrets.token_hex(16)
                api_key_plain = f"key_{random_part}"

                db_key = APIKey(
                    user_id=user.id,
                    name=name,
                    key_hash=hash_api_key(api_key_plain),
                    permissions="chat",
                    is_active=True,
                )
                session.add(db_key)
                await session.commit()
                await session.refresh(db_key)

            return _ok(
                message="API Key creada. ¡Guárdala ahora! No se mostrará de nuevo.",
                key=api_key_plain,
                id=db_key.id,
                name=db_key.name,
                username=username,
            )

        @mcp.tool(name="apikey.revoke")
        async def apikey_revoke(key_id: str) -> dict:
            """Revoca (elimina) una API Key existente.

            Solo disponible si MCP_ENABLE_ADMIN_WRITE=true. Requiere el id
            de la key (consúltalo con apikey.list).
            """
            from core.database import async_session, APIKey
            from sqlalchemy import select

            async with async_session() as session:
                result = await session.execute(
                    select(APIKey).where(APIKey.id == key_id)
                )
                db_key = result.scalar_one_or_none()
                if not db_key:
                    return _err(f"API Key '{key_id}' no encontrada",
                                details="Usa apikey.list para ver los ids")

                name = db_key.name
                await session.delete(db_key)
                await session.commit()

            return _ok(message="API Key revocada exitosamente", name=name, id=key_id)

    return mcp


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    server = create_server()
    logger.info(f"RETBOT MCP iniciando (working_dir={WORKING_DIR}, "
                f"admin_write={ADMIN_WRITE})")
    server.run(transport="stdio")