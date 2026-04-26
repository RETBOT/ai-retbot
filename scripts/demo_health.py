#!/usr/bin/env python3
"""
Demo de Health Checks

Muestra el estado completo del sistema.

Uso:
    python scripts/demo_health.py
"""
import asyncio
import httpx
import json
from datetime import datetime


BASE_URL = "http://localhost:8000"


async def test_health_simple():
    """Probar health check simple"""
    print("\n" + "="*70)
    print("🏥 HEALTH CHECK SIMPLE")
    print("="*70)
    
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(f"{BASE_URL}/health")
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"\nEstado: {data.get('status', 'unknown')}")
                print(f"Modelo: {data.get('model', 'N/A')}")
                print(f"Ollama: {data.get('ollama', 'N/A')}")
                print(f"Database: {data.get('database', 'N/A')}")
                print(f"Uptime: {data.get('uptime', 'N/A')}")
                
                return True
            else:
                print(f"❌ Error: HTTP {response.status_code}")
                print(f"   {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error de conexión: {e}")
            return False


async def test_health_full():
    """Probar health check completo"""
    print("\n" + "="*70)
    print("🏥 HEALTH CHECK COMPLETO")
    print("="*70)
    
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(f"{BASE_URL}/health/full")
            
            if response.status_code == 200:
                data = response.json()
                
                # Estado general
                print(f"\n📊 ESTADO GENERAL: {data.get('status', 'unknown').upper()}")
                
                # Uptime
                uptime = data.get('uptime', {})
                print(f"\n⏱️  Uptime: {uptime.get('formatted', 'N/A')}")
                print(f"   Inicio: {uptime.get('start_time', 'N/A')}")
                
                # Sistema
                system = data.get('system', {})
                if system and 'error' not in system:
                    print(f"\n💻 SISTEMA:")
                    print(f"   Platform: {system.get('platform', 'N/A')}")
                    print(f"   Python: {system.get('python_version', 'N/A')}")
                    print(f"   CPU: {system.get('cpu_count', 'N/A')} cores ({system.get('cpu_percent', 'N/A')}% uso)")
                    print(f"   RAM: {system.get('memory_used_gb', 'N/A')}/{system.get('memory_total_gb', 'N/A')} GB ({system.get('memory_percent', 'N/A')}%)")
                    print(f"   Disco: {system.get('disk_used_gb', 'N/A')}/{system.get('disk_total_gb', 'N/A')} GB ({system.get('disk_percent', 'N/A')}%)")
                
                # Servicios
                services = data.get('services', {})
                
                print(f"\n🔧 SERVICIOS:")
                
                # Ollama
                ollama = services.get('ollama', {})
                ollama_status = ollama.get('status', 'unknown')
                status_icon = "✅" if ollama_status == "connected" else "⚠️ " if ollama_status == "no_models" else "❌"
                print(f"   {status_icon} Ollama: {ollama_status}")
                if ollama_status == "connected":
                    print(f"      Modelos: {ollama.get('models_count', 0)} encontrados")
                    if ollama.get('models'):
                        print(f"      Primeros modelos: {', '.join(ollama['models'])}")
                if ollama.get('error'):
                    print(f"      Error: {ollama['error']}")
                
                # Database
                db = services.get('database', {})
                db_status = db.get('status', 'unknown')
                status_icon = "✅" if db_status == "connected" else "❌"
                print(f"   {status_icon} Database: {db_status}")
                if db_status == "connected":
                    print(f"      Usuarios: {db.get('users_count', 0)}")
                    print(f"      Jobs: {db.get('jobs_count', 0)}")
                if db.get('error'):
                    print(f"      Error: {db['error']}")
                
                # Redis
                redis_svc = services.get('redis', {})
                redis_status = redis_svc.get('status', 'not_configured')
                status_icon = "✅" if redis_status == "connected" else "⚪" if redis_status == "not_configured" else "❌"
                print(f"   {status_icon} Redis: {redis_status}")
                if redis_svc.get('error'):
                    print(f"      Error: {redis_svc['error']}")
                
                # GPU
                gpu = services.get('gpu', {})
                gpu_available = gpu.get('available', False)
                status_icon = "✅" if gpu_available else "⚪" if not gpu.get('error') else "❌"
                print(f"   {status_icon} GPU: {'Disponible' if gpu_available else 'No disponible'}")
                if gpu_available:
                    print(f"      GPUs detectadas: {gpu.get('count', 0)}")
                    for gpu_info in gpu.get('gpus', []):
                        print(f"      - GPU {gpu_info.get('index')}: {gpu_info.get('name', 'N/A')}")
                        print(f"        Memoria: {gpu_info.get('memory_used_gb', 0)}/{gpu_info.get('memory_total_gb', 0)} GB")
                        print(f"        Utilización: {gpu_info.get('utilization_gpu_percent', 0)}%")
                if gpu.get('error'):
                    print(f"      Error: {gpu['error']}")
                
                # Modelo
                model = data.get('model', {})
                print(f"\n🤖 MODELO:")
                print(f"   Nombre: {model.get('name', 'N/A')}")
                print(f"   Tipo: {model.get('type', 'N/A')}")
                print(f"   Contexto: {model.get('context_length', 'N/A')} tokens")
                
                # Rate limiting
                rate_limit = data.get('rate_limiting', {})
                print(f"\n🚦 RATE LIMITING:")
                print(f"   Habilitado: {'Sí' if rate_limit.get('enabled') else 'No'}")
                print(f"   Por usuario: {rate_limit.get('per_user', 'N/A')} req/min")
                print(f"   Por IP: {rate_limit.get('per_minute', 'N/A')} req/min")
                
                # Timestamp
                print(f"\n🕐 Timestamp: {data.get('timestamp', 'N/A')}")
                
                return True
            else:
                print(f"❌ Error: HTTP {response.status_code}")
                print(f"   {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error de conexión: {e}")
            return False


