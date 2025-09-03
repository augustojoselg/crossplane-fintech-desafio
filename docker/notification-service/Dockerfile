# =============================================================================
# NOTIFICATION SERVICE - DOCKERFILE
# =============================================================================
# Multi-stage build para otimização de tamanho e segurança
# =============================================================================

# =============================================================================
# STAGE 1: BUILD STAGE
# =============================================================================
FROM python:3.11-slim as builder

# Definir variáveis de ambiente para build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar dependências de sistema necessárias para build
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Criar diretório de trabalho
WORKDIR /app

# Copiar arquivos de dependências
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --user --no-cache-dir -r requirements.txt

# =============================================================================
# STAGE 2: RUNTIME STAGE
# =============================================================================
FROM python:3.11-slim as runtime

# Definir variáveis de ambiente para runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/appuser/.local/bin:$PATH" \
    PYTHONPATH="/app"

# Criar usuário não-root para segurança
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Instalar dependências de runtime
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Criar diretório de trabalho
WORKDIR /app

# Copiar dependências instaladas do stage de build
COPY --from=builder /root/.local /home/appuser/.local

# Copiar código da aplicação
COPY --chown=appuser:appuser . .

# Mudar para usuário não-root
USER appuser

# Expor porta da aplicação
EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

# Comando de inicialização
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]
