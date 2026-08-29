"""
Tests básicos de smoke para verificar que la aplicación funciona
"""
import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Test que el endpoint de health responde"""
    response = await client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    # "ok" cuando Ollama está arriba; "degraded" sin Ollama (el endpoint no falla)
    assert data["status"] in ("ok", "degraded")
    assert "model" in data
    assert "ollama" in data
    assert "database" in data


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Test que el endpoint raíz responde"""
    response = await client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "name" in data
    assert "version" in data
    assert data["name"] == "AI Coding Assistant API"


@pytest.mark.asyncio
async def test_list_models_endpoint(client):
    """Test que el endpoint de modelos responde (formato OpenAI compatible)"""
    response = await client.get("/api/v1/models")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["object"] == "list"
    assert "data" in data
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 1  # al menos el modelo default (fallback sin Ollama)


@pytest.mark.asyncio
async def test_auth_login_invalid_credentials(client):
    """Test que login con credenciales inválidas falla"""
    response = await client.post(
        "/auth/login",
        json={"username": "nonexistent", "password": "wrongpass"}
    )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_protected_endpoint_without_token(client):
    """Test que endpoints protegidos rechazan requests sin token"""
    response = await client.get("/auth/me")
    
    # El proyecto usa HTTPBearer(auto_error=False) + manejo manual → 401
    # (ver core/auth.py::get_current_user con credentials=None)
    assert response.status_code == 401
