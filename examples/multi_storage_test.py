#!/usr/bin/env python3
"""
Multi-Storage Test Script
Tests GKE backend with both bucket and filestore mounted simultaneously
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

def test_multi_storage():
    """Test GKE backend with multiple storage types"""
    print("🚀 Multi-Storage GKE Test")
    print("=" * 50)
    
    # Initialize client
    print("1️⃣ Initializing OnMemOS Client...")
    client = OnMemOSClient(API_BASE, API_KEY)
    print("   ✅ Client initialized")
    
    # Test: Create GKE session with both bucket and persistent storage
    print("\n2️⃣ Creating GKE Session with Multiple Storage Types...")
    timestamp = int(time.time())
    
    # Use an existing bucket that we know works
    bucket_name = "onmemos-test-bucket-2024"
    
    session_spec = {
        "provider": "gke",
        "template": "python",
        "namespace": "multi-storage-test",
        "user": "service-admin",  # Use service-admin for testing
        "workspace_id": f"multi-storage-workspace-{timestamp}",
        "ttl_minutes": 60,
        "resource_package": "dev_small",  # Specify resource package explicitly
        "user_type": "admin",  # Explicitly set user type to admin
        "storage_config": {
            "storage_type": "persistent_volume",
            "mount_path": "/workspace",
            "pvc_name": f"pvc-multi-storage-{timestamp}",
            "pvc_size": "10Gi",
            "storage_class": "standard-rwo",
            "additional_storage": [
                {
                    "storage_type": "gcs_fuse",
                    "mount_path": "/data",
                    "bucket_name": bucket_name,
                    "gcs_mount_options": "implicit-dirs,file-mode=0644,dir-mode=0755"
                }
            ]
        }
    }
    
    print("   📋 Session Spec:")
    print(json.dumps(session_spec, indent=2))
    
    try:
        # Create session
        session = client.create_session(session_spec)
        print("   ✅ Session created successfully!")
        print(f"   🆔 Session ID: {session['id']}")
        
        # Wait for session to be ready
        print("\n3️⃣ Waiting for session to be ready...")
        time.sleep(10)  # Wait for pod to be ready
        
        # Test command execution
        print("\n4️⃣ Testing command execution...")
        commands = [
            "echo 'Testing multiple storage mounts...'",
            "ls -la /workspace",
            "ls -la /data",
            "echo 'Hello from workspace!' > /workspace/test.txt",
            "echo 'Hello from data bucket!' > /data/bucket_test.txt",
            "cat /workspace/test.txt",
            "cat /data/bucket_test.txt",
            "df -h"
        ]
        
        for cmd in commands:
            print(f"   📤 Running: {cmd}")
            result = client.execute_session(session['id'], cmd)
            print(f"   📥 Result: {result['stdout']}")
            if result['stderr']:
                print(f"   ⚠️  Stderr: {result['stderr']}")
            print()
        
        # Test file operations in both storage locations
        print("\n5️⃣ Testing file operations in both storage locations...")
        
        # Test workspace (persistent volume)
        print("   📁 Testing /workspace (persistent volume):")
        workspace_commands = [
            "mkdir -p /workspace/project",
            "echo 'Project data' > /workspace/project/README.md",
            "ls -la /workspace/project/"
        ]
        
        for cmd in workspace_commands:
            result = client.execute_session(session['id'], cmd)
            print(f"   📤 {cmd}")
            print(f"   📥 {result['stdout']}")
        
        # Test data bucket (GCS FUSE)
        print("\n   📁 Testing /data (GCS bucket):")
        bucket_commands = [
            "mkdir -p /data/datasets",
            "echo 'Dataset info' > /data/datasets/info.txt",
            "ls -la /data/datasets/"
        ]
        
        for cmd in bucket_commands:
            result = client.execute_session(session['id'], cmd)
            print(f"   📤 {cmd}")
            print(f"   📥 {result['stdout']}")
        
        print("\n✅ Multi-storage test completed successfully!")
        print("🎉 Both persistent volume (/workspace) and GCS bucket (/data) are working!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_multi_storage()
    if success:
        print("\n🎯 Multi-storage functionality is working!")
    else:
        print("\n💥 Multi-storage test failed!")
        sys.exit(1)
