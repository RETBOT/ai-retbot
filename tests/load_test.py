"""
Load Testing Script para RETBOT

Script de load testing para simular múltiples usuarios concurrentes.

Uso:
    python tests/load_test.py --users 15 --duration 300

Opciones:
    --users: Número de usuarios concurrentes (default: 10)
    --duration: Duración en segundos (default: 300)
    --host: URL del servidor (default: http://localhost:8000)
    --api-key: API key a usar (default: demo_key_123)
"""

import asyncio
import httpx
import argparse
import time
import statistics
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class RequestResult:
    """Resultado de una request"""
    success: bool
    response_time: float
    status_code: int
    error: str = ""
    cached: bool = False


class LoadTester:
    """Load tester para RETBOT"""
    
    def __init__(
        self,
        host: str = "http://localhost:8000",
        api_key: str = "demo_key_123",
        num_users: int = 10
    ):
        self.host = host
        self.api_key = api_key
        self.num_users = num_users
        self.results: List[RequestResult] = []
        self.start_time = None
        self.end_time = None
        
        # Preguntas de prueba (simulan developers haciendo preguntas)
        self.questions = [
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
    
    async def make_request(
        self,
        session: httpx.AsyncClient,
        user_id: int,
        request_num: int
    ) -> RequestResult:
        """
        Hacer una request al endpoint de chat.
        
        Args:
            session: Sesión HTTP
            user_id: ID del usuario
            request_num: Número de request
        
        Returns:
            RequestResult: Resultado de la request
        """
        # Seleccionar pregunta aleatoria
        import random
        question = random.choice(self.questions)
        
        start = time.time()
        
        try:
            response = await session.post(
                f"{self.host}/agent/chat/completions",
                json={
                    "messages": [{"role": "user", "content": question}]
                },
                headers={"X-API-Key": self.api_key},
                timeout=300  # 5 minutos timeout
            )
            
            response_time = time.time() - start
            
            # Verificar si vino del cache
            is_cached = False
            if response.status_code == 200:
                data = response.json()
                is_cached = "cache" in data.get("id", "").lower()
            
            return RequestResult(
                success=response.status_code == 200,
                response_time=response_time,
                status_code=response.status_code,
                cached=is_cached
            )
            
        except httpx.TimeoutException:
            response_time = time.time() - start
            return RequestResult(
                success=False,
                response_time=response_time,
                status_code=0,
                error="Timeout"
            )
        except Exception as e:
            response_time = time.time() - start
            return RequestResult(
                success=False,
                response_time=response_time,
                status_code=0,
                error=str(e)
            )
    
    async def user_session(
        self,
        session: httpx.AsyncClient,
        user_id: int,
        duration: int
    ):
        """
        Simular sesión de usuario haciendo requests durante la duración.
        
        Args:
            session: Sesión HTTP
            user_id: ID del usuario
            duration: Duración en segundos
        """
        request_num = 0
        
        while (time.time() - self.start_time) < duration:
            request_num += 1
            
            # Hacer request
            result = await self.make_request(session, user_id, request_num)
            self.results.append(result)
            
            # Esperar entre 5-15 segundos (simula usuario real)
            import random
            await asyncio.sleep(random.uniform(5, 15))
    
    async def run(self, duration: int = 300):
        """
        Ejecutar load test.
        
        Args:
            duration: Duración en segundos
        """
        print("\n" + "="*70)
        print("🧪 LOAD TESTING - RETBOT")
        print("="*70)
        
        print(f"\n📊 Configuración:")
        print(f"   Usuarios concurrentes: {self.num_users}")
        print(f"   Duración: {duration} segundos ({duration/60:.1f} minutos)")
        print(f"   Host: {self.host}")
        print(f"   API Key: {self.api_key}")
        print(f"\n📝 Iniciando load test...")
        print("-"*70)
        
        self.start_time = time.time()
        
        async with httpx.AsyncClient(timeout=300) as client:
            # Crear tareas para cada usuario
            tasks = [
                self.user_session(client, user_id, duration)
                for user_id in range(1, self.num_users + 1)
            ]
            
            # Ejecutar en paralelo
            await asyncio.gather(*tasks)
        
        self.end_time = time.time()
        
        # Imprimir resultados
        self.print_results()
    
    def print_results(self):
        """Imprimir resultados del load test"""
        print("\n" + "="*70)
        print("📊 RESULTADOS")
        print("="*70)
        
        # Filtrar resultados
        total = len(self.results)
        successes = [r for r in self.results if r.success]
        failures = [r for r in self.results if not r.success]
        cached = [r for r in self.results if r.cached]
        
        # Calcular estadísticas
        success_rate = (len(successes) / total * 100) if total > 0 else 0
        failure_rate = (len(failures) / total * 100) if total > 0 else 0
        cache_rate = (len(cached) / total * 100) if total > 0 else 0
        
        response_times = [r.response_time for r in successes]
        
        if response_times:
            avg_time = statistics.mean(response_times)
            median_time = statistics.median(response_times)
            p95_time = sorted(response_times)[int(len(response_times) * 0.95)] if len(response_times) > 20 else max(response_times)
            min_time = min(response_times)
            max_time = max(response_times)
        else:
            avg_time = median_time = p95_time = min_time = max_time = 0
        
        # Duración total
        total_duration = self.end_time - self.start_time if self.end_time else 0
        requests_per_second = total / total_duration if total_duration > 0 else 0
        
        # Imprimir estadísticas
        print(f"\n⏱️  Duración: {total_duration:.1f} segundos")
        print(f"\n📈 Throughput:")
        print(f"   Total Requests: {total}")
        print(f"   Requests/segundo: {requests_per_second:.2f}")
        
        print(f"\n✅ Éxito:")
        print(f"   Exitosos: {len(successes)} ({success_rate:.1f}%)")
        print(f"   Fallidos: {len(failures)} ({failure_rate:.1f}%)")
        print(f"   Desde cache: {len(cached)} ({cache_rate:.1f}%)")
        
        print(f"\n⚡ Tiempos de respuesta:")
        print(f"   Promedio: {avg_time:.2f}s")
        print(f"   Mediana: {median_time:.2f}s")
        print(f"   95th Percentile: {p95_time:.2f}s")
        print(f"   Mínimo: {min_time:.2f}s")
        print(f"   Máximo: {max_time:.2f}s")
        
        # Errores comunes
        if failures:
            print(f"\n❌ Errores:")
            error_counts = defaultdict(int)
            for r in failures:
                error_counts[r.error] += 1
            
            for error, count in error_counts.items():
                print(f"   {error}: {count}")
        
        # Evaluación
        print("\n" + "="*70)
        print("📋 EVALUACIÓN")
        print("="*70)
        
        if failure_rate < 1 and p95_time < 10:
            print("\n✅ SISTEMA SALUDABLE")
            print("   - Failures < 1%")
            print("   - 95th percentile < 10s")
            print("   - Sistema listo para producción")
        elif failure_rate < 5 and p95_time < 30:
            print("\n⚠️  SISTEMA BAJO ESTRÉS")
            print("   - Failures 1-5%")
            print("   - 95th percentile 10-30s")
            print("   - Considerar ajustes")
        else:
            print("\n❌ SISTEMA SATURADO")
            print("   - Failures > 5%")
            print("   - 95th percentile > 30s")
            print("   - Se requieren ajustes urgentes")
        
        # Recomendaciones
        print("\n💡 RECOMENDACIONES:")
        
        if failure_rate > 1:
            print("   - Reducir OLLAMA_NUM_PARALLEL")
            print("   - Aumentar timeouts")
        
        if p95_time > 10:
            print("   - Usar modelo más pequeño")
            print("   - Reducir contexto")
            print("   - Habilitar cache")
        
        if cache_rate < 20:
            print("   - Verificar que Redis esté corriendo")
            print("   - Revisar configuración de cache")
        
        print("\n" + "="*70)


async def main():
    """Main"""
    parser = argparse.ArgumentParser(description="Load Testing para RETBOT")
    parser.add_argument(
        "--users",
        type=int,
        default=10,
        help="Número de usuarios concurrentes (default: 10)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Duración en segundos (default: 300)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="http://localhost:8000",
        help="URL del servidor (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default="demo_key_123",
        help="API key (default: demo_key_123)"
    )
    
    args = parser.parse_args()
    
    # Verificar conexión
    print("\n🔍 Verificando conexión con el servidor...")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{args.host}/health")
            if response.status_code != 200:
                print(f"❌ Servidor respondió con HTTP {response.status_code}")
                return
    except Exception:
        print(f"❌ No se pudo conectar a {args.host}")
        print(f"   ¿El servidor está corriendo?")
        print(f"   Ejecutar: python server.py")
        return
    
    print("✅ Servidor detectado correctamente")
    
    # Preguntar confirmación
    print(f"\n⚠️  ¿Listo para ejecutar load test con {args.users} usuarios por {args.duration/60:.1f} minutos?")
    confirm = input("Presiona ENTER para continuar o Ctrl+C para cancelar: ")
    
    # Ejecutar load test
    tester = LoadTester(
        host=args.host,
        api_key=args.api_key,
        num_users=args.users
    )
    
    await tester.run(duration=args.duration)


if __name__ == "__main__":
    asyncio.run(main())
