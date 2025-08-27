# OnMemOS v3 - GKE Pipeline Documentation

## Overview

OnMemOS v3 provides a unified session management system that supports multiple backend providers, including **Google Kubernetes Engine (GKE) Autopilot**. This document details the GKE implementation, features, and usage patterns.

**✅ Status: FULLY OPERATIONAL** - All GKE backend tests passing, persistent storage working correctly.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [GKE Features](#gke-features)
3. [Session Management](#session-management)
4. [Execution Modes](#execution-modes)
5. [Storage Options](#storage-options)
6. [User Management & Entitlements](#user-management--entitlements)
7. [API Reference](#api-reference)
8. [SDK Usage](#sdk-usage)
9. [Examples](#examples)
10. [Troubleshooting](#troubleshooting)
11. [Recent Fixes](#recent-fixes)

## Architecture Overview

### GKE Backend Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Client SDK    │───▶│  Unified API     │───▶│  GKE Provider   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │ Session Manager  │    │  GKE Service    │
                       └──────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │ Kubernetes API  │
                                               └─────────────────┘
```

### Key Components

1. **GKE Provider** (`server/services/sessions/gke_provider.py`)
   - Manages GKE session lifecycle
   - Handles user storage allocation and deallocation
   - Integrates with user management system
   - ✅ **Fixed**: Storage deallocation bug resolved

2. **GKE Service** (`server/services/gke/gke_service.py`)
   - Creates and manages Kubernetes pods
   - Handles storage mounting (GCS FUSE, Persistent Volumes)
   - Manages resource allocation and limits

3. **WebSocket Shell** (`server/services/gke/gke_websocket_shell.py`)
   - Provides interactive shell sessions
   - Supports multiple concurrent connections
   - Real-time command execution
   - ✅ **Fixed**: Normal WebSocket closures no longer logged as errors

## GKE Features

### ✅ Core Capabilities

- **Multiple Execution Modes**
  - **Synchronous**: Direct `kubectl exec` for quick commands
  - **Asynchronous**: Kubernetes Jobs for long-running tasks
  - **Interactive**: WebSocket shell for real-time interaction

- **Storage Options**
  - **Ephemeral**: Temporary storage using `emptyDir`
  - **Persistent**: Google Cloud Filestore via Persistent Volume Claims ✅ **WORKING**
  - **GCS FUSE**: Google Cloud Storage bucket mounting

- **Resource Management**
  - **Resource Tiers**: Configurable CPU/memory limits
  - **User Quotas**: Storage and resource entitlements
  - **Automatic Cleanup**: Session expiration and resource cleanup

- **Isolation & Security**
  - **Per-user isolation**: Separate namespaces and resources
  - **Security contexts**: Non-root execution, capability restrictions
  - **Network policies**: Pod-to-pod communication controls

### 🔧 Technical Specifications

- **Base Image**: Alpine Linux (configurable)
- **Shell**: `/bin/sh` (configurable)
- **Resource Limits**: Configurable tiers (Small, Medium, Large, XLarge)
- **Storage Classes**: `standard-rwo` (default), configurable
- **Namespace Pattern**: `onmemos-{namespace}`

## Session Management

### Session Lifecycle

1. **Creation**
   ```python
   session = client.create_session({
       "provider": "gke",
       "template": "python",
       "namespace": "my-project",
       "user": "developer",
       "ttl_minutes": 60,
       "request_persistent_storage": True,
       "persistent_storage_size_gb": 10
   })
   ```

2. **Execution**
   ```python
   # Sync execution
   result = client.execute_session(session_id, "ls -la")
   
   # Async execution
   result = client.execute_session(session_id, "long-running-task", async_execution=True)
   
   # Interactive shell
   # Connect via WebSocket to session.websocket URL
   ```

3. **Cleanup**
   ```python
   client.delete_session(session_id)
   ```

### Session States

- **Creating**: Pod is being created
- **Running**: Pod is ready and accepting commands
- **Terminating**: Pod is being deleted
- **Failed**: Pod creation or execution failed

## User Management & Entitlements

### User Types and Storage Limits

| User Type | Max Buckets | Max PVCs | Max Storage | Can Share | Cross Namespace |
|-----------|-------------|----------|-------------|-----------|-----------------|
| **Normal** | 1 | 1 | 50GB | ❌ | ❌ |
| **Pro** | 5 | 3 | 500GB | ✅ | ✅ |
| **Enterprise** | 100 | 50 | 10TB | ✅ | ✅ |
| **Admin** | 1000 | 1000 | 100TB | ✅ | ✅ |

### Storage Allocation

- **Persistent Storage**: Mounted at `/workspace/` in pods
- **GCS Buckets**: Available via environment variables and FUSE mounts
- **Automatic Cleanup**: Storage deallocated when sessions end
- **Usage Tracking**: Real-time monitoring of user storage consumption

## Recent Fixes

### ✅ Persistent Storage Issues Resolved

**Problem**: Persistent storage tests were failing due to user entitlement issues and storage deallocation bugs.

**Root Causes**:
1. **User Type Issue**: Test user was "normal" type with limited storage (1 PVC, 50GB)
2. **Storage Deallocation Bug**: `'dict' object has no attribute 'bucket_name'` error
3. **Resource Cleanup**: Orphaned PVCs causing incorrect usage tracking

**Solutions**:
1. **Upgraded Test User**: Changed from "normal" to "pro" type with higher entitlements
2. **Fixed Deallocation**: Proper conversion of dictionary to `UserStorageAllocation` object
3. **Resource Cleanup**: Implemented proper cleanup of orphaned Kubernetes resources

**Result**: ✅ All persistent storage tests now pass successfully.

### ✅ WebSocket Error Handling Improved

**Problem**: Normal WebSocket closures (code 1000) were being logged as errors, creating noise in logs.

**Solution**: 
- Added proper handling for `ConnectionClosed` exceptions
- Code 1000 closures now log as DEBUG level
- Other closure codes log as INFO level
- Only actual errors still log as ERROR level

**Result**: ✅ Cleaner logs with proper WebSocket lifecycle handling.

## Troubleshooting

### Common Issues

#### 1. Persistent Storage Allocation Fails

**Error**: `User tester (normal) cannot allocate requested storage`

**Solution**:
```bash
# Reset user to pro type with higher entitlements
python reset_test_user.py

# Clean up orphaned resources
kubectl get pvc --all-namespaces | grep tester
kubectl delete pvc <pvc-name> -n <namespace>
```

#### 2. WebSocket Connection Errors

**Error**: `Error receiving message: (1000, '')`

**Note**: This is actually a **normal WebSocket closure**, not an error. Code 1000 means "Normal Closure".

**Solution**: ✅ **Fixed** - Normal closures now log as DEBUG level.

#### 3. Storage Deallocation Errors

**Error**: `'dict' object has no attribute 'bucket_name'`

**Solution**: ✅ **Fixed** - Proper object conversion in storage deallocation.

#### 4. Orphaned Kubernetes Resources

**Problem**: Old pods, PVCs, or jobs not being cleaned up

**Solution**:
```bash
# Clean up old resources
python cleanup_orphans.py --containers
kubectl delete pods --all -n <namespace>
kubectl delete pvc --all -n <namespace>
kubectl delete jobs --all -n <namespace>
```

### Testing

#### Run Full Test Suite
```bash
# Test all GKE capabilities
python test_session_backends.py --backend gke

# Test persistent storage specifically
python test_persistent_storage.py
```

#### Expected Results
- ✅ All 8 GKE backend tests should pass
- ✅ Persistent storage should work with data persistence
- ✅ WebSocket connections should work without error noise
- ✅ Storage should be properly allocated and deallocated

### Monitoring

#### Check User Entitlements
```python
from server.models.users import user_manager

user = user_manager.get_user("tester")
entitlements = user_manager.get_user_entitlements("tester")
print(f"User type: {user.user_type}")
print(f"Max PVCs: {entitlements.max_persistent_storage}")
print(f"Max storage: {entitlements.max_storage_size_gb}GB")
```

#### Check Kubernetes Resources
```bash
# Check pods
kubectl get pods --all-namespaces | grep tester

# Check PVCs
kubectl get pvc --all-namespaces | grep tester

# Check jobs
kubectl get jobs --all-namespaces | grep tester
```

## API Reference

### Session Creation

```python
POST /v1/sessions
{
    "provider": "gke",
    "template": "python",
    "namespace": "my-project",
    "user": "developer",
    "ttl_minutes": 60,
    "request_persistent_storage": true,
    "persistent_storage_size_gb": 10,
    "resource_tier": "small"
}
```

### Session Execution

```python
POST /v1/sessions/{session_id}/execute
{
    "command": "ls -la",
    "timeout": 120,
    "async_execution": false
}
```

### WebSocket Shell

```python
# Connect to interactive shell
ws://localhost:8080/v1/gke/shell/{session_id}?k8s_ns={namespace}&pod={pod_name}
```

## SDK Usage

### Basic Usage

```python
from sdk.python.client import OnMemOSClient

client = OnMemOSClient(
    base_url="http://localhost:8080",
    api_key="your-api-key"
)

# Create session with persistent storage
session = client.create_session({
    "provider": "gke",
    "template": "python",
    "namespace": "test-project",
    "user": "developer",
    "ttl_minutes": 30,
    "request_persistent_storage": True,
    "persistent_storage_size_gb": 5
})

# Execute commands
result = client.execute_session(session["id"], "echo 'Hello from GKE!'")

# Clean up
client.delete_session(session["id"])
```

### Persistent Storage Example

```python
# Create session with persistent storage
session = client.create_session({
    "provider": "gke",
    "template": "python",
    "namespace": "data-analysis",
    "user": "analyst",
    "ttl_minutes": 120,
    "request_persistent_storage": True,
    "persistent_storage_size_gb": 20
})

# Write data to persistent storage
client.execute_session(session["id"], "echo 'Important data' > /workspace/data.txt")

# Read data back (persists across pod restarts)
result = client.execute_session(session["id"], "cat /workspace/data.txt")
print(result["stdout"])  # Output: Important data
```

## Examples

### Interactive Shell Session

```python
# Create session
session = client.create_session({
    "provider": "gke",
    "template": "python",
    "namespace": "interactive",
    "user": "developer",
    "ttl_minutes": 60
})

# Get WebSocket URL for interactive shell
ws_url = session["websocket"]
print(f"Connect to: {ws_url}")

# Use WebSocket client to connect and interact
import websockets
import asyncio

async def interactive_shell():
    async with websockets.connect(ws_url) as websocket:
        # Send command
        await websocket.send(json.dumps({
            "type": "command",
            "command": "ls -la"
        }))
        
        # Receive response
        response = await websocket.recv()
        print(json.loads(response))
```

### Long-Running Job

```python
# Submit long-running task as job
result = client.execute_session(
    session_id,
    "python long_analysis_script.py",
    async_execution=True
)

job_id = result["job_id"]

# Check job status
status = client.get_job_status(job_id, session_id)
print(f"Job status: {status['status']}")
```

---

**Last Updated**: August 27, 2025  
**Status**: ✅ All GKE functionality working correctly  
**Test Coverage**: 8/8 tests passing
