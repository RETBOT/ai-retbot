"""
Tools/Function Calling para RETBOT

Este módulo implementa el sistema de tools que permite al LLM
interactuar con el filesystem y ejecutar comandos de forma segura.
"""

from .definitions import TOOLS, TOOL_DEFINITIONS
from .executor import ToolExecutor, ToolResult

__all__ = [
    "TOOLS",
    "TOOL_DEFINITIONS", 
    "ToolExecutor",
    "ToolResult",
]
