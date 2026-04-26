"""
Cache de Respuestas con Redis

Este módulo implementa cache para reducir llamadas al LLM y mejorar
el tiempo de respuesta para preguntas frecuentes.
"""
import hashlib
import json
import asyncio
from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ResponseCache:
    """
    Cache de respuestas usando Redis.
    
    Características:
    - Cache por hash de mensajes + modelo
    - TTL configurable por tipo de respuesta
    - Invalidación manual
    - Estadísticas de cache (hits/misses)
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """
        Inicializar cache de Redis.
        
        Args:
            redis_url: URL de conexión a Redis
        """
        self.redis_url = redis_url
        self._client = None
        self._connected = False
        
        # Estadísticas
        self.stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "keys_set": 0,
            "keys_deleted": 0
        }
    
    async def connect(self):
        """Establecer conexión con Redis"""
        if self._connected:
            return
        
        try:
            import redis.asyncio as redis
            
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Verificar conexión
            await self._client.ping()
            self._connected = True
            logger.info(f"✅ Conectado a Redis: {self.redis_url}")
            
        except ImportError:
            logger.warning("⚠️ redis-py no instalado. Cache deshabilitado.")
            self._connected = False
        except Exception as e:
            logger.error(f"❌ Error conectando a Redis: {e}")
            self._connected = False
    
    async def disconnect(self):
        """Cerrar conexión con Redis"""
        if self._client:
            await self._client.close()
            self._connected = False
            logger.info("Desconectado de Redis")
    
    def _generate_key(self, messages: List[Dict], model: str, prefix: str = "cache") -> str:
        """
        Generar clave única para cache basada en mensajes y modelo.
        
        Args:
            messages: Lista de mensajes de la conversación
            model: Nombre del modelo
            prefix: Prefijo para la clave
        
        Returns:
            str: Clave hash para cache
        """
        # Normalizar mensajes para generar hash consistente
        normalized = json.dumps(messages, sort_keys=True, ensure_ascii=False)
        content = f"{normalized}:{model}"
        
        # Generar hash MD5
        key_hash = hashlib.md5(content.encode()).hexdigest()
        
        return f"{prefix}:{key_hash}"
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Obtener respuesta del cache.
        
        Args:
            key: Clave del cache
        
        Returns:
            dict: Respuesta cacheada o None si no existe
        """
        if not self._connected or not self._client:
            return None
        
        try:
            data = await self._client.get(key)
            
            if data:
                self.stats["hits"] += 1
                logger.debug(f"Cache HIT: {key}")
                return json.loads(data)
            else:
                self.stats["misses"] += 1
                logger.debug(f"Cache MISS: {key}")
                return None
                
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error obteniendo cache: {e}")
            return None
    
    async def set(self, key: str, value: Dict[str, Any], ttl: int = 3600) -> bool:
        """
        Guardar respuesta en cache.
        
        Args:
            key: Clave del cache
            value: Valor a cache
            ttl: Tiempo de vida en segundos (default: 1 hora)
        
        Returns:
            bool: True si se guardó exitosamente
        """
        if not self._connected or not self._client:
            return False
        
        try:
            # Serializar valor
            data = json.dumps(value, ensure_ascii=False)
            
            # Guardar con TTL
            await self._client.setex(key, ttl, data)
            self.stats["keys_set"] += 1
            
            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error guardando cache: {e}")
            return False
    
    async def get_response(self, messages: List[Dict], model: str) -> Optional[Dict[str, Any]]:
        """
        Obtener respuesta cacheada para mensajes específicos.
        
        Args:
            messages: Lista de mensajes
            model: Nombre del modelo
        
        Returns:
            dict: Respuesta cacheada o None
        """
        key = self._generate_key(messages, model)
        return await self.get(key)
    
    async def set_response(
        self,
        messages: List[Dict],
        model: str,
        response: Dict[str, Any],
        ttl: int = 3600
    ) -> bool:
        """
        Guardar respuesta en cache para mensajes específicos.
        
        Args:
            messages: Lista de mensajes
            model: Nombre del modelo
            response: Respuesta a cache
            ttl: Tiempo de vida en segundos
        
        Returns:
            bool: True si se guardó exitosamente
        """
        key = self._generate_key(messages, model)
        return await self.set(key, response, ttl)
    
    async def delete(self, key: str) -> bool:
        """
        Eliminar clave del cache.
        
        Args:
            key: Clave a eliminar
        
        Returns:
            bool: True si se eliminó
        """
        if not self._connected or not self._client:
            return False
        
        try:
            await self._client.delete(key)
            self.stats["keys_deleted"] += 1
            logger.debug(f"Cache DELETE: {key}")
            return True
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error eliminando cache: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """
        Eliminar múltiples claves por patrón.
        
        Args:
            pattern: Patrón a buscar (ej. "cache:*")
        
        Returns:
            int: Número de claves eliminadas
        """
        if not self._connected or not self._client:
            return 0
        
        try:
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                await self._client.delete(*keys)
                self.stats["keys_deleted"] += len(keys)
                logger.info(f"Cache DELETE PATTERN: {pattern} ({len(keys)} keys)")
                return len(keys)
            
            return 0
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Error eliminando patrón: {e}")
            return 0
    
    async def clear_all(self) -> int:
        """
        Limpiar todo el cache.
        
        Returns:
            int: Número de claves eliminadas
        """
        return await self.delete_pattern("cache:*")
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Obtener estadísticas del cache.
        
        Returns:
            dict: Estadísticas del cache
        """
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total * 100) if total > 0 else 0
        
        return {
            **self.stats,
            "total_requests": total,
            "hit_rate_percent": round(hit_rate, 2),
            "connected": self._connected
        }
    
    async def get_ttl(self, key: str) -> Optional[int]:
        """
        Obtener TTL restante de una clave.
        
        Args:
            key: Clave del cache
        
        Returns:
            int: TTL en segundos o None si no existe
        """
        if not self._connected or not self._client:
            return None
        
        try:
            return await self._client.ttl(key)
        except Exception as e:
            logger.error(f"Error obteniendo TTL: {e}")
            return None
    
    async def exists(self, key: str) -> bool:
        """
        Verificar si una clave existe en cache.
        
        Args:
            key: Clave a verificar
        
        Returns:
            bool: True si existe
        """
        if not self._connected or not self._client:
            return False
        
        try:
            return await self._client.exists(key) > 0
        except Exception as e:
            logger.error(f"Error verificando existencia: {e}")
            return False


# Instancia global del cache
cache = ResponseCache()


async def init_cache(redis_url: str = "redis://localhost:6379"):
    """
    Inicializar cache global.
    
    Args:
        redis_url: URL de Redis
    """
    await cache.connect()


async def close_cache():
    """Cerrar conexión del cache"""
    await cache.disconnect()


# Decorador para cachear funciones
def cached(ttl: int = 3600, prefix: str = "cache"):
    """
    Decorador para cachear resultados de funciones async.
    
    Args:
        ttl: Tiempo de vida en segundos
        prefix: Prefijo para las claves
    
    Usage:
        @cached(ttl=1800)
        async def get_expensive_data(param1, param2):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generar clave basada en argumentos
            key_data = {
                "function": func.__name__,
                "args": args,
                "kwargs": kwargs
            }
            key = cache._generate_key([key_data], "", prefix)
            
            # Intentar obtener del cache
            cached_result = await cache.get(key)
            if cached_result:
                return cached_result
            
            # Ejecutar función
            result = await func(*args, **kwargs)
            
            # Guardar en cache
            if result is not None:
                await cache.set(key, result, ttl)
            
            return result
        
        return wrapper
    return decorator
