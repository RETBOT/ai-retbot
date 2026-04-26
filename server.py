import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from core.config import settings
from core.database import init_db, User
from core.auth import hash_password
from core.rate_limit import create_limiter

# Crear limiter configurado para rate limiting por usuario
limiter = create_limiter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializar cache
    from core.cache import init_cache, close_cache
    await init_cache(settings.REDIS_URL)
    
    await init_db()
    logger.info("Base de datos inicializada")
    
    from core.database import async_session
    from sqlalchemy import select
    
    async with async_session() as session:
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
        elif not admin:
            logger.warning("⚠️ No hay admin. Configura ADMIN_PASSWORD en .env")
    
    logger.info("Aplicación iniciada")
    yield
    logger.info("Aplicación cerrada")
    
    # Cerrar cache
    await close_cache()


app = FastAPI(
    title="AI Coding Assistant API",
    description="API multi-usuario con Ollama",
    version="1.0.0",
    lifespan=lifespan
)

# Configurar rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: permitir todos si ALLOWED_ORIGINS=*, si no usar la lista configurada
cors_origins = ["*"] if settings.ALLOWED_ORIGINS == "*" else settings.cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error", "code": "rate_limit_error"}}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=settings.PORT, reload=True)