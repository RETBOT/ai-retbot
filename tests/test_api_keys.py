"""
Tests para autenticación con API Keys
"""
import pytest
import hashlib
import uuid
from datetime import datetime
from sqlalchemy import select


@pytest.mark.asyncio
async def test_api_key_model_created(client, db_session, test_user):
    """Test que el modelo APIKey se puede crear"""
    from core.database import APIKey
    
    api_key = "rb_test_key_12345"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    db_key = APIKey(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        name="Test Key",
        key_hash=key_hash,
        permissions="chat",
        is_active=True
    )
    
    db_session.add(db_key)
    await db_session.commit()
    await db_session.refresh(db_key)
    
    assert db_key.id is not None
    assert db_key.user_id == test_user.id
    assert db_key.name == "Test Key"
    assert db_key.is_active is True


@pytest.mark.asyncio
async def test_get_user_from_api_key_function(client, db_session, test_user):
    """Test la función get_user_from_api_key"""
    from core.database import APIKey
    from core.auth import get_user_from_api_key
    
    # Crear API key
    api_key = "rb_test_valid_key_123"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    db_key = APIKey(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        name="Valid Key",
        key_hash=key_hash,
        is_active=True
    )
    db_session.add(db_key)
    await db_session.commit()
    
    # Test función
    user = await get_user_from_api_key(api_key, db_session)
    
    assert user is not None
    assert user.id == test_user.id
    assert user.username == test_user.username


@pytest.mark.asyncio
async def test_get_user_from_invalid_api_key(client, db_session):
    """Test que una API key inválida retorna None"""
    from core.auth import get_user_from_api_key
    
    user = await get_user_from_api_key("rb_invalid_key", db_session)
    
    assert user is None


@pytest.mark.asyncio
async def test_get_user_from_inactive_api_key(client, db_session, test_user):
    """Test que una API key inactiva no funciona"""
    from core.database import APIKey
    from core.auth import get_user_from_api_key
    
    # Crear API key inactiva
    api_key = "rb_inactive_key_123"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    db_key = APIKey(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        name="Inactive Key",
        key_hash=key_hash,
        is_active=False  # Inactiva
    )
    db_session.add(db_key)
    await db_session.commit()
    
    # Test función
    user = await get_user_from_api_key(api_key, db_session)
    
    assert user is None


@pytest.mark.asyncio
async def test_api_key_updates_last_used(client, db_session, test_user):
    """Test que usar una API key actualiza last_used_at"""
    from core.database import APIKey
    from core.auth import get_user_from_api_key
    
    # Crear API key
    api_key = "rb_lastused_key_123"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    db_key = APIKey(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        name="Last Used Key",
        key_hash=key_hash,
        is_active=True,
        last_used_at=None
    )
    db_session.add(db_key)
    await db_session.commit()
    
    # Usar la key
    await get_user_from_api_key(api_key, db_session)
    
    # Refrescar desde DB
    await db_session.refresh(db_key)
    
    assert db_key.last_used_at is not None
    assert isinstance(db_key.last_used_at, datetime)


@pytest.mark.asyncio
async def test_streaming_endpoint_with_api_key(client, db_session, test_user):
    """Test que el endpoint streaming acepta API key"""
    from core.database import APIKey
    
    # Crear API key
    api_key = "rb_streaming_key_123"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    db_key = APIKey(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        name="Streaming Key",
        key_hash=key_hash,
        is_active=True
    )
    db_session.add(db_key)
    await db_session.commit()
    
    # Llamar endpoint con API key (va a fallar por Ollama no disponible, pero auth debe pasar)
    response = await client.post(
        "/v1/chat/completions",
        headers={"X-API-Key": api_key},
        json={
            "messages": [{"role": "user", "content": "test"}],
            "stream": True
        }
    )
    
    # La autenticación debe pasar (200 o error de Ollama, no 401)
    assert response.status_code != 401
    assert response.status_code != 403


@pytest.mark.asyncio
async def test_streaming_endpoint_rejects_invalid_api_key(client):
    """Test que el endpoint streaming rechaza API key inválida"""
    response = await client.post(
        "/v1/chat/completions",
        headers={"X-API-Key": "rb_invalid_key_12345"},
        json={
            "messages": [{"role": "user", "content": "test"}],
            "stream": True
        }
    )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_streaming_endpoint_accepts_bearer_token(client, test_user):
    """Test que el endpoint streaming aún acepta Bearer token"""
    from core.auth import create_access_token
    
    token = create_access_token({
        "sub": str(test_user.id),
        "username": test_user.username
    })
    
    response = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "messages": [{"role": "user", "content": "test"}],
            "stream": True
        }
    )
    
    # La autenticación debe pasar
    assert response.status_code != 401
    assert response.status_code != 403


@pytest.mark.asyncio
async def test_jobs_endpoint_with_api_key(client, db_session, test_user):
    """Test que el endpoint jobs acepta API key"""
    from core.database import APIKey
    
    # Crear API key
    api_key = "rb_jobs_key_123"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    db_key = APIKey(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        name="Jobs Key",
        key_hash=key_hash,
        is_active=True
    )
    db_session.add(db_key)
    await db_session.commit()
    
    # Llamar endpoint con API key
    response = await client.post(
        "/agent/chat/completions",
        headers={"X-API-Key": api_key},
        json={
            "messages": [{"role": "user", "content": "test"}],
            "stream": False
        }
    )
    
    # La autenticación debe pasar (puede fallar por Ollama pero no por auth)
    assert response.status_code != 401
    assert response.status_code != 403


@pytest.mark.asyncio
async def test_api_key_format_validation():
    """Test que el formato de API key es correcto"""
    import secrets
    import re
    
    # Generar key como lo hace el CLI
    random_part = secrets.token_urlsafe(32)
    api_key = f"rb_{random_part}"
    
    # Debe empezar con rb_
    assert api_key.startswith("rb_")
    
    # Debe tener longitud razonable
    assert len(api_key) > 35
    
    # Solo caracteres válidos
    assert re.match(r'^rb_[A-Za-z0-9_-]+$', api_key)
