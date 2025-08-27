# OnMemOS v3 Backend Pipeline Documentation

## Overview

OnMemOS v3 provides a unified session management system with multiple backend providers (Cloud Run, GKE Autopilot, Cloud Workstations) through a single API surface. This document covers the complete backend pipeline, endpoints, and usage examples.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [API Endpoints](#api-endpoints)
3. [Backend Providers](#backend-providers)
4. [Session Management](#session-management)
5. [Code Examples](#code-examples)
6. [Testing](#testing)
7. [Configuration](#configuration)

## Architecture Overview

### Unified Sessions Layer

OnMemOS v3 introduces a unified `/v1/sessions/*` API that abstracts different backend providers:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Cloud Run     │    │   GKE Autopilot │    │   Workstations  │
│   (Serverless)  │    │   (Kubernetes)  │    │   (Managed IDE) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │ Unified Sessions│
                    │     API         │
                    │  /v1/sessions/* │
                    └─────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Client SDK    │
                    │   (Python)      │
                    └─────────────────┘
```

### Backend Capabilities Matrix

| Capability | Cloud Run | GKE Autopilot | Cloud Workstations |
|------------|-----------|---------------|-------------------|
| One-shot Commands | ✅ Jobs-based | ✅ kubectl exec | ❌ Not supported |
| Interactive Shell | ✅ WebSocket | 🔄 Planned | ✅ Native |
| Persistent Storage | ✅ Filestore | 🔄 PVC/CSI | ✅ Native |
| GCS Bucket Mount | ✅ FUSE | 🔄 FUSE | ✅ Native |
| Scale to Zero | ✅ Native | ❌ Pod lifecycle | ❌ Always-on |
| Session Duration | ✅ TTL-based | ✅ Pod lifecycle | ✅ TTL-based |
| Isolation | ✅ Per-service | ✅ Per-pod | ✅ Per-workstation |
| Web Terminal | 🔄 Planned | 🔄 Planned | ✅ Native |

## API Endpoints

### Unified Sessions API (`/v1/sessions/*`)

#### Create Session
```http
POST /v1/sessions
Content-Type: application/json
X-API-Key: your-api-key

{
  "provider": "cloud_run|gke|workstations|auto",
  "template": "python|nodejs|go",
  "namespace": "team-a",
  "user": "alice",
  "ttl_minutes": 60,
  "storage": {
    "bucket": "my-bucket",
    "filestore": {
      "ip": "10.0.0.1",
      "share": "workspace"
    }
  },
  "needs_ssh": false,
  "long_lived": false,
  "expected_duration_minutes": 30
}
```

**Response:**
```json
{
  "id": "ws-team-a-alice-1756062811",
  "provider": "cloud_run",
  "namespace": "team-a",
  "user": "alice",
  "status": "running",
  "url": "https://onmemos-ws-team-a-alice-1756062811-803927173002.us-central1.run.app",
  "websocket": "/v1/cloudrun/workspaces/ws-team-a-alice-1756062811/shell",
  "ssh": false,
  "details": {
    "service_name": "onmemos-ws-team-a-alice-1756062811",
    "bucket_name": "onmemos-team-a-alice-1756062811"
  }
}
```

#### Get Session
```http
GET /v1/sessions/{session_id}
X-API-Key: your-api-key
```

#### Execute Command
```http
POST /v1/sessions/{session_id}/execute
Content-Type: application/json
X-API-Key: your-api-key

{
  "command": "ls -la /workspace",
  "timeout": 120
}
```

**Response:**
```json
{
  "stdout": "total 8\ndrwxr-xr-x 2 root root 4096 Aug 24 19:13 .\ndrwxr-xr-x 1 root root 4096 Aug 24 19:13 ..\n",
  "stderr": "",
  "returncode": 0,
  "success": true
}
```

#### Delete Session
```http
DELETE /v1/sessions/{session_id}
X-API-Key: your-api-key
```

#### Get Connection Info
```http
GET /v1/sessions/{session_id}/connect
X-API-Key: your-api-key
```

### Legacy Cloud Run API (`/v1/cloudrun/*`)

For backward compatibility, the original Cloud Run endpoints are still available:

#### Create Cloud Run Workspace
```http
POST /v1/cloudrun/workspaces
Content-Type: application/json
X-API-Key: your-api-key

{
  "template": "python",
  "namespace": "team-a",
  "user": "alice",
  "ttl_minutes": 30,
  "storage_options": {
    "bucket": "my-bucket",
    "filestore": {
      "ip": "10.0.0.1",
      "share": "workspace"
    }
  }
}
```

#### Execute in Cloud Run Workspace
```http
POST /v1/cloudrun/workspaces/{workspace_id}/execute?command=pwd&timeout=30
X-API-Key: your-api-key
```

#### WebSocket Shell
```http
WebSocket: /v1/cloudrun/workspaces/{workspace_id}/shell?api_key=your-api-key
```

## Backend Providers

### 1. Cloud Run Provider

**Best for:** Serverless, event-driven workloads, short-lived sessions

**Features:**
- Scale to zero (pay only when active)
- GCS FUSE bucket mounting
- Filestore (NFS) integration
- Cloud Run Jobs for command execution
- WebSocket shell support

**Configuration:**
```bash
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"
```

**Example Session Creation:**
```python
import requests

response = requests.post(
    "http://localhost:8080/v1/sessions",
    headers={"X-API-Key": "your-api-key"},
    json={
        "provider": "cloud_run",
        "template": "python",
        "namespace": "data-processing",
        "user": "analyst",
        "ttl_minutes": 60,
        "storage": {
            "bucket": "data-lake-bucket",
            "filestore": {
                "ip": "10.0.0.1",
                "share": "workspace"
            }
        }
    }
)

session = response.json()
print(f"Session created: {session['id']}")
print(f"Service URL: {session['url']}")
```

### 2. GKE Autopilot Provider

**Best for:** Long-lived sessions, Kubernetes-native workloads, resource-intensive tasks

**Features:**
- Per-pod isolation
- Persistent volume support (planned)
- kubectl exec for command execution
- Autopilot compatibility
- Resource limits and requests

**Configuration:**
```bash
export GKE_NAMESPACE_PREFIX="onmemos"
export GKE_DEFAULT_IMAGE="alpine:latest"
export GKE_SHELL="/bin/sh"

# Ensure kubectl context is set
kubectl config current-context
```

**Example Session Creation:**
```python
import requests

response = requests.post(
    "http://localhost:8080/v1/sessions",
    headers={"X-API-Key": "your-api-key"},
    json={
        "provider": "gke",
        "template": "python",
        "namespace": "ml-training",
        "user": "researcher",
        "long_lived": True,
        "expected_duration_minutes": 480  # 8 hours
    }
)

session = response.json()
print(f"GKE Pod created: {session['id']}")
```

### 3. Cloud Workstations Provider

**Best for:** Interactive development, IDE integration, SSH access

**Features:**
- Full IDE environment
- SSH access
- Persistent storage
- Web terminal
- Long-lived sessions

**Configuration:**
```bash
export WORKSTATIONS_REGION="us-central1"
export WORKSTATIONS_CLUSTER="my-ws-cluster"
export WORKSTATIONS_CONFIG="onmemos-default"
```

**Example Session Creation:**
```python
import requests

response = requests.post(
    "http://localhost:8080/v1/sessions",
    headers={"X-API-Key": "your-api-key"},
    json={
        "provider": "workstations",
        "template": "python",
        "namespace": "development",
        "user": "developer",
        "needs_ssh": True,
        "long_lived": True
    }
)

session = response.json()
print(f"Workstation created: {session['id']}")
print(f"Access URL: {session['url']}")
```

## Session Management

### Provider Selection Logic

The unified API automatically selects the best provider based on your requirements:

```python
def _choose_provider(req: CreateSessionRequest) -> SessionProvider:
    if req.provider != SessionProvider.auto:
        return req.provider
    
    if req.needs_ssh or (req.expected_duration_minutes and req.expected_duration_minutes > 60):
        return SessionProvider.workstations
    
    if req.long_lived:
        return SessionProvider.gke
    
    return SessionProvider.cloud_run
```

### Session Lifecycle

1. **Creation**: Provider-specific workspace/pod/workstation is created
2. **Ready**: Session is available for commands or connections
3. **Active**: Commands are executed or connections are established
4. **Cleanup**: Automatic deletion based on TTL or manual deletion

### Environment Variables

All sessions include these environment variables:

```bash
WORKSPACE_ID=ws-namespace-user-timestamp
NAMESPACE=namespace
USER=user
BUCKET_NAME=onmemos-namespace-user-timestamp
```

## Code Examples

### Python SDK Usage

```python
from sdk.python.client import OnMemOSClient

# Initialize client
client = OnMemOSClient(
    base_url="http://localhost:8080",
    api_key="your-api-key"
)

# Create session with automatic provider selection
session = client.create_session({
    "template": "python",
    "namespace": "my-project",
    "user": "developer",
    "ttl_minutes": 120
})

print(f"Session created: {session['id']}")

# Execute commands
result = client.execute_session(session['id'], "python --version")
print(f"Python version: {result['stdout']}")

# Execute multiple commands
commands = [
    "pwd",
    "ls -la",
    "echo 'Hello from OnMemOS!'",
    "python -c 'import sys; print(sys.version)'"
]

for cmd in commands:
    result = client.execute_session(session['id'], cmd)
    print(f"Command: {cmd}")
    print(f"Output: {result['stdout']}")
    print(f"Success: {result['success']}\n")

# Clean up
client.delete_session(session['id'])
```

### Context Manager Usage

```python
from sdk.python.client import OnMemOSClient

client = OnMemOSClient("http://localhost:8080", "your-api-key")

# Cloud Run context manager
with client.cloudrun_workspace_session("python", "data-analysis", "analyst", ttl_minutes=60) as workspace:
    result = workspace.execute("pip install pandas numpy")
    print(f"Install result: {result['success']}")
    
    result = workspace.execute("python -c 'import pandas as pd; print(pd.__version__)'")
    print(f"Pandas version: {result['stdout']}")

# GKE context manager (planned)
with client.gke_workspace_session("python", "ml-training", "researcher", ttl_minutes=480) as workspace:
    result = workspace.execute("nvidia-smi")
    print(f"GPU info: {result['stdout']}")
```

### WebSocket Shell Usage

```python
import asyncio
import websockets
import json

async def interactive_shell(session_id: str, api_key: str):
    ws_url = f"ws://localhost:8080/v1/cloudrun/workspaces/{session_id}/shell?api_key={api_key}"
    
    async with websockets.connect(ws_url) as websocket:
        # Send command
        await websocket.send(json.dumps({
            "type": "command",
            "command": "ls -la /workspace"
        }))
        
        # Receive response
        response = await websocket.recv()
        data = json.loads(response)
        
        if data.get("type") == "command_result":
            print(f"Output: {data['stdout']}")
            print(f"Error: {data['stderr']}")
            print(f"Success: {data['success']}")

# Usage
asyncio.run(interactive_shell("ws-my-project-developer-123", "your-api-key"))
```

### Advanced Usage Examples

#### Data Processing Pipeline

```python
from sdk.python.client import OnMemOSClient
import json

client = OnMemOSClient("http://localhost:8080", "your-api-key")

# Create session for data processing
session = client.create_session({
    "provider": "cloud_run",
    "template": "python",
    "namespace": "data-pipeline",
    "user": "processor",
    "ttl_minutes": 120,
    "storage": {
        "bucket": "raw-data-bucket"
    }
})

# Data processing workflow
workflow = [
    "pip install pandas numpy scikit-learn",
    "gsutil cp gs://raw-data-bucket/data.csv /workspace/",
    "python -c 'import pandas as pd; df = pd.read_csv(\"data.csv\"); print(f\"Loaded {len(df)} rows\")'",
    "python -c 'import pandas as pd; df = pd.read_csv(\"data.csv\"); df.to_csv(\"processed_data.csv\"); gsutil cp processed_data.csv gs://processed-data-bucket/'",
    "echo 'Data processing complete!'"
]

for step in workflow:
    result = client.execute_session(session['id'], step)
    print(f"Step: {step[:50]}...")
    print(f"Success: {result['success']}")
    if result['stderr']:
        print(f"Error: {result['stderr']}")
    print()

client.delete_session(session['id'])
```

#### Machine Learning Training

```python
from sdk.python.client import OnMemOSClient

client = OnMemOSClient("http://localhost:8080", "your-api-key")

# Create long-lived GKE session for ML training
session = client.create_session({
    "provider": "gke",
    "template": "python",
    "namespace": "ml-training",
    "user": "researcher",
    "long_lived": True,
    "expected_duration_minutes": 480
})

# ML training setup
setup_commands = [
    "pip install torch torchvision torchaudio",
    "pip install transformers datasets",
    "nvidia-smi",  # Check GPU availability
    "python -c 'import torch; print(f\"PyTorch version: {torch.__version__}\")'"
]

for cmd in setup_commands:
    result = client.execute_session(session['id'], cmd)
    print(f"Setup: {cmd}")
    print(f"Output: {result['stdout']}")
    print(f"Success: {result['success']}\n")

# Training script (simplified)
training_script = '''
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# Load model and tokenizer
model_name = "gpt2"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)

print(f"Loaded {model_name} model")
print(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")
'''

result = client.execute_session(session['id'], f"python -c '{training_script}'")
print(f"Training setup: {result['stdout']}")

# Keep session alive for training
print(f"Session {session['id']} ready for training. Don't forget to delete when done!")
```

## Testing

### Running Tests

```bash
# Test all backends
python test_session_backends.py

# Test specific backend
python test_session_backends.py --backend gke

# Test specific capability
python test_session_backends.py --backend cloud_run --test one_shot_commands

# Test multiple backends
python test_session_backends.py --backend gke --test persistent_storage
```

### Test Capabilities

The test suite validates these capabilities across all backends:

1. **one_shot_commands**: Basic command execution
2. **persistent_storage**: File system operations
3. **bucket_mount**: GCS bucket access
4. **scale_to_zero**: Resource scaling behavior
5. **session_duration**: Session lifecycle management
6. **isolation_model**: Multi-tenant isolation
7. **shell_interactive**: Interactive shell support
8. **web_terminal**: Web terminal interface

### Test Results Example

```
🚀 Session Backends Capability Test Suite - GKE
============================================================

🔍 Testing: one_shot_commands
   Result: ✅ PASSED

🔍 Testing: persistent_storage
   Result: ✅ PASSED

🔍 Testing: bucket_mount
   Result: ✅ PASSED

============================================================
📊 Session Backends Capability Test Summary
============================================================
one_shot_commands         ✅ PASSED
persistent_storage        ✅ PASSED
bucket_mount              ✅ PASSED

✅ Passed : 3
⏭️  Skipped: 0
❌ Failed : 0
```

## Configuration

### Environment Variables

```bash
# Required for all backends
export PROJECT_ID="your-project-id"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"

# Cloud Run specific
export REGION="us-central1"

# GKE specific
export GKE_NAMESPACE_PREFIX="onmemos"
export GKE_DEFAULT_IMAGE="alpine:latest"
export GKE_SHELL="/bin/sh"

# Cloud Workstations specific
export WORKSTATIONS_REGION="us-central1"
export WORKSTATIONS_CLUSTER="my-ws-cluster"
export WORKSTATIONS_CONFIG="onmemos-default"
```

### Service Account Permissions

```bash
# Cloud Run permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:agent-gcs-accessor@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:agent-gcs-accessor@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.jobsAdmin"

# GKE permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:agent-gcs-accessor@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/container.admin"

# Cloud Workstations permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:agent-gcs-accessor@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/workstations.admin"
```

### API Keys

```bash
# Generate API key
export API_KEY="onmemos-internal-key-2024-secure"

# Use in requests
curl -H "X-API-Key: $API_KEY" \
     -X POST http://localhost:8080/v1/sessions \
     -H "Content-Type: application/json" \
     -d '{"template": "python", "namespace": "test", "user": "user"}'
```

## Troubleshooting

### Common Issues

1. **Pod not ready (GKE)**
   ```bash
   kubectl get pods -A | grep onmemos
   kubectl describe pod <pod-name> -n <namespace>
   ```

2. **Cloud Run service not accessible**
   ```bash
   gcloud run services list --region=us-central1
   gcloud run services describe <service-name> --region=us-central1
   ```

3. **Permission denied**
   ```bash
   gcloud auth list
   gcloud config get-value project
   ```

4. **Session not found**
   ```bash
   # Check if session exists
   curl -H "X-API-Key: $API_KEY" \
        http://localhost:8080/v1/sessions/<session-id>
   ```

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or set environment variable
export LOG_LEVEL=DEBUG
```

### Health Checks

```bash
# Server health
curl http://localhost:8080/health

# GCP connectivity
curl -H "X-API-Key: $API_KEY" \
     http://localhost:8080/health
```

## Best Practices

1. **Provider Selection**
   - Use Cloud Run for short-lived, serverless workloads
   - Use GKE for long-lived, resource-intensive tasks
   - Use Workstations for interactive development

2. **Resource Management**
   - Always delete sessions when done
   - Set appropriate TTL values
   - Monitor resource usage

3. **Security**
   - Use service accounts with minimal permissions
   - Rotate API keys regularly
   - Enable audit logging

4. **Performance**
   - Reuse sessions for multiple commands
   - Use appropriate timeout values
   - Monitor cold start times

## Future Enhancements

1. **WebSocket Shell for GKE**
2. **Persistent Volume Support for GKE**
3. **GCS FUSE for GKE**
4. **Web Terminal Interface**
5. **Session Monitoring Dashboard**
6. **Automatic Resource Scaling**
7. **Multi-region Support**
8. **Custom Container Images**

---

For more information, see the [OnMemOS v3 GitHub repository](https://github.com/your-org/onmemos-v3).
