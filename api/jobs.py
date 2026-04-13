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


class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    model_type: Optional[str] = None  # "ollama" o "opencode"
    system_prompt: Optional[str] = None


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
    
    try:
        job.status = "processing"
        await session.commit()
        
        provider = get_model_provider(data.model, model_type)
        result = provider.chat(data.message, data.system_prompt or SYSTEM_PROMPT)
        
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


# Importar settings para MODEL_NAME
from core.config import settings