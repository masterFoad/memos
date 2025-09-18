#!/bin/bash
# Start OnMemOS v3 Public SDK Server with conda activation

set -e

echo "🚀 Starting OnMemOS v3 Public SDK Server..."

# Activate conda environment
echo "📦 Activating conda environment: imru-orchestrator"
eval "$(conda shell.bash hook)"
conda activate imru-orchestrator

# Set environment variables
export ONMEMOS_INTERNAL_API_KEY="${ONMEMOS_INTERNAL_API_KEY:-onmemos-internal-key-2024-secure}"
export AUTO_PROVISION_IDENTITY="${AUTO_PROVISION_IDENTITY:-true}"
export GCP_PROJECT="${GCP_PROJECT:-ai-engine-448418}"
export GKE_REGION="${GKE_REGION:-us-central1}"
export GKE_CLUSTER="${GKE_CLUSTER:-onmemos-autopilot}"

echo "📋 Public endpoints: http://localhost:8080/docs"
echo "🔑 Passport authentication required for user endpoints"
echo "🌍 Environment: $CONDA_DEFAULT_ENV"

# Start the server
cd "$(dirname "$0")"
python start_public_server.py


