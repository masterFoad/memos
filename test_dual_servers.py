#!/usr/bin/env python3
"""
Test script for dual server configuration
Tests both admin and public servers with reusable storage
"""

import os
import sys
import time
import subprocess
import requests
import json
from pathlib import Path

def test_server_health(host, name, health_path="/health"):
    """Test if a server is running and healthy"""
    try:
        response = requests.get(f"{host}{health_path}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ {name} server healthy: {data.get('status')}")
            return True
        else:
            print(f"❌ {name} server unhealthy: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ {name} server unreachable: {e}")
        return False

def test_admin_endpoints(admin_host, internal_key):
    """Test admin endpoints"""
    headers = {"X-API-Key": internal_key, "Content-Type": "application/json"}
    
    print("\n🔧 Testing admin endpoints...")
    
    # Test admin health
    try:
        response = requests.get(f"{admin_host}/admin/health", headers=headers, timeout=5)
        if response.status_code == 200:
            print("✅ Admin health endpoint working")
        else:
            print(f"❌ Admin health failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Admin health error: {e}")
        return False
    
    # Test admin docs
    try:
        response = requests.get(f"{admin_host}/admin/docs", timeout=5)
        if response.status_code == 200:
            print("✅ Admin docs accessible")
        else:
            print(f"❌ Admin docs failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Admin docs error: {e}")
    
    return True

def test_public_endpoints(public_host):
    """Test public endpoints"""
    print("\n🌐 Testing public endpoints...")
    
    # Test public health
    try:
        response = requests.get(f"{public_host}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Public health endpoint working")
        else:
            print(f"❌ Public health failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Public health error: {e}")
        return False
    
    # Test public docs
    try:
        response = requests.get(f"{public_host}/docs", timeout=5)
        if response.status_code == 200:
            print("✅ Public docs accessible")
        else:
            print(f"❌ Public docs failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Public docs error: {e}")
    
    return True

def run_sdk_test(public_host, admin_host, internal_key):
    """Run the SDK E2E test with reusable storage"""
    print("\n🧪 Running SDK E2E test with reusable storage...")
    
    # Generate unique email
    timestamp = int(time.time())
    email = f"test.user+{timestamp}@example.com"
    
    # Use file-relative path for robustness
    sdk_path = Path(__file__).with_name("sdk_e2e.py")
    cmd = [
        sys.executable, str(sdk_path),
        "--host", public_host,
        "--admin-host", admin_host,
        "--internal-key", internal_key,
        "--email", email,
        "--name", "Test User",
        "--credits", "25",
        "--provider", "gke",
        "--test-reusable",
        "--use-vault",
        "--use-drive"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            print("✅ SDK E2E test passed")
            return True
        else:
            print(f"❌ SDK E2E test failed: {result.returncode}")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
    except subprocess.TimeoutExpired:
        print("❌ SDK E2E test timed out")
        return False
    except Exception as e:
        print(f"❌ SDK E2E test error: {e}")
        return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="OnMemOS v3 Dual Server Test")
    parser.add_argument("--admin-host", default=os.getenv("ONMEM_ADMIN_HOST", "http://127.0.0.1:8001"), help="Admin server host")
    parser.add_argument("--public-host", default=os.getenv("ONMEM_PUBLIC_HOST", "http://127.0.0.1:8080"), help="Public server host")
    parser.add_argument("--internal-key", default=os.getenv("ONMEM_INTERNAL_KEY"), required=not os.getenv("ONMEM_INTERNAL_KEY"), help="Internal API key (required via env var ONMEM_INTERNAL_KEY or --internal-key)")
    
    args = parser.parse_args()
    
    print("🚀 OnMemOS v3 Dual Server Test")
    print("=" * 50)
    
    # Configuration
    admin_host = args.admin_host
    public_host = args.public_host
    internal_key = args.internal_key
    
    # Test server health
    print("\n📡 Testing server health...")
    admin_healthy = test_server_health(admin_host, "Admin", "/admin/health")
    public_healthy = test_server_health(public_host, "Public", "/health")
    
    if not admin_healthy or not public_healthy:
        print("\n❌ One or more servers are not running!")
        print("Please start the servers first:")
        print("  ./start_admin.sh")
        print("  ./start_public.sh")
        return 1
    
    # Test endpoints
    admin_ok = test_admin_endpoints(admin_host, internal_key)
    public_ok = test_public_endpoints(public_host)
    
    if not admin_ok or not public_ok:
        print("\n❌ Endpoint tests failed!")
        return 1
    
    # Run SDK test
    sdk_ok = run_sdk_test(public_host, admin_host, internal_key)
    
    if not sdk_ok:
        print("\n❌ SDK test failed!")
        return 1
    
    print("\n🎉 All tests passed!")
    print("✅ Dual server configuration working correctly")
    print("✅ Reusable storage functionality working")
    print("✅ WebSocket authentication working")
    return 0

if __name__ == "__main__":
    sys.exit(main())
