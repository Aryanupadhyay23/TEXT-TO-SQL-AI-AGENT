# ==============================================================================
# Stage 1: Build React Frontend (Node 20 Alpine)
# ==============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Cache npm dependencies
COPY frontend/package*.json ./
RUN npm ci --prefer-offline --no-audit

# Build production static bundle (HTML, JS, CSS)
COPY frontend/ ./
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

# ==============================================================================
# Stage 2: Compile Python Dependencies (Isolated Build Environment)
# ==============================================================================
FROM python:3.12-slim AS backend-builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install compiler tools and strip utility to compile wheels and strip debug symbols
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    binutils \
    && rm -rf /var/lib/apt/lists/*

# Create isolated virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY backend/requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    # Strip unnecessary files, caches, and test suites to minimize disk footprint
    find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -name "*.pyc" -delete && \
    find /opt/venv -name "*.pyo" -delete && \
    find /opt/venv -name "*.so" -exec strip --strip-unneeded {} + 2>/dev/null || true

# ==============================================================================
# Stage 3: Ultra-Minimal Final Runtime (Nginx + FastAPI)
# ==============================================================================
FROM python:3.12-slim AS runner

# Install only minimal runtime requirements: Nginx web server and curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    curl \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Activate compiled virtual environment from builder stage
ENV PATH="/opt/venv/bin:$PATH"

# ------------------------------------------------------------------------------
# Memory & Low-RAM Optimizations
# ------------------------------------------------------------------------------
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONOPTIMIZE=1 \
    PYTHONUNBUFFERED=1 \
    MALLOC_ARENA_MAX=2 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    VECLIB_MAXIMUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    TOKENIZERS_PARALLELISM=false \
    PYTHONPATH=/app/backend

WORKDIR /app

# Copy compiled virtual environment from Stage 2 (no compiler tools in final image)
COPY --from=backend-builder /opt/venv /opt/venv

# Copy compiled React frontend bundle into /var/www/html and /usr/share/nginx/html
RUN rm -rf /etc/nginx/sites-enabled/* /etc/nginx/sites-available/* /var/www/html/*
COPY --from=frontend-builder /app/frontend/dist /var/www/html
RUN mkdir -p /var/www/html/chatbot /usr/share/nginx/html/chatbot && \
    cp -r /var/www/html/* /var/www/html/chatbot/ 2>/dev/null || true && \
    cp -r /var/www/html/* /usr/share/nginx/html/ 2>/dev/null || true

# Copy FastAPI backend code
COPY backend /app/backend

# Setup backend directories for sqlite checkpoints and ChromaDB
WORKDIR /app/backend
RUN mkdir -p /app/backend/chatbot/data/sqlite_storage /app/backend/chatbot/data/chroma

# Copy Nginx reverse proxy configuration and entrypoint
RUN rm -rf /etc/nginx/sites-enabled/* /etc/nginx/sites-available/* /etc/nginx/conf.d/*
COPY deploy/nginx/nginx.conf /etc/nginx/conf.d/default.conf

COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose Nginx on port 80 (Frontend + Proxied API) and FastAPI on port 8000
EXPOSE 80 8000

# Health check against FastAPI
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]