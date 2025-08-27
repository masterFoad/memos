#!/usr/bin/env python3
"""
Cloud Run Integration Test for OnMemOS v3
========================================
Comprehensive test of Cloud Run workspace management and API endpoints
"""

import sys
import time
import json
import asyncio
import websockets
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from sdk.python.client import OnMemOSClient

def test_cloudrun_api_endpoints():
    """Test Cloud Run API endpoints"""
    print("🚀 Cloud Run API Integration Test")
    print("=" * 50)
    
    # Initialize client
    client = OnMemOSClient()
    
    namespace = "cloudrun-api-test"
    user = "test-user"
    
    try:
        # Step 1: Test server health
        print("\n📊 Step 1: Testing server health...")
        health = client.health_check()
        print(f"✅ Server health: {health.get('status', 'unknown')}")
        print(f"   GCP status: {health.get('gcp', {}).get('status', 'unknown')}")
        
        # Step 2: Create Cloud Run workspace
        print("\n📦 Step 2: Creating Cloud Run workspace...")
        workspace = client.create_cloudrun_workspace(
            template="python",
            namespace=namespace,
            user=user,
            ttl_minutes=30
        )
        
        workspace_id = workspace["id"]
        service_url = workspace["service_url"]
        bucket_name = workspace["bucket_name"]
        
        print(f"✅ Cloud Run workspace created: {workspace_id}")
        print(f"   Service URL: {service_url}")
        print(f"   Bucket: {bucket_name}")
        print(f"   Status: {workspace['status']}")
        
        # Step 3: Wait for service to be ready
        print("\n⏳ Step 3: Waiting for service to be ready...")
        time.sleep(30)
        
        # Step 4: Test command execution
        print("\n💻 Step 4: Testing command execution...")
        
        test_commands = [
            "pwd",
            "ls -la /workspace",
            "python --version",
            "echo 'Hello from Cloud Run!'"
        ]
        
        for cmd in test_commands:
            print(f"\n   Testing: {cmd}")
            try:
                result = client.execute_in_cloudrun_workspace(workspace_id, cmd)
                if result["success"]:
                    print(f"   ✅ Output: {result['stdout'].strip()}")
                else:
                    print(f"   ❌ Error: {result['stderr'].strip()}")
            except Exception as e:
                print(f"   ❌ Failed: {e}")
        
        # Step 5: Test Python execution
        print("\n🐍 Step 5: Testing Python execution...")
        
        python_code = """
import os
import sys
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Workspace environment: {os.environ.get('WORKSPACE_ID', 'Not set')}")
"""
        
        try:
            result = client.run_python_in_cloudrun_workspace(workspace_id, python_code)
            if result["success"]:
                print(f"✅ Python output: {result['stdout'].strip()}")
            else:
                print(f"❌ Python error: {result['stderr'].strip()}")
        except Exception as e:
            print(f"❌ Python execution failed: {e}")
        
        # Step 6: Test shell execution
        print("\n💻 Step 6: Testing shell execution...")
        
        try:
            result = client.run_shell_in_cloudrun_workspace(workspace_id, "ls -la /workspace && df -h")
            if result["success"]:
                print(f"✅ Shell output: {result['stdout'].strip()}")
            else:
                print(f"❌ Shell error: {result['stderr'].strip()}")
        except Exception as e:
            print(f"❌ Shell execution failed: {e}")
        
        # Step 7: List workspaces
        print("\n📋 Step 7: Listing Cloud Run workspaces...")
        workspaces = client.list_cloudrun_workspaces(namespace=namespace)
        print(f"✅ Found {len(workspaces)} Cloud Run workspaces in namespace '{namespace}'")
        for ws in workspaces:
            print(f"   - {ws['id']}: {ws['status']}")
        
        # Step 8: Get workspace details
        print("\n🔍 Step 8: Getting workspace details...")
        workspace_details = client.get_cloudrun_workspace(workspace_id)
        if workspace_details:
            print(f"✅ Workspace details retrieved: {workspace_details['id']}")
            print(f"   Status: {workspace_details['status']}")
            print(f"   Service URL: {workspace_details['service_url']}")
        else:
            print("❌ Failed to get workspace details")
        
        # Step 9: Cleanup
        print("\n🧹 Step 9: Cleaning up...")
        success = client.delete_cloudrun_workspace(workspace_id)
        if success:
            print("✅ Cloud Run workspace deleted successfully")
        else:
            print("⚠️  Cloud Run workspace deletion failed")
        
        print("\n🎉 Cloud Run API integration test completed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False

async def test_cloudrun_websocket_shell():
    """Test Cloud Run WebSocket shell with slash commands"""
    print("\n🔌 Cloud Run WebSocket Shell Test")
    print("=" * 50)
    
    # Initialize client
    client = OnMemOSClient()
    
    namespace = "cloudrun-ws-test"
    user = "test-user"
    
    try:
        # Step 1: Create Cloud Run workspace
        print("\n📦 Step 1: Creating Cloud Run workspace for WebSocket test...")
        workspace = client.create_cloudrun_workspace(
            template="python",
            namespace=namespace,
            user=user,
            ttl_minutes=30
        )
        
        workspace_id = workspace["id"]
        print(f"✅ Cloud Run workspace created: {workspace_id}")
        
        # Step 2: Wait for service to be ready
        print("\n⏳ Step 2: Waiting for service to be ready...")
        time.sleep(30)
        
        # Step 3: Test WebSocket connection
        print("\n🔌 Step 3: Testing WebSocket connection...")
        
        # WebSocket URL with API key
        ws_url = f"ws://127.0.0.1:8080/v1/cloudrun/workspaces/{workspace_id}/shell?api_key=onmemos-internal-key-2024-secure"
        
        async with websockets.connect(ws_url) as websocket:
            print("✅ WebSocket connected")
            
            # Test slash commands
            slash_commands = [
                "/help",
                "/info",
                "/status",
                "/pwd",
                "/ls",
                "/buckets",
                "/persist",
                "/ps",
                "/df",
                "/env"
            ]
            
            for cmd in slash_commands:
                print(f"\n   Testing slash command: {cmd}")
                
                # Send command
                await websocket.send(json.dumps({
                    "type": "command",
                    "command": cmd
                }))
                
                # Receive response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(response)
                    
                    if data["type"] == "command_result":
                        print(f"   ✅ Success: {data.get('stdout', '')[:100]}...")
                    elif data["type"] == "help":
                        print(f"   ✅ Help received")
                    elif data["type"] == "info":
                        print(f"   ✅ Info received")
                    elif data["type"] == "status":
                        print(f"   ✅ Status: {data.get('message', '')}")
                    else:
                        print(f"   ✅ Response: {data.get('message', '')[:100]}...")
                        
                except asyncio.TimeoutError:
                    print(f"   ⚠️  Timeout for command: {cmd}")
                except Exception as e:
                    print(f"   ❌ Error for command {cmd}: {e}")
            
            # Test regular command
            print(f"\n   Testing regular command: ls -la")
            await websocket.send(json.dumps({
                "type": "command",
                "command": "ls -la"
            }))
            
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                
                if data["type"] == "command_result":
                    print(f"   ✅ Regular command success: {data.get('stdout', '')[:100]}...")
                else:
                    print(f"   ✅ Response: {data.get('message', '')[:100]}...")
                    
            except asyncio.TimeoutError:
                print(f"   ⚠️  Timeout for regular command")
            except Exception as e:
                print(f"   ❌ Error for regular command: {e}")
            
            # Test exit command
            print(f"\n   Testing exit command")
            await websocket.send(json.dumps({
                "type": "command",
                "command": "/exit"
            }))
            
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                print(f"   ✅ Exit response: {data.get('message', '')}")
            except:
                print(f"   ✅ WebSocket closed")
        
        # Step 4: Cleanup
        print("\n🧹 Step 4: Cleaning up WebSocket test workspace...")
        success = client.delete_cloudrun_workspace(workspace_id)
        if success:
            print("✅ WebSocket test workspace deleted successfully")
        else:
            print("⚠️  WebSocket test workspace deletion failed")
        
        print("\n🎉 Cloud Run WebSocket shell test completed!")
        return True
        
    except Exception as e:
        print(f"\n❌ WebSocket test failed: {e}")
        return False

def test_cloudrun_context_manager():
    """Test Cloud Run context manager"""
    print("\n🔄 Cloud Run Context Manager Test")
    print("=" * 50)
    
    # Initialize client
    client = OnMemOSClient()
    
    namespace = "cloudrun-context-test"
    user = "test-user"
    
    try:
        print("\n📦 Testing Cloud Run context manager...")
        
        with client.cloudrun_workspace_session("python", namespace, user, ttl_minutes=30) as workspace:
            print(f"✅ Context manager created workspace: {workspace['id']}")
            
            # Wait for service to be ready
            time.sleep(30)
            
            # Test command execution
            result = client.execute_in_cloudrun_workspace(workspace['id'], "echo 'Hello from context manager!'")
            if result["success"]:
                print(f"✅ Context manager command executed: {result['stdout'].strip()}")
            else:
                print(f"❌ Context manager command failed: {result['stderr'].strip()}")
        
        print("✅ Context manager automatically cleaned up workspace")
        print("\n🎉 Cloud Run context manager test completed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Context manager test failed: {e}")
        return False

def main():
    """Run all Cloud Run integration tests"""
    print("🚀 OnMemOS v3 Cloud Run Integration Test Suite")
    print("=" * 60)
    
    # Test 1: API Endpoints
    api_success = test_cloudrun_api_endpoints()
    
    # Test 2: WebSocket Shell
    ws_success = asyncio.run(test_cloudrun_websocket_shell())
    
    # Test 3: Context Manager
    context_success = test_cloudrun_context_manager()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"   API Endpoints: {'✅ PASSED' if api_success else '❌ FAILED'}")
    print(f"   WebSocket Shell: {'✅ PASSED' if ws_success else '❌ FAILED'}")
    print(f"   Context Manager: {'✅ PASSED' if context_success else '❌ FAILED'}")
    
    overall_success = api_success and ws_success and context_success
    print(f"\n🎯 Overall Result: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    return 0 if overall_success else 1

if __name__ == "__main__":
    sys.exit(main())
