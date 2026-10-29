#!/usr/bin/env bash
set -e

export PYTHONPATH="/app/backend:/app:${PYTHONPATH}"
mkdir -p /app/backend/chatbot/data/sqlite_storage /app/backend/chatbot/data/chroma

# Start Streamlit frontend in background
streamlit run /app/frontend/app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true &

# Start FastAPI backend in foreground
cd /app/backend
exec uvicorn main:app --host 0.0.0.0 --port 8000
