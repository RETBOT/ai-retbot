"""
Locust Load Testing para RETBOT

Archivo de configuración para Locust.

Uso:
    locust -f tests/load_test_locust.py --host=http://localhost:8000
    
Abrir navegador en http://localhost:8089
"""

from locust import HttpUser, task, between
import random


class RETBOTUser(HttpUser):
    """
    Usuario simulado para RETBOT.
    
    Simula un desarrollador haciendo preguntas de código.
    """
    
    # Tiempo de espera entre tasks (5-15 segundos)
    wait_time = between(5, 15)
    
    # Preguntas de prueba
    questions = [
        "¿Cómo creo una función en Python que ordene una lista?",
        "¿Qué es FastAPI y cómo lo uso?",
        "¿Cómo hago un commit en Git?",
        "¿Qué es Docker y para qué sirve?",
        "¿Cómo creo una clase en Python?",
        "¿Qué es una API REST?",
        "¿Cómo instalo paquetes en Python?",
        "¿Qué es un decorator en Python?",
        "¿Cómo uso async/await en Python?",
        "¿Qué es type hinting en Python?",
    ]
    
    @task(3)
    def chat_simple(self):
        """
        Task: Chat simple (sin tools).
        
        Más común, por eso weight=3
        """
        question = random.choice(self.questions)
        
        with self.client.post(
            "/agent/chat/completions",
            json={"messages": [{"role": "user", "content": question}]},
            headers={"X-API-Key": "demo_key_123"},
            catch_response=True,
            timeout=300000  # 5 minutos
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.failure("Rate limit exceeded")
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def chat_with_tools(self):
        """
        Task: Chat con tools.
        
        Menos común, por eso weight=1
        """
        question = "Lee el archivo README.md y dime qué dice"
        
        with self.client.post(
            "/agent/chat/completions",
            json={
                "messages": [{"role": "user", "content": question}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "description": "Read file contents",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string"}
                                }
                            }
                        }
                    }
                ]
            },
            headers={"X-API-Key": "demo_key_123"},
            catch_response=True,
            timeout=300000
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.failure("Rate limit exceeded")
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def check_health(self):
        """
        Task: Health check.
        
        Muy rápido, útil para monitoreo.
        """
        self.client.get("/health")
    
    @task(1)
    def check_cache_stats(self):
        """
        Task: Ver estadísticas del cache.
        """
        self.client.get("/agent/cache/stats")


class HeavyUser(HttpUser):
    """
    Usuario pesado que hace muchas requests.
    
    Simula un usuario que abusa del sistema.
    """
    
    wait_time = between(1, 3)  # Más rápido
    
    @task
    def spam_chat(self):
        """Hacer muchas requests rápidamente"""
        question = "¿Qué es Python?"
        
        self.client.post(
            "/agent/chat/completions",
            json={"messages": [{"role": "user", "content": question}]},
            headers={"X-API-Key": "demo_key_123"},
            timeout=300000
        )
