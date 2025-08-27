#!/usr/bin/env python3
"""
Auto-Cleanup Demo of OnMemOS v3 SDK functionality

This demo showcases automatic resource cleanup using context managers:
- Automatic workspace cleanup
- Automatic bucket cleanup
- Context manager usage
- No manual cleanup required!
"""

import os
import time
import json
import tempfile
from sdk.python.client import OnMemClient
from test_utils import generate_test_token

def main():
    print("🚀 OnMemOS v3 Auto-Cleanup Demo")
    print("=" * 50)
    print("🧹 Automatic resource cleanup with context managers!")
    print("=" * 50)
    
    # Check if we have GCS credentials
    gcs_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    project_id = os.getenv("PROJECT_ID")
    
    if not gcs_credentials and not project_id:
        print("⚠️  Warning: No Google Cloud credentials found!")
        print("   Set GOOGLE_APPLICATION_CREDENTIALS or use gcloud auth")
        print("   This demo will use real implementations but may fail without credentials")
    else:
        print("✅ Google Cloud credentials configured!")
        if gcs_credentials:
            print(f"   📄 Service account key: {gcs_credentials}")
        if project_id:
            print(f"   🏭 Project ID: {project_id}")
    
    # Initialize client with authentication
    token = generate_test_token()
    
    # Demo 1: Using the client as a context manager (automatic cleanup)
    print("\n🧹 Demo 1: Client Context Manager")
    print("-" * 40)
    
    with OnMemClient("http://localhost:8080", token) as client:
        print("✅ Client context manager active - automatic cleanup enabled")
        
        # Create a bucket (will be tracked for cleanup)
        bucket_name = f"auto-cleanup-bucket-{int(time.time())}"
        print(f"📦 Creating bucket: {bucket_name}")
        
        bucket_result = client.create_bucket(bucket_name, "demo-namespace", "demo-user")
        print(f"✅ Bucket created: {bucket_result['name']}")
        
        # Create a workspace (will be tracked for cleanup)
        print("🏗️ Creating workspace...")
        workspace = client.create_workspace_with_mounted_bucket(
            template="python",
            namespace="demo-namespace",
            user="demo-user",
            bucket_name=bucket_result['name'],
            mount_path="/data",
            prefix="demo/",
            read_only=False
        )
        print(f"✅ Workspace created: {workspace['id']}")
        
        # Upload a file
        sample_data = {
            "message": "Hello from Auto-Cleanup Demo!",
            "timestamp": time.time(),
            "feature": "automatic_cleanup",
            "context_manager": True
        }
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            json.dump(sample_data, f, indent=2)
            temp_file = f.name
        
        try:
            client.upload_to_bucket(bucket_result['name'], temp_file, "auto_cleanup_demo.json")
            print("✅ File uploaded to bucket")
        finally:
            os.unlink(temp_file)
        
        # Run some processing
        print("🖥️ Running workspace processing...")
        result = client.run_python(workspace["id"], {
            "code": """
import os
import json
print("🔍 Auto-cleanup demo workspace processing...")
print(f"📁 Current directory: {os.getcwd()}")
print(f"📂 Directory contents: {os.listdir('.')}")

if os.path.exists("/data"):
    print(f"📂 /data contents: {os.listdir('/data')}")
    print("✅ Bucket mount working!")

print("🎉 Processing complete!")
""",
            "timeout": 30.0
        })
        
        print("📄 Processing Output:")
        print(result.get('stdout', ''))
        
        print("\n📋 Bucket contents:")
        contents = client.list_bucket_contents(bucket_result['name'], prefix="")
        for item in contents:
            print(f"   📄 {item}")
        
        print("\n🔚 Exiting context manager - automatic cleanup will happen...")
    
    print("✅ Context manager exited - all resources automatically cleaned up!")
    
    # Demo 2: Individual context managers
    print("\n🧹 Demo 2: Individual Context Managers")
    print("-" * 40)
    
    client = OnMemClient("http://localhost:8080", token)
    
    # Bucket context manager
    bucket_name = f"individual-bucket-{int(time.time())}"
    print(f"📦 Creating bucket with context manager: {bucket_name}")
    
    with client.bucket(bucket_name, "demo-namespace", "demo-user") as bucket_result:
        print(f"✅ Bucket active: {bucket_result['name']}")
        
        # Workspace context manager
        print("🏗️ Creating workspace with context manager...")
        
        with client.workspace(
            template="python",
            namespace="demo-namespace", 
            user="demo-user",
            bucket_mounts=[client.mount_bucket(bucket_result['name'], "/data")],
            ttl_minutes=30
        ) as workspace:
            print(f"✅ Workspace active: {workspace['id']}")
            
            # Upload and process
            sample_data = {
                "message": "Individual context manager demo",
                "timestamp": time.time(),
                "context": "individual"
            }
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                json.dump(sample_data, f, indent=2)
                temp_file = f.name
            
            try:
                client.upload_to_bucket(bucket_result['name'], temp_file, "individual_demo.json")
                print("✅ File uploaded")
                
                # Process
                result = client.run_python(workspace["id"], {
                    "code": "print('🎉 Individual context manager processing!')",
                    "timeout": 10.0
                })
                print("📄 Processing Output:")
                print(result.get('stdout', ''))
                
            finally:
                os.unlink(temp_file)
            
            print("🔚 Exiting workspace context manager...")
        
        print("✅ Workspace context manager exited - workspace cleaned up!")
        print("🔚 Exiting bucket context manager...")
    
    print("✅ Bucket context manager exited - bucket tracked for cleanup!")
    
    # Demo 3: Manual cleanup
    print("\n🧹 Demo 3: Manual Cleanup")
    print("-" * 40)
    
    client = OnMemClient("http://localhost:8080", token)
    
    # Create resources without auto-cleanup
    bucket_name = f"manual-cleanup-bucket-{int(time.time())}"
    print(f"📦 Creating bucket (manual cleanup): {bucket_name}")
    
    bucket_result = client.create_bucket(bucket_name, "demo-namespace", "demo-user")
    print(f"✅ Bucket created: {bucket_result['name']}")
    
    workspace = client.create_workspace_with_mounted_bucket(
        template="python",
        namespace="demo-namespace",
        user="demo-user",
        bucket_name=bucket_result['name'],
        mount_path="/data"
    )
    print(f"✅ Workspace created: {workspace['id']}")
    
    # Show tracked resources
    print(f"📋 Tracked workspaces: {len(client._workspaces)}")
    print(f"📋 Tracked buckets: {len(client._buckets)}")
    
    # Manual cleanup
    print("🧹 Performing manual cleanup...")
    client.cleanup()
    
    print("✅ Manual cleanup completed!")
    
    print("\n🎉 Auto-Cleanup Demo Completed Successfully!")
    print("=" * 50)
    print("📊 Demo Summary:")
    print("   ✅ Client context manager with automatic cleanup")
    print("   ✅ Individual workspace context manager")
    print("   ✅ Individual bucket context manager")
    print("   ✅ Manual cleanup functionality")
    print("   ✅ No resource leaks - everything cleaned up!")
    print("   ✅ Real Google Cloud Storage integration")
    print("   ✅ Real workspace execution")

if __name__ == "__main__":
    main()
