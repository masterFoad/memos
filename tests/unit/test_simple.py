#!/usr/bin/env python3
"""
🔍 Simple OnMemOS v3 Test
=========================

A minimal test to debug workspace execution.
"""

from sdk.python.client import OnMemClient
from sdk.python.models import ExecCode
from test_utils import generate_test_token

def main():
    print("🔍 Simple OnMemOS v3 Test")
    print("=" * 30)
    
    # Setup
    token = generate_test_token()
    client = OnMemClient('http://localhost:8080', token)
    
    print("✅ Connected to OnMemOS v3 server")
    print()
    
    # Create workspace
    print("📦 Creating workspace...")
    workspace = client.create_workspace_with_buckets(
        template="python",
        namespace="test",
        user="demo-user",
        bucket_mounts=[]
    )
    print(f"✅ Workspace created: {workspace['id']}")
    print()
    
    # Test 1: Simple print
    print("🧪 Test 1: Simple print")
    print("-" * 20)
    
    code1 = "print('Hello from OnMemOS!')"
    result1 = client.run_python(workspace['id'], ExecCode(code=code1, timeout=10.0))
    print(f"Result: {result1}")
    print(f"stdout: {result1.get('stdout', 'NO OUTPUT')}")
    print(f"stderr: {result1.get('stderr', 'NO ERRORS')}")
    print(f"exit_code: {result1.get('exit_code', 'UNKNOWN')}")
    print()
    
    # Test 2: Basic computation
    print("🧪 Test 2: Basic computation")
    print("-" * 20)
    
    code2 = """
print("Starting computation...")
result = 2 + 2
print(f"2 + 2 = {result}")
print("Computation complete!")
"""
    result2 = client.run_python(workspace['id'], ExecCode(code=code2, timeout=10.0))
    print(f"Result: {result2}")
    print(f"stdout: {result2.get('stdout', 'NO OUTPUT')}")
    print(f"stderr: {result2.get('stderr', 'NO ERRORS')}")
    print(f"exit_code: {result2.get('exit_code', 'UNKNOWN')}")
    print()
    
    # Test 3: Shell command
    print("🧪 Test 3: Shell command")
    print("-" * 20)
    
    shell_result = client.run_shell(workspace['id'], "echo 'Hello from shell!' && pwd")
    print(f"Shell result: {shell_result}")
    print(f"stdout: {shell_result.get('stdout', 'NO OUTPUT')}")
    print(f"stderr: {shell_result.get('stderr', 'NO ERRORS')}")
    print(f"exit_code: {shell_result.get('exit_code', 'UNKNOWN')}")
    print()
    
    # Cleanup
    print("🧹 Cleaning up...")
    client.delete(workspace['id'])
    print("✅ Workspace deleted")
    print()
    
    print("🎉 Test complete!")

if __name__ == "__main__":
    main()
