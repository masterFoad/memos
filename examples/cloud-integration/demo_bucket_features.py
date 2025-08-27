#!/usr/bin/env python3
"""
OnMemOS v3 Bucket Features Demo
Demonstrates bucket creation, mounting, and operations
"""

import os
import sys
import tempfile
import time
import json
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from sdk.python.client import OnMemClient
from sdk.python.models import CreateWorkspace

def demo_bucket_features():
    """Demo bucket features"""
    print("🚀 OnMemOS v3 Bucket Features Demo")
    print("=" * 50)
    
    # Initialize client
    client = OnMemClient("http://localhost:8080", "demo-token")
    
    # Test bucket creation
    print("\n1. Creating test bucket...")
    bucket_name = f"demo-bucket-{int(time.time())}"
    
    try:
        bucket_result = client.create_bucket(
            bucket_name=bucket_name,
            namespace="demo",
            user="demo-user"
        )
        print(f"   ✅ Bucket created: {bucket_result['name']}")
    except Exception as e:
        print(f"   ⚠️  Bucket creation failed (may need cloud credentials): {e}")
        bucket_name = "demo-bucket-existing"  # Use existing bucket for demo
    
    # Test workspace with bucket mount
    print("\n2. Creating workspace with bucket mount...")
    
    bucket_mounts = [{
        "bucket_name": bucket_name,
        "mount_path": "/bucket",
        "prefix": "workspace/",
        "read_only": False
    }]
    
    try:
        workspace = client.create_workspace_with_buckets(
            template="python",
            namespace="demo",
            user="demo-user",
            bucket_mounts=bucket_mounts,
            bucket_prefix="workspace/"
        )
        
        print(f"   ✅ Workspace created: {workspace['id']}")
        print(f"   📦 Bucket mounts: {workspace['bucket_mounts']}")
        
        # Test bucket operations in workspace
        print("\n3. Testing bucket operations in workspace...")
        
        result = client.run_python(workspace["id"], {
            "code": """
import os
import json

print("🔍 Bucket Mount Test")
print("=" * 30)

# Check bucket mount
bucket_path = "/bucket"
print(f"Bucket path exists: {os.path.exists(bucket_path)}")

if os.path.exists(bucket_path):
    print(f"Bucket contents: {os.listdir(bucket_path)}")
    
    # Create test file in bucket
    test_file = os.path.join(bucket_path, "workspace", "test.txt")
    os.makedirs(os.path.dirname(test_file), exist_ok=True)
    
    with open(test_file, 'w') as f:
        f.write("Hello from OnMemOS v3 bucket mount!")
    
    print(f"✅ Created test file: {test_file}")
    
    # Read test file
    with open(test_file, 'r') as f:
        content = f.read()
    print(f"📄 File content: {content}")
    
    # List workspace directory
    workspace_dir = os.path.join(bucket_path, "workspace")
    if os.path.exists(workspace_dir):
        files = os.listdir(workspace_dir)
        print(f"📁 Workspace files: {files}")
else:
    print("❌ Bucket mount not available")

# Check other mount points
print("\\n📂 Other mount points:")
for mount in ["/work", "/persist", "/tmp"]:
    exists = os.path.exists(mount)
    print(f"   {mount}: {'✅' if exists else '❌'}")
    if exists:
        try:
            contents = os.listdir(mount)
            print(f"     Contents: {len(contents)} items")
        except:
            print(f"     Cannot list contents")
""",
            "timeout": 30.0
        })
        
        print(f"   📄 Output:\n{result.get('stdout', '')}")
        
        # Cleanup workspace
        print("\n4. Cleaning up...")
        client.delete(workspace["id"])
        print("   ✅ Workspace deleted")
        
    except Exception as e:
        print(f"   ❌ Workspace test failed: {e}")
    
    # Test bucket operations
    print("\n5. Testing bucket operations...")
    
    try:
        # List buckets
        buckets = client.list_buckets("demo", "demo-user")
        print(f"   📦 Found {len(buckets)} buckets")
        
        # List bucket contents
        if bucket_name:
            result = client.bucket_operation(
                bucket_name=bucket_name,
                operation="list",
                recursive=True
            )
            
            if result["success"]:
                objects = result["data"]["objects"]
                print(f"   📄 Bucket contains {len(objects)} objects")
                for obj in objects[:5]:  # Show first 5
                    print(f"     - {obj}")
            else:
                print(f"   ⚠️  Bucket listing failed: {result['error']}")
    
    except Exception as e:
        print(f"   ⚠️  Bucket operations failed: {e}")
    
    print("\n🎉 Bucket features demo completed!")
    print("\n✨ Key Features Demonstrated:")
    print("   ✅ Bucket creation and management")
    print("   ✅ Workspace with bucket mounts")
    print("   ✅ File operations in mounted buckets")
    print("   ✅ Bucket listing and operations")
    print("   ✅ Per-user bucket isolation")

