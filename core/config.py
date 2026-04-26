from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Servidor
    PORT: int = 8000
    
    # Modelo - Llama 3.1 recomendado para function calling
    MODEL_NAME: str = "llama3.1:8b"
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
    RATE_LIMIT_PER_MINUTE: int = 10  # Rate limit global por IP
    RATE_LIMIT_PER_USER: int = 20    # Rate limit por usuario/API key
    RATE_LIMIT_ENABLED: bool = True  # Habilitar/deshabilitar rate limiting
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # CORS - Lista de orígenes permitidos (separados por coma)
    # Por defecto solo permite localhost para desarrollo seguro
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:8000"
    
    @property
    def cors_origins(self) -> List[str]:
        """Parsear orígenes permitidos desde string"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]
    
    def validate_security(self) -> bool:
        """Validar configuraciones de seguridad críticas"""
        issues = []
        
        if self.SECRET_KEY == "CHANGE_ME_TO_A_RANDOM_SECRET_KEY":
            issues.append("SECRET_KEY usa valor por defecto - cambiar en producción")
        
        if not self.ADMIN_PASSWORD:
            issues.append("ADMIN_PASSWORD no configurado")
        
        return len(issues) == 0, issues


settings = Settings()