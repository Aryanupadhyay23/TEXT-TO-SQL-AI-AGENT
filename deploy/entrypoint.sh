#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "Starting Text-to-SQL AI Chatbot Services (Memory-Optimized)"
echo "=========================================================="

# Limit container internal Nginx to a single worker process to conserve RAM
sed -i 's/worker_processes auto;/worker_processes 1;/' /etc/nginx/nginx.conf 2>/dev/null || true
rm -rf /etc/nginx/sites-enabled/* /etc/nginx/sites-available/* 2>/dev/null || true

# Start container internal Nginx in background to serve React frontend & reverse-proxy API/SSE
echo "Starting container internal Nginx web server (1 worker)..."
nginx

# Setup Python environment
export PYTHONPATH="/app/backend:${PYTHONPATH}"
cd /app/backend

# Graceful termination handler
trap "echo 'Stopping container services...'; nginx -s quit; kill -TERM 0" SIGINT SIGTERM

# Ensure ChromaDB vector database is initialized and up to date with new files
echo "Checking ChromaDB vectorstore status..."
if [ "${SKIP_CHROMA_TRAIN:-false}" = "true" ] || [ "${CI:-false}" = "true" ]; then
    echo "ChromaDB training skipped (CI smoke test environment)."
elif [ ! -d "/app/backend/chatbot/data/chroma" ] || [ -z "$(ls -A /app/backend/chatbot/data/chroma 2>/dev/null)" ]; then
    echo "ChromaDB vectorstore not found. Indexing all schema files in background..."
    (python chatbot/scripts/train_chroma.py --force && echo "ChromaDB initial indexing completed.") || echo "Warning: ChromaDB training notice." &
else
    echo "ChromaDB vectorstore detected. Running incremental sync for new/updated schema files in background..."
    (python chatbot/scripts/train_chroma.py && echo "ChromaDB incremental sync completed.") || echo "Warning: ChromaDB sync notice." &
fi

# If persistent SQLite storage directory exists, ensure checkpoints are saved there
if [ -d "/app/backend/chatbot/data/sqlite_storage" ]; then
    export SQLITE_CHECKPOINT_PATH="/app/backend/chatbot/data/sqlite_storage/checkpoints.sqlite"
    echo "Using persistent SQLite checkpointer path: ${SQLITE_CHECKPOINT_PATH}"
fi

# Subpath root path for FastAPI Swagger UI and reverse proxy routing
ROOT_PATH="${FASTAPI_ROOT_PATH:-/chatbot-backend}"

echo "Starting FastAPI backend via Uvicorn (workers: 1, root-path: ${ROOT_PATH})..."
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --root-path "${ROOT_PATH}" \
    --proxy-headers \
    --forwarded-allow-ips='*' \
    --workers 1 \
    --limit-concurrency 50 \
    --timeout-keep-alive 5 \
    --no-access-log
