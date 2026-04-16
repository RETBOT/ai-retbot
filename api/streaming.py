"""
Router de streaming para OpenCode
Usa httpx directo para streaming SSE como el ejemplo ai-ejemplo
"""
import uuid
import json
import httpx
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.config import settings
from core.database import get_session, User
from core.auth import get_current_user_or_api_key

router = APIRouter(prefix="/v1")

# Cliente global para streaming
stream_client = httpx.AsyncClient(timeout=None)


# Modelos Pydantic
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False


async def get_or_create_default_user(session: AsyncSession) -> User:
    """Obtener o crear usuario default"""
    result = await session.execute(select(User).where(User.username == "default"))
    user = result.scalar_one_or_none()
    
    if not user:
        import hashlib
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


@router.get("/models")
async def list_models():
    """Lista de modelos disponibles desde Ollama - compatible con OpenCode"""
    from core.models import OllamaProvider
    
    try:
        ollama = OllamaProvider()
        models = ollama.list_models()
        
        if models:
            return {
                "object": "list",
                "data": [
                    {
                        "id": model.get("name", "unknown"),
                        "object": "model",
                        "owned_by": "retbot",
                        "created": model.get("modified_at", ""),
                        "context_length": model.get("details", {}).get("context_length", 8192)
                    }
                    for model in models
                ]
            }
    except Exception as e:
        # Si falla, retornar modelo default
        pass
    
    # Fallback: retornar modelo configurado
    return {
        "object": "list",
        "data": [
            {
                "id": settings.MODEL_NAME,
                "object": "model",
                "owned_by": "retbot",
                "context_length": 8192
            }
        ]
    }


@router.get("/models/{model_id}")
async def get_model(model_id: str):
    """Info de un modelo específico"""
    return {
        "id": model_id,
        "object": "model",
        "owned_by": "retbot",
        "permission": []
    }


@router.post("/chat/completions")
async def chat_completions_streaming(
    request: Request,
    db_user: User = Depends(get_current_user_or_api_key),
    session: AsyncSession = Depends(get_session)
):
    """Streaming endpoint - acepta JWT Bearer token o X-API-Key"""
    
    # Usuario ya autenticado por la dependencia
    
    body = await request.json()
    messages = body.get("messages", [])
    model = body.get("model", settings.MODEL_NAME)
    stream = body.get("stream", True)
    
    # Encontrar último mensaje del usuario
    user_message = ""
    for msg in messages:
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break
    
    if not user_message:
        raise HTTPException(status_code=400, detail="No user message found")
    
    # URL de Ollama
    ollama_url = f"{settings.OLLAMA_URL}/api/chat"
    
    # Agregar system prompt al inicio si no está
    from core.models import SYSTEM_PROMPT
    full_messages = []
    if not any(m.get("role") == "system" for m in messages):
        full_messages.append({"role": "system", "content": SYSTEM_PROMPT})
    
    for msg in messages:
        full_messages.append({"role": msg.get("role"), "content": msg.get("content")})
    
    async def generate():
        model_id = model
        ollama_url = f"{settings.OLLAMA_URL}/api/chat"
        
        try:
            async with stream_client.stream(
                "POST",
                ollama_url,
                json={
                    "model": model_id,
                    "messages": full_messages,
                    "stream": True,
                    "options": {
                        "keep_alive": 300
                    }
                }
            ) as response:
                
                # Primer chunk (rol)
                yield f"data: {json.dumps({'id': 'chatcmpl-123', 'object': 'chat.completion.chunk', 'choices': [{'delta': {'role': 'assistant'}, 'index': 0, 'finish_reason': None}]})}\n\n"

                buffer = ""

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                    except:
                        continue

                    content = data.get("message", {}).get("content", "")

                    if content:
                        buffer += content

                        # Agrupa tokens (más fluido)
                        if len(buffer) > 20:
                            yield f"data: {json.dumps({'id': 'chatcmpl-123', 'object': 'chat.completion.chunk', 'choices': [{'delta': {'content': buffer}, 'index': 0, 'finish_reason': None}]})}\n\n"
                            buffer = ""

                # Flush final
                if buffer:
                    yield f"data: {json.dumps({'id': 'chatcmpl-123', 'object': 'chat.completion.chunk', 'choices': [{'delta': {'content': buffer}, 'index': 0, 'finish_reason': None}]})}\n\n"

                # Cierre
                yield f"data: {json.dumps({'id': 'chatcmpl-123', 'object': 'chat.completion.chunk', 'choices': [{'delta': {}, 'index': 0, 'finish_reason': 'stop'}]})}\n\n"

                yield "data: [DONE]\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'id': 'chatcmpl-123', 'object': 'chat.completion.chunk', 'choices': [{'delta': {'content': f'Error: {str(e)}'}, 'index': 0, 'finish_reason': 'stop'}]})}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")