def print_recommendations(data: dict):
    """Imprimir recomendaciones basadas en el health check"""
    print("\n" + "="*70)
    print("💡 RECOMENDACIONES")
    print("="*70)
    
    services = data.get('services', {})
    
    # Verificar Ollama
    ollama = services.get('ollama', {})
    if ollama.get('status') == 'no_models':
        print("\n⚠️  Ollama sin modelos:")
        print("   Ejecutar: ollama pull qwen2.5-coder:14b")
    
    if ollama.get('status') == 'error':
        print("\n❌ Error con Ollama:")
        print(f"   {ollama.get('error')}")
        print("   Verificar que Ollama esté corriendo: ollama serve")
    
    # Verificar Database
    db = services.get('database', {})
    if db.get('status') == 'error':
        print("\n❌ Error con Database:")
        print(f"   {db.get('error')}")
        print("   Verificar permisos del archivo data.db")
    
    # Verificar GPU
    gpu = services.get('gpu', {})
    if not gpu.get('available') and not gpu.get('error'):
        print("\nℹ️  GPU no detectada:")
        print("   El sistema está corriendo en CPU")
        print("   Para mejor rendimiento, instalar GPU NVIDIA")
    
    # Verificar disco
    system = data.get('system', {})
    disk_percent = system.get('disk_percent', 0)
    if disk_percent > 80:
        print(f"\n⚠️  Disco lleno ({disk_percent}%):")
        print("   Liberar espacio para evitar problemas")
    
    # Verificar RAM
    memory_percent = system.get('memory_percent', 0)
    if memory_percent > 80:
        print(f"\n⚠️  RAM usage alto ({memory_percent}%):")
        print("   Considerar cerrar otras aplicaciones")


async def main():
    """Main"""
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║  RETBOT - Health Check Demo                                ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    # Verificar conexión
    print("\n🔍 Verificando conexión con el servidor...")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{BASE_URL}/health")
            if response.status_code != 200:
                print(f"❌ Servidor respondió con HTTP {response.status_code}")
                return
    except Exception:
        print(f"❌ No se pudo conectar a {BASE_URL}")
        print(f"   ¿El servidor está corriendo?")
        print(f"   Ejecutar: python server.py")
        return
    
    print("✅ Servidor detectado correctamente")
    
    # Ejecutar tests
    await test_health_simple()
    await test_health_full()
    
    print("\n" + "="*70)
    print("✅ Health checks completados")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
