# 🛠️ RETBOT MCP Server

RETBOT expone sus capacidades como **MCP Tools** (Model Context Protocol) para
que el agente (OpenCode + Ollama) las descubra y use automáticamente según la
solicitud del usuario. Ejemplo: si el usuario escribe *"analiza este problema
y busca la información necesaria"*, el agente decide por sí solo qué tools
llamar.

## Diseño

- **UNA capa, NO una reimplementación.** Cada MCP Tool delega en la lógica
  existente del proyecto (`core/`). No se duplica código.
- El **uso manual se mantiene intacto**: CLI, API REST, Web UI y el endpoint
  de función calling (`/api/v1/chat`) siguen funcionando igual.
- Es un **MCP Server tipo `stdio`**: corre como proceso local del agente.
- **Seguridad por defecto**: solo tools de lectura + filesystem. Las tools de
  escritura admin se habilitan explícitamente con un flag.

## Cómo funciona

```
OpenCode (cliente MCP)
    │   stdio (JSON-RPC / líneas)
    ▼
retbot_mcp/server.py (servidor MCP)
    │
    ├── core/tools/executor.py     → read/write/edit/list/execute
    ├── core/health.py             → system.health / system.info
    ├── core/model_manager.py      → models.list
    ├── core/cache.py              → cache.stats
    └── core/database.py           → admin.* / apikey.*
```

## Ejecución

```bash
python retbot_mcp/server.py
```

Variables de entorno opcionales:

| Variable | Default | Descripción |
|----------|---------|-------------|
| `MCP_WORKING_DIR` | cwd | Directorio base de las file tools (path traversal protected) |
| `MCP_ENABLE_ADMIN_WRITE` | `false` | `true` habilita `apikey.create`, `apikey.revoke` y `cache.clear` |

Estas variables también se pueden definir en `.env` (`core/config.py`).

## Tools disponibles

### Por defecto (12)

| Tool | Qué hace | Reutiliza |
|------|----------|-----------|
| `read_file(path)` | Lee un archivo de texto del proyecto | `core/tools/executor.py` |
| `write_file(path, content)` | Crea/sobrescribe un archivo (crea dirs) | `core/tools/executor.py` |
| `edit_file(path, old_string, new_string)` | Reemplaza la 1ª ocurrencia exacta | `core/tools/executor.py` |
| `list_directory(path=".")` | Lista contenido del directorio | `core/tools/executor.py` |
| `execute_command(command, timeout=30)` | Ejecuta comandos de la whitelist | `core/tools/executor.py` |
| `system.health` | Estado de Ollama y la BD (rápido) | `core/health.py` |
| `system.info` | Config del servidor (modelo, puerto, uptime) | `core/config.py` |
| `models.list` | Modelos disponibles en Ollama | `core/model_manager.py` |
| `cache.stats` | Métricas del cache (hits, misses, hit rate) | `core/cache.py` |
| `admin.list_users` | Usuarios registrados (sin passwords) | `core/database.py` |
| `admin.audit_logs(limit=20)` | Logs de auditoría recientes | `core/database.py` |
| `apikey.list` | API Keys (nunca expone el valor/hash) | `core/database.py` |

### Bajo flag `MCP_ENABLE_ADMIN_WRITE=true` (+3)

| Tool | Qué hace |
|------|----------|
| `apikey.create(username, name)` | Crea API Key (la devuelve 1 sola vez) |
| `apikey.revoke(key_id)` | Revoca una API Key |
| `cache.clear` | Limpia todo el cache |

**Nota**: `apikey.create` requiere el `username` (consúltalo con
`admin.list_users`). La key completa se muestra UNA sola vez.

## Formato de respuesta

Todas las tools responden con estructura consistente para que el agente
pueda procesarlas sin adivinar:

```json
{ "success": true,  "...": "datos de la tool" }
{ "success": false, "error": "mensaje corto", "details": "contexto extra" }
```

## Configuración en OpenCode

### Opción A: Automática (recomendada)

```bash
python scripts/setup_opencode.py --api-key key_TU_API_KEY
```

Detecta el OS, el python del venv, y la URL (`PUBLIC_URL` del `.env` o
`localhost:PORT`), y genera `opencode.json` completo.

### Opción B: Manual

Bloque `mcp` en `opencode.json` (ver también `opencode.json.example`):

```json
"mcp": {
  "retbot": {
    "type": "local",
    "command": ["python", "retbot_mcp/server.py"],
    "enabled": true,
    "environment": {
      "MCP_WORKING_DIR": ".",
      "MCP_ENABLE_ADMIN_WRITE": "false"
    }
  }
}
```

> En Windows la ruta real del python del venv suele ser
> `C:\ruta\al\proyecto\venv\Scripts\python.exe`.

## Tests

```bash
python -m pytest tests/test_mcp.py -v
```

Cubren: registro de tools (12 y 15), file tools vía MCP, system/modelos/cache,
DB tools, validación Pydantic, flag de seguridad y **E2E por stdio**
(arrancan el server real como subprocess y hacen el handshake MCP completo).

> Los tests NO requieren Ollama ni Redis corriendo: las tools heredan la
> tolerancia a errores de la lógica existente (health y model_manager
> devuelven fallback en vez de crashear).

## Troubleshooting

| Problema | Causa / Fix |
|----------|-------------|
| `No module named 'core'` al correr el server | El server ya hace path bootstrap; verifica que lo lanzas como `python retbot_mcp/server.py` desde el proyecto |
| Las tools de admin no aparecen | `MCP_ENABLE_ADMIN_WRITE` no está en `true` (o `false`/vacío) |
| `No module named 'mcp'` | Falta instalar dependencias: `pip install -r requirements.txt` |
| OpenCode no muestra las tools | Reinicia OpenCode tras crear `opencode.json` (el MCP se carga al inicio) |
| `psutil` no importa | `pip install psutil` (está en requirements.txt) |

## Nota de diseño: ¿por qué `retbot_mcp/` y no `mcp/`?

El SDK oficial de MCP de Python se llama `mcp`. Si el proyecto tuviera un
directorio `mcp/`, ocultaría al SDK (module shadowing) y rompería cualquier
`import mcp` (incluido el propio servidor). Por eso el paquete local se llama
`retbot_mcp/`.