#!/usr/bin/env python3
"""
🔍 OnMemOS v3 SDK Exploration (Simple)
======================================

A tiny script to explore and understand the SDK's potential.
Uses only standard Python libraries.
"""

import os
import json
import time
from sdk.python.client import OnMemClient
from sdk.python.models import ExecCode
from test_utils import generate_test_token

def main():
    print("🔍 OnMemOS v3 SDK Exploration (Simple)")
    print("=" * 45)
    
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
import sys

# Show we're running in RAM
print(f"🔍 Current directory: {os.getcwd()}")
print(f"🐍 Python version: {sys.version}")
print(f"📁 /work directory exists: {os.path.exists('/work')}")
print(f"📁 /tmp directory exists: {os.path.exists('/tmp')}")
print(f"⏱️  Timestamp: {time.time()}")

# Do some RAM-speed computation
start_time = time.time()
result = sum(i**2 for i in range(100000))
computation_time = time.time() - start_time

print(f"🧮 Computed sum of squares (0-99999): {result}")
print(f"⚡ Computation time: {computation_time:.4f} seconds")
"""
    
    result = client.run_python(workspace['id'], ExecCode(code=code, timeout=30.0))
    print("📊 Python execution result:")
    print(result.get('stdout', 'No output'))
    if result.get('stderr'):
        print(f"⚠️  Errors: {result.get('stderr')}")
    print()
    
    # Step 3: File Operations in RAM
    print("📁 Step 3: File operations in RAM")
    print("-" * 30)
    
    file_code = """
import json
import os
import time

# Create a file in RAM
data = {
    "message": "Hello from RAM!",
    "timestamp": time.time(),
    "location": "/work (RAM disk)",
    "python_version": "3.11"
}

# Write to RAM disk
with open('/work/ram_data.json', 'w') as f:
    json.dump(data, f, indent=2)

# Read it back
with open('/work/ram_data.json', 'r') as f:
    loaded_data = json.load(f)

print("📄 File operations in RAM:")
print(f"✅ Created: /work/ram_data.json")
print(f"📖 Content: {loaded_data}")
print(f"📁 Files in /work: {os.listdir('/work')}")

# Test file size
file_size = os.path.getsize('/work/ram_data.json')
print(f"📏 File size: {file_size} bytes")
"""
    
    result = client.run_python(workspace['id'], ExecCode(code=file_code, timeout=30.0))
    print(result.get('stdout', 'No output'))
    if result.get('stderr'):
        print(f"⚠️  Errors: {result.get('stderr')}")
    print()
    
    # Step 4: Data Processing in RAM (using standard library)
    print("🧮 Step 4: Data processing in RAM")
    print("-" * 30)
    
    processing_code = """
import time
import random
import statistics

# Create large dataset in RAM using standard library
print("🔄 Creating 100K random numbers in RAM...")
data = [random.random() for _ in range(100000)]

# Process in RAM (ultra-fast!)
start_time = time.time()
mean_val = statistics.mean(data)
std_val = statistics.stdev(data) if len(data) > 1 else 0
min_val = min(data)
max_val = max(data)
processing_time = time.time() - start_time

print(f"📊 Processing complete in {processing_time:.3f} seconds!")
print(f"📈 Mean: {mean_val:.4f}")
print(f"📊 Std: {std_val:.4f}")
print(f"📊 Min: {min_val:.4f}")
print(f"📊 Max: {max_val:.4f}")
print(f"💾 Data size: {len(data)} numbers in RAM")
"""
    
    result = client.run_python(workspace['id'], ExecCode(code=processing_code, timeout=30.0))
    print(result.get('stdout', 'No output'))
    if result.get('stderr'):
        print(f"⚠️  Errors: {result.get('stderr')}")
    print()
    
    # Step 5: Interactive Shell
    print("🖥️ Step 5: Interactive shell commands")
    print("-" * 30)
    
    shell_commands = [
        "echo '🔍 System info:' && uname -a",
        "echo '💾 Memory usage:' && free -h",
        "echo '📁 Current directory:' && pwd && ls -la",
        "echo '⚡ CPU info:' && nproc"
    ]
    
    for cmd in shell_commands:
        result = client.run_shell(workspace['id'], cmd)
        print(f"🔧 Command: {cmd}")
        print(result.get('stdout', 'No output'))
        if result.get('stderr'):
            print(f"⚠️  Errors: {result.get('stderr')}")
        print()
    
    # Step 6: Environment Exploration
    print("🔍 Step 6: Environment exploration")
    print("-" * 30)
    
    env_code = """
import os
import sys
import platform

print("🔍 Environment Information:")
print(f"🐍 Python: {sys.version}")
print(f"🖥️  Platform: {platform.platform()}")
print(f"📁 Working dir: {os.getcwd()}")
print(f"🏠 Home dir: {os.path.expanduser('~')}")
print(f"📦 Python path: {sys.path[:3]}...")  # First 3 entries

print("\\n📁 Directory structure:")
for path in ['/', '/work', '/tmp', '/persist', '/run']:
    if os.path.exists(path):
        print(f"✅ {path}: {len(os.listdir(path))} items")
    else:
        print(f"❌ {path}: Not found")

print("\\n🔧 Environment variables:")
for key in ['PATH', 'PYTHONPATH', 'HOME', 'USER']:
    if key in os.environ:
        print(f"✅ {key}: {os.environ[key]}")
"""
    
    result = client.run_python(workspace['id'], ExecCode(code=env_code, timeout=30.0))
    print(result.get('stdout', 'No output'))
    if result.get('stderr'):
        print(f"⚠️  Errors: {result.get('stderr')}")
    print()
    
    # Step 7: Cleanup
    print("🧹 Step 7: Cleanup")
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
    print("✅ Environment exploration")
    print("✅ Automatic cleanup")
    print()
    print("🚀 This is just the beginning!")
    print("Next: Try bucket operations, namespaces, snapshots...")

if __name__ == "__main__":
    main()
