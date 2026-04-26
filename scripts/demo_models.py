#!/usr/bin/env python3
"""
Demo de Múltiples Modelos

Muestra cómo seleccionar y usar diferentes modelos dinámicamente.

Uso:
    python scripts/demo_models.py
"""

import asyncio
import httpx
from datetime import datetime


BASE_URL = "http://localhost:8000"
API_KEY = "demo_key_123"
HEADERS = {"X-API-Key": API_KEY}


async def list_available_models():
    """Listar modelos disponibles"""
    print("\n" + "="*70)
    print("📋 MODELOS DISPONIBLES")
    print("="*70)
    
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(f"{BASE_URL}/agent/models/available")
            
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                
                print(f"\nTotal de modelos: {data.get('count', 0)}")
                print(f"Modelo default: {data.get('default', 'N/A')}")
                print("\nModelos:")
                
                for model in models:
                    size_gb = model.get("size", 0) / (1024**3)
                    print(f"  • {model.get('id', 'unknown')}")
                    print(f"    Tamaño: {size_gb:.2f} GB")
                    print(f"    Modified: {model.get('modified_at', 'N/A')[:19]}")
                    print()
                
                return models
            else:
                print(f"❌ Error: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return []


async def recommend_model(task_type: str = "general"):
    """Obtener recomendación de modelo"""
    print("\n" + "="*70)
    print(f"💡 RECOMENDACIÓN PARA: {task_type.upper()}")
    print("="*70)
    
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(
                f"{BASE_URL}/agent/models/recommend",
                params={"task_type": task_type}
            )
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"\nTarea: {data.get('task_type', 'N/A')}")
                print(f"Modelo recomendado: {data.get('recommended', 'N/A')}")
                
                info = data.get("info", {})
                if info:
                    size_gb = info.get("size", 0) / (1024**3)
                    print(f"Tamaño: {size_gb:.2f} GB")
                
                return data.get("recommended")
            else:
                print(f"❌ Error: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return None


async def test_model(model_name: str, question: str):
    """Probar un modelo específico"""
    print("\n" + "="*70)
    print(f"🧪 PROBANDO MODELO: {model_name}")
    print("="*70)
    
    async with httpx.AsyncClient(timeout=300) as client:
        try:
            start = datetime.now()
            
            response = await client.post(
                f"{BASE_URL}/agent/chat/completions",
                json={
                    "messages": [{"role": "user", "content": question}],
                    "model": model_name
                },
                headers=HEADERS
            )
            
            elapsed = (datetime.now() - start).total_seconds()
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                print(f"\n⏱️  Tiempo: {elapsed:.2f}s")
                print(f"\n💬 Respuesta:")
                print(f"   {content[:200]}..." if len(content) > 200 else f"   {content}")
                
                # Verificar si vino del cache
                is_cached = "cache" in data.get("id", "").lower()
                if is_cached:
                    print(f"\n💾 Respuesta servida desde CACHE")
                
                return True
            else:
                print(f"❌ Error: HTTP {response.status_code}")
                print(f"   {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False


async def demo_model_selection():
    """Demo de selección automática de modelos"""
    print("\n" + "="*70)
    print("🎯 DEMO DE SELECCIÓN AUTOMÁTICA DE MODELOS")
    print("="*70)
    
    # Escenarios de prueba
    scenarios = [
        ("general", "¿Qué es Python?"),
        ("code", "¿Cómo creo una función en Python?"),
        ("fast", "¿Qué es 2+2?"),
        ("chat", "¿Cómo estás?"),
    ]
    
    async with httpx.AsyncClient(timeout=300) as client:
        for task_type, question in scenarios:
            print(f"\n📌 Escenario: {task_type}")
            print(f"Pregunta: {question}")
            
            # Obtener recomendación
            recommended = await recommend_model(task_type)
            
            if recommended:
                # Probar con el modelo recomendado
                await test_model(recommended, question)
            
            await asyncio.sleep(1)


async def demo_manual_model_selection():
    """Demo de selección manual de modelos"""
    print("\n" + "="*70)
    print("🎯 DEMO DE SELECCIÓN MANUAL DE MODELOS")
    print("="*70)
    
    # Listar modelos disponibles
    models = await list_available_models()
    
    if not models:
        print("\n⚠️  No hay modelos disponibles")
        return
    
    # Preguntar qué modelo probar
    print("\nModelos disponibles:")
    for i, model in enumerate(models, 1):
        print(f"  {i}. {model.get('id')}")
    
    print(f"  {len(models) + 1}. Probar todos")
    print()
    
    choice = input(f"Selecciona modelo (1-{len(models) + 1}): ").strip()
    
    if choice.isdigit():
        choice = int(choice)
        
        if choice == len(models) + 1:
            # Probar todos
            for model in models[:3]:  # Máximo 3 para no tardar mucho
                model_name = model.get("id")
                await test_model(model_name, "¿Qué es Python?")
                await asyncio.sleep(2)
        elif 1 <= choice <= len(models):
            model_name = models[choice - 1].get("id")
            await test_model(model_name, "¿Qué es Python?")
        else:
            print("Opción inválida")
    else:
        print("Opción inválida")


async def main():
    """Main"""
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║  RETBOT - Demo de Múltiples Modelos                       ║")
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
    print("  1. Selección automática (por tipo de tarea)")
    print("  2. Selección manual (elegir modelo)")
    print("  3. Ambas demos")
    print()
    
    choice = input("Opción (1/2/3): ").strip()
    
    if choice == "1":
        await demo_model_selection()
    elif choice == "2":
        await demo_manual_model_selection()
    elif choice == "3":
        await demo_model_selection()
        print("\n")
        await demo_manual_model_selection()
    else:
        print("Opción inválida")
    
    print("\n" + "="*70)
    print("✅ Demo completada")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
