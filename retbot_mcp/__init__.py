"""
RETBOT MCP Server

Capa de integración MCP (Model Context Protocol) que expone las
funcionalidades existentes de RETBOT como MCP Tools para que el agente
(OpenCode + Ollama) pueda descubrirlas y utilizarlas automáticamente.

Principio de diseño: el MCP es UNA CAPA, no una reimplementación.
Cada tool llama a la lógica existente del proyecto (core/).

NOTA: el paquete se llama `retbot_mcp` (no `mcp`) para no chocar con
el SDK oficial `mcp` (model context protocol) instalado en el venv.
"""

from .server import create_server

__all__ = ["create_server"]