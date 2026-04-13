from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import User, AuditLog, get_session
from core.auth import (
    hash_password, verify_password, create_access_token, 
    get_current_user, is_password_expired
)
from core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str


class PasswordChangeRequest(BaseModel):
    old_password: Optional[str] = None
    new_password: str


class UserInfo(BaseModel):
    id: str
    username: str
    is_admin: bool
    is_active: bool
    password_changed_at: str
    password_expires_at: str
    created_at: str


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, req: Request, session: AsyncSession = Depends(get_session)):
    """Login de usuario"""
    result = await session.execute(select(User).where(User.username == request.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名 o contraseña incorretti")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario desactivado")
    
    # Verificar si password expiró
    if is_password_expired(user):
        raise HTTPException(
            status_code=403,
            detail="Password expirada. Debes cambiar tu password.",
            headers={"X-Password-Expired": "true"}
        )
    
    # Crear token
    expires_delta = timedelta(days=7)
    access_token = create_access_token(
        {"sub": user.id, "username": user.username},
        expires_delta
    )
    
    return LoginResponse(
        access_token=access_token,
        expires_at=(datetime.utcnow() + expires_delta).isoformat()
    )


@router.get("/me", response_model=UserInfo)
async def get_me(user: User = Depends(get_current_user)):
    """Obtener información del usuario actual"""
    return UserInfo(**user.to_dict())


@router.post("/password")
async def change_password(
    data: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Cambiar password del usuario"""
    # Vérificar password anterior si se proporciona
    if data.old_password:
        if not verify_password(data.old_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Password anterior incorrecta")
    elif user.is_admin and user.username == "admin":
        pass  # Admin puede cambiar sin password anterior
    else:
        raise HTTPException(status_code=400, detail="Debes proporcionar password anterior")
    
    # Hash nueva password
    user.password_hash = hash_password(data.new_password)
    user.password_changed_at = datetime.utcnow()
    user.password_expires_at = datetime.utcnow() + timedelta(days=settings.PASSWORD_EXPIRE_DAYS)
    
    # Guardar
    session.add(user)
    await session.commit()
    
    # Log de auditoría
    audit = AuditLog(
        user_id=user.id,
        action="password_changed",
        details=f"Usuario cambió su password"
    )
    session.add(audit)
    await session.commit()
    
    return {"message": "Password cambiada exitosamente"}


@router.post("/logout")
async def logout(user: User = Depends(get_current_user)):
    """Logout (invalidar token) - El cliente debe descartar el token"""
    # Podrías implementar una blacklist de tokens aquí
    return {"message": "Logout exitoso. Discard el token."}