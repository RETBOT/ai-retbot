import requests
import json
import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException
from core.config import settings

logger = logging.getLogger(__name__)


def build_ollama_payload(
    model: str,
    messages: list,
    stream: bool,
    keep_alive: int = 300,
    num_predict: Optional[int] = None
) -> dict:
    """Construir el payload para la API de Ollama /api/chat"""
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "options": {
            "keep_alive": keep_alive
        }
    }
    if num_predict is not None and num_predict > 0:
        payload["options"]["num_predict"] = num_predict
    return payload


def _parse_max_tokens(body: dict) -> Optional[int]:
    """Extraer y validar max_tokens del body (positivo entero)"""
    if "max_tokens" not in body:
        return None
    valor = body.get("max_tokens")
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
        raise HTTPException(status_code=400, detail="max_tokens must be a positive integer")
    return valor


class OllamaProvider:
    """Proveedor de Ollama"""
    
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.MODEL_NAME
        self.url = settings.OLLAMA_URL
    
    def is_available(self) -> bool:
        """Verificar si Ollama está disponible"""
        try:
            response = requests.get(f"{self.url}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.exceptions.ConnectionError:
            logger.warning(f"No se pudo conectar a Ollama en {self.url}")
            return False
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout al conectar a Ollama en {self.url}")
            return False
        except Exception as e:
            logger.warning(f"Error verificando disponibilidad de Ollama: {e}")
            return False
    
    def download_model(self) -> bool:
        """Descargar el modelo si no existe"""
        from core.database import async_session
        import asyncio
        from sqlalchemy import select
        from core.database import Job
        
        logger.info(f"Descargando modelo {self.model_name}...")
        
        try:
            response = requests.post(
                f"{self.url}/api/pull",
                json={"model": self.model_name, "stream": False},
                timeout=300
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    logger.info(f"Modelo {self.model_name} descargado exitosamente")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error descargando modelo: {e}")
            return False
    
    def ensure_model(self) -> bool:
        """Asegurar que el modelo existe, descargarlo si no"""
        models = self.list_models()
        model_names = [m.get("name", "").split(":")[0] for m in models]
        
        model_base = self.model_name.split(":")[0]
        
        if model_base not in model_names:
            logger.info(f"Modelo {self.model_name} no encontrado, descargando...")
            return self.download_model()
        
        return True
    
    def chat(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        num_predict: Optional[int] = None
    ) -> str:
        """Enviar mensaje a Ollama (num_predict = limite de tokens, opcional)"""
        # Verificar si Ollama está disponible
        if not self.is_available():
            raise Exception(
                "Ollama no está disponible. "
                " inicia Ollama con: docker-compose up -d "
                " o ejecuta 'ollama serve'"
            )
        
        # Asegurar que el modelo existe
        if not self.ensure_model():
            raise Exception(
                f"No se pudo descargar el modelo {self.model_name}. "
                "Verifica tu conexión a internet e intenta manualmente: "
                f"ollama pull {self.model_name}"
            )
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        
        try:
            response = requests.post(
                f"{self.url}/api/chat",
                json=build_ollama_payload(
                    self.model_name,
                    messages,
                    stream=False,
                    num_predict=num_predict
                ),
                timeout=180
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")
        except requests.exceptions.ConnectionError:
            raise Exception(f"Ollama no está disponible en {self.url}")
        except requests.exceptions.Timeout:
            raise Exception("Timeout al comunicarse con Ollama. El modelo puede ser muy grande para tu equipo.")
        except Exception as e:
            raise Exception(f"Error con Ollama: {str(e)}")
    
    async def chat_async(self, message: str, system_prompt: Optional[str] = None) -> str:
        """Versión async"""
        return self.chat(message, system_prompt)
    
    def list_models(self) -> list:
        """Listar modelos disponibles"""
        try:
            response = requests.get(f"{self.url}/api/tags", timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error listando modelos de Ollama: {e}")
            return []


class OpenCodeProvider:
    """Proveedor de OpenCode Server"""
    
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or "claude-haiku-4-5"
        self.url = settings.OPENCODE_URL
    
    def chat(self, message: str, system_prompt: Optional[str] = None) -> str:
        """Enviar mensaje a OpenCode"""
        try:
            from opencode_agent_sdk import SDKClient, AgentOptions
            
            client = SDKClient(AgentOptions(
                model=self.model_name,
                server_url=self.url,
                system_prompt=system_prompt or SYSTEM_PROMPT
            ))
            
            result = client.query(message)
            return result
        except ImportError:
            raise Exception("opencode-agent-sdk no está instalado")
        except Exception as e:
            raise Exception(f"Error con OpenCode: {str(e)}")
    
    def list_available_tools(self) -> list:
        """Listar herramientas disponibles"""
        try:
            from opencode_agent_sdk import SDKClient, AgentOptions
            client = SDKClient(AgentOptions(
                server_url=self.url
            ))
            return client.list_tools()
        except ImportError:
            logger.warning("opencode-agent-sdk no está instalado")
            return []
        except Exception as e:
            logger.warning(f"Error listando tools de OpenCode: {e}")
            return []
    
    def is_available(self) -> bool:
        """Verificar si OpenCode está disponible"""
        try:
            response = requests.get(f"{self.url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False


def get_model_provider(model_name: Optional[str] = None, model_type: Optional[str] = None):
    """Factory para obtener proveedor de modelo"""
    name = model_name or settings.MODEL_NAME
    mtype = model_type or settings.MODEL_TYPE
    
    if mtype == "opencode":
        return OpenCodeProvider(name.replace("opencode:", "") if name.startswith("opencode:") else name)
    elif mtype == "mock":
        # Modo mock para pruebas sin Ollama (equipos limitados)
        return MockProvider(name.replace("mock:", "") if name.startswith("mock:") else name)
    elif mtype == "ollama":
        return OllamaProvider(name.replace("ollama/", "") if name.startswith("ollama/") else name)
    else:
        # Por defecto Ollama
        return OllamaProvider(name)


class MockProvider:
    """Proveedor mock para pruebas sin Ollama.
    
    Útil para:
    - Pruebas locales en equipos limitado
    - Testing CI/CD sin dependencia de Ollama
    - Desarrollo cuando Ollama no está disponible
    
    Usage:
        MODEL_NAME=mock
        MODEL_TYPE=mock
    """
    
    def __init__(self, model_name: str = "mock"):
        self.model_name = model_name or "mock"
        
    def is_available(self) -> bool:
        """Siempre disponible en modo mock"""
        return True
    
    def list_models(self) -> list:
        """Retorna modelo mock"""
        return [{"name": self.model_name, "modified_at": "2024-01-01"}]
    
    def chat(self, message: str, system_prompt: Optional[str] = None) -> str:
        """Responde con respuestas predefinidas basadas en palabras clave"""
        message_lower = message.lower()
        
        # Respuestas basadas en palabras clave del mensaje
        responses = [
            # Keywords that might be in the message -> response
            ("hola", "hello", "hi", "hey", "Buenos días", "Qué onda"),
            "¡Hola! Soy el asistente en modo mock. ¿En qué puedo ayudarte hoy?",
            
            ("read", "leer", "archivo"),
            "Para leer un archivo, usaría la herramienta read_file con la ruta del archivo que deseas leer.",
            
            ("write", "escribir", "crear archivo"),
            "Para crear un archivo, usaría write_file especificando la ruta y el contenido.",
            
            ("edit", "editar", "modificar"),
            "Para modificar un archivo, usaría edit_file con el path, old_string y new_string.",
            
            ("test", "pytest", "prueba"),
            "Para ejecutar pruebas, usaría: pytest tests/ -v o el comando específico que necesites.",
            
            ("git", "commit", "push"),
            "Para git,常见的 comandos son: git status, git add, git commit -m 'msg', git push.",
            
            ("error", "bug", "falla"),
            "Parece que hay un error. ¿Podrías mostrarme el mensaje de error completo?",
            
            ("help", "ayuda", "comandos"),
            "Mis herramientas disponibles son: read_file, write_file, edit_file, list_directory, execute_command.",
        ]
        
        # Buscar coincidencia
        for i in range(0, len(responses), 2):
            keywords = responses[i]
            response = responses[i + 1]
            
            if isinstance(keywords, str):
                keywords = (keywords,)
            
            for kw in keywords:
                if kw in message_lower:
                    return f"[MOCK - {self.model_name}] {response}"
        
        # Respuesta por defecto
        return (
            f"[MOCK - {self.model_name}] "
            f"Entendí tu mensaje: '{message[:100]}...'. "
            f"En un entorno real, procesaría esto con Ollama y las tools disponibles. "
            f"¿Necesitas ayuda con algo específico?"
        )
    
    async def chat_async(self, message: str, system_prompt: Optional[str] = None) -> str:
        """Versión async"""
        return self.chat(message, system_prompt)


# Prompt del sistema por defecto - OPTIMIZED FOR OPENCODE
SYSTEM_PROMPT = """You are RETBOT, an expert AI coding assistant integrated with OpenCode.

## Your Core Purpose
Help users write, debug, refactor, and understand code. You have direct access to the filesystem through tools.

## Guidelines

### When Helping with Code:
1. ALWAYS read relevant files before making changes
2. Use edit_file for small changes (preserves context)
3. Use write_file only for new files or complete rewrites
4. Run tests or linters after changes when available
5. Explain WHAT you're doing and WHY

### Code Quality Standards:
- Write clean, maintainable code
- Follow existing patterns in the codebase
- Add comments for complex logic
- Handle edge cases appropriately
- Use meaningful variable names
- Keep functions focused and small

### Communication Style:
- Be concise but thorough
- Show code first, explain after
- Use technical terms appropriately
- Ask clarifying questions when needed
- If unsure, say so honestly

### Preferred Languages & Frameworks:
- Python (FastAPI, Django, pytest)
- JavaScript/TypeScript (React, Node.js)
- Go (standard patterns)
- Rust (idiomatic code)
- SQL (PostgreSQL, SQLite)

### Security & Safety:
- Never expose sensitive data
- Validate inputs in code examples
- Warn about security implications
- Don't execute destructive commands without confirmation

## Response Format
When providing solutions:
1. Brief explanation of the approach
2. The actual code
3. Explanation of key parts
4. Any considerations or next steps"""