"""
Tests E2E de chat para el servidor RETBOT (requieren servidor + Ollama).

A diferencia del resto de la suite (in-process con ASGITransport), estos
tests pegan contra el SERVIDOR REAL (http://localhost:8000) para validar el
pipeline completo: HTTP API -> streaming.py -> Ollama -> SSE.

POR QUE server real y no ASGI in-process:
- El endpoint /chat/completions usa un httpx.AsyncClient global (módulo) para
  stream-ear a Ollama. Con pytest-asyncio (un event loop por test) ese client
  global queda atado al loop del primer test y en el segundo explota con
  "Error: Event loop is closed". En producción (uvicorn, un solo loop) no
  ocurre. Corriendo contra el server real se valida el flujo real y se evita
  el acoplamiento con el loop de pytest.

Si el server no responde o Ollama no esta disponible, se marcan SKIP.
El job "integration" del CI arranca ambos y los ejecuta.
"""
import urllib.request

import httpx
import pytest

from core.config import settings

pytestmark = pytest.mark.asyncio

BASE_URL = "http://localhost:8000"
# Key creada por el job integration del CI (ver .github/workflows/ci.yml).
# Vale para rate_limit y para estos tests (limites separados por key).
API_KEY = "demo_key_123"
CHAT_URL = f"{BASE_URL}/api/v1/chat/completions"


def _server_available() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=5) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


def _ollama_available() -> bool:
    url = settings.OLLAMA_URL.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


live_env = _server_available() and _ollama_available()


@pytest.mark.skipif(not live_env, reason="Server u Ollama no disponibles (corren en CI)")
async def test_chat_streaming_returns_200():
    """POST /api/v1/chat/completions con key valida -> 200 y cuerpo SSE."""
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            CHAT_URL,
            headers={"X-API-Key": API_KEY},
            json={
                "model": settings.MODEL_NAME,
                "messages": [{"role": "user", "content": "Hola, responde en una sola frase."}],
                "stream": True,
            },
        )

    assert response.status_code == 200, f"status {response.status_code}: {response.text[:300]}"
    assert "data:" in response.text, "La respuesta debe ser SSE con chunks data:"
    assert response.headers.get("content-type", "").startswith("text/event-stream")


@pytest.mark.skipif(not live_env, reason="Server u Ollama no disponibles (corren en CI)")
async def test_chat_replies_with_content():
    """El modelo responde con contenido real (no solo el chunk de rol)."""
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            CHAT_URL,
            headers={"X-API-Key": API_KEY},
            json={
                "model": settings.MODEL_NAME,
                "messages": [{"role": "user", "content": "Dime unicamente: todo listo"}],
                "stream": True,
            },
        )

    assert response.status_code == 200, f"status {response.status_code}: {response.text[:300]}"

    # Sumar el contenido de todos los chunks de contenido
    import json

    content_parts = []
    for line in response.text.splitlines():
        if line.startswith("data: "):
            try:
                chunk = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            delta = chunk.get("choices", [{}])[0].get("delta", {})
            if delta.get("content"):
                content_parts.append(delta["content"])

    full = "".join(content_parts)
    assert full.strip(), "El modelo no genero contenido (respuesta vacia)"
    assert "todo listo" in full.lower(), f"Respuesta inesperada: {full[:200]}"


@pytest.mark.skipif(not _server_available(), reason="Server no disponible")
async def test_chat_rejects_invalid_key():
    """Sin auth valida -> 401 (sin tocar Ollama)."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            CHAT_URL,
            headers={"X-API-Key": "rb_key_que_no_existe"},
            json={
                "messages": [{"role": "user", "content": "Hola"}],
                "stream": True,
            },
        )
    assert response.status_code == 401