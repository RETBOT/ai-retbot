import os
import json
import time
import asyncio
import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from typing import AsyncIterator
from ollama_init import init_ollama

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "phi3:mini")
API_KEY = os.getenv("API_KEY", None)
PORT = int(os.getenv("PORT", "8000"))

app = FastAPI()


@app.on_event("startup")
async def startup():
    print("🚀 Iniciando servidor...")
    try:
        init_ollama()
    except Exception as e:
        print(f"⚠️ Advertencia: No se pudo iniciar Ollama: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def check_api_key(request: Request) -> bool:
    if API_KEY is None:
        return True
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        return token == API_KEY
    return False


def extract_json(text: str):
    import re
    try:
        match = re.search(r"\{[\s\S]*?\}", text)
        if match:
            return json.loads(match.group(0))
    except:
        pass
    return None


def ollama_chat(messages: list, stream: bool = False, model: str = None):
    url = f"{OLLAMA_URL}/api/chat"
    payload = {
        "model": model or MODEL_NAME,
        "messages": messages,
        "stream": stream
    }
    response = requests.post(url, json=payload, stream=stream, timeout=120)
    response.raise_for_status()
    return response


async def stream_ollama(response, model: str) -> AsyncIterator[str]:
    chunk_id = 0
    for line in response.iter_lines():
        if line:
            try:
                data = json.loads(line)
                content = data.get("message", {}).get("content", "")
                if content:
                    chunk = {
                        "id": f"chatcmpl-{int(time.time())}-{chunk_id}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": content},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                    chunk_id += 1
            except json.JSONDecodeError:
                pass
    
    yield "data: [DONE]\n\n"


@app.get("/health")
async def health():
    try:
        res = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return {"status": "ok", "ollama": "connected"}
    except:
        return {"status": "ok", "ollama": "disconnected"}


@app.get("/v1/models")
async def list_models():
    try:
        res = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        data = res.json()
        models = data.get("models", [])
        return {
            "object": "list",
            "data": [
                {
                    "id": m["name"],
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "local"
                }
                for m in models
            ]
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": {"message": str(e), "type": "internal_error"}}
        )


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    if not check_api_key(request):
        return JSONResponse(
            status_code=401,
            content={"error": {"message": "Invalid API key", "type": "unauthorized"}}
        )

    try:
        body = await request.json()
    except:
        body = {}

    messages = body.get("messages", [])
    if not messages:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "No messages provided", "type": "invalid_request"}}
        )

    last_message = messages[-1].get("content", "")
    if isinstance(last_message, list):
        last_message = " ".join(
            x.get("text", "") for x in last_message if isinstance(x, dict)
        )

    model = body.get("model", MODEL_NAME)
    stream = body.get("stream", False)

    system_prompt = {
        "role": "system",
        "content": """You are a coding assistant. Use tools when needed.

AVAILABLE TOOLS (all return text):
- read_file(path, offset=0, limit=200): Read file content
- write_file(path, content): Write/create file  
- glob(pattern, path=None): Find files by pattern
- grep(pattern, path=None, include="*"): Search text in files
- bash(command): Run shell command
- list_files(path=None): List directory contents
- question(questions): Ask user for choices

When using tools, respond ONLY with valid JSON:
{"tool": "tool_name", "param": "value"}

Rules:
1. Keep responses SHORT and direct
2. Use code blocks for code examples
3. When tool is needed, respond ONLY with JSON
4. If tool fails, explain error and try different approach
5. After tool result, analyze it and respond or call another tool"""
    }

    ollama_messages = [system_prompt] + messages

    try:
        response = ollama_chat(ollama_messages, stream=True, model=model)

        if stream:
            return StreamingResponse(
                stream_ollama(response, model),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache"}
            )
        else:
            data = response.json()
            content = data.get("message", {}).get("content", "")
            return {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            }

    except requests.exceptions.Timeout:
        return JSONResponse(
            status_code=504,
            content={"error": {"message": "Ollama request timeout", "type": "gateway_timeout"}}
        )
    except requests.exceptions.ConnectionError:
        return JSONResponse(
            status_code=503,
            content={"error": {"message": "Ollama not available. Make sure it's running.", "type": "service_unavailable"}}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": {"message": str(e), "type": "internal_error"}}
        )


@app.get("/")
async def root():
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "ollama": OLLAMA_URL
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
