#!/usr/bin/env python3
"""
User → Namespace → Google Cloud Storage Hierarchy Demo

This demo shows the hierarchical structure:
User
├── Namespace 1
│   ├── Google Cloud Storage Buckets
│   └── Persistent Storage (local for now, cloud volumes later)
├── Namespace 2
│   ├── Google Cloud Storage Buckets
│   └── Persistent Storage
└── Namespace 3
    ├── Google Cloud Storage Buckets
    └── Persistent Storage
"""

import os
import time
import json
import tempfile
from datetime import datetime
from sdk.python.client import OnMemClient
from test_utils import generate_test_token

def main():
    print("👤 OnMemOS v3 User → Namespace → Google Cloud Storage Demo")
    print("=" * 70)
    print("🏗️ Hierarchical storage management with Google Cloud")
    print("=" * 70)
    
    # Check GCS credentials
    project_id = os.getenv("PROJECT_ID")
    if not project_id:
        print("❌ PROJECT_ID environment variable not set")
        print("   Set PROJECT_ID to your Google Cloud project ID")
        return
    
    print(f"✅ Using Google Cloud Project: {project_id}")
    
    # Initialize client
    token = generate_test_token()
    client = OnMemClient("http://localhost:8080", token)
    
    # Demo 1: Set up a user with multiple namespaces
    print("\n👤 Demo 1: User with Multiple Namespaces")
    print("-" * 50)
    
    # Set the current user
    user_name = "demo-user-123"
    client.set_user(user_name)
    print(f"👤 Current user: {client.get_user()}")
    
    # Create multiple namespaces for the user
    namespaces = ["data-science", "web-app", "ml-training"]
    
    for namespace in namespaces:
        print(f"\n🏗️ Creating namespace: {namespace}")
        ns_info = client.create_namespace(namespace)
        print(f"✅ Namespace '{namespace}' created")
        
        # Create a bucket for each namespace (GCS-compliant naming)
        timestamp = int(time.time()) % 1000000
        safe_namespace = namespace.replace("-", "").replace("_", "")[:8]
        safe_user = user_name.replace("-", "").replace("_", "")[:8]
        bucket_name = f"onmemos-{safe_namespace}-{safe_user}-{timestamp}"
        bucket_result = client.create_bucket_in_namespace(bucket_name, namespace)
        print(f"📦 Bucket created: {bucket_result['name']}")
        
        # Store some namespace-specific data
        namespace_data = {
            "namespace": namespace,
            "user": user_name,
            "project_id": project_id,
            "bucket": bucket_result["name"],
            "created_at": datetime.now().isoformat(),
            "purpose": f"Storage for {namespace} projects",
            "storage_types": ["gcs_bucket", "persistent_storage"]
        }
        
        # Store in both persistent and bucket storage
        client.store_in_namespace(namespace_data, "namespace_config.json", namespace, storage_type="persistent")
        client.store_in_namespace(namespace_data, "namespace_config.json", namespace, storage_type="bucket")
        
        print(f"💾 Data stored in namespace '{namespace}'")
    
    # Demo 2: List user's namespaces
    print("\n📁 Demo 2: User's Namespaces")
    print("-" * 50)
    
    user_namespaces = client.list_namespaces()
    print(f"📁 User '{user_name}' has {len(user_namespaces)} namespaces:")
    
    for ns in user_namespaces:
        print(f"   📁 {ns['namespace']}")
        print(f"      📅 Created: {ns['created_at']}")
        buckets = ns.get('storage', {}).get('buckets', [])
        print(f"      📦 Buckets: {len(buckets)}")
        for bucket in buckets:
            print(f"         ☁️ {bucket['name']}")
    
    # Demo 3: Work with specific namespace
    print("\n🔧 Demo 3: Working with Specific Namespace")
    print("-" * 50)
    
    # Use the data-science namespace
    with client.namespace("data-science") as ns_info:
        print(f"📁 Working in namespace: {ns_info['namespace']}")
        
        # Create some data science specific data
        dataset_info = {
            "dataset_name": "customer_behavior_2024",
            "namespace": "data-science",
            "user": user_name,
            "created_at": datetime.now().isoformat(),
            "columns": ["user_id", "timestamp", "action", "value"],
            "row_count": 1000000,
            "file_format": "parquet",
            "storage_location": "gcs_bucket"
        }
        
        # Store dataset info
        client.store_in_namespace(dataset_info, "dataset_metadata.json", "data-science", storage_type="persistent")
        client.store_in_namespace(dataset_info, "dataset_metadata.json", "data-science", storage_type="bucket")
        
        # Create a workspace for data processing
        workspace = client.create_workspace_with_mounted_bucket(
            template="python",
            namespace="data-science",
            user=user_name,
            bucket_name=ns_info['storage']['buckets'][0]['name'],
            mount_path="/data",
            prefix="data-science/",
            read_only=False
        )
        
        print(f"🏗️ Created workspace: {workspace['id']}")
        
        # Run some data science code
        data_science_code = """
import os
import json
import pandas as pd
from datetime import datetime

print("📊 Data Science Workspace Demo")
print("=" * 40)

# Check available data
print("📂 Available data:")
if os.path.exists("/data"):
    for item in os.listdir("/data"):
        print(f"   📄 {item}")

# Simulate data processing
print("\\n🔬 Processing data...")

# Create sample dataset
data = {
    'user_id': range(1, 1001),
    'timestamp': [datetime.now().isoformat() for _ in range(1000)],
    'action': ['click', 'purchase', 'view'] * 333 + ['click'],
    'value': [10.0 + i * 0.1 for i in range(1000)]
}

df = pd.DataFrame(data)
print(f"📊 Created dataset with {len(df)} rows")

# Save processed data
output_path = "/work/processed_data.parquet"
df.to_parquet(output_path)
print(f"💾 Saved processed data to: {output_path}")

# Create processing report
report = {
    "workspace_id": os.environ.get("WORKSPACE_ID", "unknown"),
    "processing_timestamp": datetime.now().isoformat(),
    "dataset_name": "customer_behavior_2024",
    "rows_processed": len(df),
    "columns": list(df.columns),
    "output_file": "processed_data.parquet"
}

with open("/work/processing_report.json", "w") as f:
    json.dump(report, f, indent=2)

print("✅ Data processing complete!")
"""
        
        result = client.run_python(workspace["id"], {
            "code": data_science_code,
            "timeout": 60.0
        })
        
        print("📄 Processing Output:")
        print(result.get('stdout', ''))
        
        # Clean up workspace
        client.delete(workspace["id"])
        print(f"🧹 Cleaned up workspace: {workspace['id']}")
    
    # Demo 4: Cross-namespace data sharing
    print("\n🔄 Demo 4: Cross-Namespace Data Sharing")
    print("-" * 50)
    
    # Load data from data-science namespace
    ds_data = client.load_from_namespace("dataset_metadata.json", "data-science", storage_type="persistent")
    print(f"📊 Loaded dataset info: {ds_data['dataset_name']}")
    
    # Share with web-app namespace
    web_app_data = {
        "source_namespace": "data-science",
        "source_user": user_name,
        "shared_data": ds_data,
        "shared_at": datetime.now().isoformat(),
        "purpose": "Web app analytics dashboard"
    }
    
    client.store_in_namespace(web_app_data, "shared_analytics.json", "web-app", storage_type="persistent")
    client.store_in_namespace(web_app_data, "shared_analytics.json", "web-app", storage_type="bucket")
    
    print(f"🔄 Shared data from 'data-science' to 'web-app' namespace")
    
    # Demo 5: Namespace management
    print("\n🗂️ Demo 5: Namespace Management")
    print("-" * 50)
    
    # Show namespace details
    for namespace in namespaces:
        print(f"\n📁 Namespace: {namespace}")
        
        # Get namespace info
        ns_info = client.get_namespace(namespace)
        if ns_info:
            print(f"   👤 User: {ns_info['user']}")
            print(f"   📅 Created: {ns_info['created_at']}")
            
            # List buckets
            buckets = client.list_buckets_in_namespace(namespace)
            print(f"   📦 Buckets: {len(buckets)}")
            for bucket in buckets:
                print(f"      ☁️ {bucket['name']}")
            
            # List persistent storage files
            try:
                # This would list files in persistent storage
                print(f"   💾 Persistent storage: {ns_info['storage']['persistent_path']}")
            except:
                print(f"   💾 Persistent storage: Available")
    
    # Demo 6: User summary
    print("\n📋 Demo 6: User Summary")
    print("-" * 50)
    
    print(f"👤 User: {user_name}")
    print(f"📁 Total Namespaces: {len(user_namespaces)}")
    
    total_buckets = 0
    for ns in user_namespaces:
        buckets = ns.get('storage', {}).get('buckets', [])
        total_buckets += len(buckets)
    
    print(f"📦 Total Buckets: {total_buckets}")
    print(f"🏭 Google Cloud Project: {project_id}")
    
    print("\n🎉 User → Namespace → Google Cloud Storage Demo Completed!")
    print("=" * 70)
    print("📊 Demo Summary:")
    print("   ✅ Created user with multiple namespaces")
    print("   ✅ Each namespace has its own GCS bucket")
    print("   ✅ Combined persistent and bucket storage")
    print("   ✅ Cross-namespace data sharing")
    print("   ✅ Workspace integration with bucket mounts")
    print("   ✅ Real Google Cloud Storage integration")
    print("\n💡 All namespaces and data persist for future use!")
    print("💡 Ready for cloud volume integration (Filestore/Persistent Disks)")

if __name__ == "__main__":
    main()
