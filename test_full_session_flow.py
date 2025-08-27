#!/usr/bin/env python3
"""
Test script for the full session flow with user management
"""

import sys
import os
import time
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from server.models.sessions import CreateSessionRequest, SessionProvider, UserType, ResourceTier
from server.services.sessions.gke_provider import gke_provider
from server.models.users import user_manager

def test_session_flow():
    """Test the full session flow with user management"""
    print("🧪 Testing Full Session Flow with User Management")
    print("=" * 60)
    
    # Clean up any existing users
    user_manager.users.clear()
    
    # Test scenarios
    scenarios = [
        {
            "name": "Normal User - No Storage (Ephemeral)",
            "user": "normal_user_1",
            "user_type": UserType.NORMAL,
            "request_bucket": False,
            "request_persistent_storage": False,
            "expected_success": True
        },
        {
            "name": "Normal User - Bucket Only",
            "user": "normal_user_2", 
            "user_type": UserType.NORMAL,
            "request_bucket": True,
            "request_persistent_storage": False,
            "bucket_size_gb": 10,
            "expected_success": True
        },
        {
            "name": "Normal User - Persistent Storage Only",
            "user": "normal_user_3",
            "user_type": UserType.NORMAL,
            "request_bucket": False,
            "request_persistent_storage": True,
            "persistent_storage_size_gb": 20,
            "expected_success": True
        },
        {
            "name": "Normal User - Both (Should Fail)",
            "user": "normal_user_4",
            "user_type": UserType.NORMAL,
            "request_bucket": True,
            "request_persistent_storage": True,
            "bucket_size_gb": 10,
            "persistent_storage_size_gb": 20,
            "expected_success": False
        },
        {
            "name": "Pro User - Both Storage Types",
            "user": "pro_user_1",
            "user_type": UserType.PRO,
            "request_bucket": True,
            "request_persistent_storage": True,
            "bucket_size_gb": 50,
            "persistent_storage_size_gb": 100,
            "expected_success": True
        },
        {
            "name": "Enterprise User - Large Resources",
            "user": "enterprise_user_1",
            "user_type": UserType.ENTERPRISE,
            "request_bucket": True,
            "request_persistent_storage": True,
            "bucket_size_gb": 500,
            "persistent_storage_size_gb": 1000,
            "expected_success": True
        }
    ]
    
    created_sessions = []
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['name']}")
        print("-" * 40)
        
        try:
            # Create session request
            req = CreateSessionRequest(
                provider=SessionProvider.gke,
                template="python",
                namespace=f"test-{scenario['user']}",
                user=scenario['user'],
                user_type=scenario['user_type'],
                ttl_minutes=30,
                request_bucket=scenario['request_bucket'],
                request_persistent_storage=scenario['request_persistent_storage'],
                bucket_size_gb=scenario.get('bucket_size_gb'),
                persistent_storage_size_gb=scenario.get('persistent_storage_size_gb'),
                resource_tier=ResourceTier.SMALL
            )
            
            # Try to create session
            session_info = gke_provider.create(req)
            
            if scenario['expected_success']:
                print(f"   ✅ SUCCESS: Session created")
                print(f"   Session ID: {session_info.id}")
                print(f"   User Type: {session_info.user_type.value}")
                print(f"   Storage Type: {session_info.storage_config.storage_type.value if session_info.storage_config else 'ephemeral'}")
                print(f"   Bucket: {session_info.storage_allocation.bucket_name if session_info.storage_allocation else 'None'}")
                print(f"   PVC: {session_info.storage_allocation.persistent_volume_name if session_info.storage_allocation else 'None'}")
                print(f"   Storage Size: {session_info.storage_allocation.storage_size_gb if session_info.storage_allocation else 0}GB")
                
                created_sessions.append(session_info.id)
                
                # Test command execution
                print(f"   Testing command execution...")
                result = gke_provider.execute(session_info.id, "echo 'Hello from session test'")
                if result.get('success'):
                    print(f"   ✅ Command executed successfully: {result.get('stdout', '').strip()}")
                else:
                    print(f"   ❌ Command failed: {result.get('stderr', 'Unknown error')}")
                
            else:
                print(f"   ❌ UNEXPECTED SUCCESS: Session should have failed")
                
        except Exception as e:
            if scenario['expected_success']:
                print(f"   ❌ UNEXPECTED FAILURE: {e}")
            else:
                print(f"   ✅ EXPECTED FAILURE: {e}")
    
    # Show user usage after all tests
    print(f"\n📊 User Usage Summary:")
    print("=" * 40)
    for user_id in set([s['user'] for s in scenarios]):
        user = user_manager.get_user(user_id)
        if user:
            print(f"   {user_id} ({user.user_type.value}):")
            print(f"     - Buckets: {len(user.current_buckets)}")
            print(f"     - Persistent storage: {len(user.current_persistent_storage)}")
            print(f"     - Total storage used: {user.current_storage_size_gb}GB")
    
    # Clean up created sessions
    print(f"\n🧹 Cleaning up created sessions...")
    for session_id in created_sessions:
        try:
            success = gke_provider.delete(session_id)
            if success:
                print(f"   ✅ Deleted session: {session_id}")
            else:
                print(f"   ❌ Failed to delete session: {session_id}")
        except Exception as e:
            print(f"   ❌ Error deleting session {session_id}: {e}")
    
    # Show final user usage
    print(f"\n📊 Final User Usage:")
    print("=" * 40)
    for user_id in set([s['user'] for s in scenarios]):
        user = user_manager.get_user(user_id)
        if user:
            print(f"   {user_id} ({user.user_type.value}):")
            print(f"     - Buckets: {len(user.current_buckets)}")
            print(f"     - Persistent storage: {len(user.current_persistent_storage)}")
            print(f"     - Total storage used: {user.current_storage_size_gb}GB")
    
    print(f"\n✅ Full session flow test completed!")

if __name__ == "__main__":
    test_session_flow()
