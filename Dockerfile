# Dockerfile para AI Coding Assistant API
# Incluye: Python API + OpenCode Proxy + Ollama

FROM oven/bun:1 AS base

# Evitar interacciones durante la instalación
ENV DEBIAN_FRONTEND=noninteractive

# Install Python and system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    git \
    zstd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy all project files
COPY . .

# Install Python dependencies
RUN python3 -m venv venv && \
    ./venv/bin/pip install --no-cache-dir -r requirements.txt

# Install Bun dependencies
RUN bun install opencode-llm-proxy

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Download model at build time
RUN ollama serve & sleep 10 && ollama pull qwen:0.5b

# Expose ports
EXPOSE 8000 4010 11435

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start all services - esperar que Ollama inicie primero
CMD ["sh", "-c", "ollama serve & sleep 5 && bunx opencode-llm-proxy & ./venv/bin/python server.py"]