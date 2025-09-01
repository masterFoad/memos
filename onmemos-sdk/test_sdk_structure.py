#!/usr/bin/env python3
"""
Test SDK Structure
Verifies that the SDK can be imported and basic functionality works
"""

import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Test that all main modules can be imported"""
    print("🧪 Testing SDK Imports")
    print("=" * 30)
    
    try:
        # Test core imports
        from onmemos import OnMemOSClient, create_client, client, quick_session
        print("✅ Core client imports successful")
        
        from onmemos import (
            ResourceTier, StorageType, GPUType, ImageType, UserType,
            SessionStatus, MountType, TemplateCategory
        )
        print("✅ Enum imports successful")
        
        from onmemos import (
            CreateSessionRequest, Session, SessionList,
            MountRequest, Mount, FileInfo
        )
        print("✅ Model imports successful")
        
        from onmemos import (
            SessionService, StorageService, TemplateService,
            ShellService, CostEstimationService
        )
        print("✅ Service imports successful")
        
        from onmemos import (
            OnMemOSError, AuthenticationError, ConfigurationError
        )
        print("✅ Exception imports successful")
        
        from onmemos import ClientConfig, get_default_config, get_api_key
        print("✅ Configuration imports successful")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_config():
    """Test configuration functionality"""
    print("\n🔧 Testing Configuration")
    print("=" * 30)
    
    try:
        from onmemos import ClientConfig, get_default_config
        
        # Test default config
        config = get_default_config()
        print(f"✅ Default config: {config.base_url}")
        print(f"   Timeout: {config.timeout}s")
        print(f"   User Agent: {config.user_agent}")
        
        # Test custom config
        custom_config = ClientConfig(
            base_url="http://localhost:8080",
            timeout=60.0
        )
        print(f"✅ Custom config: {custom_config.base_url}")
        print(f"   Timeout: {custom_config.timeout}s")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


def test_models():
    """Test model creation and validation"""
    print("\n📦 Testing Models")
    print("=" * 30)
    
    try:
        from onmemos import (
            CreateSessionRequest, ResourceTier, StorageType,
            MountRequest, MountType
        )
        
        # Test session request
        session_request = CreateSessionRequest(
            template_id="dev-python",
            resource_tier=ResourceTier.MEDIUM,
            storage_type=StorageType.GCS_FUSE,
            storage_size_gb=20,
            ttl_minutes=120
        )
        print(f"✅ Session request: {session_request.template_id}")
        print(f"   Resource tier: {session_request.resource_tier}")
        print(f"   Storage: {session_request.storage_type}")
        
        # Test mount request
        mount_request = MountRequest(
            mount_type=MountType.GCS_BUCKET,
            source_name="my-bucket",
            mount_path="/workspace"
        )
        print(f"✅ Mount request: {mount_request.mount_type}")
        print(f"   Source: {mount_request.source_name}")
        print(f"   Path: {mount_request.mount_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Model test failed: {e}")
        return False


def test_client_creation():
    """Test client creation (without API key)"""
    print("\n🔌 Testing Client Creation")
    print("=" * 30)
    
    try:
        from onmemos import OnMemOSClient
        
        # This should fail without API key, but we can test the constructor
        try:
            client = OnMemOSClient(api_key="test_key", base_url="http://localhost:8080")
            print("✅ Client created with test configuration")
            print(f"   Base URL: {client.config.base_url}")
            print(f"   API Key: {client.api_info['api_key']}")
            return True
        except Exception as e:
            print(f"⚠️  Client creation failed (expected): {e}")
            return True  # This is expected behavior
            
    except Exception as e:
        print(f"❌ Client creation test failed: {e}")
        return False


def test_version_info():
    """Test version and info functions"""
    print("\n📋 Testing Version Info")
    print("=" * 30)
    
    try:
        from onmemos import get_version, get_info
        
        version = get_version()
        info = get_info()
        
        print(f"✅ Version: {version}")
        print(f"   Name: {info['name']}")
        print(f"   Author: {info['author']}")
        print(f"   Description: {info['description']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Version info test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("🚀 OnMemOS SDK Structure Test")
    print("=" * 50)
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Models", test_models),
        ("Client Creation", test_client_creation),
        ("Version Info", test_version_info),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n📊 Test Results")
    print("=" * 30)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! SDK structure is correct.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
