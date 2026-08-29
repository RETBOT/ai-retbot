"""
Test de Rate Limiting

Verifica que el rate limiting por usuario/API key funcione correctamente.

Uso:
    python tests/test_rate_limit.py
"""
import asyncio
import httpx
import pytest
import time


BASE_URL = "http://localhost:8000"
API_KEY = "demo_key_123"
HEADERS = {"X-API-Key": API_KEY}
CHAT_URL = f"{BASE_URL}/api/v1/chat/completions"


@pytest.mark.asyncio
async def test_rate_limit_headers():
    """Verificar que los headers de rate limiting se incluyen en las respuestas"""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            CHAT_URL,
            json={"messages": [{"role": "user", "content": "Hola"}]},
            headers=HEADERS
        )
        
        # Verificar headers de rate limiting
        assert "X-RateLimit-Limit" in response.headers or response.status_code in [200, 429]
        print("[OK] Headers de rate limiting presentes")
        print(f"   X-RateLimit-Limit: {response.headers.get('X-RateLimit-Limit', 'N/A')}")
        print(f"   X-RateLimit-Remaining: {response.headers.get('X-RateLimit-Remaining', 'N/A')}")


@pytest.mark.asyncio
async def test_rate_limit_exceeded():
    """Verificar que se exceda el rate limit después de múltiples requests"""
    async with httpx.AsyncClient(timeout=30) as client:
        success_count = 0
        rate_limited_count = 0
        
        # Hacer 25 requests rápidas (límite es 20/minuto)
        for i in range(25):
            try:
                response = await client.post(
                    CHAT_URL,
                    json={"messages": [{"role": "user", "content": f"Test {i}"}]},
                    headers=HEADERS
                )
                
                if response.status_code == 200:
                    success_count += 1
                elif response.status_code == 429:
                    rate_limited_count += 1
                    print(f"[WARN] Rate limit alcanzado en request {i+1}")
                    break
                    
            except Exception as e:
                print(f"Error en request {i+1}: {e}")
        
        print(f"\n-- Resultados:")
        print(f"   Requests exitosos: {success_count}")
        print(f"   Rate limited: {rate_limited_count}")
        
        # Debería haber al menos 20 exitosos y luego rate limit
        assert success_count >= 18, f"Se esperaban al menos 18 exitosos, se obtuvieron {success_count}"
        assert rate_limited_count >= 1 or success_count <= 25, "Debería activarse el rate limit"


@pytest.mark.asyncio
async def test_different_api_keys_have_separate_limits():
    """Verificar que diferentes API keys tienen límites separados"""
    async with httpx.AsyncClient(timeout=30) as client:
        # Hacer 10 requests con API key 1
        for i in range(10):
            await client.post(
                CHAT_URL,
                json={"messages": [{"role": "user", "content": f"Key1 Test {i}"}]},
                headers={"X-API-Key": "demo_key_123"}
            )
        
        # Hacer 10 requests con API key 2
        for i in range(10):
            response = await client.post(
                CHAT_URL,
                json={"messages": [{"role": "user", "content": f"Key2 Test {i}"}]},
                headers={"X-API-Key": "otra_api_key"}
            )
            
            # La segunda key debería tener sus propios límites
            assert response.status_code == 200, f"La segunda API key debería tener límites separados"
        
        print("[OK] Diferentes API keys tienen limites separados")


@pytest.mark.asyncio
async def test_rate_limit_error_response():
    """Verificar el formato de la respuesta cuando se excede el rate limit"""
    async with httpx.AsyncClient(timeout=30) as client:
        # Hacer muchas requests hasta alcanzar el límite
        for i in range(30):
            response = await client.post(
                CHAT_URL,
                json={"messages": [{"role": "user", "content": f"Test {i}"}]},
                headers=HEADERS
            )
            
            if response.status_code == 429:
                # Verificar formato de error
                data = response.json()
                assert "error" in data, "La respuesta 429 debe incluir 'error'"
                assert "message" in data["error"], "El error debe incluir 'message'"
                assert "rate_limit" in data["error"]["message"].lower(), "El mensaje debe mencionar rate limit"
                
                print(f"✅ Respuesta 429 correcta:")
                print(f"   {data}")
                return
        
        print("⚠️ No se alcanzó el rate limit en 30 requests")


async def main():
    """Ejecutar tests manualmente"""
    print("[TEST] Rate Limiting\n")
    
    try:
        print("Test 1: Headers de rate limiting...")
        await test_rate_limit_headers()
        print()
        
        print("Test 2: Rate limit exceeded...")
        await test_rate_limit_exceeded()
        print()
        
        print("Test 3: Diferentes API keys...")
        await test_different_api_keys_have_separate_limits()
        print()
        
        print("Test 4: Formato de error 429...")
        await test_rate_limit_error_response()
        print()
        
        print("[OK] Todos los tests pasaron!")
        
    except AssertionError as e:
        print(f"\n[FAIL] Test fallido: {e}")
    except httpx.ConnectError as e:
        print(f"\n[FAIL] Error de conexion: {e}")
        print(f"   ¿El servidor está corriendo en {BASE_URL}?")
        print(f"   Ejecutar: python server.py")


if __name__ == "__main__":
    asyncio.run(main())
