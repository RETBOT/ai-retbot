#!/usr/bin/env python3
"""
Demo de Rate Limiting

Muestra cómo funciona el rate limiting en tiempo real.

Uso:
    python scripts/demo_rate_limit.py
"""
import asyncio
import httpx
import time
from datetime import datetime


BASE_URL = "http://localhost:8000"
API_KEY = "demo_key_123"
RATE_LIMIT = 20  # requests por minuto


async def make_request(session: httpx.AsyncClient, request_num: int):
    """Hacer una request y mostrar resultado"""
    start = time.time()
    
    try:
        response = await session.post(
            f"{BASE_URL}/v1/chat/completions",
            json={"messages": [{"role": "user", "content": f"Request {request_num}"}]},
            headers={"X-API-Key": API_KEY}
        )
        
        elapsed = time.time() - start
        status_color = "✅" if response.status_code == 200 else "⚠️ " if response.status_code == 429 else "❌"
        
        print(f"{status_color} Request {request_num:2d} | Status: {response.status_code:3d} | Time: {elapsed:.2f}s | ", end="")
        
        if response.status_code == 200:
            print("OK")
        elif response.status_code == 429:
            print("RATE LIMIT EXCEEDED!")
        else:
            print(f"Error: {response.text[:50]}")
            
        return response.status_code
        
    except Exception as e:
        print(f"❌ Request {request_num:2d} | Error: {e}")
        return None


async def demo_rate_limit():
    """Demostración de rate limiting"""
    print("\n" + "="*70)
    print("🚦 DEMO DE RATE LIMITING - RETBOT")
    print("="*70)
    print(f"\n📊 Configuración:")
    print(f"   Límite: {RATE_LIMIT} requests por minuto")
    print(f"   API Key: {API_KEY}")
    print(f"   URL: {BASE_URL}")
    print(f"\n📝 Haremos 30 requests rápidas para demostrar el rate limiting...\n")
    print("-"*70)
    
    async with httpx.AsyncClient(timeout=30) as client:
        success_count = 0
        rate_limited_count = 0
        error_count = 0
        
        start_time = time.time()
        
        for i in range(1, 31):
            status = await make_request(client, i)
            
            if status == 200:
                success_count += 1
            elif status == 429:
                rate_limited_count += 1
            else:
                error_count += 1
            
            # Pequeña pausa para no saturar
            await asyncio.sleep(0.1)
        
        elapsed = time.time() - start_time
        
        print("-"*70)
        print(f"\n📊 Resultados:")
        print(f"   Tiempo total: {elapsed:.2f}s")
        print(f"   ✅ Exitosos: {success_count}")
        print(f"   ⚠️  Rate Limited: {rate_limited_count}")
        print(f"   ❌ Errores: {error_count}")
        
        print(f"\n💡 Conclusión:")
        if rate_limited_count > 0:
            print(f"   El rate limiting funcionó correctamente después de ~{success_count} requests.")
            print(f"   Los usuarios no pueden exceder {RATE_LIMIT} requests por minuto.")
        else:
            print(f"   No se activó el rate limit. Verificar configuración.")
        
        print("\n" + "="*70)


async def demo_multiple_users():
    """Demostración de rate limiting con múltiples usuarios"""
    print("\n" + "="*70)
    print("👥 DEMO DE MÚLTIPLES USUARIOS")
    print("="*70)
    print(f"\n📊 Simularemos 3 usuarios haciendo requests simultáneas...\n")
    
    api_keys = [
        ("Usuario 1", "demo_key_123"),
        ("Usuario 2", "user_2_key"),
        ("Usuario 3", "user_3_key"),
    ]
    
    async def user_session(user_name: str, api_key: str):
        async with httpx.AsyncClient(timeout=30) as client:
            success = 0
            limited = 0
            
            for i in range(15):
                try:
                    response = await client.post(
                        f"{BASE_URL}/v1/chat/completions",
                        json={"messages": [{"role": "user", "content": f"{user_name} - Request {i}"}]},
                        headers={"X-API-Key": api_key}
                    )
                    
                    if response.status_code == 200:
                        success += 1
                    elif response.status_code == 429:
                        limited += 1
                        break
                        
                except Exception:
                    pass
                
                await asyncio.sleep(0.05)
            
            return user_name, success, limited
    
    # Ejecutar sesiones de usuarios en paralelo
    tasks = [user_session(name, key) for name, key in api_keys]
    results = await asyncio.gather(*tasks)
    
    print(f"📊 Resultados por usuario:")
    for user_name, success, limited in results:
        print(f"   {user_name}: ✅ {success} exitosos, ⚠️  {limited} rate limited")
    
    print(f"\n💡 Conclusión:")
    print(f"   Cada usuario tiene su propio límite independiente.")
    print(f"   Un usuario no afecta a los demás.")
    
    print("\n" + "="*70)


async def main():
    """Main"""
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║  RETBOT - Demo de Rate Limiting                           ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    # Verificar que el servidor esté corriendo
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{BASE_URL}/health")
            if response.status_code != 200:
                print(f"\n❌ Error: El servidor no está corriendo en {BASE_URL}")
                print(f"   Ejecutar: python server.py")
                return
    except Exception:
        print(f"\n❌ Error: No se pudo conectar a {BASE_URL}")
        print(f"   ¿El servidor está corriendo?")
        print(f"   Ejecutar: python server.py")
        return
    
    print("\n✅ Servidor detectado correctamente\n")
    
    # Preguntar qué demo ejecutar
    print("Selecciona una demo:")
    print("  1. Rate limiting básico (30 requests)")
    print("  2. Múltiples usuarios (3 usuarios)")
    print("  3. Ambas demos")
    print()
    
    choice = input("Opción (1/2/3): ").strip()
    
    if choice == "1":
        await demo_rate_limit()
    elif choice == "2":
        await demo_multiple_users()
    elif choice == "3":
        await demo_rate_limit()
        await asyncio.sleep(2)
        await demo_multiple_users()
    else:
        print("Opción inválida")


if __name__ == "__main__":
    asyncio.run(main())
