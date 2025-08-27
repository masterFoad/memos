# OnMemOS v3 SDK Quick Reference

## Status
- **Backend Status**: ✅ FULLY OPERATIONAL
- **GKE**: ✅ All tests passing
- **Cloud Run**: ✅ All tests passing  
- **Cloud Workstations**: 🔄 In development
- **Recent Fixes**: 
  - Fixed persistent storage allocation for GKE sessions
  - Fixed WebSocket logging to reduce noise
  - Enhanced resource control with workspace-based packages

## Quick Start

```python
from sdk.python.client import OnMemOSClient

# Initialize client
client = OnMemOSClient(
    base_url="http://localhost:8080",
    api_key="your-api-key"
)

# Create a workspace first
workspace = client.create_workspace(
    user_id="developer",
    workspace_id="my-dev-workspace", 
    name="Development Environment",
    resource_package=WorkspaceResourcePackage.DEV_MEDIUM
)

# Create a session within the workspace
session = client.create_session_in_workspace(
    workspace_id="my-dev-workspace",
    template="python",
    namespace="project1",
    user="developer"
)
```

## Workspace Management

### User Types & Entitlements

| User Type | Max Workspaces | Allowed Packages | Sharing | Cross Namespace |
|-----------|----------------|------------------|---------|-----------------|
| **FREE** | 1 | FREE_MICRO, DEV_MICRO, DEV_SMALL | ❌ | ❌ |
| **PRO** | 5 | DEV_*, DS_SMALL/MEDIUM, ML_T4_*, COMPUTE_SMALL/MEDIUM | ✅ | ✅ |
| **ENTERPRISE** | 20 | All packages | ✅ | ✅ |
| **ADMIN** | 1000 | All packages | ✅ | ✅ |

### Workspace Resource Packages

#### Development Packages
- `DEV_MICRO`: 250m CPU, 512Mi RAM
- `DEV_SMALL`: 500m CPU, 1Gi RAM  
- `DEV_MEDIUM`: 1 CPU, 2Gi RAM
- `DEV_LARGE`: 2 CPU, 4Gi RAM

#### Data Science Packages (CPU Only)
- `DS_SMALL`: 1 CPU, 2Gi RAM
- `DS_MEDIUM`: 2 CPU, 4Gi RAM
- `DS_LARGE`: 4 CPU, 8Gi RAM

#### Machine Learning Packages (with GPU)
- `ML_T4_SMALL`: 1 CPU, 4Gi RAM + T4 GPU
- `ML_T4_MEDIUM`: 2 CPU, 8Gi RAM + T4 GPU
- `ML_T4_LARGE`: 4 CPU, 16Gi RAM + T4 GPU
- `ML_A100_SMALL`: 2 CPU, 8Gi RAM + A100 GPU
- `ML_A100_MEDIUM`: 4 CPU, 16Gi RAM + A100 GPU
- `ML_A100_LARGE`: 8 CPU, 32Gi RAM + A100 GPU
- `ML_H100_SMALL`: 4 CPU, 16Gi RAM + H100 GPU
- `ML_H100_MEDIUM`: 8 CPU, 32Gi RAM + H100 GPU
- `ML_H100_LARGE`: 8 CPU, 32Gi RAM + H100 GPU

#### Compute Packages
- `COMPUTE_SMALL`: 500m CPU, 1Gi RAM
- `COMPUTE_MEDIUM`: 1 CPU, 2Gi RAM
- `COMPUTE_LARGE`: 2 CPU, 4Gi RAM
- `COMPUTE_XLARGE`: 4 CPU, 8Gi RAM

### Workspace Management Methods

```python
# Create workspace
workspace = client.create_workspace(
    user_id="developer",
    workspace_id="my-workspace",
    name="My Development Workspace",
    resource_package=WorkspaceResourcePackage.DEV_MEDIUM,
    description="Main development environment"
)

# List workspaces
workspaces = client.list_workspaces("developer")

# Get workspace details
workspace = client.get_workspace("developer", "my-workspace")

# Delete workspace
success = client.delete_workspace("developer", "my-workspace")
```

## Session Creation

### Basic Session Creation

```python
# Create session using workspace's resource package
session = client.create_session_in_workspace(
    workspace_id="my-workspace",
    template="python",
    namespace="project1",
    user="developer"
)
```

