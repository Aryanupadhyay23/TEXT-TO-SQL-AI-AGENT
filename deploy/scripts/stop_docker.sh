#!/bin/bash
# Stop and remove existing container if running
CONTAINER_NAME="ai-chatbot-container"

echo "=== [CodeDeploy] Stopping container: ${CONTAINER_NAME} ==="
if command -v docker &> /dev/null; then
    docker stop "${CONTAINER_NAME}" 2>/dev/null || true
    docker rm "${CONTAINER_NAME}" 2>/dev/null || true
fi
echo "Container cleanup finished."
