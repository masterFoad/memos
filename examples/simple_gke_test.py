#!/usr/bin/env python3
"""
Simple GKE Test Script
Tests GKE backend step by step with clear logging
"""

import sys
import os
import time
import json
from typing import Dict, Any

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sdk', 'python'))

from client import OnMemOSClient

# ============================================================================
# Configuration
# ============================================================================

API_BASE = "http://127.0.0.1:8080"
API_KEY = "onmemos-internal-key-2024-secure"

def test_gke_backend():
    """Test GKE backend step by step"""
    print("🚀 Simple GKE Backend Test")
    print("=" * 50)
    
    # Initialize client
    print("1️⃣ Initializing OnMemOS Client...")
    client = OnMemOSClient(base_url=API_BASE, api_key=API_KEY)
    print("   ✅ Client initialized")
    
    # Test 1: Create a simple GKE session with persistent volume storage
    print("\n2️⃣ Creating GKE Session with Persistent Volume Storage...")
    timestamp = int(time.time())
    session_spec = {
        "provider": "gke",
        "template": "python",
        "namespace": "test-user",
        "user": "pro-user",  # Use PRO user for testing
        "workspace_id": f"test-workspace-{timestamp}",
        "ttl_minutes": 60,
        "resource_package": "dev_small",  # Specify resource package explicitly
        "storage_config": {
            "storage_type": "persistent_volume",
            "mount_path": "/workspace",
            "pvc_name": f"pvc-test-user-pro-user-{timestamp}",
            "pvc_size": "10Gi",
            "storage_class": "standard-rwo"
        }
    }
    
    print(f"   📋 Session Spec: {json.dumps(session_spec, indent=2)}")
    
    try:
        session = client.create_session(session_spec)
        print(f"   ✅ Session created: {session}")
        
        if not session or "id" not in session:
            print(f"   ❌ Failed to create session: {session}")
            return False
        
        workspace_id = session["id"]
        print(f"   🆔 Workspace ID: {workspace_id}")
    
        
        # Test 3: Execute a simple command
        print("\n4️⃣ Testing command execution...")
        result = client.execute_session(
            workspace_id,
            "echo 'Hello from GKE!' && pwd && ls -la /workspace",
            timeout=180
        )
        
        print(f"   📤 Command Result: {json.dumps(result, indent=2)}")
        
        if result.get("success"):
            print("   ✅ Command executed successfully!")
            print(f"   📄 Output: {result.get('stdout', '')}")
        else:
            print(f"   ❌ Command failed: {result.get('stderr', '')}")
            return False
        
        # Test 4: Test file operations
        print("\n5️⃣ Testing file operations...")
        
        # Create a file
        create_result = client.execute_session(
            workspace_id,
            "echo 'This is a test file from GKE' > /workspace/test_file.txt",
            timeout=180
        )
        
        if create_result.get("success"):
            print("   ✅ File created successfully!")
        else:
            print(f"   ❌ File creation failed: {create_result.get('stderr', '')}")
            return False
        
        # Read the file
        read_result = client.execute_session(
            workspace_id,
            "cat /workspace/test_file.txt",
            timeout=180
        )
        
        if read_result.get("success"):
            print(f"   ✅ File read successfully: {read_result.get('stdout', '')}")
        else:
            print(f"   ❌ File read failed: {read_result.get('stderr', '')}")
            return False
        
        # List files
        list_result = client.execute_session(
            workspace_id,
            "ls -la /workspace/",
            timeout=180
        )
        
        if list_result.get("success"):
            print(f"   ✅ Directory listing: {list_result.get('stdout', '')}")
        else:
            print(f"   ❌ Directory listing failed: {list_result.get('stderr', '')}")
            return False
        
        print("\n🎉 All tests passed! GKE backend is working correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = test_gke_backend()
        if success:
            print("\n✅ GKE Backend Test: PASSED")
        else:
            print("\n❌ GKE Backend Test: FAILED")
    except KeyboardInterrupt:
        print("\n\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
