"""
Tests E2E de chat para el servidor RETBOT (requieren Ollama).

Estos tests verifican el pipeline completo: API -> Ollama -> SSE.
Si Ollama no esta disponible, se marcan como SKIP (no fallan), para que la
suite local pase sin Ollama pero el CI (que instala Ollama) los corra.

NOTA sobre tool calling:
El tool calling en RETBOT lo orquesta el CLIENTE (OpenCode via MCP),
no el servidor /chat/completions. Las tools del MCP (file.*, tools.*) se
validan de forma determinista en tests/test_mcp.py y en
scripts/validate_local.py. Aqui se valida el flujo de chat streaming.
"""
import pytest

from core.config import settings

pytestmark = pytest.mark.asyncio


def _ollama_available() -> bool:
    """Checar si Ollama responde en OLLAMA_URL (sin lanzar errores)."""
    import urllib.request

    url = settings.OLLAMA_URL.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001 - cualquier fallo = no disponible
        return False


ollama_up = _ollama_available()


async def _create_user_and_key(db_session, username: str, api_key: str):
    """Crear usuario + API key (texto plano, convencion del proyecto)."""
    import uuid
    from datetime import datetime, timedelta, timezone

    from core.auth import hash_password
    from core.config import settings
    from core.database import APIKey, User

    user = User(
        id=str(uuid.uuid4()),
        username=username,
        password_hash=hash_password("testpass"),
        is_active=True,
        password_changed_at=datetime.now(timezone.utc),
        password_expires_at=datetime.now(timezone.utc) + timedelta(days=settings.PASSWORD_EXPIRE_DAYS),
    )
    db_session.add(user)
    await db_session.commit()

    db_key = APIKey(
        id=str(uuid.uuid4()),
        user_id=user.id,
        name="E2E Key",
        key_hash=api_key,
        is_active=True,
    )
    db_session.add(db_key)
    await db_session.commit()
    return user


@pytest.mark.skipif(not ollama_up, reason="Ollama no disponible - correr con CI o servidor local")
async def test_chat_streaming_returns_200(client, db_session):
    """POST /api/v1/chat/completions con key valida -> 200 y cuerpo SSE."""
    api_key = "rb_e2e_stream_key"
    await _create_user_and_key(db_session, "e2e_stream", api_key)

    response = await client.post(
        "/api/v1/chat/completions",
        headers={"X-API-Key": api_key},
        json={
            "model": settings.MODEL_NAME,
            "messages": [{"role": "user", "content": "Hola, responde en una sola frase."}],
            "stream": True,
        },
    )

    assert response.status_code == 200, f"status {response.status_code}: {response.text[:300]}"
    assert "data:" in response.text, "La respuesta debe ser SSE con chunks data:"
    assert response.headers.get("content-type", "").startswith("text/event-stream")


@pytest.mark.skipif(not ollama_up, reason="Ollama no disponible - correr con CI o servidor local")
async def test_chat_replies_with_content(client, db_session):
    """El modelo responde con contenido real (no solo el chunk de rol)."""
    api_key = "rb_e2e_reply_key"
    await _create_user_and_key(db_session, "e2e_reply", api_key)

    response = await client.post(
        "/api/v1/chat/completions",
        headers={"X-API-Key": api_key},
        json={
            "model": settings.MODEL_NAME,
            "messages": [{"role": "user", "content": "Dime unicamente: todo listo"}],
            "stream": True,
        },
    )

    assert response.status_code == 200

    # Sumar el contenido de todos los chunks de contenido
    content_parts = []
    for line in response.text.splitlines():
        if line.startswith("data: "):
            import json

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


@pytest.mark.skipif(not ollama_up, reason="Ollama no disponible - correr con CI o servidor local")
async def test_chat_rejects_invalid_key(client):
    """Sin auth valida -> 401 (sin tocar Ollama)."""
    response = await client.post(
        "/api/v1/chat/completions",
        headers={"X-API-Key": "rb_key_que_no_existe"},
        json={
            "messages": [{"role": "user", "content": "Hola"}],
            "stream": True,
        },
    )
    assert response.status_code == 401