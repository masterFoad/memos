# OnMemOS v3 API Reference

## Quick Reference

### Base URL
```
http://localhost:8080
```

### Authentication
All requests require the `X-API-Key` header:
```http
X-API-Key: your-api-key
```

## Unified Sessions API (`/v1/sessions/*`)

### Create Session
```http
POST /v1/sessions
Content-Type: application/json
X-API-Key: your-api-key

{
  "provider": "auto|cloud_run|gke|workstations",
  "template": "python",
  "namespace": "my-project",
  "user": "developer",
  "ttl_minutes": 60
}
```

### Get Session
```http
GET /v1/sessions/{session_id}
X-API-Key: your-api-key
```

### Execute Command
```http
POST /v1/sessions/{session_id}/execute
Content-Type: application/json
X-API-Key: your-api-key

{
  "command": "ls -la",
  "timeout": 120
}
```

### Delete Session
```http
DELETE /v1/sessions/{session_id}
X-API-Key: your-api-key
```

### Get Connection Info
```http
GET /v1/sessions/{session_id}/connect
X-API-Key: your-api-key
```

## Legacy Cloud Run API (`/v1/cloudrun/*`)

### Create Workspace
```http
POST /v1/cloudrun/workspaces
Content-Type: application/json
X-API-Key: your-api-key

{
  "template": "python",
  "namespace": "my-project",
  "user": "developer",
  "ttl_minutes": 30
}
```

### List Workspaces
```http
GET /v1/cloudrun/workspaces?namespace=my-project&user=developer
X-API-Key: your-api-key
```

### Get Workspace
```http
GET /v1/cloudrun/workspaces/{workspace_id}
X-API-Key: your-api-key
```

### Execute Command
```http
POST /v1/cloudrun/workspaces/{workspace_id}/execute?command=pwd&timeout=30
X-API-Key: your-api-key
```

### Run Python
```http
POST /v1/cloudrun/workspaces/{workspace_id}/runpython?code=print("Hello World")
X-API-Key: your-api-key
```

### Run Shell
```http
POST /v1/cloudrun/workspaces/{workspace_id}/runsh?command=ls -la
X-API-Key: your-api-key
```

### Delete Workspace
```http
DELETE /v1/cloudrun/workspaces/{workspace_id}
X-API-Key: your-api-key
```

### WebSocket Shell
```http
WebSocket: /v1/cloudrun/workspaces/{workspace_id}/shell?api_key=your-api-key
```

## Health Check
```http
GET /health
```

## Response Formats

### Session Response
```json
{
  "id": "ws-my-project-developer-1756062811",
  "provider": "cloud_run",
  "namespace": "my-project",
  "user": "developer",
  "status": "running",
  "url": "https://onmemos-ws-my-project-developer-1756062811-803927173002.us-central1.run.app",
  "websocket": "/v1/cloudrun/workspaces/ws-my-project-developer-1756062811/shell",
  "ssh": false,
  "details": {
    "service_name": "onmemos-ws-my-project-developer-1756062811",
    "bucket_name": "onmemos-my-project-developer-1756062811"
  }
}
```

### Command Execution Response
```json
{
  "stdout": "total 8\ndrwxr-xr-x 2 root root 4096 Aug 24 19:13 .\ndrwxr-xr-x 1 root root 4096 Aug 24 19:13 ..\n",
  "stderr": "",
  "returncode": 0,
  "success": true
}
```

### Error Response
```json
{
  "detail": "Session not found"
}
```

## cURL Examples

### Create Cloud Run Session
```bash
curl -X POST http://localhost:8080/v1/sessions \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "cloud_run",
    "template": "python",
    "namespace": "test",
    "user": "developer",
    "ttl_minutes": 30
  }'
```

### Create GKE Session
```bash
curl -X POST http://localhost:8080/v1/sessions \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "gke",
    "template": "python",
    "namespace": "ml-training",
    "user": "researcher",
    "long_lived": true
  }'
```

### Execute Command
```bash
curl -X POST http://localhost:8080/v1/sessions/ws-test-developer-123/execute \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "python --version",
    "timeout": 30
  }'
```

### Delete Session
```bash
curl -X DELETE http://localhost:8080/v1/sessions/ws-test-developer-123 \
  -H "X-API-Key: your-api-key"
```

## Python SDK Examples

### Basic Usage
```python
from sdk.python.client import OnMemOSClient

client = OnMemOSClient("http://localhost:8080", "your-api-key")

# Create session
session = client.create_session({
    "template": "python",
    "namespace": "my-project",
    "user": "developer"
})

# Execute command
result = client.execute_session(session['id'], "python --version")
print(result['stdout'])

# Clean up
client.delete_session(session['id'])
```

### Context Manager
```python
from sdk.python.client import OnMemOSClient

client = OnMemOSClient("http://localhost:8080", "your-api-key")

with client.cloudrun_workspace_session("python", "test", "developer") as workspace:
    result = workspace.execute("echo 'Hello from OnMemOS!'")
    print(result['stdout'])
```

## Status Codes

- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request parameters
- `401 Unauthorized` - Missing or invalid API key
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

## Rate Limits

- No rate limits currently implemented
- Consider implementing rate limiting for production use

## WebSocket Protocol

### Connect
```javascript
const ws = new WebSocket('ws://localhost:8080/v1/cloudrun/workspaces/ws-test-developer-123/shell?api_key=your-api-key');
```

### Send Command
```javascript
ws.send(JSON.stringify({
  type: 'command',
  command: 'ls -la'
}));
```

### Receive Response
```javascript
ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  if (data.type === 'command_result') {
    console.log('Output:', data.stdout);
    console.log('Error:', data.stderr);
    console.log('Success:', data.success);
  }
};
```