### Advanced Session Creation

```python
# Override workspace package with specific resources
session = client.create_session_in_workspace(
    workspace_id="ml-workspace",
    template="python",
    namespace="experiment1",
    user="researcher",
    resource_package=ResourcePackage.ML_T4_LARGE,
    gpu_type=GPUType.T4,
    gpu_count=2,
    request_persistent_storage=True,
    persistent_storage_size_gb=50
)
```

### Convenience Methods

```python
# Development session
session = client.create_development_session(
    workspace_id="my-workspace",
    namespace="project1",
    user="developer",
    image_type=ImageType.UBUNTU,
    cpu_size=CPUSize.MEDIUM,
    memory_size=MemorySize.MEDIUM,
    request_persistent_storage=True
)

# Python session
session = client.create_python_session(
    workspace_id="my-workspace",
    namespace="project1", 
    user="developer",
    python_version="3.11-slim",
    gpu_type=GPUType.T4
)

# Machine learning session
session = client.create_ml_session(
    workspace_id="ml-workspace",
    namespace="experiment1",
    user="researcher",
    gpu_type=GPUType.A100,
    gpu_count=1,
    request_persistent_storage=True,
    persistent_storage_size_gb=100
)

# Custom image session
session = client.create_custom_session(
    workspace_id="my-workspace",
    namespace="project1",
    user="developer",
    image_url="gcr.io/my-project/custom-image:latest"
)
```

## Resource Specifications

### CPU & Memory Sizes

```python
from server.models.sessions import CPUSize, MemorySize

# CPU sizes
CPUSize.MICRO    # 250m CPU
CPUSize.SMALL    # 500m CPU  
CPUSize.MEDIUM   # 1 CPU
CPUSize.LARGE    # 2 CPU
CPUSize.XLARGE   # 4 CPU
CPUSize.XXLARGE  # 8 CPU
CPUSize.CUSTOM   # Custom specification

# Memory sizes
MemorySize.MICRO     # 512Mi RAM
MemorySize.SMALL     # 1Gi RAM
MemorySize.MEDIUM    # 2Gi RAM
MemorySize.LARGE     # 4Gi RAM
MemorySize.XLARGE    # 8Gi RAM
MemorySize.XXLARGE   # 16Gi RAM
MemorySize.XXXLARGE  # 32Gi RAM
MemorySize.CUSTOM    # Custom specification
```

### Image Types

```python
from server.models.sessions import ImageType

ImageType.ALPINE   # Alpine Linux (default)
ImageType.UBUNTU   # Ubuntu
ImageType.PYTHON   # Python runtime
ImageType.NODEJS   # Node.js runtime
ImageType.GO       # Go runtime
ImageType.RUST     # Rust runtime
ImageType.JAVA     # Java runtime
ImageType.CUSTOM   # Custom image
```

### GPU Types

```python
from server.models.sessions import GPUType

GPUType.NONE   # No GPU (default)
GPUType.T4     # NVIDIA T4
GPUType.V100   # NVIDIA V100
GPUType.A100   # NVIDIA A100
GPUType.H100   # NVIDIA H100
GPUType.L4     # NVIDIA L4
```

### Resource Specification Helpers

```python
# Create resource specification
resource_spec = client.resource_spec(
    cpu_size=CPUSize.MEDIUM,
    memory_size=MemorySize.LARGE,
    custom_cpu_request="1.5",      # Optional custom CPU
    custom_memory_request="6Gi"    # Optional custom memory
)

# Create image specification
image_spec = client.image_spec(
    image_type=ImageType.PYTHON,
    image_tag="3.11-slim"
)

# Create GPU specification
gpu_spec = client.gpu_spec(
    gpu_type=GPUType.T4,
    gpu_count=2
)
```

## Session Management

```python
# Execute command
result = client.execute_session(
    session_id="session-123",
    command="python --version",
    timeout=120
)

# Get session info
session = client.get_session("session-123")

# List sessions
sessions = client.list_sessions(
    namespace="project1",
    user="developer"
)
```

## Storage Configuration

### Persistent Storage

