# OnMemOS v3 Documentation

Welcome to the OnMemOS v3 documentation! This guide will help you understand and use our unified session management system.

## What is OnMemOS v3?

OnMemOS v3 is a unified session management platform that provides seamless access to multiple backend providers:

- **Cloud Run** - Serverless, event-driven workloads
- **GKE Autopilot** - Kubernetes-native, long-lived sessions  
- **Cloud Workstations** - Interactive development environments

All backends are accessible through a single, unified API that automatically selects the best provider for your needs.

## Quick Start

### 1. Install Dependencies

```bash
# Clone the repository
git clone https://github.com/your-org/onmemos-v3.git
cd onmemos-v3

# Install Python dependencies
pip install -r requirements.txt

# Install gcloud CLI (if not already installed)
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init
```

### 2. Configure Environment

```bash
# Set up environment variables
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"
export API_KEY="onmemos-internal-key-2024-secure"

# Set up GKE (if using GKE backend)
gcloud container clusters get-credentials your-cluster --region=us-central1
```

### 3. Start the Server

```bash
# Start the development server
python -m uvicorn server.app:app --host 127.0.0.1 --port 8080 --reload
```

### 4. Create Your First Session

```python
from sdk.python.client import OnMemOSClient

# Initialize client
client = OnMemOSClient("http://localhost:8080", "your-api-key")

# Create a session (automatically selects best provider)
session = client.create_session({
    "template": "python",
    "namespace": "my-project",
    "user": "developer",
    "ttl_minutes": 60
})

print(f"Session created: {session['id']}")

# Execute a command
result = client.execute_session(session['id'], "python --version")
print(f"Python version: {result['stdout']}")

# Clean up
client.delete_session(session['id'])
```

## Documentation Index

### 📚 [Backend Pipeline Documentation](BACKEND_PIPELINE.md)
Complete guide to the backend architecture, providers, and capabilities.

**Topics covered:**
- Architecture overview
- Backend providers (Cloud Run, GKE, Workstations)
- Session management
- Code examples
- Testing
- Configuration
- Troubleshooting

### 🔧 [API Reference](API_REFERENCE.md)
Quick reference for all API endpoints and usage examples.

**Topics covered:**
- Unified Sessions API (`/v1/sessions/*`)
- Legacy Cloud Run API (`/v1/cloudrun/*`)
- Request/response formats
- cURL examples
- Python SDK examples
- WebSocket protocol

## Backend Capabilities

| Feature | Cloud Run | GKE Autopilot | Cloud Workstations |
|---------|-----------|---------------|-------------------|
| **One-shot Commands** | ✅ Jobs-based | ✅ kubectl exec | ❌ Not supported |
| **Interactive Shell** | ✅ WebSocket | ⏭️ Planned | ✅ Native |
| **Persistent Storage** | ✅ Filestore | ⏭️ PVC/CSI | ✅ Native |
| **GCS Bucket Mount** | ✅ FUSE | ⏭️ FUSE | ✅ Native |
| **Scale to Zero** | ✅ Native | ❌ Pod lifecycle | ❌ Always-on |
| **Session Duration** | ✅ TTL-based | ✅ Pod lifecycle | ✅ TTL-based |
| **Isolation** | ✅ Per-service | ✅ Per-pod | ✅ Per-workstation |
| **Web Terminal** | ⏭️ Planned | ⏭️ Planned | ✅ Native |

## Use Cases

### Data Processing (Cloud Run)
```python
# Perfect for ETL jobs, data analysis, batch processing
session = client.create_session({
    "provider": "cloud_run",
    "template": "python",
    "namespace": "data-pipeline",
    "user": "analyst",
    "ttl_minutes": 120,
    "storage": {"bucket": "data-lake-bucket"}
})

# Process data
client.execute_session(session['id'], "pip install pandas numpy")
client.execute_session(session['id'], "python process_data.py")
```

