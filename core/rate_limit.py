"""
Rate Limiting por Usuario/API Key

Este módulo implementa rate limiting basado en la identidad del usuario
(API key o JWT token) en lugar de la dirección IP.
"""
from slowapi import Limiter
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Security scheme para obtener JWT
security = HTTPBearer(auto_error=False)

# Limiter global (se configura después con settings)
_limiter: Optional[Limiter] = None


def get_limiter() -> Optional[Limiter]:
    """Obtener el limiter global"""
    return _limiter


def get_user_identifier(request: Request) -> str:
    """
    Obtener identificador único del usuario para rate limiting.
    
    Prioridad:
    1. API Key (header X-API-Key)
    2. JWT token (header Authorization: Bearer)
    3. IP address (fallback)
    
    Returns:
        str: Identificador único del usuario
    """
    # Intentar obtener API Key
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"api_key:{api_key}"
    
    # Intentar obtener JWT token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remover "Bearer "
        return f"jwt:{token[:32]}"  # Usar primeros 32 chars del token como ID
    
    # Fallback a IP address
    return f"ip:{get_remote_address(request)}"


def get_remote_address(request: Request) -> str:
    """Obtener dirección IP del request"""
    # Verificar headers de proxy (X-Forwarded-For)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Primer IP es la del cliente original
        return forwarded_for.split(",")[0].strip()
    
    # Obtener IP directa del cliente
    client_host = request.client.host if request.client else "unknown"
    return client_host


def create_limiter() -> Limiter:
    """
    Crear instancia de Limiter configurada para rate limiting por usuario.
    
    Returns:
        Limiter: Instancia configurada de slowapi Limiter
    """
    global _limiter
    from core.config import settings
    
    if not settings.RATE_LIMIT_ENABLED:
        logger.warning("⚠️ Rate limiting DESHABILITADO")
    
    _limiter = Limiter(
        key_func=get_user_identifier,
        default_limits=[f"{settings.RATE_LIMIT_PER_USER}/minute"],
        enabled=settings.RATE_LIMIT_ENABLED,
        storage_uri="memory://"  # Usar memoria para simplicidad
        # Para producción con múltiples instancias: f"redis://{settings.REDIS_URL}"
    )
    
    return _limiter


def parse_rate_limit(limit_string: str) -> dict:
    """
    Parsear string de rate limit a componentes.
    
    Args:
        limit_string: Ej. "10/minute", "100/hour", "1000/day"
    
    Returns:
        dict: {"count": 10, "period": "minute"}
    """
    count_str, period = limit_string.split("/")
    
    return {
        "count": int(count_str),
        "period": period,
        "seconds": {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400
        }.get(period, 60)
    }


# Decoradores personalizados
def rate_limit_user(limit: str):
    """
    Decorador para aplicar rate limit específico a un endpoint.
    
    Args:
        limit: String de rate limit. Ej. "10/minute", "100/hour"
    
    Usage:
        @router.post("/chat")
        @rate_limit_user("10/minute")
        async def chat():
            ...
    """
    from core.config import settings
    
    if not settings.RATE_LIMIT_ENABLED:
        # Si está deshabilitado, retornar decorador que no hace nada
        def decorator(func):
            return func
        return decorator
    
    limiter = create_limiter()
    return limiter.limit(limit)


async def check_rate_limit(request: Request, limit: str) -> bool:
    """
    Verificar manualmente si se excedió el rate limit.
    
    Útil para lógica condicional o mensajes personalizados.
    
    Args:
        request: FastAPI request object
        limit: String de rate limit. Ej. "10/minute"
    
    Returns:
        bool: True si está dentro del límite, False si excedido
    
    Raises:
        HTTPException: Si se excedió el límite
    """
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    
    limiter = create_limiter()
    
    try:
        # Verificar límite
        await limiter.check(request, limit)
        return True
    except RateLimitExceeded:
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "message": f"Rate limit exceeded. Maximum {limit} allowed.",
                    "type": "rate_limit_error",
                    "code": "rate_limit_exceeded"
                }
            }
        )
