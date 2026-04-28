from datetime import datetime, timedelta, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import User, Job, AuditLog, APIKey, get_session
from core.auth import hash_password, verify_password, get_current_user, get_current_admin
import secrets

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


class APIKeyResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    name: str
    key_hash: str
    is_active: bool
    created_at: Optional[str] = None


class CreateAPIKeyRequest(BaseModel):
    name: str


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
        password_changed_at=datetime.now(timezone.utc),
        password_expires_at=datetime.now(timezone.utc) + timedelta(days=settings.PASSWORD_EXPIRE_DAYS)
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
        user.password_changed_at = datetime.now(timezone.utc)
        user.password_expires_at = datetime.now(timezone.utc) + timedelta(days=settings.PASSWORD_EXPIRE_DAYS)
    
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


@router.post("/setup/opencode")
async def generate_opencode_config(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Generar configuración de OpenCode automáticamente.
    
    Este endpoint crea una configuración lista para usar con OpenCode,
    incluyendo la API key del usuario si existe.
    """
    from core.database import APIKey
    from core.models import SYSTEM_PROMPT
    import hashlib
    
    # Buscar API key existente del usuario
    result = await session.execute(
        select(APIKey)
        .where(APIKey.user_id == user.id, APIKey.is_active == True)
        .order_by(APIKey.created_at.desc())
    )
    api_key = result.scalar_one_or_none()
    
    # Si no tiene API key, crear una
    if not api_key:
        import secrets
        import uuid
        
        random_part = secrets.token_urlsafe(32)
        api_key_plain = f"key_{random_part}"  # Prefix genérico
        
        api_key = APIKey(
            id=str(uuid.uuid4()),
            user_id=user.id,
            name="OpenCode Auto-Generated",
            key_hash=api_key_plain,  # Guardar sin hash
            permissions="chat",
            is_active=True
        )
        session.add(api_key)
        await session.commit()
        await session.refresh(api_key)
    else:
        # No podemos recuperar la key en texto plano, instructivo al usuario
        api_key_plain = "[TU_API_KEY_AQUI - Usa list-api-keys para ver tus keys]"
    
    # Detectar URL base
    host = request.headers.get("host", "localhost:8000")
    scheme = "https" if request.headers.get("x-forwarded-proto") == "https" else "http"
    base_url = f"{scheme}://{host}/api/v1"
    
    config = {
        "$schema": "https://opencode.ai/config.json",
        "model": f"retbot/{settings.MODEL_NAME}",
        "provider": {
            "retbot": {
                "name": "RETBOT",
                "npm": "@ai-sdk/openai-compatible",
                "options": {
                    "baseURL": base_url,
                    "headers": {
                        "X-API-Key": api_key_plain if api_key_plain.startswith("key_") else "[API_KEY]"
                    }
                },
                "models": {
                    settings.MODEL_NAME: {
                        "name": settings.MODEL_NAME
                    }
                }
            }
        },
        "agent": {
            "retbot": {
                "name": "RETBOT",
                "prompt": SYSTEM_PROMPT[:200] + "...",
                "description": "Expert AI coding assistant with tool support",
                "mode": "primary",
                "tools": {
                    "read": True,
                    "write": True,
                    "edit": True,
                    "bash": True
                }
            }
        }
    }
    
    return {
        "message": "Configuración generada exitosamente",
        "config": config,
        "instructions": [
            "1. Copia esta configuración a tu archivo opencode.json",
            "2. Reemplaza [API_KEY] con tu API key real",
            "3. Reinicia OpenCode para aplicar los cambios",
            "4. Alternativa: Guarda como .opencode.json en la raíz de tu proyecto"
        ]
    }

# ============================================
# API Keys Endpoints
# ============================================

@router.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Listar API Keys del usuario actual"""
    result = await session.execute(
        select(APIKey)
        .where(APIKey.user_id == user.id)
        .order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [APIKeyResponse(**k.to_dict()) for k in keys]


@router.post("/api-keys")
async def create_api_key(
    data: CreateAPIKeyRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Crear nueva API Key para el usuario actual"""
    # Generar API Key única (prefix genérico)
    api_key_plain = f"key_{secrets.token_hex(16)}"
    
    # Crear API Key en DB (guardar la key tal cual para poder revelarla después)
    api_key = APIKey(
        user_id=user.id,
        name=data.name,
        key_hash=api_key_plain,  # Guardar la key sin hashear
        is_active=True
    )
    session.add(api_key)
    
    # Log de auditoría
    audit = AuditLog(
        user_id=user.id,
        action="api_key_created",
        details=f"API Key creada: {data.name}",
        ip_address=request.client.host
    )
    session.add(audit)
    
    await session.commit()
    await session.refresh(api_key)
    
    # Retornar API Key (solo se muestra una vez)
    return {
        "key": api_key_plain,
        "id": api_key.id,
        "name": api_key.name,
        "created_at": api_key.created_at.isoformat() if api_key.created_at else None
    }


@router.get("/api-keys/{key_id}/reveal")
async def reveal_api_key(
    key_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Ver API Key completa (solo para admin o dueño)"""
    result = await session.execute(select(APIKey).where(APIKey.id == key_id))
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API Key no encontrada")
    
    # Verificar permisos
    if api_key.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="No tienes permiso para ver esta API Key")
    
    return {
        "id": api_key.id,
        "name": api_key.name,
        "key": api_key.key_hash,  # Retorna la key completa
        "is_active": api_key.is_active,
        "created_at": api_key.created_at.isoformat() if api_key.created_at else None
    }


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Revocar/eliminar API Key"""
    result = await session.execute(select(APIKey).where(APIKey.id == key_id))
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API Key no encontrada")
    
    # Verificar que la key pertenece al usuario (o es admin)
    if api_key.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="No tienes permiso para revocar esta API Key")
    
    # Eliminar API Key
    await session.delete(api_key)
    
    # Log de auditoría
    audit = AuditLog(
        user_id=user.id,
        action="api_key_revoked",
        details=f"API Key revocada: {api_key.name}",
        ip_address=request.client.host
    )
    session.add(audit)
    
    await session.commit()
    
    return {"message": "API Key revocada exitosamente"}


# Importar settings para PASSWORD_EXPIRE_DAYS
from core.config import settings