```python
# Request persistent storage
session = client.create_session_in_workspace(
    workspace_id="my-workspace",
    template="python",
    namespace="project1",
    user="developer",
    request_persistent_storage=True,
    persistent_storage_size_gb=20
)
```

### GCS Bucket Storage

```python
# Request GCS bucket
session = client.create_session_in_workspace(
    workspace_id="my-workspace",
    template="python", 
    namespace="project1",
    user="developer",
    request_bucket=True,
    bucket_size_gb=10
)
```

## Environment Variables

```python
# Set environment variables
session = client.create_session_in_workspace(
    workspace_id="my-workspace",
    template="python",
    namespace="project1", 
    user="developer",
    env={
        "PYTHONPATH": "/workspace/src",
        "DATABASE_URL": "postgresql://localhost/mydb",
        "API_KEY": "secret-key"
    }
)
```

## Examples

### Complete Development Workflow

```python
# 1. Create workspace
workspace = client.create_workspace(
    user_id="developer",
    workspace_id="my-project",
    name="My Project Workspace",
    resource_package=WorkspaceResourcePackage.DEV_MEDIUM
)

# 2. Create development session
session = client.create_development_session(
    workspace_id="my-project",
    namespace="main",
    user="developer",
    request_persistent_storage=True,
    persistent_storage_size_gb=20
)

# 3. Execute commands
result = client.execute_session(
    session_id=session["id"],
    command="git clone https://github.com/my/project.git /workspace/project"
)

# 4. Install dependencies
client.execute_session(
    session_id=session["id"],
    command="cd /workspace/project && pip install -r requirements.txt"
)

# 5. Run tests
test_result = client.execute_session(
    session_id=session["id"],
    command="cd /workspace/project && python -m pytest"
)
```

### Machine Learning Workflow

```python
# 1. Create ML workspace
workspace = client.create_workspace(
    user_id="researcher",
    workspace_id="ml-experiments",
    name="Machine Learning Lab",
    resource_package=WorkspaceResourcePackage.ML_T4_MEDIUM
)

# 2. Create ML session
session = client.create_ml_session(
    workspace_id="ml-experiments",
    namespace="experiment-1",
    user="researcher",
    gpu_type=GPUType.T4,
    gpu_count=1,
    request_persistent_storage=True,
    persistent_storage_size_gb=50
)

# 3. Install ML libraries
client.execute_session(
    session_id=session["id"],
    command="pip install torch torchvision transformers datasets"
)

# 4. Run training
client.execute_session(
    session_id=session["id"],
    command="python train.py --epochs 10 --batch-size 32"
)
```

## Troubleshooting

### Common Issues

**Connection Error**
```
Connection error - is the server running at http://127.0.0.1:8080?
```
- Check if the OnMemOS server is running
- Verify the base URL is correct
- Check firewall settings

**Authentication Failed**
```
Authentication failed - check API key
```
- Verify your API key is correct
- Check if the API key has the required permissions

**Workspace Creation Failed**
```
User developer cannot create workspace with package DEV_LARGE
```
- Check user type and entitlements
- Verify the resource package is allowed for your user type
- Check if you've reached the workspace limit

**Session Creation Failed**
```
Workspace test-workspace cannot allocate requested storage
```
- Check workspace storage limits
- Verify the workspace exists and is active
- Check if you have sufficient storage entitlements

**GPU Not Available**
```
GPU type A100 not available for user type PRO
```
- Check if your user type allows the requested GPU
- Verify the GPU is available in your region
- Consider upgrading to a higher user tier

### Debug Mode

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Create client with debug info
client = OnMemOSClient()
client._make_request("GET", "/health")  # Will show detailed request/response
```

### Health Check

```python
# Check server health
health = client.health_check()
print(f"Server status: {health['status']}")

# Get server info
info = client.get_server_info()
print(f"Server version: {info['version']}")
```

## Migration from v2

### Key Changes

1. **Workspace-based**: Sessions are now created within workspaces
2. **Resource Packages**: Use predefined packages instead of raw CPU/memory values
3. **Enum-based**: All resource specifications use enums for better type safety
4. **User Entitlements**: Resource limits are now per workspace, not per user

### Migration Guide

**Old v2 code:**
```python
session = client.create_session({
    "provider": "gke",
    "template": "python",
    "namespace": "project1",
    "user": "developer",
    "resource_tier": "medium",
    "request_persistent_storage": True
})
```

**New v3 code:**
```python
# First create workspace
workspace = client.create_workspace(
    user_id="developer",
    workspace_id="my-workspace",
    name="Development Workspace",
    resource_package=WorkspaceResourcePackage.DEV_MEDIUM
)

