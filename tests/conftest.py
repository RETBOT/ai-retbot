"""
Fixtures y configuración para tests de RETBOT
"""
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from core.database import Base, get_session
from server import app


# Configurar pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


# Base de datos en memoria para tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Crear event loop para tests async"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Crear engine de base de datos para tests"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Crear tablas
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    """Crear sesión de base de datos para cada test"""
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session
        # Rollback después de cada test para aislamiento
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    """Crear cliente HTTP async para tests"""
    
    # Override de la dependencia get_session
    async def override_get_session():
        yield db_session
    
    app.dependency_overrides[get_session] = override_get_session
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    # Limpiar overrides
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session):
    """Crear un usuario de prueba"""
    from core.database import User
    from core.auth import hash_password
    from datetime import datetime, timedelta
    from core.config import settings
    import uuid
    
    user = User(
        id=str(uuid.uuid4()),
        username="testuser",
        password_hash=hash_password("testpass123"),
        is_admin=False,
        is_active=True,
        password_changed_at=datetime.utcnow(),
        password_expires_at=datetime.utcnow() + timedelta(days=settings.PASSWORD_EXPIRE_DAYS)
    )
    
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    return user


@pytest_asyncio.fixture
async def test_admin(db_session):
    """Crear un usuario admin de prueba"""
    from core.database import User
    from core.auth import hash_password
    from datetime import datetime, timedelta
    from core.config import settings
    import uuid
    
    user = User(
        id=str(uuid.uuid4()),
        username="testadmin",
        password_hash=hash_password("adminpass123"),
        is_admin=True,
        is_active=True,
        password_changed_at=datetime.utcnow(),
        password_expires_at=datetime.utcnow() + timedelta(days=settings.PASSWORD_EXPIRE_DAYS)
    )
    
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    return user


@pytest.fixture
def auth_headers(test_user):
    """Generar headers de autenticación para un usuario"""
    from core.auth import create_access_token
    
    token = create_access_token({
        "sub": str(test_user.id),
        "username": test_user.username
    })
    
    return {"Authorization": f"Bearer {token}"}
