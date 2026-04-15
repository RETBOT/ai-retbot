import uuid
import time as time_module
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import Job, get_session, User
from core.auth import get_current_user, User as AuthUser, decode_token
from core.config import settings
from core.models import get_model_provider, SYSTEM_PROMPT

router = APIRouter(prefix="/agent", tags=["jobs"])

security = HTTPBearer(auto_error=False)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False


class OpenAIResponseChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str = "stop"


class OpenAIResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[OpenAIResponseChoice]


async def get_user_from_credentials(
    credentials: Optional[HTTPAuthorizationCredentials],
    session: AsyncSession
) -> Optional[User]:
    """Obtener usuario desde credentials"""
    if not credentials:
        return None
    
    try:
        payload = decode_token(credentials.credentials)
        user_id = payload.get("sub")
        if user_id:
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()
    except:
        pass
    
    return None


async def get_or_create_default_user(session: AsyncSession) -> User:
    """Obtener o crear usuario default"""
    result = await session.execute(select(User).where(User.username == "default"))
    user = result.scalar_one_or_none()
    
    if not user:
        import hashlib
        # Simple hash para testing - en producción usar bcrypt
        default_password = hashlib.sha256(b"default").hexdigest()
        user = User(
            id=str(uuid.uuid4()),
            username="default",
            password_hash=default_password,
            is_active=True,
            is_admin=False,
            password_changed_at=datetime.utcnow()
        )
        session.add(user)
        await session.commit()
    
    return user


@router.post("/chat/completions", response_model=OpenAIResponse)
async def create_chat(
    data: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Endpoint OpenAI-compatible para chat completions"""
    
    # Obtener usuario
    user = await get_user_from_credentials(credentials, session)
    if not user:
        user = await get_or_create_default_user(session)
    
    # Extraer mensaje del usuario
    user_message = ""
    for msg in data.messages:
        if msg.role == "user":
            user_message = msg.content
            break
    
    if not user_message:
        raise HTTPException(status_code=400, detail="No se encontró mensaje del usuario")
    
    # Modelo a usar
    model_name = data.model or settings.MODEL_NAME
    model_type = settings.MODEL_TYPE
    
    # Crear job en la base de datos
    job = Job(
        id=str(uuid.uuid4()),
        user_id=user.id,
        message=user_message,
        status="queued",
        model=f"{model_type}:{model_name}"
    )
    session.add(job)
    await session.commit()
    
    try:
        job.status = "processing"
        await session.commit()
        
        # Conectar al modelo real (Ollama o OpenCode)
        provider = get_model_provider(model_name, model_type)
        result = provider.chat(user_message, SYSTEM_PROMPT)
        
        job.status = "completed"
        job.result = result
        job.completed_at = datetime.utcnow()
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
    
    await session.commit()
    
    # Responder en formato OpenAI
    return OpenAIResponse(
        id=f"chatcmpl-{job.id[:8]}",
        created=int(time_module.time()),
        model=model_name,
        choices=[OpenAIResponseChoice(
            index=0,
            message=ChatMessage(role="assistant", content=job.result or ""),
            finish_reason="stop"
        )]
    )


# También mantenemos los endpoints originales para compatibilidad
class JobResponse(BaseModel):
    id: str
    user_id: str
    message: str
    status: str
    result: Optional[str] = None
    error: Optional[str] = None
    model: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


class JobCreateResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[str] = None
    error: Optional[str] = None


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Obtener estado de un job"""
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    if job.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="No tienes acceso a este job")
    
    return JobResponse(**job.to_dict())


@router.get("/jobs", response_model=List[JobResponse])
async def list_jobs(
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    limit: int = 50
):
    """Listar mis jobs"""
    result = await session.execute(
        select(Job)
        .where(Job.user_id == user.id)
        .order_by(Job.created_at.desc())
        .limit(limit)
    )
    jobs = result.scalars().all()
    return [JobResponse(**j.to_dict()) for j in jobs]