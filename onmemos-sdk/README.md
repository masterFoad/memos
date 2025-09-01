# OnMemOS v3 Python SDK

Official Python client library for OnMemOS v3 - Cloud Development Environments

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/badge/pypi-onmemos--sdk-blue.svg)](https://pypi.org/project/onmemos-sdk/)

## 🚀 Features

- **🔑 Auto API Key Detection** - Automatically finds API keys in `.env` files
- **📦 Type-Safe Models** - Full Pydantic models with validation
- **🔄 Async Support** - Modern async/await patterns throughout
- **🛡️ Context Managers** - Automatic resource cleanup with `with` statements
- **💾 Storage Operations** - Mount buckets, filestores, and persistent volumes
- **📊 Cost Estimation** - Pre-session cost prediction and optimization
- **🎯 Session Management** - Create, manage, and monitor development sessions
- **🐚 Shell Access** - WebSocket-based interactive shell integration

## 📦 Installation

```bash
pip install onmemos-sdk
```

### Development Installation

```bash
git clone https://github.com/onmemos/onmemos-sdk.git
cd onmemos-sdk
pip install -e .
```

## 🔑 Quick Start

### 1. Set up API Key

Create a `.env` file in your project directory:

```bash
# .env
ONMEMOS_API_KEY=your_api_key_here
ONMEMOS_BASE_URL=https://api.onmemos.com  # Optional, defaults to production
```

### 2. Basic Usage

```python
import asyncio
from onmemos import OnMemOSClient, CreateSessionRequest, ResourceTier

async def main():
    # Client automatically detects API key from .env
    async with OnMemOSClient() as client:
        # Create a development session
        session = await client.sessions.create_session(
            CreateSessionRequest(
                template_id="dev-python",
                resource_tier=ResourceTier.MEDIUM,
                ttl_minutes=120
            )
        )
        
        print(f"Session created: {session.session_id}")
        print(f"Cost per hour: ${session.cost_per_hour:.4f}")

# Run
asyncio.run(main())
```

### 3. Quick Session Creation

```python
from onmemos import quick_session

async def quick_dev():
    # One-liner session creation with auto-cleanup
    session_info = await quick_session("dev-python")
    print(f"Shell URL: {session_info['shell_url']}")

asyncio.run(quick_dev())
```

## 🏗️ Architecture

```
onmemos-sdk/
├── core/           # Core client and configuration
├── models/         # Pydantic data models
├── services/       # API service implementations
├── cli/            # Command-line interface
└── utils/          # Utility functions
```

## 📚 API Reference

### Core Client

#### `OnMemOSClient`

Main client class with auto API key detection.

```python
from onmemos import OnMemOSClient

# Auto-detect API key from .env
client = OnMemOSClient()

# Or specify explicitly
client = OnMemOSClient(api_key="your_key", base_url="http://localhost:8080")

# Use as context manager
async with OnMemOSClient() as client:
    # Your code here
    pass
```

#### Configuration

```python
from onmemos import ClientConfig

config = ClientConfig(
    base_url="https://api.onmemos.com",
    timeout=30.0,
    max_connections=100
)

client = OnMemOSClient(config=config)
```

### Session Management

#### Create Session

```python
from onmemos import CreateSessionRequest, ResourceTier, StorageType

request = CreateSessionRequest(
    template_id="dev-python",
    resource_tier=ResourceTier.MEDIUM,
    storage_type=StorageType.GCS_FUSE,
    storage_size_gb=20,
    ttl_minutes=120,
    env_vars={"PYTHONPATH": "/workspace"},
    labels={"purpose": "development"}
)

session = await client.sessions.create_session(request)
```

#### List Sessions

```python
# Get all sessions
sessions = await client.sessions.list_sessions()

# Filter by status
active_sessions = await client.sessions.list_sessions(status="running")

# Pagination
sessions = await client.sessions.list_sessions(page=1, per_page=10)

# Access session properties
for session in sessions.sessions:
    print(f"ID: {session.session_id}")
    print(f"Status: {session.status}")
    print(f"Cost: ${session.total_cost:.4f}")
    print(f"Duration: {session.duration_minutes} minutes")
```

#### Session Operations

```python
# Get session details
session = await client.sessions.get_session("session_id")

# Update session
await client.sessions.update_session("session_id", ttl_minutes=240)

# Delete session
await client.sessions.delete_session("session_id")

# Pause/Resume
await client.sessions.pause_session("session_id")
await client.sessions.resume_session("session_id")
```

### Storage Operations

#### Mount Storage

```python
from onmemos import MountRequest, MountType

# Mount GCS bucket
mount_request = MountRequest(
    mount_type=MountType.GCS_BUCKET,
    source_name="my-dev-bucket",
    mount_path="/workspace",
    read_only=False
)

mount = await client.storage.mount_storage("session_id", mount_request)

# Mount Filestore
filestore_request = MountRequest(
    mount_type=MountType.FILESTORE,
    source_name="my-filestore",
    mount_path="/shared",
    read_only=True
)

filestore_mount = await client.storage.mount_storage("session_id", filestore_request)
```

#### File Operations

```python
# List files
files = await client.storage.list_files("session_id", "/workspace")

# Upload file
await client.storage.upload_file(
    "session_id",
    local_path="./main.py",
    remote_path="/workspace/main.py"
)

# Download file
await client.storage.download_file(
    "session_id",
    remote_path="/workspace/output.txt",
    local_path="./output.txt"
)

# Get storage usage
usage = await client.storage.get_usage("session_id")
print(f"Used: {usage.used_size_gb:.2f}GB / {usage.total_size_gb:.2f}GB")
```

### Templates

#### List Templates

```python
# Get all templates
templates = await client.templates.list_templates()

# Filter by category
dev_templates = await client.templates.list_templates(category="development")

# Get popular templates
popular = await client.templates.get_popular_templates(limit=5)

# Get specific template
template = await client.templates.get_template("dev-python")
```

### Cost Estimation

#### Estimate Session Cost

```python
# Estimate cost for template
estimate = await client.cost_estimation.estimate_template_cost(
    "dev-python",
    duration_hours=4.0
)

print(f"Estimated cost: ${estimate.total_cost:.4f}")
print(f"Confidence: {estimate.confidence}")
print("Recommendations:")
for rec in estimate.recommendations:
    print(f"  • {rec}")

# Compare configurations
configs = [
    {"resource_tier": "small", "storage_type": "ephemeral"},
    {"resource_tier": "medium", "storage_type": "gcs_fuse"},
    {"resource_tier": "large", "gpu_type": "t4"}
]

comparison = await client.cost_estimation.compare_costs(configs, duration_hours=2.0)
```

### Shell Access

#### Get Shell Information

```python
# Get shell connection info
shell_info = await client.shell.get_connection_info("session_id")

# Get shell URL
shell_url = client.get_shell_url(
    "session_id",
    k8s_ns="namespace",
    pod_name="pod-name"
)

print(f"Connect to shell: {shell_url}")
```

## 🔧 Advanced Usage

### Custom Configuration

```python
from onmemos import ClientConfig, RetryConfig

# Custom retry configuration
retry_config = RetryConfig(
    max_retries=5,
    base_delay=2.0,
    max_delay=120.0,
    exponential_base=3.0,
    jitter=True
)

# Custom client configuration
config = ClientConfig(
    base_url="https://dev-api.onmemos.com",
    timeout=60.0,
    retry_config=retry_config,
    max_connections=200
)

client = OnMemOSClient(config=config)
```

### Error Handling

```python
from onmemos import (
    OnMemOSError, AuthenticationError, SessionError, StorageError
)

try:
    session = await client.sessions.create_session(request)
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
except SessionError as e:
    print(f"Session creation failed: {e}")
except StorageError as e:
    print(f"Storage operation failed: {e}")
except OnMemOSError as e:
    print(f"OnMemOS error: {e}")
```

### Batch Operations

```python
import asyncio

async def create_multiple_sessions(template_ids):
    """Create multiple sessions concurrently"""
    tasks = []
    for template_id in template_ids:
        request = CreateSessionRequest(template_id=template_id)
        task = client.sessions.create_session(request)
        tasks.append(task)
    
    sessions = await asyncio.gather(*tasks, return_exceptions=True)
    return sessions

# Usage
template_ids = ["dev-python", "data-science", "ml-training"]
sessions = await create_multiple_sessions(template_ids)
```

## 🖥️ Command Line Interface

The SDK includes a command-line interface for quick operations:

```bash
# Install CLI
pip install onmemos-sdk[cli]

# Configure API key
onmemos auth --api-key YOUR_API_KEY

# List sessions
onmemos sessions list

# Create session
onmemos sessions create --template dev-python --storage 20gb

# Mount storage
onmemos storage mount --session SESSION_ID --bucket my-bucket --path /workspace

# Upload files
onmemos storage upload --session SESSION_ID --local main.py --remote /workspace/

# Get shell access
onmemos shell connect --session SESSION_ID
```

## 📁 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ONMEMOS_API_KEY` | Your OnMemOS API key | Required |
| `ONMEMOS_BASE_URL` | API base URL | `https://api.onmemos.com` |
| `ONMEMOS_TIMEOUT` | Request timeout (seconds) | `30.0` |

## 🔒 Security

- **API Key Management**: Secure storage and auto-detection
- **Environment Isolation**: Each session runs in isolated containers
- **Network Security**: All communication over HTTPS/WSS
- **Permission Control**: API key-based access control

## 🧪 Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=onmemos

# Run specific test categories
pytest -m "unit"
pytest -m "integration"
```

## 📖 Examples

See the `examples/` directory for complete working examples:

- `basic_usage.py` - Basic SDK operations
- `storage_operations.py` - Storage and mounting examples
- `batch_operations.py` - Concurrent operations
- `cli_examples.py` - Command-line interface usage

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: [https://docs.onmemos.com/sdk](https://docs.onmemos.com/sdk)
- **Issues**: [GitHub Issues](https://github.com/onmemos/onmemos-sdk/issues)
- **Discussions**: [GitHub Discussions](https://github.com/onmemos/onmemos-sdk/discussions)
- **Email**: team@onmemos.com

## 🔗 Related Links

- [OnMemOS v3](https://github.com/onmemos/onmemos-v3) - Main platform
- [API Documentation](https://docs.onmemos.com/api) - REST API reference
- [Web Interface](https://app.onmemos.com) - Web-based management

---

**Made with ❤️ by the OnMemOS Team**
