"""
Tests para el hash seguro de API keys (HMAC-SHA256 + upgrade-on-access)

Feature: las API keys dejaron de guardarse en texto plano. Ahora:
- key_hash = "hmac:" + HMAC-SHA256(key, SECRET_KEY)  (hex digest, 69 chars)
- Las keys legacy (almacenadas en claro pre-migracion) siguen autenticando
  y se re-almacenan con hash en el primer uso (upgrade-on-access)
"""
import hashlib
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from core.auth import (
    hash_api_key,
    verify_api_key,
    key_storage_format,
    mask_api_key_hash,
    get_user_from_api_key,
)
from core.config import settings


@pytest.mark.asyncio
async def test_hash_api_key_formato_y_idempotente():
    """El hash tiene prefijo hmac:, mide 69 chars y es determinista"""
    h1 = hash_api_key("key_x_abc")
    h2 = hash_api_key("key_x_abc")
    assert h1.startswith("hmac:")
    assert len(h1) == 5 + 64  # "hmac:" + 64 hex
    assert h1 == h2


@pytest.mark.asyncio
async def test_hash_api_key_depende_de_secret_key(monkeypatch):
    """Con otra SECRET_KEY el hash cambia (no se puede forjar sin la secret)"""
    h1 = hash_api_key("key_x_abc")
    monkeypatch.setattr(settings, "SECRET_KEY", "otra_secret_key_distinta")
    h2 = hash_api_key("key_x_abc")
    assert h1 != h2


@pytest.mark.asyncio
async def test_verify_api_key_hmac_true():
    key = "rb_hmac_valida_123"
    assert verify_api_key(key, hash_api_key(key)) is True


@pytest.mark.asyncio
async def test_verify_api_key_hmac_false():
    assert verify_api_key("rb_key_incorrecta", hash_api_key("rb_key_real")) is False


@pytest.mark.asyncio
async def test_verify_api_key_legacy_true():
    """Key legacy (en claro) se verifica por igualdad"""
    assert verify_api_key("demo_key_123", "demo_key_123") is True


@pytest.mark.asyncio
async def test_verify_api_key_legacy_false():
    assert verify_api_key("demo_key_123", "demo_key_124") is False


@pytest.mark.asyncio
async def test_verify_api_key_legacy_rechaza_sha256_sin_salt():
    """Documenta el bug del CLI viejo: sha256-sin-sal nunca debe autenticar"""
    stored = hashlib.sha256(b"rb_antigua").hexdigest()
    assert verify_api_key("rb_antigua", stored) is False


@pytest.mark.asyncio
async def test_key_storage_format():
    assert key_storage_format("hmac:abc123") == "hmac"
    assert key_storage_format("demo_key_123") == "legacy"
    assert key_storage_format("key_abc") == "legacy"


@pytest.mark.asyncio
async def test_mask_api_key_hash():
    stored = "hmac:" + "ab12cd34ef56" + "7890abcdef"
    masked = mask_api_key_hash(stored)
    assert masked == stored[:12] + "..."
    assert stored not in masked
    assert mask_api_key_hash("") == "-"


@pytest.mark.asyncio
async def _seed_api_key(db_session, test_user, key_hash, is_active=True):
    """Helper: sembrar una APIKey en la DB de test"""
    from core.database import APIKey
    db_key = APIKey(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        name="Key de test",
        key_hash=key_hash,
        is_active=is_active,
        last_used_at=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(db_key)
    await db_session.commit()
    return db_key


@pytest.mark.asyncio
async def test_get_user_from_api_key_camino_hmac(db_session, test_user):
    """Key hmac autentica y NO se reescribe (idempotente)"""
    from core.database import APIKey
    api_key = "rb_hmac_456"
    db_key = await _seed_api_key(db_session, test_user, hash_api_key(api_key))

    user = await get_user_from_api_key(api_key, db_session)
    assert user is not None
    assert user.id == test_user.id

    # Sigue igual en DB (no se reescribe)
    result = await db_session.execute(select(APIKey).where(APIKey.id == db_key.id))
    stored = result.scalar_one().key_hash
    assert stored == hash_api_key(api_key)


@pytest.mark.asyncio
async def test_get_user_from_api_key_upgrade_legacy(db_session, test_user):
    """Key legacy autentica y queda migrada a hmac tras el primer uso"""
    from core.database import APIKey
    api_key = "rb_legacy_123"
    db_key = await _seed_api_key(db_session, test_user, api_key)  # en claro

    user = await get_user_from_api_key(api_key, db_session)
    assert user is not None
    assert user.id == test_user.id

    # Upgrade-on-access: ya quedo hasheada
    result = await db_session.execute(select(APIKey).where(APIKey.id == db_key.id))
    stored = result.scalar_one().key_hash
    assert stored.startswith("hmac:")
    assert stored == hash_api_key(api_key)


@pytest.mark.asyncio
async def test_get_user_from_api_key_legacy_sin_match(db_session, test_user):
    """Key legacy incorrecta -> None y el registro no se toca"""
    from core.database import APIKey
    api_key = "rb_legacy_sinmatch"
    db_key = await _seed_api_key(db_session, test_user, api_key)

    user = await get_user_from_api_key("rb_otra_key", db_session)
    assert user is None

    result = await db_session.execute(select(APIKey).where(APIKey.id == db_key.id))
    stored = result.scalar_one().key_hash
    assert stored == api_key  # sigue en claro, sin upgrade


@pytest.mark.asyncio
async def test_get_user_from_api_key_inactiva_hmac(db_session, test_user):
    api_key = "rb_inactiva_hmac"
    await _seed_api_key(db_session, test_user, hash_api_key(api_key), is_active=False)
    user = await get_user_from_api_key(api_key, db_session)
    assert user is None


@pytest.mark.asyncio
async def test_get_user_from_api_key_inactiva_legacy_sin_upgrade(db_session, test_user):
    """Key legacy inactiva -> None Y no hace upgrade"""
    from core.database import APIKey
    api_key = "rb_inactiva_legacy"
    db_key = await _seed_api_key(db_session, test_user, api_key, is_active=False)

    user = await get_user_from_api_key(api_key, db_session)
    assert user is None

    result = await db_session.execute(select(APIKey).where(APIKey.id == db_key.id))
    stored = result.scalar_one().key_hash
    assert stored == api_key  # sin prefijo hmac


@pytest.mark.asyncio
async def test_authorization_bearer_con_api_key(client, db_session, test_user):
    """OpenCode manda la API key como Bearer token: debe autenticar (no 401)"""
    from core.database import APIKey
    api_key = "rb_bearer_key_789"
    await _seed_api_key(db_session, test_user, hash_api_key(api_key))

    response = await client.post(
        "/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "messages": [{"role": "user", "content": "test"}],
            "stream": True,
        },
    )
    # Auth pasa (puede fallar por Ollama, nunca por auth)
    assert response.status_code != 401
    assert response.status_code != 403