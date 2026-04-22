# syntax=docker/dockerfile:1
# Multi-stage build for Ratio MCP Server

FROM python:3.10-slim-bullseye AS base

# Set env vars for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        ca-certificates \
        apt-transport-https \
        unixodbc \
        unixodbc-dev \
        libgssapi-krb5-2 \
        libunwind8 \
        software-properties-common && \
    update-ca-certificates

    # Add Microsoft package signing key and repository for Debian 11
RUN mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/microsoft-debian-bullseye-prod bullseye main" > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18

    # Install minimal Python packages early for pyodbc test (optional)
RUN pip install --no-cache-dir pyodbc pandas

# Clean up apt caches
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests first for layer caching
COPY pyproject.toml requirements.txt ./

# Install dependencies. Prefer requirements.txt if present for deterministic build.
RUN pip install --upgrade pip && \
    if [ -f requirements.txt ]; then pip install -r requirements.txt; fi && \
    pip install . || true

    # Create non-root user
RUN useradd -r -u 1000 appuser && chown -R appuser /app
USER appuser

# Copy source
# COPY src ./src
# COPY introspect_fastmcp.py ./
# COPY README.md ./
COPY . .

# Final working directory set to src so package imports like 'from a2a_framework...' work
WORKDIR /app/src

# Expose port (Azure Container Apps will map)
EXPOSE 8000

# Healthcheck (optional simple TCP)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# # Switch to non-root
# USER appuser

# Default envs (can override at deploy time)
ENV MCP_SERVER_HOST=0.0.0.0 \
    MCP_SERVER_PORT=8000

# Entrypoint
CMD ["python", "server.py"]
