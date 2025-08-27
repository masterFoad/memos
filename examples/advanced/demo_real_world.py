#!/usr/bin/env python3
"""
Real-world demo of OnMemOS v3 SDK functionality

This demo showcases:
- Workspace creation and management
- Bucket operations (create, upload, download, list)
- File processing and data analysis
- Multi-bucket workflows
- Code execution in workspaces
- Data persistence and sharing
"""

import os
import time
import json
import tempfile
from pathlib import Path
from sdk.python.client import OnMemClient
from test_utils import generate_test_token

def main():
    print("🚀 OnMemOS v3 Real-World Demo")
    print("=" * 50)
    
    # Initialize client with authentication
    token = generate_test_token()
    client = OnMemClient("http://localhost:8080", token)
    
    # Demo 1: Data Science Workflow with Bucket Storage
    print("\n📊 Demo 1: Data Science Workflow")
    print("-" * 30)
    
    # Create buckets for different data types
    raw_data_bucket = f"demo-raw-data-{int(time.time())}"
    processed_data_bucket = f"demo-processed-data-{int(time.time())}"
    results_bucket = f"demo-results-{int(time.time())}"
    
    print(f"Creating buckets: {raw_data_bucket}, {processed_data_bucket}, {results_bucket}")
    client.create_bucket(raw_data_bucket, "demo-namespace", "demo-user")
    client.create_bucket(processed_data_bucket, "demo-namespace", "demo-user")
    client.create_bucket(results_bucket, "demo-namespace", "demo-user")
    
    # Create sample data files
    sample_data = create_sample_data()
    
    # Upload raw data to bucket
    print("📤 Uploading sample data to raw data bucket...")
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        json.dump(sample_data, f, indent=2)
        temp_file = f.name
    
    try:
        client.upload_to_bucket(raw_data_bucket, temp_file, "sales_data.json")
        print("✅ Raw data uploaded successfully")
    finally:
        os.unlink(temp_file)
    
    # Create workspace with multiple bucket mounts
    print("🏗️ Creating workspace with bucket mounts...")
    bucket_mounts = [
        {
            "bucket_name": raw_data_bucket,
            "mount_path": "/data/raw",
            "prefix": "demo/",
            "read_only": False
        },
        {
            "bucket_name": processed_data_bucket,
            "mount_path": "/data/processed",
            "prefix": "demo/",
            "read_only": False
        },
        {
            "bucket_name": results_bucket,
            "mount_path": "/data/results",
            "prefix": "demo/",
            "read_only": False
        }
    ]
    
    workspace = client.create_workspace_with_buckets(
        template="python",
        namespace="demo-namespace",
        user="demo-user",
        bucket_mounts=bucket_mounts,
        ttl_minutes=30
    )
    
    print(f"✅ Workspace created: {workspace['id']}")
    print(f"   Bucket mounts: {len(workspace['bucket_mounts'])}")
    
    # Demo 2: Data Processing Pipeline
    print("\n🔄 Demo 2: Data Processing Pipeline")
    print("-" * 30)
    
    # Run data processing code
    processing_code = """
import json
import pandas as pd
import numpy as np
from pathlib import Path
import os

print("🔍 Starting data processing pipeline...")

# Check bucket mounts
print(f"Raw data path exists: {os.path.exists('/data/raw')}")
print(f"Processed data path exists: {os.path.exists('/data/processed')}")
print(f"Results path exists: {os.path.exists('/data/results')}")

# Read raw data
raw_data_path = "/data/raw/sales_data.json"
if os.path.exists(raw_data_path):
    with open(raw_data_path, 'r') as f:
        data = json.load(f)
    
    print(f"📊 Loaded {len(data)} sales records")
    
    # Convert to DataFrame for analysis
    df = pd.DataFrame(data)
    
    # Basic analytics
    total_sales = df['amount'].sum()
    avg_sale = df['amount'].mean()
    sales_by_region = df.groupby('region')['amount'].sum().to_dict()
    
    # Create processed data
    processed_data = {
        'summary': {
            'total_sales': float(total_sales),
            'average_sale': float(avg_sale),
            'total_transactions': len(df),
            'sales_by_region': sales_by_region
        },
        'processed_at': pd.Timestamp.now().isoformat()
    }
    
    # Save processed data
    processed_path = "/data/processed/sales_summary.json"
    os.makedirs(os.path.dirname(processed_path), exist_ok=True)
    with open(processed_path, 'w') as f:
        json.dump(processed_data, f, indent=2)
    
    print(f"✅ Processed data saved to {processed_path}")
    
    # Generate visualizations (mock)
    results = {
        'charts': {
            'sales_by_region': sales_by_region,
            'daily_sales': df.groupby('date')['amount'].sum().to_dict()
        },
        'insights': [
            f"Total sales: ${total_sales:,.2f}",
            f"Average sale: ${avg_sale:.2f}",
            f"Best performing region: {max(sales_by_region, key=sales_by_region.get)}"
        ]
    }
    
    # Save results
    results_path = "/data/results/analysis_results.json"
    os.makedirs(os.path.dirname(results_path), exist_ok=True)
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"✅ Analysis results saved to {results_path}")
    print("🎉 Data processing pipeline completed!")
    
else:
    print("❌ Raw data file not found")
"""
    
    print("🖥️ Running data processing pipeline...")
    result = client.run_python(workspace["id"], {
        "code": processing_code,
        "timeout": 60.0
    })
    
    print("📄 Processing Output:")
    print(result.get('stdout', ''))
    if result.get('stderr'):
        print("❌ Errors:")
        print(result.get('stderr', ''))
    
    # Demo 3: Results Retrieval and Analysis
    print("\n📈 Demo 3: Results Retrieval and Analysis")
    print("-" * 30)
    
    # List bucket contents
    print("📋 Listing bucket contents:")
    for bucket_name in [raw_data_bucket, processed_data_bucket, results_bucket]:
        print(f"\n📦 {bucket_name}:")
        try:
            contents = client.list_bucket_contents(bucket_name, prefix="demo/")
            for item in contents:
                print(f"   📄 {item}")
        except Exception as e:
            print(f"   ❌ Error listing {bucket_name}: {e}")
    
    # Download and display results
    print("\n📊 Downloading analysis results...")
    try:
        # Download results file
        results_file = tempfile.NamedTemporaryFile(delete=False)
        results_file.close()
        
        client.download_from_bucket(results_bucket, "demo/analysis_results.json", results_file.name)
        
        with open(results_file.name, 'r') as f:
            results = json.load(f)
        
        print("🎯 Analysis Results:")
        print(f"   📊 Total sales by region: {results['charts']['sales_by_region']}")
        print(f"   💡 Key insights:")
        for insight in results['insights']:
            print(f"      • {insight}")
        
        os.unlink(results_file.name)
        
    except Exception as e:
        print(f"❌ Error downloading results: {e}")
    
    # Demo 4: Multi-Workspace Collaboration
    print("\n👥 Demo 4: Multi-Workspace Collaboration")
    print("-" * 30)
    
    # Create a second workspace for collaboration
    print("🏗️ Creating collaborative workspace...")
    collab_workspace = client.create_workspace_with_mounted_bucket(
        template="python",
        namespace="demo-namespace",
        user="demo-user",
        bucket_name=results_bucket,
        mount_path="/shared-results",
        prefix="demo/",
        read_only=False
    )
    
    print(f"✅ Collaborative workspace created: {collab_workspace['id']}")
    
    # Run collaborative analysis
    collab_code = """
import json
import os
from datetime import datetime

print("🤝 Collaborative Analysis Session")
print("=" * 40)

# Check shared results
shared_path = "/shared-results/analysis_results.json"
if os.path.exists(shared_path):
    with open(shared_path, 'r') as f:
        results = json.load(f)
    
    print("📊 Accessing shared analysis results...")
    print(f"   📈 Sales by region: {results['charts']['sales_by_region']}")
    
    # Add collaborative insights
    new_insights = [
        "Collaborative insight: Consider regional marketing campaigns",
        "Recommendation: Focus on high-performing regions",
        f"Analysis timestamp: {datetime.now().isoformat()}"
    ]
    
    # Update results with collaborative insights
    results['collaborative_insights'] = new_insights
    results['last_updated'] = datetime.now().isoformat()
    
    # Save updated results
    with open(shared_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print("✅ Collaborative insights added to shared results")
    print("🤝 Collaboration session completed!")
    
else:
    print("❌ Shared results not found")
"""
    
    print("🖥️ Running collaborative analysis...")
    collab_result = client.run_python(collab_workspace["id"], {
        "code": collab_code,
        "timeout": 30.0
    })
    
    print("📄 Collaboration Output:")
    print(collab_result.get('stdout', ''))
    
    # Demo 5: Workspace Snapshot and Sharing
    print("\n📸 Demo 5: Workspace Snapshot and Sharing")
    print("-" * 30)
    
    # Create snapshot of the main workspace
    print("📸 Creating workspace snapshot...")
    try:
        snapshot = client.snapshot(workspace["id"], "Data Science Demo - Complete Analysis")
        print(f"✅ Snapshot created: {snapshot['id']}")
        print(f"   📊 Files: {snapshot['files']}")
        print(f"   💾 Size: {snapshot['bytes']} bytes")
        
        # Create shareable link
        share = client.share(snapshot['id'], ttl_seconds=3600, scope="fork")
        print(f"🔗 Shareable link created: {share['url']}")
        
    except Exception as e:
        print(f"❌ Error creating snapshot: {e}")
    
    # Demo 6: Cleanup and Summary
    print("\n🧹 Demo 6: Cleanup and Summary")
    print("-" * 30)
    
    # List all workspaces
    print("📋 Current workspaces:")
    print(f"   🏗️ Main workspace: {workspace['id']}")
    print(f"   🤝 Collaborative workspace: {collab_workspace['id']}")
    
    # Cleanup (optional - comment out to keep workspaces for inspection)
    print("🧹 Cleaning up demo resources...")
    try:
        client.delete(workspace["id"])
        client.delete(collab_workspace["id"])
        print("✅ Workspaces deleted")
    except Exception as e:
        print(f"⚠️ Error during cleanup: {e}")
    
    print("\n🎉 Demo completed successfully!")
    print("=" * 50)
    print("📊 Demo Summary:")
    print("   ✅ Bucket creation and management")
    print("   ✅ File upload and download")
    print("   ✅ Multi-bucket workspace creation")
    print("   ✅ Data processing pipeline")
    print("   ✅ Collaborative analysis")
    print("   ✅ Workspace snapshots and sharing")
    print("   ✅ Complete workflow automation")

def create_sample_data():
    """Create sample sales data for the demo"""
    import random
    from datetime import datetime, timedelta
    
    regions = ["North", "South", "East", "West", "Central"]
    products = ["Laptop", "Phone", "Tablet", "Monitor", "Keyboard"]
    
    data = []
    base_date = datetime.now() - timedelta(days=30)
    
    for i in range(100):
        record = {
            "id": f"TXN-{i+1:04d}",
            "date": (base_date + timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d"),
            "region": random.choice(regions),
            "product": random.choice(products),
            "amount": round(random.uniform(100, 2000), 2),
            "customer_id": f"CUST-{random.randint(1000, 9999)}"
        }
        data.append(record)
    
    return data

if __name__ == "__main__":
    main()
