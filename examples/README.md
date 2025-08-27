# OnMemOS v3 Examples

This directory contains practical examples demonstrating how to use the OnMemOS v3 SDK and platform.

## 📁 Directory Structure

### 🚀 Basic Examples (`/basic/`)
Simple examples to get started with OnMemOS v3:
- `demo_simple.py` - Basic workspace creation and execution
- `explore_sdk_simple.py` - Simple SDK exploration
- `explore_sdk.py` - SDK functionality exploration

### 🔧 Advanced Examples (`/advanced/`)
Complex examples showcasing advanced features:
- `demo_real_world.py` - Real-world application scenarios
- `demo_integration.py` - Integration examples
- `demo_real_implementation.py` - Production-ready implementations

### ☁️ Cloud Integration (`/cloud-integration/`)
Examples demonstrating Google Cloud Platform integration:
- `demo_unified_gcp_namespace.py` - Complete GCP namespace management
- `demo_cloud_persistent_storage.py` - GCP persistent disk usage
- `demo_bucket_features.py` - GCS bucket operations
- `gcloud_auth.py` - Google Cloud authentication utilities

### 🔐 Secrets Management (`/secrets-management/`)
Examples for secure secrets handling:
- *Coming soon* - Examples for namespace and workspace secrets

### 📁 Namespace Management (`/namespace-management/`)
Examples for namespace organization and management:
- `demo_user_namespace_hierarchy.py` - User namespace hierarchy
- `demo_reusable_namespace.py` - Reusable namespace patterns
- `cloud_namespace_manager.py` - Cloud namespace management utilities
- `namespace_manager.py` - Namespace management utilities

### 🧹 Auto-Cleanup (`/auto-cleanup/`)
Examples demonstrating automatic resource cleanup:
- `demo_auto_cleanup.py` - Context manager cleanup patterns

## 🎯 How to Use

1. **Start with Basic Examples**: Begin with `/basic/` to understand core concepts
2. **Explore Advanced Features**: Move to `/advanced/` for complex scenarios
3. **Cloud Integration**: Use `/cloud-integration/` for GCP features
4. **Production Patterns**: Reference `/auto-cleanup/` for best practices

## 📋 Prerequisites

- OnMemOS v3 server running
- Python 3.8+
- Required dependencies installed
- Google Cloud credentials (for cloud examples)

## 🚀 Quick Start

```bash
# Run a basic example
python examples/basic/demo_simple.py

# Run a cloud integration example
python examples/cloud-integration/demo_bucket_features.py
```

## 📚 Related Documentation

- [Main README](../README.md) - Project overview
- [Architecture Diagram](../ARCHITECTURE_DIAGRAM.md) - System architecture
- [Tests](../tests/) - Test examples and validation
