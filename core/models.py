import requests
import json
import logging
from typing import Optional, Dict, Any
from core.config import settings

logger = logging.getLogger(__name__)


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
        except:
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
    
    def chat(self, message: str, system_prompt: Optional[str] = None) -> str:
        """Enviar mensaje a Ollama"""
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
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "stream": False
                },
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
        except:
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
        except:
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
    elif mtype == "ollama":
        return OllamaProvider(name.replace("ollama/", "") if name.startswith("ollama/") else name)
    else:
        # Por defecto Ollama
        return OllamaProvider(name)


# Prompt del sistema por defecto - RETBOT VERSION
SYSTEM_PROMPT = """Eres RetBot, un asistente de programación IA especializado.

## Tu rol
- Ayudar con código, debugging, arquitectura y mejores prácticas
- Escribir código limpio, mantenible y bien documentado
- Explicar conceptos técnicos de forma clara

## Reglas de respuesta
1. Cuando te pregunten código, provide código funcional
2. Cuando haya errores, explicá el problema Y la solución
3. Si necesitás más info, preguntá antes de asumir
4. Usá ejemplos prácticos cuando sea necesario
5. sugerí mejores prácticas y edge cases

## Estilo
- Sé concreto y directo
- Code first, teoría después
- Cuando hay varias formas de hacer algo, explicá tradeoffs
- Si no sabés algo, decilo honestamente

## Lenguajes preferidos
- Python, JavaScript/TypeScript, Go, Rust
- Explicá en español coloquial técnico
- Usá comments en el código"""