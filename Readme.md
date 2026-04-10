# 🤖 AI Coding Agent

> Agente de IA local compatible con OpenCode usando Ollama

---

## 📁 Estructura del Proyecto

```
ai/
├── server.py          # API FastAPI
├── agent.py          # Lógica del agente
├── tools.py          # Herramientas del agente
├── ollama_init.py    # Auto-inicio de Ollama
├── requirements.txt  # Dependencias Python
├── opencode.json     # Config para OpenCode
└── venv/             # Entorno virtual
```

---

## 🏗️ Arquitectura

```
┌─────────────┐
│  OpenCode   │ (u otro cliente OpenAI)
└──────┬──────┘
       │ HTTP
       ▼
┌─────────────┐
│ FastAPI     │ server.py (puerto 8000)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Agent    │ agent.py
└──────┬──────┘
       │ Tools
       ▼
┌─────────────┐
│   Ollama   │ phi3:mini (puerto 11434)
└─────────────┘
```

---

## 📦 Requisitos

- Python 3.10+
- Ollama instalado
- Windows 10+ / Linux / macOS

---

## 🚀 Instalación

### 1. Clonar/Copiar el proyecto

```bash
cd ai
```

### 2. Crear entorno virtual

```bash
python -m venv venv
```

### 3. Activar entorno

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/macOS:**
```bash
source venv/bin/activate
```

### 4. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 5. Instalar Ollama

Descarga desde: https://ollama.com/download

### 6. Descargar modelo

```bash
ollama pull phi3:mini
```

---

## 🚀 Inicio Rápido

### Opción 1: Manual

```bash
# Terminal 1: Activar entorno y ejecutar
venv\Scripts\activate
uvicorn server:app --reload
```

Ollama se inicia automáticamente.

### Opción 2: Script automático

```bash
start.bat
```

---

## 🔧 Configuración

### Variables de Entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://localhost:11434` | URL de Ollama |
| `MODEL_NAME` | `phi3:mini` | Modelo a usar |
| `PORT` | `8000` | Puerto del servidor |
| `API_KEY` | `None` | API key opcional |

### Ejemplo

```bash
export OLLAMA_URL=http://192.168.1.100:11434
export MODEL_NAME=qwen2.5:3b
export PORT=8000
```

---

## 🧰 Herramientas del Agente

El agente puede usar las siguientes herramientas automáticamente:

### read_file
Lee contenido de archivos.
```json
{"tool": "read_file", "path": "server.py", "offset": 0, "limit": 200}
```

### write_file
Crea o sobrescribe archivos.
```json
{"tool": "write_file", "path": "test.py", "content": "print('hello')"}
```

### glob
Busca archivos por patrón.
```json
{"tool": "glob", "pattern": "**/*.py"}
```

### grep
Busca texto en archivos.
```json
{"tool": "grep", "pattern": "FastAPI", "include": "*.py"}
```

### bash
Ejecuta comandos de terminal.
```json
{"tool": "bash", "command": "python test.py"}
```

### list_files
Lista contenido de directorio.
```json
{"tool": "list_files"}
```

---

## 📡 Endpoints

### GET /
Estado del servidor.

```bash
curl http://localhost:8000/
```

### GET /health
Verifica conexión con Ollama.

```bash
curl http://localhost:8000/health
```

### GET /v1/models
Lista modelos disponibles.

```bash
curl http://localhost:8000/v1/models
```

### POST /v1/chat/completions
Chat con streaming.

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "phi3:mini",
    "messages": [{"role": "user", "content": "Hola"}],
    "stream": false
  }'
```

---

## 🔌 Uso con OpenCode

### 1. Copiar configuración

**Windows:**
```powershell
copy opencode.json "$env:USERPROFILE\.config\opencode\opencode.json"
```

**Linux/macOS:**
```bash
cp opencode.json ~/.config/opencode/opencode.json
```

### 2. Iniciar OpenCode

```bash
opencode
```

### 3. Seleccionar modelo

```
/models
```

Selecciona: `phi3:mini`

---

## 🧪 Ejemplos de Uso

### Ejemplo 1: Chat básico

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "phi3:mini", "messages": [{"role": "user", "content": "Explica qué hace FastAPI"}]}'
```

### Ejemplo 2: Streaming

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "phi3:mini", "messages": [{"role": "user", "content": "Cuenta hasta 10"}], "stream": true}'
```

---

## ⚠️ Troubleshooting

### ❌ "Ollama not available"

**Solución:**
```bash
ollama serve
```

### ❌ "Module not found"

**Solución:**
```bash
pip install -r requirements.txt
```

### ❌ OpenCode no responde

1. Verifica que el servidor esté corriendo
2. Prueba `/health`
3. Revisa que el modelo esté en `opencode.json`

### ❌ Modelo muy lento

- Usa un modelo más pequeño
- Cierra otras aplicaciones

### ❌ Error 401 (API Key)

Si configuraste `API_KEY`:
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer tu-api-key" \
  -d '...'
```

---

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama (`git checkout -b feature/nueva`)
3. Commit (`git commit -am 'Agrega feature'`)
4. Push (`git push origin feature/nueva`)
5. Abre un Pull Request

---

## 📄 Licencia

MIT License

---

## 🙏 Créditos

- [Ollama](https://ollama.com) - Motor de IA local
- [OpenCode](https://opencode.ai) - Coding agent
- [FastAPI](https://fastapi.tiangolo.com) - Framework web
