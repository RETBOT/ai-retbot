import secrets
import logging
from datetime import datetime, timedelta
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

security = HTTPBearer()


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
    expire = datetime.utcnow() + (expires_delta or timedelta(days=1))
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
    return datetime.utcnow() > user.password_expires_at


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session)
) -> User:
    """Obtener usuario actual desde token"""
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