#!/bin/bash
set -e

AWS_REGION="${AWS_REGION:-ap-southeast-2}"
ECR_REPOSITORY="${ECR_REPOSITORY:-ai-chatbot}"
CONTAINER_NAME="ai-chatbot-container"
HOST_PORT_FRONTEND="${HOST_PORT_FRONTEND:-8503}"
HOST_PORT_BACKEND="${HOST_PORT_BACKEND:-8002}"

# Authenticate with Amazon ECR and pull latest image
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "${AWS_REGION}")
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_URI="${ECR_REGISTRY}/${ECR_REPOSITORY}:latest"

aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_REGISTRY}"
docker pull "${IMAGE_URI}"

# Remove existing container
docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true

# Find .env.tts file if present
ENV_ARG=""
if [ -f "/home/ubuntu/.env.tts" ]; then
    ENV_ARG="--env-file /home/ubuntu/.env.tts"
elif [ -f ".env.tts" ]; then
    ENV_ARG="--env-file .env.tts"
elif [ -f "backend/.env.tts" ]; then
    ENV_ARG="--env-file backend/.env.tts"
fi

# Run container
docker run -d \
    --name "${CONTAINER_NAME}" \
    --restart unless-stopped \
    -p "${HOST_PORT_FRONTEND}:8501" \
    -p "${HOST_PORT_BACKEND}:8000" \
    -v chatbot_checkpoints:/app/backend/chatbot/data/sqlite_storage \
    -v chatbot_chroma:/app/backend/chatbot/data/chroma \
    ${ENV_ARG} \
    "${IMAGE_URI}"
