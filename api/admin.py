from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import User, Job, AuditLog, get_session
from core.auth import hash_password, verify_password, get_current_user, get_current_admin

router = APIRouter(prefix="/admin", tags=["admin"])


class CreateUserRequest(BaseModel):
    username: str
    password: str
    is_admin: bool = False


class UpdateUserRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


class UserResponse(BaseModel):
    id: str
    username: str
    is_admin: bool
    is_active: bool
    password_changed_at: str
    password_expires_at: str
    created_at: str


class JobResponse(BaseModel):
    id: str
    user_id: str
    message: str
    status: str
    result: Optional[str]
    error: Optional[str]
    model: Optional[str]
    created_at: str
    completed_at: Optional[str]


class AuditLogResponse(BaseModel):
    id: str
    user_id: Optional[str]
    action: str
    details: Optional[str]
    ip_address: Optional[str]
    created_at: str


@router.post("/users", response_model=UserResponse)
async def create_user(
    data: CreateUserRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session)
):
    """Crear nuevo usuario"""
    # Verificar si username existe
    result = await session.execute(
        select(User).where(User.username == data.username)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="Username ya existe")
    
    # Crear usuario
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        is_admin=data.is_admin,
        is_active=True,
        password_changed_at=datetime.utcnow(),
        password_expires_at=datetime.utcnow() + timedelta(days=settings.PASSWORD_EXPIRE_DAYS)
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    
    # Log de auditoría
    audit = AuditLog(
        user_id=admin.id,
        action="user_created",
        details=f"Admin {admin.username} creó usuario {user.username}",
        ip_address=request.client.host
    )
    session.add(audit)
    await session.commit()
    
    return UserResponse(**user.to_dict())


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session)
):
    """Listar todos los usuarios"""
    result = await session.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [UserResponse(**u.to_dict()) for u in users]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session)
):
    """Ver usuario específico"""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    return UserResponse(**user.to_dict())


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    data: UpdateUserRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session)
):
    """Actualizar usuario (activar/desactivar, cambiar password)"""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    changes = []
    
    if data.is_active is not None:
        user.is_active = data.is_active
        changes.append(f"is_active={data.is_active}")
    
    if data.is_admin is not None:
        user.is_admin = data.is_admin
        changes.append(f"is_admin={data.is_admin}")
    
    if data.username:
        user.username = data.username
        changes.append(f"username={data.username}")
    
    if data.password:
        user.password_hash = hash_password(data.password)
        changes.append("password cambiada")
        user.password_changed_at = datetime.utcnow()
        user.password_expires_at = datetime.utcnow() + timedelta(days=settings.PASSWORD_EXPIRE_DAYS)
    
    # Log de auditoría
    audit = AuditLog(
        user_id=admin.id,
        action="user_updated",
        details=f"Admin {admin.username} actualizó usuario {user.username}: {', '.join(changes)}",
        ip_address=request.client.host
    )
    session.add(audit)
    await session.commit()
    await session.refresh(user)
    
    return UserResponse(**user.to_dict())


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session)
):
    """Desactivar usuario"""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="No puedes desactivarte a ti mismo")
    
    user.is_active = False
    
    # Log de auditoría
    audit = AuditLog(
        user_id=admin.id,
        action="user_deactivated",
        details=f"Admin {admin.username} desactivó usuario {user.username}",
        ip_address=request.client.host
    )
    session.add(audit)
    await session.commit()
    
    return {"message": "Usuario desactivado"}


@router.get("/jobs", response_model=List[JobResponse])
async def list_all_jobs(
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
    limit: int = 100
):
    """Listar todos los jobs"""
    result = await session.execute(
        select(Job).order_by(Job.created_at.desc()).limit(limit)
    )
    jobs = result.scalars().all()
    return [JobResponse(**j.to_dict()) for j in jobs]


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session)
):
    """Ver job específico"""
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    return JobResponse(**job.to_dict())


@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
    limit: int = 100
):
    """Ver logs de auditoría"""
    result = await session.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    )
    logs = result.scalars().all()
    return [AuditLogResponse(**l.to_dict()) for l in logs]


# Importar settings para PASSWORD_EXPIRE_DAYS
from core.config import settings