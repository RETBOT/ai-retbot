"""
Soporte para Múltiples Modelos

Este módulo permite cambiar dinámicamente entre diferentes modelos
según la request, permitiendo que diferentes usuarios usen diferentes
modelos simultáneamente.

Características:
- Selector de modelo por request
- Cache de modelos disponibles
- Validación de modelo existente
- Fallback a modelo default
"""

import logging
from typing import Optional, List, Dict, Any
from core.config import settings
from core.models import OllamaProvider

logger = logging.getLogger(__name__)


class ModelManager:
    """
    Gestor de múltiples modelos.
    
    Permite seleccionar y validar modelos dinámicamente.
    """
    
    def __init__(self):
        """Inicializar gestor de modelos"""
        self._available_models: Optional[List[Dict[str, Any]]] = None
        self._model_cache: Dict[str, Dict[str, Any]] = {}
    
    async def get_available_models(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Obtener lista de modelos disponibles desde Ollama.
        
        Args:
            force_refresh: Forzar refresh de la lista
        
        Returns:
            list: Lista de modelos disponibles
        """
        # Usar cache si existe y no se fuerza refresh
        if self._available_models and not force_refresh:
            return self._available_models
        
        try:
            ollama = OllamaProvider()
            models = ollama.list_models()
            
            # Formatear lista de modelos
            self._available_models = [
                {
                    "id": model.get("name", "unknown"),
                    "name": model.get("name", "unknown"),
                    "size": model.get("size", 0),
                    "modified_at": model.get("modified_at", ""),
                    "digest": model.get("digest", ""),
                    "details": model.get("details", {})
                }
                for model in models
            ] if models else []
            
            logger.info(f"Modelos disponibles: {len(self._available_models)}")
            
            return self._available_models
            
        except Exception as e:
            logger.error(f"Error obteniendo modelos: {e}")
            # Retornar modelo default si falla
            return [{"id": settings.MODEL_NAME, "name": settings.MODEL_NAME}]
    
    def validate_model(self, model_name: str) -> bool:
        """
        Validar si un modelo está disponible.
        
        Args:
            model_name: Nombre del modelo a validar
        
        Returns:
            bool: True si el modelo está disponible
        """
        # Si es el modelo default, siempre es válido
        if model_name == settings.MODEL_NAME:
            return True
        
        # Buscar en la lista de modelos disponibles
        available = self._available_models or []
        return any(m["id"] == model_name for m in available)
    
    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtener información de un modelo específico.
        
        Args:
            model_name: Nombre del modelo
        
        Returns:
            dict: Información del modelo o None si no existe
        """
        available = self._available_models or []
        
        for model in available:
            if model["id"] == model_name:
                return model
        
        return None
    
    def select_best_model(
        self,
        task_type: str = "general",
        max_size: Optional[int] = None
    ) -> str:
        """
        Seleccionar el mejor modelo para una tarea.
        
        Args:
            task_type: Tipo de tarea (general, code, chat, fast)
            max_size: Tamaño máximo en bytes
        
        Returns:
            str: Nombre del modelo seleccionado
        """
        available = self._available_models or []
        
        if not available:
            return settings.MODEL_NAME
        
        # Filtrar por tamaño si se especifica
        if max_size:
            available = [m for m in available if m.get("size", 0) <= max_size]
        
        if not available:
            return settings.MODEL_NAME
        
        # Seleccionar según tipo de tarea
        if task_type == "code":
            # Priorizar modelos coder
            coder_models = [m for m in available if "coder" in m["id"].lower()]
            if coder_models:
                return coder_models[0]["id"]
        
        elif task_type == "fast":
            # Priorizar modelos pequeños
            sorted_by_size = sorted(available, key=lambda m: m.get("size", 0))
            return sorted_by_size[0]["id"]
        
        elif task_type == "chat":
            # Priorizar modelos medianos (balance calidad/velocidad)
            medium_models = [m for m in available if 5e9 <= m.get("size", 0) <= 20e9]
            if medium_models:
                return medium_models[0]["id"]
        
        # Default: usar modelo configurado
        return settings.MODEL_NAME
    
    def clear_cache(self):
        """Limpiar cache de modelos"""
        self._available_models = None
        self._model_cache.clear()
        logger.info("Cache de modelos limpiada")


# Instancia global del model manager
model_manager = ModelManager()


async def init_model_manager():
    """Inicializar el model manager"""
    await model_manager.get_available_models()
    logger.info("Model manager inicializado")


def get_model_for_request(
    requested_model: Optional[str] = None,
    task_type: str = "general"
) -> str:
    """
    Obtener modelo para una request.
    
    Args:
        requested_model: Modelo solicitado por el usuario
        task_type: Tipo de tarea
    
    Returns:
        str: Modelo a usar
    """
    # Si se solicitó un modelo específico
    if requested_model:
        # Validar que el modelo esté disponible
        if model_manager.validate_model(requested_model):
            logger.info(f"Usando modelo solicitado: {requested_model}")
            return requested_model
        else:
            logger.warning(f"Modelo {requested_model} no disponible, usando default")
    
    # Si no se solicitó modelo o no está disponible, seleccionar automáticamente
    selected = model_manager.select_best_model(task_type=task_type)
    logger.info(f"Modelo seleccionado automáticamente: {selected}")
    return selected
