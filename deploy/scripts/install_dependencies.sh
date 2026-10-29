#!/bin/bash
set -e

# Verify Docker is installed
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is required but not installed." >&2
    exit 1
fi