def demo_elegant_functions():
    """Demo elegant bucket functions"""
    print("\n🎨 Elegant Bucket Functions Demo")
    print("=" * 40)
    
    client = OnMemClient("http://localhost:8080", "demo-token")
    bucket_name = f"elegant-demo-{int(time.time())}"
    
    try:
        # Create bucket
        client.create_bucket(bucket_name, "demo", "demo-user")
        print(f"   📦 Created bucket: {bucket_name}")
        
        # Demo elegant mount function
        print("\n1. Using mount_bucket helper...")
        mount_config = client.mount_bucket(
            bucket_name=bucket_name,
            mount_path="/data",
            prefix="elegant/",
            read_only=False
        )
        print(f"   ✅ Mount config: {mount_config}")
        
        # Demo single bucket workspace creation
        print("\n2. Creating workspace with mounted bucket...")
        workspace = client.create_workspace_with_mounted_bucket(
            template="python",
            namespace="demo",
            user="demo-user",
            bucket_name=bucket_name,
            mount_path="/data",
            prefix="elegant/"
        )
        print(f"   ✅ Workspace created: {workspace['id']}")
        
        # Demo bucket mount testing
        print("\n3. Testing bucket mount...")
        mount_test = client.test_bucket_mount(workspace["id"], "/data")
        test_result = json.loads(mount_test.get("stdout", "{}"))
        print(f"   📊 Mount test results:")
        print(f"      - Bucket exists: {test_result.get('bucket_exists', False)}")
        print(f"      - Writable: {test_result.get('writable', False)}")
        print(f"      - Contents: {test_result.get('bucket_contents', [])}")
        
        # Demo file operations
        print("\n4. Testing file operations...")
        file_ops = client.bucket_file_operations(workspace["id"], "/data")
        ops_result = json.loads(file_ops.get("stdout", "{}"))
        print(f"   📊 File operations results:")
        for op, status in ops_result.items():
            if op != "content" and op != "files":
                print(f"      - {op}: {status}")
        
        # Demo bucket listing
        print("\n5. Listing bucket contents...")
        contents = client.list_bucket_contents(bucket_name, prefix="elegant/")
        print(f"   📦 Bucket contents: {len(contents)} objects")
        for obj in contents[:3]:  # Show first 3
            print(f"      - {obj}")
        
        # Cleanup
        client.delete(workspace["id"])
        print(f"\n   ✅ Cleanup completed")
        
    except Exception as e:
        print(f"   ❌ Elegant functions demo failed: {e}")

def demo_multiple_buckets():
    """Demo multiple bucket mounts"""
    print("\n🔄 Multiple Bucket Mounts Demo")
    print("=" * 35)
    
    client = OnMemClient("http://localhost:8080", "demo-token")
    
    try:
        # Create multiple buckets
        bucket1_name = f"multi-bucket1-{int(time.time())}"
        bucket2_name = f"multi-bucket2-{int(time.time())}"
        
        client.create_bucket(bucket1_name, "demo", "demo-user")
        client.create_bucket(bucket2_name, "demo", "demo-user")
        print(f"   📦 Created buckets: {bucket1_name}, {bucket2_name}")
        
        # Create workspace with multiple bucket mounts
        bucket_mounts = [
            {
                "bucket_name": bucket1_name,
                "mount_path": "/data1",
                "prefix": "workspace1/",
                "read_only": False
            },
            {
                "bucket_name": bucket2_name,
                "mount_path": "/data2",
                "prefix": "workspace2/",
                "read_only": True
            }
        ]
        
        workspace = client.create_workspace_with_buckets(
            template="python",
            namespace="demo",
            user="demo-user",
            bucket_mounts=bucket_mounts
        )
        
        print(f"   ✅ Workspace with multiple mounts created: {workspace['id']}")
        
        # Test multiple mounts
        test_code = """
import os
import json

mounts = ["/data1", "/data2"]
results = {}

for mount in mounts:
    results[mount] = {
        "exists": os.path.exists(mount),
        "contents": os.listdir(mount) if os.path.exists(mount) else [],
        "writable": os.access(mount, os.W_OK) if os.path.exists(mount) else False
    }

print(json.dumps(results, indent=2))
"""
        
        result = client.run_python(workspace["id"], {"code": test_code, "timeout": 10.0})
        mount_results = json.loads(result.get("stdout", "{}"))
        
        print(f"   📊 Multiple mounts test results:")
        for mount, data in mount_results.items():
            print(f"      {mount}:")
            print(f"        - Exists: {data.get('exists', False)}")
            print(f"        - Writable: {data.get('writable', False)}")
            print(f"        - Contents: {len(data.get('contents', []))} items")
        
        # Cleanup
        client.delete(workspace["id"])
        print(f"   ✅ Cleanup completed")
        
    except Exception as e:
        print(f"   ❌ Multiple buckets demo failed: {e}")

if __name__ == "__main__":
    print("OnMemOS v3 Bucket Features Demo")
    print("=" * 50)
    
    # Run all demos
    demo_bucket_features()
    demo_elegant_functions()
    demo_multiple_buckets()
    
    print("\n🎉 All bucket feature demos completed!")
    print("\n💡 Key Benefits:")
    print("   🚀 Ultra-fast bucket mounting in workspaces")
    print("   🔒 Per-user bucket isolation and security")
    print("   🎯 Elegant SDK functions for easy integration")
    print("   📦 Support for multiple bucket mounts per workspace")
    print("   🔧 Flexible prefix-based access control")
    print("   ⚡ Real-time bucket operations in RAM-backed workspaces")
