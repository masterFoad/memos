#!/usr/bin/env python3
"""
Reusable Namespace Demo for OnMemOS v3

This demo shows how to:
- Create persistent namespaces with buckets
- Store and retrieve data across sessions
- Reuse namespaces for different workflows
- Maintain state between workspace sessions
"""

import os
import time
import json
import tempfile
from datetime import datetime
from sdk.python.client import OnMemClient
from test_utils import generate_test_token

class ReusableNamespace:
    """Manages a reusable namespace with persistent storage and buckets"""
    
    def __init__(self, client: OnMemClient, namespace: str, user: str):
        self.client = client
        self.namespace = namespace
        self.user = user
        self.bucket_name = None
        self.workspace_id = None
        
    def setup_bucket(self, bucket_name: str = None):
        """Set up a bucket for this namespace"""
        if bucket_name is None:
            # Create a shorter, GCS-compliant bucket name
            timestamp = int(time.time()) % 1000000  # Use last 6 digits
            safe_namespace = self.namespace.replace("-", "").replace("_", "")[:10]
            safe_user = self.user.replace("-", "").replace("_", "")[:10]
            bucket_name = f"onmemos-{safe_namespace}-{safe_user}-{timestamp}"
        
        print(f"📦 Setting up bucket: {bucket_name}")
        bucket_result = self.client.create_bucket(bucket_name, self.namespace, self.user)
        self.bucket_name = bucket_result["name"]
        print(f"✅ Bucket created: {self.bucket_name}")
        return self.bucket_name
    
    def create_workspace(self, template: str = "python", ttl_minutes: int = 180):
        """Create a workspace with bucket mount and persistent storage"""
        print(f"🏗️ Creating workspace for namespace: {self.namespace}")
        
        # Create bucket mount configuration
        bucket_mounts = [{
            "bucket_name": self.bucket_name,
            "mount_path": "/data",
            "prefix": f"{self.namespace}/",
            "read_only": False
        }]
        
        workspace = self.client.create_workspace_with_buckets(
            template=template,
            namespace=self.namespace,
            user=self.user,
            bucket_mounts=bucket_mounts,
            bucket_prefix=f"{self.namespace}/",
            ttl_minutes=ttl_minutes
        )
        
        self.workspace_id = workspace["id"]
        print(f"✅ Workspace created: {self.workspace_id}")
        return workspace
    
    def store_persistent_data(self, data: dict, filename: str):
        """Store data in persistent storage"""
        print(f"💾 Storing data in persistent storage: {filename}")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            json.dump(data, f, indent=2)
            temp_file = f.name
        
        try:
            # Upload to persistent storage using the filename as dst parameter
            result = self.client.upload_persist(self.namespace, self.user, temp_file, filename)
            print(f"✅ Data stored: {result['path']}")
            return result
        finally:
            os.unlink(temp_file)
    
    def load_persistent_data(self, filename: str):
        """Load data from persistent storage"""
        print(f"📂 Loading data from persistent storage: {filename}")
        
        # Create temporary file for download
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_file = f.name
        
        try:
            # Download from persistent storage
            self.client.download_persist(self.namespace, self.user, filename, temp_file)
            
            # Load and return data
            with open(temp_file, 'r') as f:
                data = json.load(f)
            
            print(f"✅ Data loaded: {filename}")
            return data
        finally:
            os.unlink(temp_file)
    
    def store_bucket_data(self, data: dict, filename: str):
        """Store data in bucket storage"""
        print(f"☁️ Storing data in bucket: {filename}")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            json.dump(data, f, indent=2)
            temp_file = f.name
        
        try:
            # Upload to bucket
            remote_path = f"{self.namespace}/{filename}"
            result = self.client.upload_to_bucket(self.bucket_name, temp_file, remote_path)
            print(f"✅ Data stored in bucket: {remote_path}")
            return result
        finally:
            os.unlink(temp_file)
    
    def load_bucket_data(self, filename: str):
        """Load data from bucket storage"""
        print(f"☁️ Loading data from bucket: {filename}")
        
        # Create temporary file for download
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_file = f.name
        
        try:
            # Download from bucket
            remote_path = f"{self.namespace}/{filename}"
            self.client.download_from_bucket(self.bucket_name, remote_path, temp_file)
            
            # Load and return data
            with open(temp_file, 'r') as f:
                data = json.load(f)
            
            print(f"✅ Data loaded from bucket: {remote_path}")
            return data
        finally:
            os.unlink(temp_file)
    
    def run_workspace_code(self, code: str, timeout: float = 30.0):
        """Run code in the workspace"""
        print("🖥️ Running workspace code...")
        
        result = self.client.run_python(self.workspace_id, {
            "code": code,
            "timeout": timeout
        })
        
        print("📄 Code Output:")
        print(result.get('stdout', ''))
        if result.get('stderr'):
            print("⚠️ Errors:")
            print(result.get('stderr', ''))
        
        return result
    
    def cleanup_workspace(self):
        """Clean up the workspace (but keep persistent data and bucket)"""
        if self.workspace_id:
            print(f"🧹 Cleaning up workspace: {self.workspace_id}")
            self.client.delete(self.workspace_id)
            self.workspace_id = None
            print("✅ Workspace cleaned up")

