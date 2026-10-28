#!/bin/bash
set -e

echo "=== [3/3] Starting AI Chatbot Container on EC2 (Space & RAM Optimized) ==="

# Default AWS & Container configuration
AWS_REGION="${AWS_REGION:-ap-southeast-2}"
ECR_REPOSITORY="${ECR_REPOSITORY:-ai-chatbot}"
CONTAINER_NAME="ai-chatbot-container"
HOST_PORT_FRONTEND="${HOST_PORT_FRONTEND:-8503}"
HOST_PORT_BACKEND="${HOST_PORT_BACKEND:-8002}"

# Fetch AWS Account ID dynamically
AWS_ACCOUNT_ID=$(aws sts get-caller-identity \
    --region "${AWS_REGION}" \
    --query Account \
    --output text)

ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_URI="${ECR_REGISTRY}/${ECR_REPOSITORY}:latest"

echo "Logging in to Amazon ECR (${ECR_REGISTRY})..."
aws ecr get-login-password --region "${AWS_REGION}" | \
    docker login --username AWS --password-stdin "${ECR_REGISTRY}"

echo "Pulling latest Docker image: ${IMAGE_URI}..."
docker pull "${IMAGE_URI}"

# Locate single environment file (.env.tts)
ENV_FILE=""
if [ -f "/home/ubuntu/.env.tts" ]; then
    ENV_FILE="/home/ubuntu/.env.tts"
elif [ -f "backend/.env.tts" ]; then
    ENV_FILE="backend/.env.tts"
elif [ -f "$(pwd)/backend/.env.tts" ]; then
    ENV_FILE="$(pwd)/backend/.env.tts"
elif [ -f "/home/ubuntu/app/backend/.env.tts" ]; then
    ENV_FILE="/home/ubuntu/app/backend/.env.tts"
elif [ -f ".env.tts" ]; then
    ENV_FILE=".env.tts"
fi

ENV_ARGS=()
if [ -n "${ENV_FILE}" ]; then
    echo "Found environment file: ${ENV_FILE}"
    sed -i 's/\r$//' "${ENV_FILE}"
    sed -i 's/[[:space:]]*=[[:space:]]*/=/' "${ENV_FILE}"
    sed -i -E 's/="?([^"]*)"?$/=\1/' "${ENV_FILE}"
    ENV_ARGS=(--env-file "${ENV_FILE}")
else
    echo "No custom .env file found. Relying on container defaults and environment."
fi

echo "Removing existing container if present..."
if docker container inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
    docker rm -f "${CONTAINER_NAME}"
fi

# Clean up dangling images and build cache to save disk space
echo "Pruning dangling images to free EC2 disk space..."
docker image prune -f 2>/dev/null || true

echo "Running Docker container on ports ${HOST_PORT_FRONTEND} (Frontend/Reverse Proxy) and ${HOST_PORT_BACKEND} (FastAPI)..."
docker run -d \
    --name "${CONTAINER_NAME}" \
    --restart unless-stopped \
    --log-opt max-size=10m \
    --log-opt max-file=3 \
    -p "${HOST_PORT_FRONTEND}:80" \
    -p "${HOST_PORT_BACKEND}:8000" \
    -v chatbot_checkpoints:/app/backend/chatbot/data/sqlite_storage \
    -v chatbot_chroma:/app/backend/chatbot/data/chroma \
    "${ENV_ARGS[@]}" \
    "${IMAGE_URI}"

docker update --restart unless-stopped "${CONTAINER_NAME}"

# Verify container health
echo "Waiting for container startup and health check..."
for i in {1..20}; do
    sleep 2
    if curl -sf "http://localhost:${HOST_PORT_BACKEND}/health" | grep -q "ok"; then
        echo "Container is HEALTHY!"
        break
    fi
    echo "Waiting for health endpoint... (attempt $i/20)"
done

echo "=========================================================="
echo "AI Chatbot deployed successfully!"
echo "Public Domain Frontend: https://aryan-projects.duckdns.org/chatbot/"
echo "Public Domain Backend:  https://aryan-projects.duckdns.org/chatbot-backend/docs"
echo "Direct Host Port: http://<EC2-HOST>:${HOST_PORT_FRONTEND}/"
echo "Backend Health:   http://<EC2-HOST>:${HOST_PORT_BACKEND}/health"
echo "=========================================================="
