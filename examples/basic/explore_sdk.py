#!/usr/bin/env python3
"""
🔍 OnMemOS v3 SDK Exploration Script
====================================

A tiny script to explore and understand the SDK's potential.
Starts small and builds up to show what's possible.
"""

import os
import json
from sdk.python.client import OnMemClient
from sdk.python.models import ExecCode
from test_utils import generate_test_token

def main():
    print("🔍 OnMemOS v3 SDK Exploration")
    print("=" * 40)
    
    # Setup
    token = generate_test_token()
    client = OnMemClient('http://localhost:8080', token)
    
    print("✅ Connected to OnMemOS v3 server")
    print()
    
    # Step 1: Basic Workspace Creation
    print("📦 Step 1: Create a workspace")
    print("-" * 30)
    
    workspace = client.create_workspace_with_buckets(
        template="python",
        namespace="explore",
        user="demo-user",
        bucket_mounts=[]
    )
    print(f"✅ Workspace created: {workspace['id']}")
    print()
    
    # Step 2: Run Python Code (RAM-speed!)
    print("⚡ Step 2: Run Python code (in RAM)")
    print("-" * 30)
    
    code = """
import time
import os
import psutil

# Show we're running in RAM
print(f"🔍 Current directory: {os.getcwd()}")
print(f"💾 Available memory: {psutil.virtual_memory().available / 1024**3:.1f} GB")
print(f"📁 /work directory: {os.listdir('/work')}")
print(f"⏱️  Timestamp: {time.time()}")

# Do some RAM-speed computation
result = sum(i**2 for i in range(1000000))
print(f"🧮 Computed sum: {result}")
"""
    
    result = client.run_python(workspace['id'], ExecCode(code=code, timeout=30.0))
    print("📊 Python execution result:")
    print(result.get('stdout', ''))
    print()
    
    # Step 3: File Operations in RAM
    print("📁 Step 3: File operations in RAM")
    print("-" * 30)
    
    file_code = """
import json
import os

# Create a file in RAM
data = {
    "message": "Hello from RAM!",
    "timestamp": "2024-01-17",
    "location": "/work (RAM disk)"
}

with open('/work/ram_data.json', 'w') as f:
    json.dump(data, f, indent=2)

# Read it back
with open('/work/ram_data.json', 'r') as f:
    loaded_data = json.load(f)

print("📄 File operations in RAM:")
print(f"✅ Created: /work/ram_data.json")
print(f"📖 Content: {loaded_data}")
print(f"📁 Files in /work: {os.listdir('/work')}")
"""
    
    result = client.run_python(workspace['id'], ExecCode(code=file_code, timeout=30.0))
    print(result.get('stdout', ''))
    print()
    
    # Step 4: Data Processing in RAM
    print("🧮 Step 4: Data processing in RAM")
    print("-" * 30)
    
    processing_code = """
import numpy as np
import time

# Create large dataset in RAM
print("🔄 Creating 1M random numbers in RAM...")
data = np.random.random(1000000)

# Process in RAM (ultra-fast!)
start_time = time.time()
mean_val = np.mean(data)
std_val = np.std(data)
percentiles = np.percentile(data, [25, 50, 75])
processing_time = time.time() - start_time

print(f"📊 Processing complete in {processing_time:.3f} seconds!")
print(f"📈 Mean: {mean_val:.4f}")
print(f"📊 Std: {std_val:.4f}")
print(f"📊 Percentiles: {percentiles}")
print(f"💾 Data size: {data.nbytes / 1024**2:.1f} MB in RAM")
"""
    
    result = client.run_python(workspace['id'], ExecCode(code=processing_code, timeout=30.0))
    print(result.get('stdout', ''))
    print()
    
    # Step 5: Interactive Shell
    print("🖥️ Step 5: Interactive shell commands")
    print("-" * 30)
    
    shell_commands = [
        "echo '🔍 System info:' && uname -a",
        "echo '💾 Memory usage:' && free -h",
        "echo '📁 Current directory:' && pwd && ls -la",
        "echo '⚡ CPU info:' && nproc && cat /proc/cpuinfo | grep 'model name' | head -1"
    ]
    
    for cmd in shell_commands:
        result = client.run_shell(workspace['id'], cmd)
        print(result.get('stdout', ''))
    
    print()
    
    # Step 6: Cleanup
    print("🧹 Step 6: Cleanup")
    print("-" * 30)
    
    client.delete(workspace['id'])
    print("✅ Workspace deleted")
    print()
    
    # Summary
    print("🎉 SDK Exploration Complete!")
    print("=" * 40)
    print("What we explored:")
    print("✅ Workspace creation in RAM")
    print("✅ Ultra-fast Python execution")
    print("✅ File operations in memory")
    print("✅ Data processing at RAM speed")
    print("✅ Interactive shell access")
    print("✅ Automatic cleanup")
    print()
    print("🚀 This is just the beginning!")
    print("Next: Try bucket operations, namespaces, snapshots...")

if __name__ == "__main__":
    main()
