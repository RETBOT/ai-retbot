#!/usr/bin/env python
"""
setup_opencode.py - Genera opencode.json portable para RETBOT + MCP

Detecta automáticamente:
  1. El intérprete de Python del venv del proyecto (Windows/Linux/Mac)
  2. La URL pública (PUBLIC_URL del .env, o localhost:PORT por defecto)

Genera opencode.json listo para OpenCode con:
  - Provider "retbot" (baseURL correcto, sin hardcodear host)
  - MCP Server "retbot-mcp" (command apuntando al python del venv)

Uso:
  python scripts/setup_opencode.py                 # genera opencode.json
  python scripts/setup_opencode.py --api-key KEY   # incluye la API key
  python scripts/setup_opencode.py --print         # solo imprime, no escribe

Funciona en cualquier VPS o computadora local.
"""

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent


def find_venv_python() -> list:
    """Localizar el python del venv en cualquier plataforma."""
    candidates = [
        PROJECT_DIR / "venv" / "Scripts" / "python.exe",   # Windows
        PROJECT_DIR / "venv" / "bin" / "python",           # Linux/Mac
        PROJECT_DIR / ".venv" / "Scripts" / "python.exe",  # Windows (.venv)
        PROJECT_DIR / ".venv" / "bin" / "python",          # Linux/Mac (.venv)
    ]
    for cand in candidates:
        if cand.exists():
            return [str(cand)]

    # Fallback: python del PATH actual
    return [sys.executable]


def mcp_server_command() -> list:
    """Comando para arrancar el MCP server (retbot_mcp/server.py)."""
    return find_venv_python() + [str(PROJECT_DIR / "retbot_mcp" / "server.py")]


def read_env(key: str, default: str = "") -> str:
    """Leer una variable del .env sin importar pydantic ni exponer secretos."""
    env_file = PROJECT_DIR / ".env"
    if not env_file.exists():
        return default
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
    return default


def build_config(api_key: str, print_only: bool) -> dict:
    """Construir la configuración completa de OpenCode."""
    port = read_env("PORT", "8000")
    model = read_env("MODEL_NAME", "llama3.1:8b")
    public_url = read_env("PUBLIC_URL", "")

    if not api_key:
        # Si el usuario no dio key, indicar placeholder para reemplazar
        api_key = "TU_API_KEY_AQUI"

    if public_url:
        base_url = f"{public_url.rstrip('/')}/api/v1"
        api_url_display = public_url
    else:
        base_url = f"http://localhost:{port}/api/v1"
        api_url_display = f"http://localhost:{port}"

    venv_python = mcp_server_command()

    config = {
        "$schema": "https://opencode.ai/config.json",
        "model": f"retbot/{model}",
        "provider": {
            "retbot": {
                "name": "RETBOT",
                "npm": "@ai-sdk/openai-compatible",
                "options": {
                    "baseURL": base_url,
                    "headers": {
                        "X-API-Key": api_key,
                    },
                },
                "models": {
                    model: {"name": model},
                },
            }
        },
        "mcp": {
            "retbot": {
                "type": "local",
                "command": venv_python,
                "enabled": True,
                "environment": {
                    "MCP_WORKING_DIR": str(PROJECT_DIR),
                },
            }
        },
        "agent": {
            "retbot": {
                "name": "RETBOT",
                "prompt": (
                    "You are RETBOT, an expert AI coding assistant. "
                    "Use the MCP tools available when you need to read or "
                    "write files, explore the project, run commands, or "
                    "diagnose the system."
                ),
                "description": "Expert AI coding assistant with MCP tool access",
                "mode": "primary",
                "tools": {"mcp": True},
            }
        },
    }

    if print_only:
        print(json.dumps(config, indent=2, ensure_ascii=False))
        print("\n# API unica:")
        print(f"#   {api_url_display}")
        print(f"# MCP server: {' '.join(venv_python)}")
        print("#   (Si API_KEY esta como 'TU_API_KEY_AQUI', reemplazala por tu key real)")
        return config

    # Escribir opencode.json
    out = PROJECT_DIR / "opencode.json"
    out.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[OK] opencode.json generado: {out}")
    print(f"     Base URL : {base_url}")
    print(f"     Modelo   : {model}")
    print(f"     MCP      : {' '.join(venv_python)}")
    if api_key == "TU_API_KEY_AQUI":
        print("     [!] Reemplaza 'TU_API_KEY_AQUI' por tu API key real en opencode.json")
    else:
        print("     [*] API key incluida")
    print("")
    print("     Reinicia OpenCode para cargar el MCP server.")
    return config


def main():
    parser = argparse.ArgumentParser(
        description="Genera opencode.json portable para RETBOT + MCP"
    )
    parser.add_argument("--api-key", default="", help="API key de RETBOT (opcional)")
    parser.add_argument("--print", action="store_true", help="Solo imprimir, no escribir")
    args = parser.parse_args()

    build_config(args.api_key, print_only=args.print)


if __name__ == "__main__":
    main()