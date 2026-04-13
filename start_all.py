#!/usr/bin/env python3
"""
Script para iniciar API + OpenCode LLM Proxy juntos
"""
import subprocess
import time
import sys
import os

def start_api():
    """Iniciar el servidor API"""
    print("[API] Iniciando servidor en puerto 8000...")
    return subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )

def start_proxy():
    """Iniciar opencode-llm-proxy en puerto 4010"""
    print("[PROXY] Iniciando OpenCode LLM Proxy en puerto 4010...")
    return subprocess.Popen(
        ["npx", "opencode-llm-proxy"],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )

def main():
    processes = []
    
    try:
        # Iniciar API
        api_process = start_api()
        processes.append(api_process)
        
        # Esperar a que la API este lista
        time.sleep(5)
        
        # Iniciar proxy
        proxy_process = start_proxy()
        processes.append(proxy_process)
        
        print("\n=== Servicios iniciados ===")
        print("   - API: http://localhost:8000")
        print("   - Proxy: http://localhost:4010")
        print("   - Ollama: http://localhost:11435")
        print("\nPresiona Ctrl+C para detener todos los servicios...")
        
        # Mantener procesos corriendo
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nDeteniendo servicios...")
        for p in processes:
            p.terminate()
        print("Servicios detenidos")

if __name__ == "__main__":
    main()