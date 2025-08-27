#!/usr/bin/env python3
"""
Test script for the new user management system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from server.models.users import (
    UserType, UserManager, UserStorageRequest, 
    USER_ENTITLEMENTS, user_manager
)
from server.models.sessions import CreateSessionRequest, SessionProvider, ResourceTier

def test_user_management():
    """Test the user management system"""
    print("🧪 Testing User Management System")
    print("=" * 50)
    
    # Create test users
    print("\n1. Creating test users...")
    
    # Normal user
    normal_user = user_manager.create_user(
        user_id="normal_user",
        user_type=UserType.NORMAL,
        email="normal@example.com",
        name="Normal User"
    )
    print(f"✅ Created {normal_user.user_type} user: {normal_user.user_id}")
    
    # Pro user
    pro_user = user_manager.create_user(
        user_id="pro_user", 
        user_type=UserType.PRO,
        email="pro@example.com",
        name="Pro User"
    )
    print(f"✅ Created {pro_user.user_type} user: {pro_user.user_id}")
    
    # Enterprise user
    enterprise_user = user_manager.create_user(
        user_id="enterprise_user",
        user_type=UserType.ENTERPRISE,
        email="enterprise@example.com", 
        name="Enterprise User"
    )
    print(f"✅ Created {enterprise_user.user_type} user: {enterprise_user.user_id}")
    
    # Show entitlements
    print("\n2. User Entitlements:")
    for user_type, entitlements in USER_ENTITLEMENTS.items():
        print(f"   {user_type.value.upper()}:")
        print(f"     - Max buckets: {entitlements.max_buckets}")
        print(f"     - Max persistent storage: {entitlements.max_persistent_storage}")
        print(f"     - Max storage size: {entitlements.max_storage_size_gb}GB")
        print(f"     - Can share: {entitlements.can_share_storage}")
        print(f"     - Cross namespace: {entitlements.can_cross_namespace}")
    
    # Test storage allocation scenarios
    print("\n3. Testing Storage Allocation Scenarios:")
    
    # Scenario 1: Normal user with no storage
    print("\n   Scenario 1: Normal user with no storage")
    req1 = CreateSessionRequest(
        provider=SessionProvider.gke,
        template="python",
        namespace="test1",
        user="normal_user",
        ttl_minutes=30,
        user_type=UserType.NORMAL,
        request_bucket=False,
        request_persistent_storage=False
    )
    
    storage_req1 = req1.to_storage_request("session-1")
    can_allocate1 = user_manager.can_allocate_storage("normal_user", storage_req1)
    print(f"     Can allocate: {can_allocate1} ✅")
    
    # Scenario 2: Normal user with bucket only
    print("\n   Scenario 2: Normal user with bucket only")
    req2 = CreateSessionRequest(
        provider=SessionProvider.gke,
        template="python", 
        namespace="test2",
        user="normal_user",
        ttl_minutes=30,
        user_type=UserType.NORMAL,
        request_bucket=True,
        request_persistent_storage=False,
        bucket_size_gb=10
    )
    
    storage_req2 = req2.to_storage_request("session-2")
    can_allocate2 = user_manager.can_allocate_storage("normal_user", storage_req2)
    print(f"     Can allocate: {can_allocate2} ✅")
    
    if can_allocate2:
        allocation2 = user_manager.allocate_storage("normal_user", storage_req2)
        print(f"     Allocated bucket: {allocation2.bucket_name}")
    
    # Scenario 3: Normal user trying to get both (should fail)
    print("\n   Scenario 3: Normal user trying to get both (should fail)")
    req3 = CreateSessionRequest(
        provider=SessionProvider.gke,
        template="python",
        namespace="test3", 
        user="normal_user",
        ttl_minutes=30,
        user_type=UserType.NORMAL,
        request_bucket=True,
        request_persistent_storage=True,
        bucket_size_gb=10,
        persistent_storage_size_gb=20
    )
    
    storage_req3 = req3.to_storage_request("session-3")
    can_allocate3 = user_manager.can_allocate_storage("normal_user", storage_req3)
    print(f"     Can allocate: {can_allocate3} ❌ (Expected: False)")
    
    # Scenario 4: Pro user with multiple resources
    print("\n   Scenario 4: Pro user with multiple resources")
    req4 = CreateSessionRequest(
        provider=SessionProvider.gke,
        template="python",
        namespace="test4",
        user="pro_user", 
        ttl_minutes=30,
        user_type=UserType.PRO,
        request_bucket=True,
        request_persistent_storage=True,
        bucket_size_gb=50,
        persistent_storage_size_gb=100
    )
    
    storage_req4 = req4.to_storage_request("session-4")
    can_allocate4 = user_manager.can_allocate_storage("pro_user", storage_req4)
    print(f"     Can allocate: {can_allocate4} ✅")
    
    if can_allocate4:
        allocation4 = user_manager.allocate_storage("pro_user", storage_req4)
        print(f"     Allocated bucket: {allocation4.bucket_name}")
        print(f"     Allocated PVC: {allocation4.persistent_volume_name}")
        print(f"     Total storage: {allocation4.storage_size_gb}GB")
    
    # Show current usage
    print("\n4. Current User Usage:")
    for user_id in ["normal_user", "pro_user", "enterprise_user"]:
        user = user_manager.get_user(user_id)
        if user:
            print(f"   {user_id} ({user.user_type.value}):")
            print(f"     - Buckets: {len(user.current_buckets)}")
            print(f"     - Persistent storage: {len(user.current_persistent_storage)}")
            print(f"     - Total storage used: {user.current_storage_size_gb}GB")
    
    print("\n✅ User management system test completed!")

if __name__ == "__main__":
    test_user_management()
