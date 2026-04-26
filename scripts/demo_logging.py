#!/usr/bin/env python3
"""
Demo de Logging Estructurado

Muestra cómo funciona el logging estructurado con correlation IDs.

Uso:
    python scripts/demo_logging.py
"""

import asyncio
import logging
import time
from core.logging_config import (
    setup_logging,
    logger,
    set_correlation_id,
    add_extra_context,
    clear_correlation_id,
    with_correlation_id
)


def demo_basic_logging():
    """Demo de logging básico"""
    print("\n" + "="*70)
    print("📝 DEMO DE LOGGING BÁSICO")
    print("="*70)
    
    # Configurar logging
    setup_logging(level="DEBUG", format_type="colored")
    
    logger.debug("Este es un mensaje DEBUG")
    logger.info("Este es un mensaje INFO")
    logger.warning("Este es un mensaje WARNING")
    logger.error("Este es un mensaje ERROR")
    logger.critical("Este es un mensaje CRITICAL")


def demo_json_logging():
    """Demo de logging en formato JSON"""
    print("\n" + "="*70)
    print("📝 DEMO DE LOGGING JSON")
    print("="*70)
    print("\nLogs en formato JSON (listos para producción):\n")
    
    # Configurar logging JSON
    setup_logging(level="INFO", format_type="json")
    
    logger.info("Usuario inició sesión")
    logger.info("Procesando payment", extra={"extra_context": {"user_id": "123", "amount": 99.99}})
    logger.warning("Intento de login fallido", extra={"extra_context": {"username": "admin", "ip": "192.168.1.1"}})
    
    try:
        # Simular error
        raise ValueError("Error de prueba")
    except Exception as e:
        logger.error(f"Error procesando request: {e}", exc_info=True)


@with_correlation_id
async def process_request(request_id: int):
    """
    Simular procesamiento de request con correlation ID.
    
    El decorador agrega automáticamente correlation ID.
    """
    logger.info(f"Procesando request {request_id}")
    
    # Simular trabajo
    await asyncio.sleep(0.1)
    
    logger.info(f"Request {request_id} completado")


async def demo_correlation_id():
    """Demo de correlation IDs"""
    print("\n" + "="*70)
    print("📝 DEMO DE CORRELATION IDS")
    print("="*70)
    print("\nCada request tiene su propio ID para追踪:\n")
    
    # Configurar logging
    setup_logging(level="INFO", format_type="colored")
    
    # Simular múltiples requests en paralelo
    tasks = [process_request(i) for i in range(1, 6)]
    await asyncio.gather(*tasks)


async def demo_middleware():
    """Demo de middleware de logging"""
    print("\n" + "="*70)
    print("📝 DEMO DE MIDDLEWARE DE LOGGING")
    print("="*70)
    print("\nEl middleware agrega correlation ID automáticamente:\n")
    
    from fastapi import FastAPI, Request
    from core.logging_config import LoggingMiddleware, setup_logging
    
    # Configurar logging
    setup_logging(level="INFO", format_type="colored")
    
    # Crear app con middleware
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)
    
    @app.get("/test")
    async def test_endpoint(request: Request):
        logger.info("Endpoint /test llamado")
        return {"message": "OK"}
    
    # Simular requests
    from starlette.testclient import TestClient
    
    with TestClient(app) as client:
        for i in range(3):
            response = client.get("/test")
            print(f"  Response {i+1}: {response.status_code}")
    
    print("\n✅ Cada request tuvo su propio correlation ID")


def demo_extra_context():
    """Demo de contexto adicional"""
    print("\n" + "="*70)
    print("📝 DEMO DE CONTEXTO ADICIONAL")
    print("="*70)
    print("\nAgregando información extra a los logs:\n")
    
    # Configurar logging
    setup_logging(level="INFO", format_type="colored")
    
    # Simular flujo de usuario
    user_id = "user_123"
    session_id = "session_456"
    
    add_extra_context(user_id=user_id, session_id=session_id)
    
    logger.info("Usuario autenticado")
    logger.info("Usuario cargando dashboard")
    logger.info("Usuario ejecutando query")
    
    # Limpiar contexto
    clear_extra_context()
    
    logger.info("Usuario cerró sesión (sin contexto)")


async def main():
    """Main"""
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║  RETBOT - Demo de Logging Estructurado                     ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    print("\nSelecciona una demo:")
    print("  1. Logging básico (niveles)")
    print("  2. Logging JSON (producción)")
    print("  3. Correlation IDs")
    print("  4. Middleware de logging")
    print("  5. Contexto adicional")
    print("  6. Todas las demos")
    print()
    
    choice = input("Opción (1/2/3/4/5/6): ").strip()
    
    if choice == "1":
        demo_basic_logging()
    elif choice == "2":
        demo_json_logging()
    elif choice == "3":
        await demo_correlation_id()
    elif choice == "4":
        await demo_middleware()
    elif choice == "5":
        demo_extra_context()
    elif choice == "6":
        demo_basic_logging()
        print("\n")
        demo_json_logging()
        print("\n")
        await demo_correlation_id()
        print("\n")
        await demo_middleware()
        print("\n")
        demo_extra_context()
    else:
        print("Opción inválida")
    
    print("\n" + "="*70)
    print("✅ Demo completada")
    print("="*70)
    print("\n📚 Logs guardados en: logs/server.log")
    print("📖 Más info: docs/LOGGING_GUIDE.md (próximamente)\n")


if __name__ == "__main__":
    asyncio.run(main())
