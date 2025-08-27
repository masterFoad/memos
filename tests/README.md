# OnMemOS v3 Tests

This directory contains comprehensive tests for the OnMemOS v3 platform, organized by category.

## 📁 Directory Structure

### 🧪 Unit Tests (`/unit/`)
Basic unit tests for core functionality:
- `test_simple.py` - Simple functionality tests
- `test_utils.py` - Utility function tests

### 🔗 Integration Tests (`/integration/`)
End-to-end integration tests:
- `run_tests.py` - Test runner and orchestration
- `debug_permissions.py` - Permission and authentication tests

### ☁️ Cloud Tests (`/cloud/`)
Tests for Google Cloud Platform integration:
- `test_gcp_persistent_storage.py` - GCP persistent disk tests
- `test_bucket_implementation.py` - GCS bucket implementation tests
- `debug_bucket_service.py` - Bucket service debugging

### 🔐 Secrets Tests (`/secrets/`)
Tests for secrets management functionality:
- `test_secrets_namespaces.py` - Namespace secrets tests
- `test_secrets_with_code.py` - Secrets usage in code execution

### 📁 Namespace Tests (`/namespace/`)
Tests for namespace management:
- `test_namespace_storage_access.py` - Namespace storage access tests

### 🔄 CRUD Tests (`/crud/`)
Tests for Create, Read, Update, Delete operations:
- `test_sdk_crud_operations.py` - Comprehensive CRUD operations
- `test_list_clone_verify.py` - List → Clone → Verify workflow tests

## 🎯 Test Categories

### Unit Tests
- **Purpose**: Test individual components in isolation
- **Scope**: Single functions, classes, or modules
- **Speed**: Fast execution
- **Dependencies**: Minimal external dependencies

### Integration Tests
- **Purpose**: Test component interactions
- **Scope**: Multiple components working together
- **Speed**: Medium execution time
- **Dependencies**: May require server or external services

### Cloud Tests
- **Purpose**: Test Google Cloud Platform integration
- **Scope**: GCS, GCP disks, authentication
- **Speed**: Slower (network calls)
- **Dependencies**: GCP credentials and services

### Secrets Tests
- **Purpose**: Test secrets management and security
- **Scope**: Namespace and workspace secrets
- **Speed**: Medium execution time
- **Dependencies**: Secrets service

### Namespace Tests
- **Purpose**: Test namespace organization and isolation
- **Scope**: Namespace creation, management, access
- **Speed**: Medium execution time
- **Dependencies**: Namespace service

### CRUD Tests
- **Purpose**: Test resource lifecycle management
- **Scope**: Create, read, update, delete, clone operations
- **Speed**: Variable (depends on resource type)
- **Dependencies**: Various services

## 🚀 Running Tests

### Run All Tests
```bash
python tests/integration/run_tests.py
```

### Run Specific Categories
```bash
# Unit tests
python -m pytest tests/unit/

# Cloud tests
python -m pytest tests/cloud/

# Secrets tests
python -m pytest tests/secrets/
```

### Run Individual Tests
```bash
# Specific test file
python tests/crud/test_list_clone_verify.py

# Debug specific functionality
python tests/cloud/debug_bucket_service.py
```

## 📋 Prerequisites

- OnMemOS v3 server running
- Python 3.8+
- pytest installed
- Google Cloud credentials (for cloud tests)
- Required dependencies installed

## 🔧 Test Configuration

Tests use the following configuration:
- **Server URL**: `http://localhost:8080` (default)
- **Test Namespace**: `test-*` (isolated from production)
- **Test User**: `test-user-*` (isolated from production)
- **Cleanup**: Automatic cleanup after tests

## 📊 Test Results

Tests provide detailed output including:
- ✅ Pass/Fail status
- 📊 Performance metrics
- 🧹 Cleanup verification
- 📝 Detailed logs

## 🐛 Debugging

For debugging specific issues:
1. Run individual test files
2. Check server logs
3. Use debug scripts in `/cloud/` and `/integration/`
4. Verify GCP credentials and permissions

## 📚 Related Documentation

- [Examples](../examples/) - Practical usage examples
- [Main README](../README.md) - Project overview
- [Architecture Diagram](../ARCHITECTURE_DIAGRAM.md) - System architecture
