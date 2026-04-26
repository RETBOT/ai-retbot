"""
Health Checks Avanzados

Módulo para verificar el estado de todos los servicios del sistema.
"""
import asyncio
import psutil
import platform
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import text, select, func
import logging

logger = logging.getLogger(__name__)


# Variables para uptime
START_TIME = datetime.now(timezone.utc)


async def check_ollama() -> Dict[str, Any]:
    """
    Verificar conexión con Ollama.
    
    Returns:
        dict: Estado de Ollama
    """
    from core.models import OllamaProvider
    from core.config import settings
    
    result = {
        "status": "unknown",
        "url": settings.OLLAMA_URL,
        "models_count": 0,
        "error": None
    }
    
    try:
        ollama = OllamaProvider()
        models = ollama.list_models()
        
        if models:
            result["status"] = "connected"
            result["models_count"] = len(models)
            result["models"] = [m.get("name", "unknown") for m in models[:5]]  # Primeros 5 modelos
        else:
            result["status"] = "no_models"
            result["warning"] = "Ollama conectado pero sin modelos. Ejecutar: ollama pull <modelo>"
            
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        logger.error(f"Error verificando Ollama: {e}")
    
    return result


async def check_database() -> Dict[str, Any]:
    """
    Verificar conexión y estado de la base de datos.
    
    Returns:
        dict: Estado de la base de datos
    """
    from core.database import async_session, User, Job
    
    result = {
        "status": "unknown",
        "type": "sqlite",
        "users_count": 0,
        "jobs_count": 0,
        "error": None
    }
    
    try:
        async with async_session() as session:
            # Verificar conexión con query simple
            await session.execute(text("SELECT 1"))
            
            # Contar usuarios
            user_count = await session.execute(select(func.count()).select_from(User))
            result["users_count"] = user_count.scalar()
            
            # Contar jobs
            job_count = await session.execute(select(func.count()).select_from(Job))
            result["jobs_count"] = job_count.scalar()
            
            result["status"] = "connected"
            
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        logger.error(f"Error verificando base de datos: {e}")
    
    return result


async def check_redis() -> Dict[str, Any]:
    """
    Verificar conexión con Redis (si está configurado).
    
    Returns:
        dict: Estado de Redis
    """
    from core.config import settings
    
    result = {
        "status": "not_configured",
        "url": None,
        "error": None
    }
    
    if not settings.REDIS_URL or settings.REDIS_URL == "redis://localhost:6379":
        return result
    
    result["url"] = settings.REDIS_URL
    
    try:
        import redis.asyncio as redis
        
        client = redis.from_url(settings.REDIS_URL)
        await client.ping()
        await client.close()
        
        result["status"] = "connected"
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        logger.error(f"Error verificando Redis: {e}")
    
    return result


async def check_gpu() -> Dict[str, Any]:
    """
    Verificar estado de GPU (si está disponible).
    
    Returns:
        dict: Estado de la GPU
    """
    result = {
        "available": False,
        "count": 0,
        "gpus": [],
        "error": None
    }
    
    try:
        # Intentar importar pynvml para NVIDIA
        import pynvml
        
        try:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            
            result["available"] = True
            result["count"] = device_count
            
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                
                result["gpus"].append({
                    "index": i,
                    "name": name,
                    "memory_total_gb": round(memory_info.total / (1024**3), 2),
                    "memory_used_gb": round(memory_info.used / (1024**3), 2),
                    "memory_free_gb": round(memory_info.free / (1024**3), 2),
                    "utilization_gpu_percent": utilization.gpu,
                    "utilization_memory_percent": utilization.memory
                })
            
            pynvml.nvmlShutdown()
            
        except pynvml.NVMLError as e:
            result["error"] = f"NVML Error: {str(e)}"
            
    except ImportError:
        result["error"] = "pynvml no instalado. Instalar: pip install nvidia-ml-py3"
    except Exception as e:
        result["error"] = str(e)
    
    return result


def get_system_info() -> Dict[str, Any]:
    """
    Obtener información del sistema.
    
    Returns:
        dict: Información del sistema
    """
    try:
        # Memoria
        memory = psutil.virtual_memory()
        
        # Disco
        disk = psutil.disk_usage('/')
        
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        return {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": cpu_percent,
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "memory_used_gb": round(memory.used / (1024**3), 2),
            "memory_percent": memory.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_percent": disk.percent
        }
    except Exception as e:
        logger.error(f"Error obteniendo información del sistema: {e}")
        return {"error": str(e)}


def get_uptime() -> Dict[str, Any]:
    """
    Obtener uptime del servidor.
    
    Returns:
        dict: Uptime en diferentes formatos
    """
    now = datetime.now(timezone.utc)
    uptime_delta = now - START_TIME
    
    total_seconds = int(uptime_delta.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    return {
        "seconds": total_seconds,
        "formatted": f"{days}d {hours}h {minutes}m {seconds}s",
        "start_time": START_TIME.isoformat(),
        "days": days,
        "hours": hours,
        "minutes": minutes
    }


async def health_check_full() -> Dict[str, Any]:
    """
    Health check completo de todos los servicios.
    
    Returns:
        dict: Estado completo del sistema
    """
    from core.config import settings
    
    # Ejecutar checks en paralelo
    ollama_result, db_result, redis_result, gpu_result = await asyncio.gather(
        check_ollama(),
        check_database(),
        check_redis(),
        check_gpu(),
        return_exceptions=True
    )
    
    # Manejar excepciones
    for i, result in enumerate([ollama_result, db_result, redis_result, gpu_result]):
        if isinstance(result, Exception):
            logger.error(f"Error en health check: {result}")
    
    # Determinar estado general
    critical_services = [ollama_result, db_result]
    all_healthy = all(
        r.get("status") in ["connected", "ok", "not_configured"]
        for r in critical_services
        if isinstance(r, dict)
    )
    
    status = "healthy" if all_healthy else "degraded"
    
    # Construir respuesta
    response = {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "uptime": get_uptime(),
        "system": get_system_info(),
        "services": {
            "ollama": ollama_result if isinstance(ollama_result, dict) else {"status": "error"},
            "database": db_result if isinstance(db_result, dict) else {"status": "error"},
            "redis": redis_result if isinstance(redis_result, dict) else {"status": "not_configured"},
            "gpu": gpu_result if isinstance(gpu_result, dict) else {"status": "unknown"}
        },
        "model": {
            "name": settings.MODEL_NAME,
            "type": settings.MODEL_TYPE,
            "context_length": settings.OLLAMA_CONTEXT_LENGTH if hasattr(settings, 'OLLAMA_CONTEXT_LENGTH') else 4096
        },
        "rate_limiting": {
            "enabled": settings.RATE_LIMIT_ENABLED,
            "per_user": settings.RATE_LIMIT_PER_USER,
            "per_minute": settings.RATE_LIMIT_PER_MINUTE
        }
    }
    
    return response


async def health_check_simple() -> Dict[str, Any]:
    """
    Health check rápido (solo servicios críticos).
    
    Returns:
        dict: Estado simplificado
    """
    from core.config import settings
    
    ollama_result = await check_ollama()
    db_result = await check_database()
    
    status = "ok" if (
        ollama_result.get("status") in ["connected", "no_models"] and
        db_result.get("status") == "connected"
    ) else "degraded"
    
    return {
        "status": status,
        "model": settings.MODEL_NAME,
        "ollama": ollama_result.get("status"),
        "database": db_result.get("status"),
        "uptime": get_uptime()["formatted"]
    }
