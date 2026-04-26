"""
Tests de integración end-to-end para RETBOT

Estos tests verifican que todos los componentes funcionen juntos.
"""
import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    """Test básico de health endpoint"""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "model" in data


@pytest.mark.asyncio
async def test_list_models_endpoint(client):
    """Test que /v1/models responde correctamente"""
    response = await client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_chat_endpoint_without_auth(client):
    """Test que el chat endpoint crea usuario default sin auth"""
    response = await client.post(
        "/agent/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False
        }
    )
    
    # Debe aceptar la request (aunque falle por Ollama)
    assert response.status_code != 401
    assert response.status_code != 403


@pytest.mark.asyncio
async def test_tools_are_available():
    """Test que todas las tools están definidas"""
    from core.tools import TOOL_DEFINITIONS, TOOLS
    
    expected_tools = [
        "read_file",
        "write_file", 
        "edit_file",
        "list_directory",
        "execute_command"
    ]
    
    for tool in expected_tools:
        assert tool in TOOLS, f"Tool {tool} no encontrada"
    
    assert len(TOOL_DEFINITIONS) == len(expected_tools)


@pytest.mark.asyncio
async def test_system_prompt_updated():
    """Test que el system prompt es el nuevo optimizado"""
    from core.models import SYSTEM_PROMPT
    
    # El nuevo prompt debe mencionar OpenCode
    assert "OpenCode" in SYSTEM_PROMPT or "RETBOT" in SYSTEM_PROMPT
    
    # Debe ser más largo que el anterior
    assert len(SYSTEM_PROMPT) > 500


@pytest.mark.asyncio
async def test_default_model_is_llama31():
    """Test que el modelo default es llama3.1"""
    from core.config import settings
    
    assert "llama" in settings.MODEL_NAME.lower()


@pytest.mark.asyncio  
async def test_api_key_model_exists():
    """Test que el modelo APIKey existe en la base de datos"""
    from core.database import APIKey
    
    # Verificar que la clase existe y tiene los campos esperados
    assert hasattr(APIKey, 'id')
    assert hasattr(APIKey, 'user_id')
    assert hasattr(APIKey, 'key_hash')
    assert hasattr(APIKey, 'name')
    assert hasattr(APIKey, 'is_active')


@pytest.mark.asyncio
async def test_tool_executor_security():
    """Test que ToolExecutor tiene protecciones de seguridad"""
    from core.tools.executor import ToolExecutor
    
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = ToolExecutor(tmpdir)
        
        # Debe tener límites configurados
        assert executor.MAX_FILE_SIZE > 0
        assert executor.MAX_OUTPUT_SIZE > 0
        assert executor.MAX_TIMEOUT > 0
        
        # Debe tener whitelist de comandos
        assert len(executor.ALLOWED_COMMANDS) > 0
        assert 'ls' in executor.ALLOWED_COMMANDS or 'dir' in executor.ALLOWED_COMMANDS


@pytest.mark.asyncio
async def test_endpoints_require_auth_or_create_default(client):
    """Test que endpoints protegidos manejan auth correctamente"""
    
    # Sin auth, algunos endpoints deben funcionar con default user
    response = await client.get("/")
    assert response.status_code == 200
    
    # El streaming endpoint debe requerir auth
    response = await client.post("/v1/chat/completions", json={})
    # Puede ser 401, 403, o 422 (validation error)
    assert response.status_code in [401, 403, 422]


@pytest.mark.asyncio
async def test_cli_commands_exist():
    """Test que los comandos CLI de API keys existen"""
    import cli.main as cli_module
    
    # Verificar que las funciones existen
    assert hasattr(cli_module, 'create_api_key')
    assert hasattr(cli_module, 'list_api_keys')


@pytest.mark.asyncio
async def test_full_api_key_workflow(client, db_session):
    """Test del flujo completo de API key"""
    import hashlib
    from core.database import APIKey, User
    from core.auth import hash_password
    from datetime import datetime, timedelta, timezone
    from core.config import settings
    import uuid
    
    # Crear usuario de prueba
    user = User(
        id=str(uuid.uuid4()),
        username="testworkflow",
        password_hash=hash_password("testpass"),
        is_active=True,
        password_changed_at=datetime.now(timezone.utc),
        password_expires_at=datetime.now(timezone.utc) + timedelta(days=settings.PASSWORD_EXPIRE_DAYS)
    )
    db_session.add(user)
    await db_session.commit()
    
    # Crear API key
    api_key = "rb_test_workflow_key"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    db_key = APIKey(
        id=str(uuid.uuid4()),
        user_id=user.id,
        name="Test Workflow",
        key_hash=key_hash,
        is_active=True
    )
    db_session.add(db_key)
    await db_session.commit()
    
    # Usar API key en endpoint
    response = await client.post(
        "/agent/chat/completions",
        headers={"X-API-Key": api_key},
        json={
            "messages": [{"role": "user", "content": "Test"}],
            "stream": False
        }
    )
    
    # No debe dar error de autenticación
    assert response.status_code not in [401, 403]
