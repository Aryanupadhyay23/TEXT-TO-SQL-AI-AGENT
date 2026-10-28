#!/bin/bash
set -e

echo "=== [1/3] Verifying EC2 Environment ==="

# Non-intrusive check: Docker is already active on this EC2 instance
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is required but not installed on this host." >&2
    exit 1
fi

# Ensure AWS CLI v2 is available for ECR authentication
if ! command -v aws &> /dev/null; then
    echo "Installing AWS CLI v2..."
    curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    ./aws/install --update
    rm -rf aws awscliv2.zip
fi

echo "EC2 dependencies verified without restarting services."
