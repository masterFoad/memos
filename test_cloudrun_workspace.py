#!/usr/bin/env python3
"""
Test Cloud Run Workspace for OnMemOS v3
======================================
Demonstrates Cloud Run-based workspace management with GCS mounts
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from cloudrun_workspace_manager import cloudrun_workspace_manager

def test_cloudrun_workspace():
    """Test Cloud Run workspace creation and management"""
    print("🚀 Cloud Run Workspace Test")
    print("=" * 50)
    
    namespace = "cloudrun-test"
    user = "test-user"
    
    try:
        # Step 1: Create Cloud Run workspace
        print("\n📦 Step 1: Creating Cloud Run workspace...")
        workspace = cloudrun_workspace_manager.create_workspace(
            template="python",
            namespace=namespace,
            user=user,
            ttl_minutes=30
        )
        
        workspace_id = workspace["id"]
        service_url = workspace["service_url"]
        bucket_name = workspace["bucket_name"]
        
        print(f"✅ Workspace created: {workspace_id}")
        print(f"   Service URL: {service_url}")
        print(f"   Bucket: {bucket_name}")
        print(f"   Status: {workspace['status']}")
        
        # Step 2: Test workspace access
        print("\n🔍 Step 2: Testing workspace access...")
        
        # Wait for service to be ready
        print("⏳ Waiting for service to be ready...")
        time.sleep(30)
        
        # Test basic command execution
        test_commands = [
            "pwd",
            "ls -la /workspace",
            "python --version",
            "echo 'Hello from Cloud Run!'"
        ]
        
        for cmd in test_commands:
            print(f"\n💻 Testing command: {cmd}")
            try:
                result = cloudrun_workspace_manager.execute_in_workspace(workspace_id, cmd)
                if result["success"]:
                    print(f"✅ Output: {result['stdout'].strip()}")
                else:
                    print(f"❌ Error: {result['stderr'].strip()}")
            except Exception as e:
                print(f"❌ Failed: {e}")
        
        # Step 3: Test GCS bucket access
        print("\n🪣 Step 3: Testing GCS bucket access...")
        
        gcs_commands = [
            "ls -la /workspace/buckets",
            "echo 'test file' > /workspace/buckets/test.txt",
            "ls -la /workspace/buckets",
            "cat /workspace/buckets/test.txt"
        ]
        
        for cmd in gcs_commands:
            print(f"\n💻 Testing GCS command: {cmd}")
            try:
                result = cloudrun_workspace_manager.execute_in_workspace(workspace_id, cmd)
                if result["success"]:
                    print(f"✅ Output: {result['stdout'].strip()}")
                else:
                    print(f"❌ Error: {result['stderr'].strip()}")
            except Exception as e:
                print(f"❌ Failed: {e}")
        
        # Step 4: List workspaces
        print("\n📋 Step 4: Listing workspaces...")
        workspaces = cloudrun_workspace_manager.list_workspaces(namespace=namespace)
        print(f"✅ Found {len(workspaces)} workspaces in namespace '{namespace}'")
        for ws in workspaces:
            print(f"   - {ws['id']}: {ws['status']}")
        
        # Step 5: Cleanup
        print("\n🧹 Step 5: Cleaning up...")
        success = cloudrun_workspace_manager.delete_workspace(workspace_id)
        if success:
            print("✅ Workspace deleted successfully")
        else:
            print("⚠️  Workspace deletion failed")
        
        print("\n🎉 Cloud Run workspace test completed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_cloudrun_workspace()
    sys.exit(0 if success else 1)
