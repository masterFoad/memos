#!/usr/bin/env python3
"""
Start OnMemOS v3 Admin Server
Internal admin-only endpoints for UI management
"""

import os
import sys
import uvicorn
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment variables
os.environ.setdefault("ONMEMOS_INTERNAL_API_KEY", "onmemos-internal-key-2024-secure")
os.environ.setdefault("AUTO_PROVISION_IDENTITY", "true")
os.environ.setdefault("GCP_PROJECT", "ai-engine-448418")
os.environ.setdefault("GKE_REGION", "us-central1")
os.environ.setdefault("GKE_CLUSTER", "onmemos-autopilot")

if __name__ == "__main__":
    print("🚀 Starting OnMemOS v3 Admin Server...")
    print("📋 Admin endpoints: http://localhost:8001/admin/docs")
    print("🔐 Internal API Key required for all endpoints")
    print("💡 Make sure to activate conda environment first: conda activate imru-orchestrator")
    
    uvicorn.run(
        "server.app_admin:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        reload=True,
        reload_dirs=["server"]
    )
