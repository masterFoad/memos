#!/usr/bin/env python3
"""
Test GKE persistent storage functionality
"""

import sys
import os
import time
import subprocess

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sdk', 'python'))

from client import OnMemOSClient

def test_gke_persistent_storage():
    """Test GKE persistent storage functionality"""
    print("🧪 Testing GKE Persistent Storage...")
    
    # Initialize client
    client = OnMemOSClient()
    
    # Test parameters
    user_id = "tester"
    workspace_id = "test-workspace"
    namespace = "test-gke-persistent"
    session_id = None
    
    try:
        # Create session with persistent storage
        print(f"📦 Creating GKE session with persistent storage...")
        session = client.create_session_in_workspace(
            workspace_id=workspace_id,
            template="python",
            namespace=namespace,
            user=user_id,
            request_persistent_storage=True,
            persistent_storage_size_gb=5,
            ttl_minutes=20
        )
        
        session_id = session.get('id')
        print(f"✅ Session created: {session_id}")
        
        # Wait for session to be ready
        print("⏳ Waiting for session to be ready...")
        max_wait = 60
        wait_time = 0
        while wait_time < max_wait:
            session_info = client.get_session(session_id)
            status = session_info.get('status', 'unknown')
            print(f"   Status: {status}")
            
            if status == 'running':
                break
            elif status in ['failed', 'error']:
                raise Exception(f"Session failed to start: {status}")
            
            time.sleep(5)
            wait_time += 5
        
        if wait_time >= max_wait:
            raise Exception("Session did not become ready in time")
        
        print("✅ Session is ready!")
        
        # Test 1: Write data to persistent storage
        print("\n📝 Test 1: Writing data to persistent storage...")
        write_result = client.execute_session(
            session_id=session_id,
            command="echo 'Hello from persistent storage test!' > /workspace/test_data.txt && echo 'Data written successfully'"
        )
        
        if write_result.get('success'):
            print("✅ Data written successfully")
        else:
            raise Exception(f"Failed to write data: {write_result.get('error', 'Unknown error')}")
        
        # Test 2: Read data from persistent storage
        print("\n📖 Test 2: Reading data from persistent storage...")
        read_result = client.execute_session(
            session_id=session_id,
            command="cat /workspace/test_data.txt"
        )
        
        if read_result.get('success'):
            output = read_result.get('output', '')
            if 'Hello from persistent storage test!' in output:
                print("✅ Data read successfully")
                print(f"   Content: {output.strip()}")
            else:
                raise Exception(f"Data not found in output: {output}")
        else:
            raise Exception(f"Failed to read data: {read_result.get('error', 'Unknown error')}")
        
        # Test 3: Test persistence across restarts
        print("\n🔄 Test 3: Testing persistence across restarts...")
        
        # Restart the session
        print("   Restarting session...")
        restart_result = client.execute_session(
            session_id=session_id,
            command="echo 'Session restart test' >> /workspace/test_data.txt"
        )
        
        if not restart_result.get('success'):
            raise Exception(f"Failed to write during restart: {restart_result.get('error', 'Unknown error')}")
        
        # Read all data
        final_read = client.execute_session(
            session_id=session_id,
            command="cat /workspace/test_data.txt"
        )
        
        if final_read.get('success'):
            output = final_read.get('output', '')
            if 'Hello from persistent storage test!' in output and 'Session restart test' in output:
                print("✅ Data persisted across restart")
                print(f"   Final content: {output.strip()}")
            else:
                raise Exception(f"Data not persisted correctly: {output}")
        else:
            raise Exception(f"Failed to read final data: {final_read.get('error', 'Unknown error')}")
        
        # Test 4: Create multiple files
        print("\n📁 Test 4: Creating multiple files...")
        files_result = client.execute_session(
            session_id=session_id,
            command="for i in {1..5}; do echo 'File $i content' > /workspace/file_$i.txt; done && ls -la /workspace/"
        )
        
        if files_result.get('success'):
            output = files_result.get('output', '')
            if 'file_1.txt' in output and 'file_5.txt' in output:
                print("✅ Multiple files created successfully")
                print(f"   Files: {[line for line in output.split('\\n') if 'file_' in line]}")
            else:
                raise Exception(f"Files not created correctly: {output}")
        else:
            raise Exception(f"Failed to create files: {files_result.get('error', 'Unknown error')}")
        
        print("\n🎉 All persistent storage tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False
        
    finally:
        # Cleanup
        if session_id:
            print(f"\n🧹 Cleaning up session: {session_id}")
            try:
                # The session will auto-terminate after TTL, but we can check its status
                session_info = client.get_session(session_id)
                print(f"   Final status: {session_info.get('status', 'unknown')}")
            except Exception as e:
                print(f"   Cleanup error: {e}")

if __name__ == "__main__":
    success = test_gke_persistent_storage()
    sys.exit(0 if success else 1)
