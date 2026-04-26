import uuid
import time as time_module
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import Job, get_session, User, get_or_create_default_user
from core.auth import get_current_user, User as AuthUser, decode_token, get_user_from_api_key
from core.config import settings
from core.models import get_model_provider, SYSTEM_PROMPT
from core.tools import TOOL_DEFINITIONS, ToolExecutor
from core.rate_limit import limiter
from core.cache import cache
from core.model_manager import model_manager, get_model_for_request, init_model_manager

router = APIRouter(prefix="/agent", tags=["jobs"])

security = HTTPBearer(auto_error=False)


class ChatMessage(BaseModel):
    role: str
    content: str


class ToolDefinition(BaseModel):
    type: str = "function"
    function: dict


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    tools: Optional[List[ToolDefinition]] = None
    tool_choice: Optional[str] = "auto"


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
    except Exception as e:
        # Token inválido o expirado - retornar None y dejar que use otro método
        logger.debug(f"Token inválido o error: {e}")
    
    return None


@router.post("/chat/completions", response_model=OpenAIResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PER_USER}/minute")
async def create_chat(
    data: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Endpoint OpenAI-compatible para chat completions - soporta JWT, API Key y Tools"""
    
    # Obtener usuario (API Key > JWT > Default)
    user = None
    api_key = request.headers.get("X-API-Key")
    if api_key:
        user = await get_user_from_api_key(api_key, session)
    
    if not user:
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
    
    # Determinar modelo a usar
    requested_model = data.model  # Modelo solicitado por el usuario
    model_name = get_model_for_request(requested_model, task_type="code")
    model_type = settings.MODEL_TYPE
    
    # Verificar si se solicitaron tools
    has_tools = data.tools is not None and len(data.tools) > 0
    
    # NO usar cache si hay tools (las herramientas pueden cambiar estado)
    if not has_tools:
        # Intentar obtener del cache
        messages_list = [{"role": msg.role, "content": msg.content} for msg in data.messages]
        cached_response = await cache.get_response(messages_list, model_name)
        
        if cached_response:
            logger.info(f"✅ CACHE HIT para modelo {model_name}")
            
            # Actualizar estadísticas en background
            stats = await cache.get_stats()
            logger.debug(f"Cache stats: {stats['hits']} hits, {stats['misses']} misses, {stats['hit_rate_percent']}% hit rate")
            
            # Retornar respuesta cacheada
            return OpenAIResponse(
                id=f"chatcmpl-cache-{str(uuid.uuid4())[:8]}",
                created=int(time_module.time()),
                model=model_name,
                choices=[OpenAIResponseChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=cached_response.get("content", "")),
                    finish_reason="stop"
                )]
            )
    
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
        
        # Preparar mensajes para el modelo
        messages_for_model = []
        
        # Agregar system prompt
        system_content = SYSTEM_PROMPT
        if has_tools:
            from core.tools.definitions import TOOLS_SYSTEM_PROMPT_EXTENSION
            system_content += TOOLS_SYSTEM_PROMPT_EXTENSION
        
        messages_for_model.append({"role": "system", "content": system_content})
        
        # Agregar mensajes del usuario
        for msg in data.messages:
            messages_for_model.append({"role": msg.role, "content": msg.content})
        
        # Si hay tools, agregar instrucciones específicas
        if has_tools:
            tools_instruction = """
When you need to use a tool, respond with a JSON object in this exact format:
{"tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "tool_name", "arguments": {"arg1": "value1"}}}]}

Available tools:
"""
            for tool in TOOL_DEFINITIONS:
                tools_instruction += f"- {tool['function']['name']}: {tool['function']['description']}\n"
            
            messages_for_model.append({"role": "system", "content": tools_instruction})
        
        # Llamar al modelo
        provider = get_model_provider(model_name, model_type)
        
        # Para Llama 3.1/3.2, usar el chat normal
        # (En el futuro podemos usar el formato nativo de tools de Ollama)
        response_text = provider.chat(
            message=user_message,
            system_prompt=system_content
        )
        
        # Intentar parsear si hay tool calls
        tool_calls = None
        if has_tools:
            tool_calls = parse_tool_calls(response_text)
        
        # Si hay tool calls, ejecutarlas y hacer segunda llamada
        if tool_calls:
            # Ejecutar tools
            working_dir = request.headers.get("X-Working-Directory", ".")
            executor = ToolExecutor(working_dir)
            
            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call.get("function", {}).get("name")
                arguments = tool_call.get("function", {}).get("arguments", {})
                
                if isinstance(arguments, str):
                    import json
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                    except Exception as e:
                        logger.warning(f"Error parseando argumentos de tool: {e}")
                        arguments = {}
                
                result = await executor.execute(tool_name, arguments)
                tool_results.append({
                    "tool_call_id": tool_call.get("id", "unknown"),
                    "role": "tool",
                    "content": result.content if result.success else result.error
                })
            
            # Agregar resultados al contexto y hacer segunda llamada
            messages_for_model.append({"role": "assistant", "content": response_text})
            for result in tool_results:
                messages_for_model.append(result)
            
            # Segunda llamada al modelo
            final_prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages_for_model])
            final_response = provider.chat(
                message="Basándote en los resultados de las tools, proporciona una respuesta final al usuario.",
                system_prompt=final_prompt
            )
            response_text = final_response
        
        job.status = "completed"
        job.result = response_text
        job.completed_at = datetime.now(timezone.utc)
        
        # Guardar en cache (solo si no hay tools)
        if not has_tools and cache._connected:
            try:
                messages_list = [{"role": msg.role, "content": msg.content} for msg in data.messages]
                await cache.set_response(
                    messages_list,
                    model_name,
                    {"content": response_text},
                    ttl=3600  # 1 hora
                )
                logger.info(f"💾 Respuesta guardada en cache para modelo {model_name}")
            except Exception as e:
                logger.warning(f"No se pudo guardar en cache: {e}")
        
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        import traceback
        traceback.print_exc()
    
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


def parse_tool_calls(response_text: str) -> Optional[list]:
    """
    Parsear tool calls desde la respuesta del modelo.
    
    Llama 3.1/3.2 puede responder con JSON que contiene tool_calls.
    Esta función intenta extraerlos.
    """
    import json
    import re
    
    # Intentar encontrar JSON con tool_calls
    # Buscar patrones como {"tool_calls": [...]}
    pattern = r'\{\s*"tool_calls"\s*:\s*\[.*?\]\s*\}'
    match = re.search(pattern, response_text, re.DOTALL)
    
    if match:
        try:
            data = json.loads(match.group())
            return data.get("tool_calls")
        except json.JSONDecodeError:
            pass
    
    # Intentar parsear todo el texto como JSON
    try:
        data = json.loads(response_text)
        if "tool_calls" in data:
            return data["tool_calls"]
    except json.JSONDecodeError:
        pass
    
    return None


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


@router.get("/cache/stats")
async def get_cache_stats():
    """Obtener estadísticas del cache de respuestas"""
    stats = await cache.get_stats()
    return {
        "cache": {
            "enabled": cache._connected,
            "stats": stats
        }
    }


@router.post("/cache/clear")
async def clear_cache():
    """Limpiar todo el cache de respuestas"""
    deleted = await cache.clear_all()
    return {
        "message": f"Cache limpiado exitosamente",
        "keys_deleted": deleted
    }


@router.get("/models/available")
async def list_available_models():
    """Listar modelos disponibles en Ollama"""
    models = await model_manager.get_available_models(force_refresh=False)
    return {
        "models": models,
        "count": len(models),
        "default": settings.MODEL_NAME
    }


@router.get("/models/recommend")
async def recommend_model(task_type: str = "general"):
    """
    Recomendar modelo según tipo de tarea.
    
    Args:
        task_type: Tipo de tarea (general, code, chat, fast)
    """
    available = await model_manager.get_available_models()
    recommended = model_manager.select_best_model(task_type=task_type)
    
    model_info = model_manager.get_model_info(recommended)
    
    return {
        "task_type": task_type,
        "recommended": recommended,
        "info": model_info,
        "available_count": len(available)
    }