# Then create session in workspace
session = client.create_session_in_workspace(
    workspace_id="my-workspace",
    template="python",
    namespace="project1", 
    user="developer",
    request_persistent_storage=True
)
```

## Context Managers (Auto Cleanup) 🧹💰

**CRITICAL**: Always use context managers to ensure automatic cleanup and avoid unnecessary costs!

### Basic Context Manager

```python
# ✅ RECOMMENDED: Auto cleanup (saves money!)
with client.session_context({
    "workspace_id": "my-workspace",
    "template": "python",
    "namespace": "temp-work",
    "user": "developer",
    "ttl_minutes": 30
}) as session:
    result = client.execute_session(session["id"], "ls -la")
    print(result["stdout"])
    # Session automatically deleted when exiting context

# ❌ AVOID: Manual management (risky!)
session = client.create_session(session_spec)
try:
    # Do work...
    pass
finally:
    client.delete_session(session["id"])  # Might be forgotten!
```

### Workspace-Based Context Manager

```python
# ✅ RECOMMENDED: Workspace session with auto cleanup
with client.workspace_session_context(
    workspace_id="my-workspace",
    template="python",
    namespace="temp-dev",
    user="developer",
    ttl_minutes=30,
    request_persistent_storage=True
) as session:
    result = client.execute_session(session["id"], "pip install pandas")
    print("Dependencies installed!")
    # Session automatically deleted when exiting context
```

### Convenience Context Managers

#### Development Session

```python
# Development session with Ubuntu and persistent storage
with client.development_session_context(
    workspace_id="my-workspace",
    namespace="temp-dev",
    user="developer",
    ttl_minutes=60
) as session:
    # Install dependencies
    client.execute_session(session["id"], "apt-get update && apt-get install -y git")
    
    # Clone repository
    client.execute_session(session["id"], "git clone https://github.com/my/project.git /workspace/project")
    
    # Run tests
    result = client.execute_session(session["id"], "cd /workspace/project && python -m pytest")
    print(f"Tests passed: {result['success']}")
    # Session automatically deleted when exiting context
```

#### Python Session

```python
# Python session with optional GPU
with client.python_session_context(
    workspace_id="ml-workspace",
    namespace="experiment",
    user="researcher",
    gpu_type=GPUType.T4,
    request_persistent_storage=True
) as session:
    # Install ML libraries
    client.execute_session(session["id"], "pip install torch torchvision")
    
    # Check GPU
    result = client.execute_session(session["id"], "python -c 'import torch; print(torch.cuda.is_available())'")
    print(f"GPU available: {result['stdout'].strip()}")
    # Session automatically deleted when exiting context
```

#### Machine Learning Session

```python
# ML training session with GPU
with client.ml_session_context(
    workspace_id="ml-workspace",
    namespace="training",
    user="researcher",
    gpu_type=GPUType.A100,
    persistent_storage_size_gb=100
) as session:
    # Install ML libraries
    client.execute_session(session["id"], "pip install torch torchvision transformers datasets")
    
    # Run training
    result = client.execute_session(session["id"], "python train.py --epochs 10")
    print(f"Training completed: {result['success']}")
    # Session automatically deleted when exiting context
```

#### Custom Image Session

```python
# Custom image session
with client.custom_session_context(
    workspace_id="my-workspace",
    namespace="custom-app",
    user="developer",
    image_url="gcr.io/my-project/custom-app:latest"
) as session:
    # Run custom application
    result = client.execute_session(session["id"], "/app/start.sh")
    print(f"Custom app started: {result['success']}")
    # Session automatically deleted when exiting context
```

### Disabling Auto Cleanup (Advanced)

```python
# Disable auto cleanup for manual management
with client.session_context(session_spec, auto_cleanup=False) as session:
    # Do work...
    pass
# Session still exists, manually delete later
        client.delete_session(session["id"])
