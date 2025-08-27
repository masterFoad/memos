#!/usr/bin/env python3
"""
🔍 Debug Permissions in OnMemOS v3
==================================

Debug script to understand permission issues in containers.
"""

from sdk.python.client import OnMemClient
from sdk.python.models import ExecCode
from test_utils import generate_test_token

def main():
    print("🔍 Debug Permissions in OnMemOS v3")
    print("=" * 40)
    
    # Setup
    token = generate_test_token()
    client = OnMemClient('http://localhost:8080', token)
    
    print("✅ Connected to OnMemOS v3 server")
    print()
    
    # Create workspace
    print("📦 Creating workspace...")
    workspace = client.create_workspace_with_buckets(
        template="python",
        namespace="debug",
        user="demo-user",
        bucket_mounts=[]
    )
    print(f"✅ Workspace created: {workspace['id']}")
    print()
    
    # Test 1: Check user and permissions
    print("🔍 Test 1: Check user and permissions")
    print("-" * 30)
    
    code1 = """
import os
import pwd
import grp

print("🔍 User Information:")
print(f"User ID: {os.getuid()}")
print(f"Group ID: {os.getgid()}")
print(f"Effective User ID: {os.geteuid()}")
print(f"Effective Group ID: {os.getegid()}")

try:
    user_info = pwd.getpwuid(os.getuid())
    print(f"Username: {user_info.pw_name}")
    print(f"Home directory: {user_info.pw_dir}")
except Exception as e:
    print(f"Error getting user info: {e}")

print("\\n📁 Directory Permissions:")
for path in ['/', '/work', '/tmp', '/persist', '/run']:
    if os.path.exists(path):
        try:
            stat_info = os.stat(path)
            print(f"✅ {path}: mode={oct(stat_info.st_mode)[-3:]}, uid={stat_info.st_uid}, gid={stat_info.st_gid}")
            try:
                files = os.listdir(path)
                print(f"   📄 Files: {len(files)} items")
            except PermissionError:
                print(f"   ❌ Permission denied listing {path}")
        except Exception as e:
            print(f"❌ {path}: Error - {e}")
    else:
        print(f"❌ {path}: Not found")
"""
    
    result1 = client.run_python(workspace['id'], ExecCode(code=code1, timeout=30.0))
    print("📊 Result:")
    print(result1.get('stdout', 'No output'))
    if result1.get('stderr'):
        print(f"⚠️  Errors: {result1.get('stderr')}")
    print()
    
    # Test 2: Try to create and list files
    print("🔍 Test 2: Create and list files")
    print("-" * 30)
    
    code2 = """
import os
import json

print("📁 Testing file operations...")

# Try to create a file in /work
try:
    test_data = {"test": "data", "timestamp": "2024-01-17"}
    with open('/work/test.json', 'w') as f:
        json.dump(test_data, f)
    print("✅ Successfully created /work/test.json")
except Exception as e:
    print(f"❌ Failed to create file: {e}")

# Try to list /work directory
try:
    files = os.listdir('/work')
    print(f"✅ Successfully listed /work: {files}")
except Exception as e:
    print(f"❌ Failed to list /work: {e}")

# Try to read the file back
try:
    with open('/work/test.json', 'r') as f:
        data = json.load(f)
    print(f"✅ Successfully read file: {data}")
except Exception as e:
    print(f"❌ Failed to read file: {e}")

# Check file permissions
try:
    stat_info = os.stat('/work/test.json')
    print(f"📄 File permissions: mode={oct(stat_info.st_mode)[-3:]}, uid={stat_info.st_uid}, gid={stat_info.st_gid}")
except Exception as e:
    print(f"❌ Failed to get file stats: {e}")
"""
    
    result2 = client.run_python(workspace['id'], ExecCode(code=code2, timeout=30.0))
    print("📊 Result:")
    print(result2.get('stdout', 'No output'))
    if result2.get('stderr'):
        print(f"⚠️  Errors: {result2.get('stderr')}")
    print()
    
    # Test 3: Shell command to check permissions
    print("🔍 Test 3: Shell command to check permissions")
    print("-" * 30)
    
    shell_cmd = "ls -la /work && id && whoami"
    shell_result = client.run_shell(workspace['id'], shell_cmd)
    print(f"Shell result: {shell_result}")
    print(f"stdout: {shell_result.get('stdout', 'No output')}")
    print(f"stderr: {shell_result.get('stderr', 'No errors')}")
    print()
    
    # Cleanup
    print("🧹 Cleaning up...")
    client.delete(workspace['id'])
    print("✅ Workspace deleted")
    print()
    
    print("🎉 Debug complete!")

if __name__ == "__main__":
    main()
