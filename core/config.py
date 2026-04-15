from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Servidor
    PORT: int = 8000
    
    # Modelo
    MODEL_NAME: str = "qwen2.5:0.5b"
    MODEL_TYPE: str = "ollama"
    OLLAMA_URL: str = "http://localhost:11434"
    OPENCODE_URL: str = "http://localhost:54321"
    
    # Seguridad
    SECRET_KEY: str = "CHANGE_ME_TO_A_RANDOM_SECRET_KEY"
    PASSWORD_EXPIRE_DAYS: int = 30
    ADMIN_USER: str = "admin"
    ADMIN_PASSWORD: Optional[str] = None
    API_KEY: str = "demo_key_123"
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 10
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"


settings = Settings()