```

### Cost-Saving Best Practices

#### 1. **Always Use Context Managers**
```python
# ✅ Good: Automatic cleanup
with client.development_session_context(...) as session:
    # Do work
    pass

# ❌ Bad: Manual cleanup (risky)
session = client.create_development_session(...)
# Do work
client.delete_session(session["id"])  # Might be forgotten!
```

#### 2. **Set Appropriate TTL**
```python
# ✅ Good: Short TTL for quick tasks
with client.python_session_context(
    workspace_id="my-workspace",
    namespace="quick-test",
    user="developer",
    ttl_minutes=15  # Short TTL
) as session:
    result = client.execute_session(session["id"], "python --version")

# ❌ Bad: Long TTL for quick tasks
with client.python_session_context(
    workspace_id="my-workspace",
    namespace="quick-test",
    user="developer",
    ttl_minutes=120  # Unnecessarily long
) as session:
    result = client.execute_session(session["id"], "python --version")
```

#### 3. **Use Right-Sized Resources**
```python
# ✅ Good: Appropriate resources
with client.python_session_context(
    workspace_id="my-workspace",
    namespace="simple-task",
    user="developer",
    cpu_size=CPUSize.SMALL,      # Small CPU for simple task
    memory_size=MemorySize.SMALL  # Small memory for simple task
) as session:
    result = client.execute_session(session["id"], "echo 'Hello World'")

# ❌ Bad: Over-provisioned resources
with client.python_session_context(
    workspace_id="my-workspace",
    namespace="simple-task",
    user="developer",
    cpu_size=CPUSize.XLARGE,      # Too much CPU
    memory_size=MemorySize.XLARGE  # Too much memory
) as session:
    result = client.execute_session(session["id"], "echo 'Hello World'")
```

#### 4. **Batch Operations**
```python
# ✅ Good: Single session for multiple operations
with client.development_session_context(
    workspace_id="my-workspace",
    namespace="batch-work",
    user="developer"
) as session:
    # Install dependencies
    client.execute_session(session["id"], "pip install pandas numpy matplotlib")
    
    # Run multiple scripts
    client.execute_session(session["id"], "python script1.py")
    client.execute_session(session["id"], "python script2.py")
    client.execute_session(session["id"], "python script3.py")

# ❌ Bad: Multiple sessions for related work
for i in range(3):
    with client.development_session_context(...) as session:
        client.execute_session(session["id"], f"python script{i+1}.py")
```

#### 5. **Monitor Usage**
```python
# Monitor session usage to optimize costs
with client.ml_session_context(...) as session:
    # Get cost estimate before starting
    estimate = client.get_session_cost_estimate(session_spec)
    print(f"Estimated cost: ${estimate['estimated_total_cost']}")
    
    # Monitor usage during execution
    usage = client.monitor_session_usage(session["id"])
    print(f"CPU usage: {usage['cpu_percent']}%")
    print(f"Memory usage: {usage['memory_mb']} MB")
```

### Error Handling with Context Managers

```python
# Context managers handle cleanup even on errors
try:
    with client.ml_session_context(
        workspace_id="ml-workspace",
        namespace="experiment",
        user="researcher",
        gpu_type=GPUType.A100
    ) as session:
        # This might fail
        result = client.execute_session(session["id"], "python train.py")
        if not result["success"]:
            raise Exception("Training failed")
        
except Exception as e:
    print(f"Error occurred: {e}")
    # Session is automatically cleaned up even if error occurred
```

### Cleanup Utilities

```python
# Clean up expired sessions
cleaned = client.cleanup_expired_sessions(user="developer")
print(f"Cleaned up {cleaned} expired sessions")

# Force cleanup problematic sessions
success = client.force_cleanup_session("orphaned-session-id")
if success:
    print("Orphaned session cleaned up")
```

### Cost Estimation

```python
# Get cost estimate before creating session
estimate = client.get_session_cost_estimate({
    "workspace_id": "ml-workspace",
    "template": "python",
    "namespace": "experiment",
    "user": "researcher",
    "resource_package": ResourcePackage.ML_T4_MEDIUM,
    "gpu_type": GPUType.T4,
    "ttl_minutes": 120
})

print(f"Estimated cost: ${estimate['estimated_total_cost']}")
print(f"Cost per hour: ${estimate['total_cost_per_hour']}")
```
