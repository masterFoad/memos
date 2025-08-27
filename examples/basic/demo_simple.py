#!/usr/bin/env python3
"""
Simple demo of OnMemOS v3 SDK functionality

This demo showcases the core features:
- Workspace creation and management
- Bucket operations (create, upload, download, list)
- File processing and basic analysis
- Multi-bucket workflows
- Code execution in workspaces
"""

import os
import time
import json
import tempfile
from sdk.python.client import OnMemClient
from test_utils import generate_test_token

def main():
    print("🚀 OnMemOS v3 Simple Demo")
    print("=" * 40)
    
    # Initialize client with authentication
    token = generate_test_token()
    client = OnMemClient("http://localhost:8080", token)
    
    # Demo 1: Basic Bucket Operations
    print("\n📦 Demo 1: Basic Bucket Operations")
    print("-" * 30)
    
    # Create a bucket
    bucket_name = f"demo-bucket-{int(time.time())}"
    print(f"Creating bucket: {bucket_name}")
    client.create_bucket(bucket_name, "demo-namespace", "demo-user")
    
    # List buckets
    print("Listing buckets:")
    buckets = client.list_buckets("demo-namespace", "demo-user")
    for bucket in buckets:
        print(f"   📦 {bucket['name']} ({bucket['region']})")
    
    # Create and upload a sample file
    print("\n📤 Uploading sample data...")
    sample_data = {
        "message": "Hello from OnMemOS v3!",
        "timestamp": time.time(),
        "numbers": [1, 2, 3, 4, 5],
        "metadata": {
            "source": "demo",
            "version": "1.0"
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        json.dump(sample_data, f, indent=2)
        temp_file = f.name
    
    try:
        client.upload_to_bucket(bucket_name, temp_file, "sample_data.json")
        print("✅ Sample data uploaded successfully")
    finally:
        os.unlink(temp_file)
    
    # Demo 2: Workspace with Bucket Mount
    print("\n🏗️ Demo 2: Workspace with Bucket Mount")
    print("-" * 30)
    
    # Create workspace with bucket mount
    workspace = client.create_workspace_with_mounted_bucket(
        template="python",
        namespace="demo-namespace",
        user="demo-user",
        bucket_name=bucket_name,
        mount_path="/data",
        prefix="demo/",
        read_only=False
    )
    
    print(f"✅ Workspace created: {workspace['id']}")
    print(f"   Bucket mounts: {len(workspace['bucket_mounts'])}")
    
    # Demo 3: Data Processing in Workspace
    print("\n🔄 Demo 3: Data Processing in Workspace")
    print("-" * 30)
    
    # Run processing code
    processing_code = """
import json
import os
import time
from datetime import datetime

print("🔍 Starting data processing...")

# Check bucket mount
data_path = "/data/sample_data.json"
if os.path.exists(data_path):
    print(f"✅ Found data file: {data_path}")
    
    # Read the data
    with open(data_path, 'r') as f:
        data = json.load(f)
    
    print(f"📊 Loaded data: {data['message']}")
    print(f"   Numbers: {data['numbers']}")
    print(f"   Timestamp: {datetime.fromtimestamp(data['timestamp'])}")
    
    # Process the data
    numbers = data['numbers']
    total = sum(numbers)
    average = total / len(numbers)
    max_num = max(numbers)
    min_num = min(numbers)
    
    # Create processed results
    results = {
        "original_data": data,
        "analysis": {
            "total": total,
            "average": average,
            "maximum": max_num,
            "minimum": min_num,
            "count": len(numbers)
        },
        "processed_at": datetime.now().isoformat(),
        "processing_notes": [
            f"Found {len(numbers)} numbers",
            f"Sum: {total}",
            f"Average: {average:.2f}",
            f"Range: {min_num} to {max_num}"
        ]
    }
    
    # Save results back to bucket
    results_path = "/data/processed_results.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"✅ Results saved to {results_path}")
    print("🎉 Processing completed!")
    
else:
    print(f"❌ Data file not found: {data_path}")
    print(f"Available files in /data:")
    if os.path.exists("/data"):
        for file in os.listdir("/data"):
            print(f"   📄 {file}")
    else:
        print("   No /data directory found")
"""
    
    print("🖥️ Running data processing...")
    result = client.run_python(workspace["id"], {
        "code": processing_code,
        "timeout": 30.0
    })
    
    print("📄 Processing Output:")
    print(result.get('stdout', ''))
    if result.get('stderr'):
        print("❌ Errors:")
        print(result.get('stderr', ''))
    
    # Demo 4: Results Retrieval
    print("\n📈 Demo 4: Results Retrieval")
    print("-" * 30)
    
    # List bucket contents
    print("📋 Bucket contents:")
    try:
        contents = client.list_bucket_contents(bucket_name, prefix="demo/")
        for item in contents:
            print(f"   📄 {item}")
    except Exception as e:
        print(f"   ❌ Error listing contents: {e}")
    
    # Download and display results
    print("\n📊 Downloading processed results...")
    try:
        # Download results file
        results_file = tempfile.NamedTemporaryFile(delete=False)
        results_file.close()
        
        client.download_from_bucket(bucket_name, "demo/processed_results.json", results_file.name)
        
        with open(results_file.name, 'r') as f:
            results = json.load(f)
        
        print("🎯 Processing Results:")
        analysis = results['analysis']
        print(f"   📊 Total: {analysis['total']}")
        print(f"   📊 Average: {analysis['average']:.2f}")
        print(f"   📊 Range: {analysis['minimum']} to {analysis['maximum']}")
        print(f"   📊 Count: {analysis['count']}")
        
        print("\n💡 Processing Notes:")
        for note in results['processing_notes']:
            print(f"   • {note}")
        
        os.unlink(results_file.name)
        
    except Exception as e:
        print(f"❌ Error downloading results: {e}")
    
    # Demo 5: File Operations
    print("\n📁 Demo 5: File Operations")
    print("-" * 30)
    
    # Create a text file in the workspace
    file_ops_code = """
import os

print("📁 Creating sample files...")

# Create a text file
text_content = '''
OnMemOS v3 Demo File
===================

This is a sample file created in the workspace.
It demonstrates file operations and persistence.

Features demonstrated:
- File creation
- Text processing
- Directory operations
- Data persistence
'''

# Write to workspace
with open('/work/demo_file.txt', 'w') as f:
    f.write(text_content)

print("✅ Created /work/demo_file.txt")

# Create a JSON file with workspace info
workspace_info = {
    "workspace_id": "demo-workspace",
    "created_at": "2024-01-01T00:00:00Z",
    "features": [
        "Python execution",
        "File operations",
        "Bucket mounts",
        "Data processing"
    ],
    "status": "active"
}

import json
with open('/work/workspace_info.json', 'w') as f:
    json.dump(workspace_info, f, indent=2)

print("✅ Created /work/workspace_info.json")

# List files in workspace
print("📋 Files in workspace:")
for file in os.listdir('/work'):
    file_path = os.path.join('/work', file)
    size = os.path.getsize(file_path)
    print(f"   📄 {file} ({size} bytes)")

print("🎉 File operations completed!")
"""
    
    print("🖥️ Running file operations...")
    file_result = client.run_python(workspace["id"], {
        "code": file_ops_code,
        "timeout": 30.0
    })
    
    print("📄 File Operations Output:")
    print(file_result.get('stdout', ''))
    
    # Demo 6: Workspace Snapshot
    print("\n📸 Demo 6: Workspace Snapshot")
    print("-" * 30)
    
    # Create snapshot
    print("📸 Creating workspace snapshot...")
    try:
        snapshot = client.snapshot(workspace["id"], "Simple Demo - Complete")
        print(f"✅ Snapshot created: {snapshot['id']}")
        print(f"   📊 Files: {snapshot['files']}")
        print(f"   💾 Size: {snapshot['bytes']} bytes")
        
        # Create shareable link
        share = client.share(snapshot['id'], ttl_seconds=3600, scope="fork")
        print(f"🔗 Shareable link: {share['url']}")
        
    except Exception as e:
        print(f"❌ Error creating snapshot: {e}")
    
    # Demo 7: Cleanup
    print("\n🧹 Demo 7: Cleanup")
    print("-" * 30)
    
    print("🧹 Cleaning up demo resources...")
    try:
        client.delete(workspace["id"])
        print("✅ Workspace deleted")
    except Exception as e:
        print(f"⚠️ Error during cleanup: {e}")
    
    print("\n🎉 Simple demo completed successfully!")
    print("=" * 40)
    print("📊 Demo Summary:")
    print("   ✅ Bucket creation and management")
    print("   ✅ File upload and download")
    print("   ✅ Workspace with bucket mount")
    print("   ✅ Data processing in workspace")
    print("   ✅ File operations and persistence")
    print("   ✅ Workspace snapshots and sharing")
    print("   ✅ Complete workflow demonstration")

if __name__ == "__main__":
    main()
