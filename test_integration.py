#!/usr/bin/env python3
"""
OnMemOS v3 Integration Test
===========================
Tests the complete integration including GCP authentication, server startup, and basic functionality
"""

import os
import sys
import subprocess
import time
import requests
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

def test_gcp_authentication():
    """Test GCP authentication"""
    print("🔐 Testing GCP Authentication")
    print("=" * 40)
    
    # Check credentials
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        print("❌ GOOGLE_APPLICATION_CREDENTIALS not set")
        return False
    
    if not os.path.exists(creds_path):
        print(f"❌ Credentials file not found: {creds_path}")
        return False
    
    print(f"✅ Credentials file found: {creds_path}")
    
    # Test gcloud auth
    try:
        result = subprocess.run(["gcloud", "auth", "list", "--filter=status:ACTIVE"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and "ACTIVE" in result.stdout:
            print("✅ GCP authentication active")
        else:
            print("❌ No active GCP authentication")
            return False
    except Exception as e:
        print(f"❌ Error testing GCP auth: {e}")
        return False
    
    # Test GCS access
    try:
        result = subprocess.run(["gsutil", "ls"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            buckets = [line for line in result.stdout.split('\n') if line.strip()]
            print(f"✅ GCS access successful - {len(buckets)} buckets accessible")
        else:
            print("❌ GCS access failed")
            return False
    except Exception as e:
        print(f"❌ Error testing GCS access: {e}")
        return False
    
    return True

def test_server_startup():
    """Test server startup"""
    print("\n🚀 Testing Server Startup")
    print("=" * 40)
    
    # Check if server is already running
    try:
        response = requests.get("http://localhost:8080/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is already running")
            return True
    except:
        pass
    
    print("⚠️  Server not running - you need to start it manually")
    print("   Run: python start_server.py --dev")
    return False

def test_api_endpoints():
    """Test API endpoints"""
    print("\n🔌 Testing API Endpoints")
    print("=" * 40)
    
    base_url = "http://localhost:8080"
    api_key = "onmemos-internal-key-2024-secure"
    headers = {"X-API-Key": api_key}
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Health endpoint working")
            print(f"   Status: {data.get('status')}")
            print(f"   GCP: {data.get('gcp', {}).get('status', 'unknown')}")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing health endpoint: {e}")
        return False
    
    # Test root endpoint
    try:
        response = requests.get(f"{base_url}/", headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Root endpoint working")
            print(f"   Service: {data.get('service')}")
            print(f"   Version: {data.get('version')}")
        else:
            print(f"❌ Root endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing root endpoint: {e}")
        return False
    
    return True

def test_workspace_creation():
    """Test workspace creation"""
    print("\n🏠 Testing Workspace Creation")
    print("=" * 40)
    
    base_url = "http://localhost:8080"
    api_key = "onmemos-internal-key-2024-secure"
    headers = {"X-API-Key": api_key}
    
    try:
        # Create workspace
        params = {
            "template": "python",
            "namespace": "test",
            "user": "test-user",
            "ttl_minutes": 10
        }
        
        response = requests.post(f"{base_url}/v1/workspaces", params=params, headers=headers, timeout=30)
        
        if response.status_code == 200:
            workspace = response.json()
            workspace_id = workspace.get('id')
            print(f"✅ Workspace created: {workspace_id}")
            print(f"   Template: {workspace.get('template')}")
            print(f"   Namespace: {workspace.get('namespace')}")
            print(f"   User: {workspace.get('user')}")
            
            if workspace.get('bucket'):
                bucket = workspace['bucket']
                print(f"   🪣 Bucket: {bucket.get('bucket_name')}")
            
            if workspace.get('disk'):
                disk = workspace['disk']
                print(f"   💾 Disk: {disk.get('disk_name')}")
            
            # Clean up workspace
            delete_response = requests.delete(f"{base_url}/v1/workspaces/{workspace_id}", headers=headers, timeout=10)
            if delete_response.status_code == 200:
                print("✅ Workspace cleaned up")
            else:
                print("⚠️  Failed to cleanup workspace")
            
            return True
        else:
            print(f"❌ Workspace creation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing workspace creation: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 OnMemOS v3 Integration Test")
    print("=" * 50)
    
    tests = [
        ("GCP Authentication", test_gcp_authentication),
        ("Server Startup", test_server_startup),
        ("API Endpoints", test_api_endpoints),
        ("Workspace Creation", test_workspace_creation)
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
        print("🎉 All tests passed! OnMemOS v3 is ready to use.")
        print("\n💡 Next steps:")
        print("   1. Run: python interactive_shell_demo.py --interactive")
        print("   2. Try the WebSocket shell with slash commands")
        print("   3. Explore the GCP integration features")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
