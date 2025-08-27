#!/usr/bin/env python3
"""
Test OnMemOS v3 Client
======================
Tests the client with proper endpoints and I/O handling
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from sdk.python.client import OnMemOSClient

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_client_initialization():
    """Test client initialization"""
    print("🔧 Testing Client Initialization")
    print("=" * 40)
    
    try:
        # Test with default settings
        client = OnMemOSClient()
        print("✅ Client initialized with default settings")
        print(f"   Base URL: {client.base_url}")
        print(f"   API Key: {client.api_key[:10]}...")
        
        # Test with custom settings
        client2 = OnMemOSClient("http://localhost:8080", "custom-key")
        print("✅ Client initialized with custom settings")
        print(f"   Base URL: {client2.base_url}")
        print(f"   API Key: {client2.api_key}")
        
        return True
        
    except Exception as e:
        print(f"❌ Client initialization failed: {e}")
        return False

def test_health_check():
    """Test health check endpoint"""
    print("\n🏥 Testing Health Check")
    print("=" * 40)
    
    try:
        client = OnMemOSClient()
        health = client.health_check()
        
        print("✅ Health check successful")
        print(f"   Status: {health.get('status', 'unknown')}")
        print(f"   Version: {health.get('version', 'unknown')}")
        
        if 'gcp' in health:
            gcp_status = health['gcp']
            print(f"   GCP Status: {gcp_status.get('status', 'unknown')}")
            print(f"   GCP Message: {gcp_status.get('message', 'unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_server_info():
    """Test server info endpoint"""
    print("\nℹ️  Testing Server Info")
    print("=" * 40)
    
    try:
        client = OnMemOSClient()
        info = client.get_server_info()
        
        print("✅ Server info retrieved")
        print(f"   Service: {info.get('service', 'unknown')}")
        print(f"   Version: {info.get('version', 'unknown')}")
        print(f"   Status: {info.get('status', 'unknown')}")
        
        endpoints = info.get('endpoints', {})
        print(f"   Available endpoints: {len(endpoints)}")
        for name, path in endpoints.items():
            print(f"     - {name}: {path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Server info failed: {e}")
        return False

def test_workspace_creation():
    """Test workspace creation"""
    print("\n🏠 Testing Workspace Creation")
    print("=" * 40)
    
    try:
        client = OnMemOSClient()
        
        # Create workspace
        workspace = client.create_workspace(
            template="python",
            namespace="test",
            user="test-user",
            ttl_minutes=10
        )
        
        workspace_id = workspace.get('id')
        print(f"✅ Workspace created: {workspace_id}")
        print(f"   Template: {workspace.get('template', 'unknown')}")
        print(f"   Namespace: {workspace.get('namespace', 'unknown')}")
        print(f"   User: {workspace.get('user', 'unknown')}")
        
        # Get workspace info
        workspace_info = client.get_workspace(workspace_id)
        print(f"✅ Workspace info retrieved")
        print(f"   Status: {workspace_info.get('status', 'unknown')}")
        
        # List workspaces
        workspaces = client.list_workspaces(namespace="test")
        print(f"✅ Listed {len(workspaces)} workspaces in test namespace")
        
        # Clean up
        success = client.delete_workspace(workspace_id)
        if success:
            print("✅ Workspace cleaned up")
        else:
            print("⚠️  Failed to cleanup workspace")
        
        return True
        
    except Exception as e:
        print(f"❌ Workspace creation failed: {e}")
        return False

def test_storage_operations():
    """Test storage operations"""
    print("\n💾 Testing Storage Operations")
    print("=" * 40)
    
    try:
        client = OnMemOSClient()
        
        # Setup namespace storage
        storage = client.setup_namespace_storage("test", "test-user")
        print("✅ Namespace storage setup")
        print(f"   Namespace: {storage.get('namespace', 'unknown')}")
        print(f"   User: {storage.get('user', 'unknown')}")
        
        # List namespace storage
        storage_list = client.list_namespace_storage("test")
        print("✅ Namespace storage listed")
        print(f"   Total buckets: {storage_list.get('total_buckets', 0)}")
        print(f"   Total disks: {storage_list.get('total_disks', 0)}")
        
        # Clean up
        success = client.delete_namespace_storage("test", "test-user")
        if success:
            print("✅ Namespace storage cleaned up")
        else:
            print("⚠️  Failed to cleanup namespace storage")
        
        return True
        
    except Exception as e:
        print(f"❌ Storage operations failed: {e}")
        return False

def test_bucket_operations():
    """Test bucket operations"""
    print("\n🪣 Testing Bucket Operations")
    print("=" * 40)
    
    try:
        client = OnMemOSClient()
        
        # Create bucket
        bucket = client.create_bucket("test-bucket", "test", "test-user")
        print("✅ Bucket created")
        print(f"   Name: {bucket.get('bucket_name', 'unknown')}")
        print(f"   URL: {bucket.get('url', 'unknown')}")
        
        # List buckets
        buckets = client.list_buckets_in_namespace("test")
        print(f"✅ Listed {len(buckets)} buckets in test namespace")
        
        # Clean up
        success = client.delete_bucket("test-bucket")
        if success:
            print("✅ Bucket cleaned up")
        else:
            print("⚠️  Failed to cleanup bucket")
        
        return True
        
    except Exception as e:
        print(f"❌ Bucket operations failed: {e}")
        return False

def test_disk_operations():
    """Test disk operations"""
    print("\n💿 Testing Disk Operations")
    print("=" * 40)
    
    try:
        client = OnMemOSClient()
        
        # Create disk
        disk = client.create_persistent_disk("test-disk", "test", "test-user", 5)
        print("✅ Disk created")
        print(f"   Name: {disk.get('disk_name', 'unknown')}")
        print(f"   Size: {disk.get('size_gb', 'unknown')} GB")
        
        # List disks
        disks = client.list_persistent_disks("test")
        print(f"✅ Listed {len(disks)} disks in test namespace")
        
        # Clean up
        success = client.delete_persistent_disk("test-disk")
        if success:
            print("✅ Disk cleaned up")
        else:
            print("⚠️  Failed to cleanup disk")
        
        return True
        
    except Exception as e:
        print(f"❌ Disk operations failed: {e}")
        return False

def test_connection():
    """Test connection to server"""
    print("\n🔌 Testing Connection")
    print("=" * 40)
    
    try:
        client = OnMemOSClient()
        
        if client.test_connection():
            print("✅ Connection test successful")
            return True
        else:
            print("❌ Connection test failed")
            return False
            
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 OnMemOS v3 Client Test")
    print("=" * 50)
    
    tests = [
        ("Client Initialization", test_client_initialization),
        ("Connection Test", test_connection),
        ("Health Check", test_health_check),
        ("Server Info", test_server_info),
        ("Workspace Creation", test_workspace_creation),
        ("Storage Operations", test_storage_operations),
        ("Bucket Operations", test_bucket_operations),
        ("Disk Operations", test_disk_operations)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        print("-" * 30)
        
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} ERROR: {e}")
    
    print(f"\n🎯 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Client is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
