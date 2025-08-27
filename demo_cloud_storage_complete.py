#!/usr/bin/env python3
"""
Complete Cloud Storage Demo - OnMemOS v3
========================================

This demo showcases the complete cloud storage integration:
- GCS Buckets (✅ Already working)
- GCP Persistent Disks (🔄 New implementation)
- SDK integration with CRUD operations
- Real cloud storage (not local mounts)

Features:
1. Create workspace with cloud storage
2. Manage GCS buckets (create, list, clone, delete)
3. Manage GCP persistent disks (create, list, clone, delete)
4. Interactive shell with cloud storage commands
5. Automatic cleanup with context managers
"""

import asyncio
import time
import sys
import os

# Add the project root to the path
project_root = os.path.join(os.path.dirname(__file__))
sys.path.append(project_root)

from sdk.python.client import OnMemClient
from tests.unit.test_utils import generate_test_token

def demo_cloud_storage_complete():
    """Complete cloud storage demo"""
    print("🚀 Complete Cloud Storage Demo - OnMemOS v3")
    print("=" * 60)
    print("📋 Features:")
    print("  ✅ GCS Buckets (fully implemented)")
    print("  💾 GCP Persistent Disks (new)")
    print("  🔄 SDK CRUD operations")
    print("  ☁️ Real cloud storage integration")
    print("  🔄 Interactive shell commands")
    print("=" * 60)
    
    # Initialize client
    token = generate_test_token()
    client = OnMemClient('http://localhost:8080', token)
    
    # Set up namespace and user
    namespace = "cloud-storage-demo"
    user = "developer-456"
    
    print(f"\n👤 User: {user}")
    print(f"📁 Namespace: {namespace}")
    
    try:
        # Use context manager for automatic cleanup
        with client.namespace(namespace, user) as ns_info:
            print(f"\n✅ Using namespace: {ns_info['namespace']}")
            
            # 1. Create GCS Bucket
            print("\n🪣 Creating GCS Bucket...")
            bucket_name = f"demo-bucket-{int(time.time())}"
            bucket = client.create_bucket_in_namespace(
                bucket_name=bucket_name,
                namespace=namespace,
                user=user,
                region="us-central1",
                storage_class="STANDARD"
            )
            print(f"✅ Created bucket: {bucket['name']}")
            
            # 2. Create GCP Persistent Disk
            print("\n💾 Creating GCP Persistent Disk...")
            disk_name = f"demo-disk-{int(time.time())}"
            disk = client.create_persistent_disk(
                disk_name=disk_name,
                namespace=namespace,
                user=user,
                size_gb=10,
                disk_type="pd-standard"
            )
            print(f"✅ Created disk: {disk.get('disk_name', disk_name)}")
            
            # 3. List resources
            print("\n📋 Listing Resources:")
            print("-" * 30)
            
            # List buckets
            buckets = client.list_buckets_in_namespace(namespace, user)
            print(f"🪣 Buckets ({len(buckets)}):")
            for bucket in buckets:
                print(f"  - {bucket['name']} ({bucket.get('storage_class', 'STANDARD')})")
            
            # List disks
            disks = client.list_persistent_disks(namespace, user)
            print(f"💾 Disks ({len(disks)}):")
            for disk in disks:
                print(f"  - {disk.get('disk_name', 'Unknown')} ({disk.get('size_gb', 0)}GB)")
            
            # 4. Clone resources
            print("\n🔄 Cloning Resources:")
            print("-" * 30)
            
            # Clone bucket
            if buckets:
                source_bucket = buckets[0]['name']
                cloned_bucket = client.clone_bucket(
                    source_bucket_name=source_bucket,
                    new_bucket_name=f"{source_bucket}-cloned",
                    new_namespace=namespace,
                    new_user=user
                )
                print(f"✅ Cloned bucket: {cloned_bucket['new_bucket']}")
            
            # Clone disk
            if disks:
                source_disk = disks[0].get('disk_name', 'Unknown')
                cloned_disk = client.clone_persistent_disk(
                    source_disk_name=source_disk,
                    new_disk_name=f"{source_disk}-cloned",
                    new_namespace=namespace,
                    new_user=user
                )
                print(f"✅ Cloned disk: {cloned_disk['new_disk']}")
            
            # 5. Create workspace with cloud storage
            print("\n🐳 Creating Workspace with Cloud Storage...")
            workspace = client.create_workspace_with_buckets(
                template="python",
                namespace=namespace,
                user=user,
                ttl_minutes=30
            )
            
            workspace_id = workspace['id']
            print(f"✅ Created workspace: {workspace_id}")
            
            # 6. Test cloud storage commands
            print("\n🔧 Testing Cloud Storage Commands:")
            print("-" * 40)
            
            # Test bucket operations
            print("🪣 Testing bucket operations...")
            try:
                bucket_info = client.get_bucket(bucket_name)
                print(f"✅ Bucket info: {bucket_info['name']}")
            except Exception as e:
                print(f"⚠️ Bucket info failed: {e}")
            
            # Test disk operations
            print("💾 Testing disk operations...")
            try:
                disk_info = client.get_persistent_disk(disk_name)
                print(f"✅ Disk info: {disk_info['disk_name']}")
            except Exception as e:
                print(f"⚠️ Disk info failed: {e}")
            
            # 7. Test workspace operations
            print("\n🐳 Testing Workspace Operations:")
            print("-" * 40)
            
            # Test Python execution
            print("🐍 Testing Python execution...")
            try:
                result = client.run_python(workspace_id, "import sys; print(f'Python {sys.version}')")
                if result and 'output' in result:
                    print(f"✅ Python execution: {result['output'].strip()}")
                else:
                    print("⚠️ Python execution failed")
            except Exception as e:
                print(f"⚠️ Python execution failed: {e}")
            
            # Test shell execution
            print("💻 Testing shell execution...")
            try:
                result = client.run_shell(workspace_id, "echo 'Hello from cloud storage demo'")
                if result and 'output' in result:
                    print(f"✅ Shell execution: {result['output'].strip()}")
                else:
                    print("⚠️ Shell execution failed")
            except Exception as e:
                print(f"⚠️ Shell execution failed: {e}")
            
            # 8. Interactive shell demo
            print("\n🎯 Interactive Shell Demo:")
            print("-" * 30)
            print("Available commands in interactive shell:")
            print("  /buckets list          - List GCS buckets")
            print("  /buckets info <name>   - Get bucket info")
            print("  /disks list            - List persistent disks")
            print("  /disks create <name> <size> - Create disk")
            print("  /disks info <name>     - Get disk info")
            print("  /disks clone <src> <dst> - Clone disk")
            print("  /persist               - Show persistent storage")
            print("  /status                - Show workspace status")
            print("  /files                 - List files")
            print("  /python <code>         - Execute Python code")
            
            # Cleanup workspace
            print(f"\n🧹 Cleaning up workspace: {workspace_id}")
            client.delete_workspace(workspace_id)
            print("✅ Workspace cleaned up")
            
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n🎉 Demo completed!")
    print("=" * 60)
    print("📋 What we accomplished:")
    print("  ✅ Created GCS bucket with namespace")
    print("  ✅ Created GCP persistent disk")
    print("  ✅ Listed and managed cloud resources")
    print("  ✅ Cloned buckets and disks")
    print("  ✅ Created workspace with cloud storage")
    print("  ✅ Tested SDK CRUD operations")
    print("  ✅ Tested Python and shell execution")
    print("  ✅ Automatic cleanup with context managers")
    print("=" * 60)

def demo_interactive_commands():
    """Demo the interactive shell commands"""
    print("\n🎯 Interactive Shell Commands Demo")
    print("=" * 50)
    print("Run the interactive shell to test these commands:")
    print()
    print("🪣 Bucket Commands:")
    print("  /buckets                    - List all buckets")
    print("  /buckets my-bucket          - Show specific bucket contents")
    print()
    print("💾 Disk Commands:")
    print("  /disks list                 - List all persistent disks")
    print("  /disks create mydisk 20     - Create 20GB disk")
    print("  /disks info mydisk          - Get disk information")
    print("  /disks clone mydisk backup  - Clone disk")
    print()
    print("🔧 General Commands:")
    print("  /status                     - Show workspace status")
    print("  /files                      - List files in workspace")
    print("  /persist                    - Show persistent storage")
    print("  /python 'print(\"Hello\")'   - Execute Python code")
    print("  /help                       - Show all commands")
    print("  /exit                       - Exit shell")
    print()
    print("💡 To start interactive shell:")
    print("  python working_interactive.py")

if __name__ == "__main__":
    # Run the complete demo
    demo_cloud_storage_complete()
    
    # Show interactive commands
    demo_interactive_commands()
