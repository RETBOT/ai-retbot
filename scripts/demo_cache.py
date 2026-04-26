#!/usr/bin/env python3
"""
Demo de Cache de Respuestas

Muestra cómo el cache reduce las llamadas al LLM.

Uso:
    python scripts/demo_cache.py
"""
import asyncio
import httpx
from datetime import datetime


BASE_URL = "http://localhost:8000"
API_KEY = "demo_key_123"
HEADERS = {"X-API-Key": API_KEY}


async def make_request(session: httpx.AsyncClient, message: str, request_num: int):
    """Hacer una request y mostrar resultado"""
    start = datetime.now()
    
    try:
        response = await session.post(
            f"{BASE_URL}/agent/chat/completions",
            json={"messages": [{"role": "user", "content": message}]},
            headers=HEADERS
        )
        
        elapsed = (datetime.now() - start).total_seconds()
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")[:50]
            
            # Verificar si viene del cache por el ID
            is_cached = "cache" in data.get("id", "").lower()
            cache_icon = "💾" if is_cached else "🤖"
            
            print(f"{cache_icon} Request {request_num:2d} | {elapsed:.2f}s | {content}...")
            
            return is_cached
        else:
            print(f"❌ Request {request_num:2d} | Error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Request {request_num:2d} | Error: {e}")
        return None


async def demo_cache():
    """Demostración de cache"""
    print("\n" + "="*70)
    print("💾 DEMO DE CACHE DE RESPUESTAS")
    print("="*70)
    
    print(f"\n📊 Configuración:")
    print(f"   URL: {BASE_URL}")
    print(f"   API Key: {API_KEY}")
    print(f"\n📝 Haremos la MISMA pregunta 5 veces para demostrar el cache...\n")
    print("-"*70)
    
    message = "¿Qué es Python?"
    
    async with httpx.AsyncClient(timeout=30) as client:
        cache_hits = 0
        cache_misses = 0
        
        for i in range(1, 6):
            is_cached = await make_request(client, message, i)
            
            if is_cached is True:
                cache_hits += 1
            elif is_cached is False:
                cache_misses += 1
            
            await asyncio.sleep(0.5)
        
        print("-"*70)
        print(f"\n📊 Resultados:")
        print(f"   Cache Hits (💾): {cache_hits}")
        print(f"   Cache Misses (🤖): {cache_misses}")
        
        if cache_hits > 0:
            print(f"\n✅ ¡El cache funcionó! {cache_hits} respuestas vinieron del cache.")
            print(f"   Esto reduce la carga del LLM y mejora el tiempo de respuesta.")
        else:
            print(f"\n⚠️ El cache no se activó.")
            print(f"   Posibles razones:")
            print(f"   - Redis no está corriendo")
            print(f"   - Es la primera vez que se hace la pregunta")
            print(f"   - El cache está deshabilitado")


async def demo_cache_different_questions():
    """Demo con diferentes preguntas"""
    print("\n" + "="*70)
    print("💾 DEMO CON DIFERENTES PREGUNTAS")
    print("="*70)
    
    questions = [
        "¿Qué es Python?",
        "¿Qué es FastAPI?",
        "¿Qué es Docker?",
        "¿Qué es Python?",  # Repetida
        "¿Qué es FastAPI?",  # Repetida
        "¿Qué es Redis?",
    ]
    
    print(f"\n📝 Haremos 6 preguntas (algunas repetidas)...\n")
    print("-"*70)
    
    async with httpx.AsyncClient(timeout=30) as client:
        cache_hits = 0
        cache_misses = 0
        
        for i, question in enumerate(questions, 1):
            is_cached = await make_request(client, question, i)
            
            if is_cached is True:
                cache_hits += 1
            elif is_cached is False:
                cache_misses += 1
            
            await asyncio.sleep(0.5)
        
        print("-"*70)
        print(f"\n📊 Resultados:")
        print(f"   Cache Hits: {cache_hits}")
        print(f"   Cache Misses: {cache_misses}")
        
        if cache_hits > 0:
            hit_rate = (cache_hits / (cache_hits + cache_misses)) * 100
            print(f"\n✅ Hit rate: {hit_rate:.1f}%")
            print(f"   Las preguntas repetidas se sirvieron del cache.")


async def get_cache_stats():
    """Obtener estadísticas del cache"""
    print("\n" + "="*70)
    print("📊 ESTADÍSTICAS DEL CACHE")
    print("="*70)
    
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(f"{BASE_URL}/agent/cache/stats")
            
            if response.status_code == 200:
                data = response.json()
                cache_info = data.get("cache", {})
                stats = cache_info.get("stats", {})
                
                print(f"\nCache Habilitado: {cache_info.get('enabled', False)}")
                print(f"\nEstadísticas:")
                print(f"   Hits: {stats.get('hits', 0)}")
                print(f"   Misses: {stats.get('misses', 0)}")
                print(f"   Total Requests: {stats.get('total_requests', 0)}")
                print(f"   Hit Rate: {stats.get('hit_rate_percent', 0)}%")
                print(f"   Keys Set: {stats.get('keys_set', 0)}")
                print(f"   Errors: {stats.get('errors', 0)}")
                
            else:
                print(f"❌ Error: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error: {e}")


async def main():
    """Main"""
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║  RETBOT - Demo de Cache de Respuestas                     ║")
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
    
    # Preguntar qué demo ejecutar
    print("\nSelecciona una demo:")
    print("  1. Misma pregunta 5 veces (demo básica)")
    print("  2. Diferentes preguntas (algunas repetidas)")
    print("  3. Ver estadísticas del cache")
    print("  4. Todas las demos")
    print()
    
    choice = input("Opción (1/2/3/4): ").strip()
    
    if choice == "1":
        await demo_cache()
        await get_cache_stats()
    elif choice == "2":
        await demo_cache_different_questions()
        await get_cache_stats()
    elif choice == "3":
        await get_cache_stats()
    elif choice == "4":
        await demo_cache()
        print("\n")
        await demo_cache_different_questions()
        print("\n")
        await get_cache_stats()
    else:
        print("Opción inválida")


if __name__ == "__main__":
    asyncio.run(main())
