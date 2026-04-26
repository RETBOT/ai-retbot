import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Configurar logging estructurado
from core.logging_config import setup_logging, LoggingMiddleware, logger

# Setup logging (JSON para producción, colored para desarrollo)
log_format = "json" if os.getenv("LOG_FORMAT") == "json" else "auto"
setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format_type=log_format,
    service_name="retbot",
    log_file="logs/server.log"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Generar API Key si no existe
    from core.database import async_session, APIKey
    from sqlalchemy import select
    
    await init_db()
    logger.info("Base de datos inicializada")
    
    async with async_session() as session:
        # Verificar usuario admin primero
        result = await session.execute(select(User).where(User.username == "admin"))
        admin = result.scalar_one_or_none()
        
        if not admin and settings.ADMIN_PASSWORD:
            from datetime import datetime, timedelta
            admin = User(
                username="admin",
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                is_admin=True,
                is_active=True,
                password_changed_at=datetime.now(timezone.utc),
                password_expires_at=datetime.now(timezone.utc) + timedelta(days=settings.PASSWORD_EXPIRE_DAYS)
            )
            session.add(admin)
            await session.commit()
            logger.info("Usuario admin creado desde .env")
        
        # Verificar si hay API Keys
        result = await session.execute(select(APIKey))
        api_keys = result.scalars().all()
        
        if not api_keys:
            # Generar API Key automática
            import secrets
            auto_api_key = f"rb_{secrets.token_hex(16)}"
            
            # Asociar al usuario admin si existe, si no dejar null
            admin_user_id = admin.id if admin else None
            
            new_key = APIKey(
                key_hash=auto_api_key,
                name="Auto-generated API Key",
                user_id=admin_user_id,  # Asociar al admin si existe
                is_active=True
            )
            session.add(new_key)
            await session.commit()
            
            # Mostrar API Key en logs (solo la primera vez)
            logger.info("=" * 60)
            logger.info(f"🔑 API KEY GENERADA: {auto_api_key}")
            logger.info("=" * 60)
            logger.info("⚠️  GUARDA ESTA KEY - No se mostrará de nuevo")
            logger.info("⚠️  Úsala en: X-API-Key header o Web UI login")
            logger.info("=" * 60)
        elif not admin:
            logger.warning("⚠️ No hay admin. Configura ADMIN_PASSWORD en .env")
    
    logger.info("Aplicación iniciada")
    yield
    logger.info("Aplicación cerrada")
    
    # Cerrar cache
    await close_cache()


from core.config import settings
from core.database import init_db, User
from core.auth import hash_password


app = FastAPI(
    title="AI Coding Assistant API",
    description="API multi-usuario con Ollama",
    version="1.0.0",
    lifespan=lifespan
)

# CORS: permitir todos si ALLOWED_ORIGINS=*, si no usar la lista configurada
cors_origins = ["*"] if settings.ALLOWED_ORIGINS == "*" else settings.cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Agregar middleware de logging
app.add_middleware(LoggingMiddleware)

from api.auth import router as auth_router
from api.admin import router as admin_router
from api.jobs import router as jobs_router
from api.streaming import router as streaming_router

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(jobs_router)
app.include_router(streaming_router)


@app.get("/health")
async def health_simple():
    """Health check rápido para monitoreo básico"""
    from core.health import health_check_simple
    return await health_check_simple()


@app.get("/health/full")
async def health_full():
    """Health check completo con todos los detalles del sistema"""
    from core.health import health_check_full
    return await health_check_full()


@app.get("/")
async def root():
    return {
        "name": "AI Coding Assistant API",
        "version": "1.0.0",
        "docs": "/docs",
        "admin": "/admin/users (solo admin)"
    }


# Servir Web UI estática
@app.get("/admin/ui")
async def serve_ui():
    """Servir Web UI de administración"""
    from fastapi.responses import HTMLResponse
    
    web_dir = os.path.join(os.path.dirname(__file__), 'web')
    index_path = os.path.join(web_dir, 'index.html')
    
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        logger.error(f"No se encontró el archivo: {index_path}")
        return HTMLResponse(
            content="<h1>Error: Web UI no encontrada</h1><p>El archivo index.html no existe</p>",
            status_code=404
        )
    except Exception as e:
        logger.error(f"Error sirviendo Web UI: {e}")
        return HTMLResponse(
            content=f"<h1>Internal Server Error</h1><p>{str(e)}</p>",
            status_code=500
        )


if __name__ == "__main__":
    import uvicorn
    # Producción: sin reload
    uvicorn.run("server:app", host="0.0.0.0", port=settings.PORT, reload=False)
