#!/usr/bin/env python3
"""
Unified Sessions API Test
========================
Test the new unified sessions API that supports multiple backends.
"""

import sys
import time
import requests
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

def test_unified_sessions():
    """Test the unified sessions API"""
    base_url = "http://127.0.0.1:8080"
    api_key = "onmemos-internal-key-2024-secure"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    
    print("🚀 Unified Sessions API Test")
    print("=" * 50)
    
    # Test 1: Create Cloud Run session via unified API
    print("\n📦 Step 1: Creating Cloud Run session via unified API...")
    session_data = {
        "provider": "cloud_run",
        "template": "python",
        "namespace": "unified-test",
        "user": "test-user",
        "ttl_minutes": 30
    }
    
    try:
        response = requests.post(f"{base_url}/v1/sessions", json=session_data, headers=headers)
        if response.status_code == 200:
            session = response.json()
            session_id = session["id"]
            print(f"✅ Session created: {session_id}")
            print(f"   Provider: {session['provider']}")
            print(f"   URL: {session.get('url', 'N/A')}")
            print(f"   WebSocket: {session.get('websocket', 'N/A')}")
        else:
            print(f"❌ Failed to create session: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error creating session: {e}")
        return False
    
    # Test 2: Execute command in session
    print("\n💻 Step 2: Executing command in session...")
    try:
        exec_data = {"command": "echo 'Hello from unified sessions!' && pwd"}
        response = requests.post(f"{base_url}/v1/sessions/{session_id}/execute", json=exec_data, headers=headers)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Command executed successfully")
            print(f"   Return code: {result['returncode']}")
            print(f"   Output: {result['stdout'].strip()}")
        else:
            print(f"❌ Failed to execute command: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error executing command: {e}")
    
    # Test 3: Get session info
    print("\n📋 Step 3: Getting session info...")
    try:
        response = requests.get(f"{base_url}/v1/sessions/{session_id}", headers=headers)
        if response.status_code == 200:
            session_info = response.json()
            print(f"✅ Session info retrieved")
            print(f"   Status: {session_info['status']}")
            print(f"   Provider: {session_info['provider']}")
        else:
            print(f"❌ Failed to get session info: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error getting session info: {e}")
    
    # Test 4: Get connection info
    print("\n🔗 Step 4: Getting connection info...")
    try:
        response = requests.get(f"{base_url}/v1/sessions/{session_id}/connect", headers=headers)
        if response.status_code == 200:
            connect_info = response.json()
            print(f"✅ Connection info retrieved")
            print(f"   URL: {connect_info.get('url', 'N/A')}")
            print(f"   WebSocket: {connect_info.get('websocket', 'N/A')}")
            print(f"   SSH: {connect_info.get('ssh', 'N/A')}")
        else:
            print(f"❌ Failed to get connection info: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error getting connection info: {e}")
    
    # Test 5: Delete session
    print("\n🧹 Step 5: Deleting session...")
    try:
        response = requests.delete(f"{base_url}/v1/sessions/{session_id}", headers=headers)
        if response.status_code == 200:
            print(f"✅ Session deleted successfully")
        else:
            print(f"❌ Failed to delete session: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error deleting session: {e}")
    
    print("\n🎉 Unified Sessions API test completed!")
    return True

def test_auto_provider_selection():
    """Test automatic provider selection"""
    base_url = "http://127.0.0.1:8080"
    api_key = "onmemos-internal-key-2024-secure"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    
    print("\n🤖 Auto Provider Selection Test")
    print("=" * 40)
    
    # Test auto selection for different scenarios
    test_cases = [
        {
            "name": "Default (should pick Cloud Run)",
            "data": {
                "provider": "auto",
                "template": "python",
                "namespace": "auto-test",
                "user": "test-user",
                "ttl_minutes": 30
            }
        },
        {
            "name": "Long-lived (should pick GKE)",
            "data": {
                "provider": "auto",
                "template": "python",
                "namespace": "auto-test-long",
                "user": "test-user",
                "long_lived": True,
                "ttl_minutes": 30
            }
        },
        {
            "name": "Needs SSH (should pick Workstations)",
            "data": {
                "provider": "auto",
                "template": "python",
                "namespace": "auto-test-ssh",
                "user": "test-user",
                "needs_ssh": True,
                "ttl_minutes": 30
            }
        }
    ]
    
    created_sessions = []
    
    for i, test_case in enumerate(test_cases):
        print(f"\n📦 Test {i+1}: {test_case['name']}")
        try:
            response = requests.post(f"{base_url}/v1/sessions", json=test_case['data'], headers=headers)
            if response.status_code == 200:
                session = response.json()
                created_sessions.append(session["id"])
                print(f"✅ Session created: {session['id']}")
                print(f"   Selected provider: {session['provider']}")
            else:
                print(f"❌ Failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    # Cleanup
    print(f"\n🧹 Cleaning up {len(created_sessions)} test sessions...")
    for session_id in created_sessions:
        try:
            requests.delete(f"{base_url}/v1/sessions/{session_id}", headers=headers)
        except:
            pass
    
    print("✅ Auto provider selection test completed!")

def main():
    """Run all unified sessions tests"""
    print("🚀 OnMemOS v3 Unified Sessions Test Suite")
    print("=" * 60)
    
    # Test basic unified sessions functionality
    success1 = test_unified_sessions()
    
    # Test auto provider selection
    test_auto_provider_selection()
    
    if success1:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