### Machine Learning Training (GKE)
```python
# Perfect for long-running ML training jobs
session = client.create_session({
    "provider": "gke",
    "template": "python", 
    "namespace": "ml-training",
    "user": "researcher",
    "long_lived": True,
    "expected_duration_minutes": 480
})

# Set up training environment
client.execute_session(session['id'], "pip install torch transformers")
client.execute_session(session['id'], "python train_model.py")
```

### Interactive Development (Workstations)
```python
# Perfect for development, debugging, interactive work
session = client.create_session({
    "provider": "workstations",
    "template": "python",
    "namespace": "development", 
    "user": "developer",
    "needs_ssh": True,
    "long_lived": True
})

# Access via URL or SSH
print(f"Access URL: {session['url']}")
```

## Testing

Run the comprehensive test suite to validate all backends:

```bash
# Test all backends
python test_session_backends.py

# Test specific backend
python test_session_backends.py --backend gke

# Test specific capability
python test_session_backends.py --backend cloud_run --test one_shot_commands
```

## Configuration

### Environment Variables

```bash
# Required
export PROJECT_ID="your-project-id"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"

# Cloud Run
export REGION="us-central1"

# GKE
export GKE_NAMESPACE_PREFIX="onmemos"
export GKE_DEFAULT_IMAGE="alpine:latest"

# Workstations
export WORKSTATIONS_REGION="us-central1"
export WORKSTATIONS_CLUSTER="my-cluster"
export WORKSTATIONS_CONFIG="onmemos-default"
```

### Service Account Permissions

```bash
# Cloud Run
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:agent-gcs-accessor@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.admin"

# GKE
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:agent-gcs-accessor@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/container.admin"

# Workstations
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:agent-gcs-accessor@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/workstations.admin"
```

## Troubleshooting

### Common Issues

1. **Authentication errors**
   ```bash
   gcloud auth list
   gcloud config get-value project
   ```

2. **Pod not ready (GKE)**
   ```bash
   kubectl get pods -A | grep onmemos
   kubectl describe pod <pod-name> -n <namespace>
   ```

3. **Service not accessible (Cloud Run)**
   ```bash
   gcloud run services list --region=us-central1
   ```

### Debug Mode

```bash
export LOG_LEVEL=DEBUG
python -m uvicorn server.app:app --host 127.0.0.1 --port 8080 --reload
```

### Health Checks

```bash
# Server health
curl http://localhost:8080/health

# GCP connectivity
curl -H "X-API-Key: $API_KEY" http://localhost:8080/health
```

## Examples

### Basic Session Management
```python
from sdk.python.client import OnMemOSClient

client = OnMemOSClient("http://localhost:8080", "your-api-key")

# Create session
session = client.create_session({
    "template": "python",
    "namespace": "test",
    "user": "developer"
})

# Execute commands
commands = ["pwd", "ls -la", "python --version", "echo 'Hello World!'"]

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

# Automatic cleanup with context manager
with client.cloudrun_workspace_session("python", "test", "developer") as workspace:
    result = workspace.execute("pip install requests")
    print(f"Install result: {result['success']}")
    
    result = workspace.execute("python -c 'import requests; print(requests.__version__)'")
    print(f"Requests version: {result['stdout']}")
```

### WebSocket Shell
```python
import asyncio
import websockets
import json

async def interactive_shell(session_id: str, api_key: str):
    ws_url = f"ws://localhost:8080/v1/cloudrun/workspaces/{session_id}/shell?api_key={api_key}"
    
    async with websockets.connect(ws_url) as websocket:
        await websocket.send(json.dumps({
            "type": "command",
            "command": "ls -la /workspace"
        }))
        
        response = await websocket.recv()
        data = json.loads(response)
        
        if data.get("type") == "command_result":
            print(f"Output: {data['stdout']}")

# Usage
asyncio.run(interactive_shell("ws-test-developer-123", "your-api-key"))
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

- **Documentation**: [Backend Pipeline](BACKEND_PIPELINE.md) | [API Reference](API_REFERENCE.md)
- **Issues**: [GitHub Issues](https://github.com/your-org/onmemos-v3/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/onmemos-v3/discussions)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**OnMemOS v3** - Unified session management for the cloud-native era.
