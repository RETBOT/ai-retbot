"""
Definiciones de Tools para Function Calling

Formato compatible con OpenAI Function Calling API.
Las tools definen la interfaz que el LLM puede usar para interactuar
con el sistema de archivos y ejecutar comandos.
"""

from typing import Dict, Any, List

# Tool definitions en formato OpenAI-compatible
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the specified path. Returns the file content as a string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute or relative path to the file to read. Examples: '/app/main.py', './src/utils.js'"
                    }
                },
                "required": ["path"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Creates the file if it doesn't exist, overwrites if it does. Creates parent directories if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute or relative path where to write the file. Examples: '/app/main.py', './src/utils.js'"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file. Should be the complete file content."
                    }
                },
                "required": ["path", "content"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Apply a search and replace edit to a file. Only replaces the first occurrence of the search string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute or relative path to the file to edit."
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The exact string to search for and replace. Must match exactly including whitespace."
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The new string to replace the old_string with."
                    }
                },
                "required": ["path", "old_string", "new_string"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List the contents of a directory. Returns a list of files and subdirectories with their types.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The absolute or relative path to the directory to list. Defaults to current directory if not provided.",
                        "default": "."
                    }
                },
                "required": [],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute a shell command in a subprocess. Returns stdout and stderr. Only whitelisted commands are allowed for security.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute. Examples: 'ls -la', 'python --version', 'npm install'"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds. Default is 30 seconds, max is 300 seconds.",
                        "default": 30,
                        "minimum": 1,
                        "maximum": 300
                    }
                },
                "required": ["command"],
                "additionalProperties": False
            }
        }
    }
]

# Diccionario para lookup rápido
TOOLS = {tool["function"]["name"]: tool for tool in TOOL_DEFINITIONS}


def get_tool_schema(tool_name: str) -> Dict[str, Any]:
    """Obtener el schema de una tool por nombre"""
    return TOOLS.get(tool_name)


def list_available_tools() -> List[str]:
    """Listar nombres de tools disponibles"""
    return list(TOOLS.keys())


# System prompt extension para tools
TOOLS_SYSTEM_PROMPT_EXTENSION = """
You have access to tools that can help you interact with the file system and execute commands.

When you need to:
- Read a file: use read_file
- Write or overwrite a file: use write_file  
- Make targeted edits: use edit_file (preferred over write_file for small changes)
- List directory contents: use list_directory
- Run commands: use execute_command

Important guidelines:
1. ALWAYS read relevant files before making changes
2. Use edit_file for small changes to preserve existing code
3. Use write_file when creating new files or major rewrites
4. List directories to understand project structure
5. Run tests or linters after making changes

When calling tools, ensure arguments match the expected schema exactly.
"""
