"""
Logging Estructurado para Producción

Este módulo configura logging estructurado en formato JSON
para facilitar el análisis con herramientas como Splunk, Datadog, ELK, etc.

Características:
- Logs en formato JSON
- Correlation IDs para追踪 requests
- Contexto adicional (usuario, endpoint, etc.)
- Niveles de log configurables
"""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import traceback
import uuid


class JSONFormatter(logging.Formatter):
    """
    Formatter que produce logs en formato JSON.
    
    Ideal para producción donde los logs se envían a:
    - Splunk
    - Datadog
    - Elasticsearch/ELK
    - CloudWatch
    """
    
    def __init__(self, service_name: str = "retbot"):
        """
        Inicializar formatter JSON.
        
        Args:
            service_name: Nombre del servicio para identificar logs
        """
        super().__init__()
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Formatear log record como JSON.
        
        Args:
            record: Log record a formatear
        
        Returns:
            str: Log en formato JSON
        """
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Agregar correlation ID si existe
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id
        
        # Agregar contexto adicional si existe
        if hasattr(record, "extra_context"):
            log_data["context"] = record.extra_context
        
        # Agregar información de usuario si existe
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        
        # Agregar información de request si existe
        if hasattr(record, "endpoint"):
            log_data["endpoint"] = record.endpoint
        
        if hasattr(record, "method"):
            log_data["method"] = record.method
        
        # Agregar información de error si es ERROR o CRITICAL
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Unknown",
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Agregar cualquier atributo custom
        for key, value in record.__dict__.items():
            if key not in [
                "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "name", "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "correlation_id", "extra_context", "user_id", "endpoint", "method"
            ]:
                if isinstance(value, (str, int, float, bool, type(None))):
                    log_data[key] = value
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class ColoredFormatter(logging.Formatter):
    """
    Formatter con colores para desarrollo.
    
    Más legible en terminal durante desarrollo.
    """
    
    # Colores ANSI
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    
    def format(self, record: logging.LogRecord) -> str:
        """Formatear con colores"""
        color = self.COLORS.get(record.levelname, self.RESET)
        
        # Agregar correlation ID si existe
        correlation = ""
        if hasattr(record, "correlation_id"):
            correlation = f"[{record.correlation_id[:8]}] "
        
        formatted = (
            f"{color}[{record.levelname:^8}]{self.RESET} "
            f"{correlation}"
            f"{record.getMessage()}"
        )
        
        # Agregar contexto adicional si existe
        if hasattr(record, "extra_context"):
            context = record.extra_context
            if isinstance(context, dict):
                context_str = " ".join(f"{k}={v}" for k, v in context.items())
                formatted += f" ({context_str})"
        
        return formatted


def setup_logging(
    level: str = "INFO",
    format_type: str = "auto",
    service_name: str = "retbot",
    log_file: Optional[str] = None
):
    """
    Configurar logging para la aplicación.
    
    Args:
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Tipo de formato ("json", "colored", "auto")
        service_name: Nombre del servicio
        log_file: Archivo de log (opcional)
    
    Returns:
        logging.Logger: Logger configurado
    
    Usage:
        logger = setup_logging()
        logger.info("Mensaje de info", extra={"user_id": "123"})
    """
    # Determinar formato
    if format_type == "auto":
        # Usar JSON para producción, colored para desarrollo
        format_type = "json" if sys.stdout.isatty() is False else "colored"
    
    # Crear formatter
    if format_type == "json":
        formatter = JSONFormatter(service_name)
    elif format_type == "colored":
        formatter = ColoredFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)8s] %(message)s"
        )
    
    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Limpiar handlers existentes
    root_logger.handlers.clear()
    
    # Agregar handler para stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Agregar handler para archivo si se especifica
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(JSONFormatter(service_name))
        root_logger.addHandler(file_handler)
    
    return root_logger


# Logger global
logger = logging.getLogger(__name__)


# Contexto para correlation IDs
_correlation_id: Optional[str] = None
_extra_context: Dict[str, Any] = {}


def set_correlation_id(correlation_id: Optional[str] = None):
    """
    Establecer correlation ID para追踪 requests.
    
    Args:
        correlation_id: ID único o None para generar uno nuevo
    """
    global _correlation_id
    _correlation_id = correlation_id or str(uuid.uuid4())


def get_correlation_id() -> Optional[str]:
    """Obtener correlation ID actual"""
    return _correlation_id


def clear_correlation_id():
    """Limpiar correlation ID"""
    global _correlation_id
    _correlation_id = None


def add_extra_context(**kwargs):
    """
    Agregar contexto adicional a los logs.
    
    Args:
        **kwargs: Pares clave-valor para agregar al contexto
    
    Usage:
        add_extra_context(user_id="123", endpoint="/chat")
    """
    global _extra_context
    _extra_context.update(kwargs)


def clear_extra_context():
    """Limpiar contexto adicional"""
    global _extra_context
    _extra_context.clear()


# Decorador para agregar correlation ID automáticamente
def with_correlation_id(func):
    """
    Decorador para agregar correlation ID a una función.
    
    Usage:
        @with_correlation_id
        async def handle_request(request):
            logger.info("Procesando request")
    """
    import functools
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        set_correlation_id()
        try:
            return await func(*args, **kwargs)
        finally:
            clear_correlation_id()
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        set_correlation_id()
        try:
            return func(*args, **kwargs)
        finally:
            clear_correlation_id()
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


# Middleware para FastAPI
class LoggingMiddleware:
    """
    Middleware para logging de requests en FastAPI.
    
    Agrega correlation ID y loguea cada request.
    
    Usage:
        app.add_middleware(LoggingMiddleware)
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        # Generar correlation ID
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id)
        
        # Extraer información del request
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")
        
        # Loggear inicio de request
        logger.info(
            f"Request iniciado: {method} {path}",
            extra={
                "correlation_id": correlation_id,
                "endpoint": path,
                "method": method
            }
        )
        
        try:
            # Procesar request
            return await self.app(scope, receive, send)
        finally:
            # Limpiar correlation ID
            clear_correlation_id()


# Import asyncio para el decorador
import asyncio
