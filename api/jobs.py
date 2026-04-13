import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import Job, get_session
from core.auth import get_current_user, User as AuthUser

router = APIRouter(prefix="/v1", tags=["jobs"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: Optional[str] = None
    messages: Optional[List[ChatMessage]] = None
    model: Optional[str] = None
    model_type: Optional[str] = None
    system_prompt: Optional[str] = None


class OpenAIChatRequest(BaseModel):
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


@router.post("/chat/completions", response_model=JobCreateResponse)
async def create_chat(
    data: ChatRequest,
    request: Request,
    user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Crear un job de chat"""
    # Crear job
    model_type = data.model_type or settings.MODEL_TYPE
    job = Job(
        id=str(uuid.uuid4()),
        user_id=user.id,
        message=data.message,
        status="queued",
        model=f"{model_type}:{data.model or settings.MODEL_NAME}"
    )
    session.add(job)
    await session.commit()
    
    # Procesar con el proveedor adecuado
    from core.models import get_model_provider, SYSTEM_PROMPT
    
    # Extraer mensaje (soporta message string o messages array)
    user_message = data.message
    if not user_message and data.messages:
        for msg in reversed(data.messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break
    
    if not user_message:
        user_message = ""
    
    try:
        job.status = "processing"
        await session.commit()
        
        provider = get_model_provider(data.model, model_type)
        result = provider.chat(user_message, data.system_prompt or SYSTEM_PROMPT)
        
        job.status = "completed"
        job.result = result
        job.completed_at = datetime.utcnow()
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        import logging
        logging.error(f"Job error: {e}")
    
    await session.commit()
    
    return JobCreateResponse(
        job_id=job.id, 
        status=job.status,
        result=job.result,
        error=job.error
    )


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
    
    # Verificar que el job pertenece al usuario
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


@router.post("/chat", response_model=OpenAIResponse)
async def create_chat_openai(
    data: OpenAIRequest,
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    """Endpoint compatible con OpenAI API"""
    import time
    from core.auth import get_current_user, User as AuthUser
    
    # Intentar obtener usuario tokenizado, si no usar default
    user = None
    try:
        user = await get_current_user(request, session)
    except:
        pass
    
    if not user:
        from core.database import User
        result = await session.execute(select(User).where(User.username == "default"))
        user = result.scalar_one_or_none()
        if not user:
            from passlib.hash import argon2
            user = User(
                id=str(uuid.uuid4()),
                username="default",
                password_hash=argon2.hash("default"),
                is_active=True,
                is_admin=False,
                password_changed_at=datetime.utcnow()
            )
            session.add(user)
            await session.commit()
    
    model_type = settings.MODEL_TYPE
    model_name = data.model or settings.MODEL_NAME
        if not user:
            from passlib.hash import argon2
            user = User(
                id=str(uuid.uuid4()),
                username="default",
                password_hash=argon2.hash("default"),
                is_active=True,
                is_admin=False,
                password_changed_at=datetime.utcnow()
            )
            session.add(user)
            await session.commit()
    
    model_type = settings.MODEL_TYPE
    model_name = data.model or settings.MODEL_NAME
    
    user_message = ""
    for msg in data.messages:
        if msg.role == "user":
            user_message = msg.content
            break
    
    if not user_message:
        raise HTTPException(status_code=400, detail="No se encontró mensaje del usuario")
    
    job = Job(
        id=str(uuid.uuid4()),
        user_id=user.id,
        message=user_message,
        status="queued",
        model=f"{model_type}:{model_name}"
    )
    session.add(job)
    await session.commit()
    
    from core.models import get_model_provider, SYSTEM_PROMPT
    
    try:
        job.status = "processing"
        await session.commit()
        
        provider = get_model_provider(model_name, model_type)
        result = provider.chat(user_message, SYSTEM_PROMPT)
        
        job.status = "completed"
        job.result = result
        job.completed_at = datetime.utcnow()
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
    
    await session.commit()
    
    return OpenAIResponse(
        id=f"chatcmpl-{job.id[:8]}",
        created=int(time.time()),
        model=model_name,
        choices=[OpenAIResponseChoice(
            index=0,
            message=ChatMessage(role="assistant", content=job.result or ""),
            finish_reason="stop"
        )]
    )


# Importar settings para MODEL_NAME
from core.config import settings