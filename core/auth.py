import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from jose import JWTError, jwt
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_session, User
from core.config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


def _utc_now():
    """Obtener datetime actual en UTC"""
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    """Hashear password con bcrypt"""
    pwd = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd, salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verificar password con bcrypt"""
    pwd = password.encode('utf-8')
    hashh = password_hash.encode('utf-8')
    return bcrypt.checkpw(pwd, hashh)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crear JWT token"""
    to_encode = data.copy()
    expire = _utc_now() + (expires_delta or timedelta(days=1))
    # Exp debe ser integer (Unix timestamp), no string
    to_encode.update({"exp": int(expire.timestamp())})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    """Decodificar JWT token"""
    try:
        # Log for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Decoding token with SECRET_KEY: {settings.SECRET_KEY[:10]}...")
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        logger.info(f"Token payload: {payload}")
        return payload
    except JWTError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"JWT Error: {e}")
        raise HTTPException(status_code=401, detail="Token inválido")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Decode error: {e}")
        raise HTTPException(status_code=401, detail="Token inválido")


def is_password_expired(user: User) -> bool:
    """Verificar si password expiró"""
    if user.password_expires_at is None:
        return False
    
    # Asegurar que ambos tengan timezone para comparar
    expires_at = user.password_expires_at
    if expires_at.tzinfo is None:
        # naive datetime - asumir UTC
        from datetime import timezone
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    return datetime.now(timezone.utc) > expires_at


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_session)
) -> User:
    """Obtener usuario actual desde token"""
    # HTTPBearer(auto_error=False) no lanza si falta el header → credentials=None
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = credentials.credentials
    payload = decode_token(token)
    user_id = payload.get("sub")
    
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token inválido")
    
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario desactivado")
    
    if is_password_expired(user):
        raise HTTPException(status_code=403, detail="Password expirada. Debes cambiar tu password.")
    
    return user


async def get_current_admin(
    user: User = Depends(get_current_user)
) -> User:
    """Verificar que usuario es admin"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Se requiere permisos de administrador")
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_session)
) -> Optional[User]:
    """Obtener usuario si tiene token válido, si no None"""
    if credentials is None:
        return None
    
    try:
        return await get_current_user(credentials, session)
    except HTTPException:
        return None


async def get_user_from_api_key(
    api_key: str,
    session: AsyncSession
) -> Optional[User]:
    """Validar API key y retornar usuario asociado"""
    from core.database import APIKey
    
    if not api_key:
        return None
    
    # Buscar key en la base de datos (comparación directa, sin hash)
    result = await session.execute(
        select(APIKey).where(
            APIKey.key_hash == api_key,
            APIKey.is_active == True
        )
    )
    db_key = result.scalar_one_or_none()
    
    if not db_key:
        return None
    
    # Actualizar last_used_at
    db_key.last_used_at = datetime.now(timezone.utc)
    await session.commit()
    
    # Obtener usuario asociado
    result = await session.execute(
        select(User).where(User.id == db_key.user_id)
    )
    user = result.scalar_one_or_none()
    
    if user and not user.is_active:
        return None
    
    return user


async def get_current_user_or_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_session)
) -> User:
    """
    Obtener usuario desde API Key (X-API-Key o Authorization: Bearer) o JWT.
    Soporta tanto el formato nativo (X-API-Key) como OpenAI-compatible (Bearer).
    """
    # Intentar API Key desde header X-API-Key
    api_key = request.headers.get("X-API-Key")
    if api_key:
        user = await get_user_from_api_key(api_key, session)
        if user:
            return user
    
    # Intentar Bearer token como API Key (formato OpenAI/OpenCode)
    if credentials:
        bearer_token = credentials.credentials
        # Primero intentar como API Key
        user = await get_user_from_api_key(bearer_token, session)
        if user:
            return user
        
        # Luego intentar como JWT
        try:
            return await get_current_user(credentials, session)
        except HTTPException:
            pass
    
    # Ninguna autenticación válida
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide X-API-Key header or Authorization Bearer token."
    )