def main():
    print("🚀 OnMemOS v3 Reusable Namespace Demo")
    print("=" * 60)
    print("🏗️ Creating and using reusable namespaces with persistent storage")
    print("=" * 60)
    
    # Check GCS credentials
    gcs_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    project_id = os.getenv("PROJECT_ID")
    
    if not gcs_credentials and not project_id:
        print("⚠️  Warning: No Google Cloud credentials found!")
        print("   Set GOOGLE_APPLICATION_CREDENTIALS or use gcloud auth")
    else:
        print("✅ Google Cloud credentials configured!")
    
    # Initialize client
    token = generate_test_token()
    client = OnMemClient("http://localhost:8080", token)
    
    # Demo 1: Create a reusable namespace
    print("\n🏗️ Demo 1: Creating Reusable Namespace")
    print("-" * 50)
    
    namespace_name = "demo-ns"
    user_name = "demo-user"
    
    # Create namespace manager
    namespace = ReusableNamespace(client, namespace_name, user_name)
    
    # Set up bucket
    bucket_name = namespace.setup_bucket()
    
    # Create workspace
    workspace = namespace.create_workspace()
    
    # Store some persistent data
    persistent_data = {
        "namespace": namespace_name,
        "user": user_name,
        "created_at": datetime.now().isoformat(),
        "type": "persistent_storage",
        "description": "This data persists across workspace sessions",
        "counter": 1
    }
    
    namespace.store_persistent_data(persistent_data, "namespace_config.json")
    
    # Store some bucket data
    bucket_data = {
        "namespace": namespace_name,
        "user": user_name,
        "created_at": datetime.now().isoformat(),
        "type": "bucket_storage",
        "description": "This data is stored in Google Cloud Storage",
        "bucket_name": bucket_name,
        "features": ["persistent", "scalable", "cloud-native"]
    }
    
    namespace.store_bucket_data(bucket_data, "bucket_config.json")
    
    # Run some workspace code that uses both storage types
    workspace_code = """
import os
import json
import datetime

print("🔍 Exploring namespace storage...")

# Check persistent storage
persist_root = "/opt/onmemos/persist"
if os.path.exists(persist_root):
    print(f"📁 Persistent storage root: {persist_root}")
    for root, dirs, files in os.walk(persist_root):
        for file in files:
            if file.endswith('.json'):
                print(f"   📄 {os.path.join(root, file)}")

# Check bucket mount
if os.path.exists("/data"):
    print("📂 Bucket mount contents:")
    for item in os.listdir("/data"):
        print(f"   📦 {item}")

# Create some workspace-specific data
workspace_data = {
    "workspace_id": os.environ.get("WORKSPACE_ID", "unknown"),
    "timestamp": datetime.datetime.now().isoformat(),
    "message": "Hello from workspace!",
    "storage_types": ["persistent", "bucket", "workspace"]
}

print("💾 Creating workspace data...")
with open("/work/workspace_data.json", "w") as f:
    json.dump(workspace_data, f, indent=2)

print("✅ Workspace exploration complete!")
"""
    
    namespace.run_workspace_code(workspace_code)
    
    # Clean up workspace (but keep persistent data and bucket)
    namespace.cleanup_workspace()
    
    # Demo 2: Reuse the namespace in a new session
    print("\n🔄 Demo 2: Reusing Namespace in New Session")
    print("-" * 50)
    
    # Create a new workspace in the same namespace
    new_workspace = namespace.create_workspace()
    
    # Load the persistent data we stored earlier
    loaded_persistent = namespace.load_persistent_data("namespace_config.json")
    print(f"📂 Loaded persistent data: {loaded_persistent['description']}")
    
    # Load the bucket data we stored earlier
    loaded_bucket = namespace.load_bucket_data("bucket_config.json")
    print(f"☁️ Loaded bucket data: {loaded_bucket['description']}")
    
    # Update the persistent data
    loaded_persistent["counter"] += 1
    loaded_persistent["last_accessed"] = datetime.now().isoformat()
    namespace.store_persistent_data(loaded_persistent, "namespace_config.json")
    
    # Run code that demonstrates data persistence
    reuse_code = """
import json
import datetime

print("🔄 Demonstrating namespace reusability...")

# Load workspace data from previous session
try:
    with open("/work/workspace_data.json", "r") as f:
        workspace_data = json.load(f)
    print(f"📄 Previous workspace data: {workspace_data['message']}")
except FileNotFoundError:
    print("📄 No previous workspace data found (expected for new workspace)")

# Create new session data
session_data = {
    "session_id": "session_2",
    "timestamp": datetime.datetime.now().isoformat(),
    "message": "This is a new workspace session in the same namespace!",
    "persistent_data_available": True,
    "bucket_data_available": True
}

print("💾 Creating new session data...")
with open("/work/session_data.json", "w") as f:
    json.dump(session_data, f, indent=2)

print("✅ Namespace reuse demonstration complete!")
"""
    
    namespace.run_workspace_code(reuse_code)
    
    # Demo 3: Multiple workflows in the same namespace
    print("\n🔄 Demo 3: Multiple Workflows in Same Namespace")
    print("-" * 50)
    
    # Clean up current workspace
    namespace.cleanup_workspace()
    
    # Create workspace for data processing workflow
    processing_workspace = namespace.create_workspace()
    
    # Simulate data processing workflow
    processing_code = """
import json
import datetime
import random

print("📊 Data Processing Workflow...")

# Simulate processing some data
data_points = [random.randint(1, 100) for _ in range(10)]
processed_data = {
    "workflow": "data_processing",
    "timestamp": datetime.datetime.now().isoformat(),
    "data_points": data_points,
    "statistics": {
        "count": len(data_points),
        "sum": sum(data_points),
        "average": sum(data_points) / len(data_points),
        "min": min(data_points),
        "max": max(data_points)
    }
}

# Save processed data to persistent storage
with open("/work/processed_data.json", "w") as f:
    json.dump(processed_data, f, indent=2)

print(f"📊 Processed {len(data_points)} data points")
print(f"📈 Average: {processed_data['statistics']['average']:.2f}")
print("✅ Data processing complete!")
"""
    
    namespace.run_workspace_code(processing_code)
    
    # Clean up and create workspace for analysis workflow
    namespace.cleanup_workspace()
    analysis_workspace = namespace.create_workspace()
    
    # Simulate analysis workflow
    analysis_code = """
import json
import datetime

print("🔍 Data Analysis Workflow...")

# Load processed data from previous workflow
try:
    with open("/work/processed_data.json", "r") as f:
        processed_data = json.load(f)
    
    print(f"📊 Analyzing data from: {processed_data['workflow']}")
    print(f"📈 Statistics: {processed_data['statistics']}")
    
    # Perform analysis
    analysis_result = {
        "workflow": "data_analysis",
        "timestamp": datetime.datetime.now().isoformat(),
        "input_data": processed_data['statistics'],
        "analysis": {
            "data_quality": "good" if processed_data['statistics']['count'] > 5 else "poor",
            "variance": "high" if processed_data['statistics']['max'] - processed_data['statistics']['min'] > 50 else "low",
            "recommendations": [
                "Data looks good for further processing",
                "Consider collecting more samples for better accuracy"
            ]
        }
    }
    
    # Save analysis results
    with open("/work/analysis_results.json", "w") as f:
        json.dump(analysis_result, f, indent=2)
    
    print("✅ Analysis complete!")
    
except FileNotFoundError:
    print("⚠️ No processed data found for analysis")
"""
    
    namespace.run_workspace_code(analysis_code)
    
    # Demo 4: Show namespace contents
    print("\n📋 Demo 4: Namespace Contents Summary")
    print("-" * 50)
    
    # List bucket contents
    print("☁️ Bucket Contents:")
    try:
        bucket_contents = client.bucket_operation(bucket_name, "list", prefix=f"{namespace_name}/")
        if bucket_contents.get("success"):
            for item in bucket_contents.get("data", {}).get("objects", []):
                print(f"   📦 {item}")
    except Exception as e:
        print(f"   ⚠️ Error listing bucket: {e}")
    
    # Show persistent storage info
    print(f"\n💾 Persistent Storage:")
    print(f"   📁 Namespace: {namespace_name}")
    print(f"   👤 User: {user_name}")
    print(f"   🗂️ Path: /opt/onmemos/persist/{namespace_name}/{user_name}/")
    
    # Load and display final state
    try:
        final_persistent = namespace.load_persistent_data("namespace_config.json")
        print(f"   📄 Config file: {final_persistent['counter']} accesses")
    except Exception as e:
        print(f"   ⚠️ Error loading config: {e}")
    
    # Clean up workspace
    namespace.cleanup_workspace()
    
    print("\n🎉 Reusable Namespace Demo Completed Successfully!")
    print("=" * 60)
    print("📊 Demo Summary:")
    print("   ✅ Created reusable namespace with persistent storage")
    print("   ✅ Set up Google Cloud Storage bucket")
    print("   ✅ Stored and retrieved data across sessions")
    print("   ✅ Demonstrated multiple workflows in same namespace")
    print("   ✅ Maintained state between workspace sessions")
    print("   ✅ Real cloud integration with GCS")
    print("   ✅ Persistent storage across workspace lifecycles")
    print("\n💡 The namespace and its data will persist for future use!")

if __name__ == "__main__":
    main()
