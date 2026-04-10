import os
import subprocess
import requests
import time
import shutil

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "phi3:mini")


def find_ollama():
    ollama_path = shutil.which("ollama")
    if ollama_path:
        return ollama_path

    possible_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
        os.path.expandvars(r"%USERPROFILE%\AppData\Local\Programs\Ollama\ollama.exe"),
        r"C:\Program Files\Ollama\ollama.exe",
        r"C:\Program Files (x86)\Ollama\ollama.exe",
        os.path.expanduser(r"~\AppData\Local\Ollama\ollama.exe"),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def is_ollama_running():
    try:
        requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        return True
    except:
        return False


def start_ollama():
    if is_ollama_running():
        print(f"✅ Ollama ya corriendo en {OLLAMA_URL}")
        return True

    ollama_exec = find_ollama()

    if not ollama_exec:
        print("❌ Ollama no encontrado")
        print("   Instálalo desde: https://ollama.com/download")
        return False

    print(f"🚀 Iniciando Ollama: {ollama_exec}")

    try:
        subprocess.Popen([ollama_exec, "serve"], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"❌ Error iniciando Ollama: {e}")
        return False

    for i in range(30):
        if is_ollama_running():
            print(f"✅ Ollama listo ({i+1}s)")
            return True
        time.sleep(1)

    print("❌ Ollama no respondio a tiempo")
    return False


def ensure_model():
    try:
        res = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"] for m in res.json().get("models", [])]
    except:
        models = []

    if MODEL_NAME not in models:
        print(f"⬇️ Descargando {MODEL_NAME}...")
        print("   (Esto puede tomar varios minutos)")
        result = subprocess.run(
            ["ollama", "pull", MODEL_NAME],
            capture_output=False
        )
        if result.returncode != 0:
            print(f"❌ Error descargando modelo")
            return False
    else:
        print(f"✅ Modelo {MODEL_NAME} listo")

    return True


def init_ollama():
    if not start_ollama():
        raise Exception("No se pudo iniciar Ollama")

    if not ensure_model():
        raise Exception("No se pudo cargar el modelo")

    print(f"\n🎉 Servidor listo!")
    print(f"   URL: {OLLAMA_URL}")
    print(f"   Modelo: {MODEL_NAME}")
