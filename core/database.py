import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, Enum, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from core.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    password_changed_at = Column(DateTime, default=datetime.utcnow)
    password_expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=settings.PASSWORD_EXPIRE_DAYS))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "is_admin": self.is_admin,
            "is_active": self.is_active,
            "password_changed_at": self.password_changed_at.isoformat() if self.password_changed_at else None,
            "password_expires_at": self.password_expires_at.isoformat() if self.password_expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    message = Column(Text, nullable=False)
    status = Column(String, default="queued")
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    model = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "message": self.message,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "model": self.model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "details": self.details,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class APIKey(Base):
    """API Keys persistentes para integración con OpenCode y otros clientes"""
    __tablename__ = "api_keys"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)  # Descripción: "OpenCode Desktop", "CLI", etc.
    key_hash = Column(String, nullable=False, index=True)  # SHA256 hash de la key
    permissions = Column(String, default="chat")  # "chat", "chat,admin", etc.
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "permissions": self.permissions,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }


DATABASE_URL = "sqlite+aiosqlite:///./data.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    import os
    os.makedirs(".", exist_ok=True)
    async with engine.begin() as conn:
        # NOTA: Nunca usar drop_all en producción - borra todos los datos
        # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Base de datos inicializada")


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


async def create_admin_user(username: str, password_hash: str) -> User:
    async with async_session() as session:
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            password_hash=password_hash,
            is_admin=True,
            is_active=True,
            password_changed_at=datetime.utcnow(),
            password_expires_at=datetime.utcnow() + timedelta(days=settings.PASSWORD_EXPIRE_DAYS)
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user