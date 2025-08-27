#!/usr/bin/env python3
"""
Create user via API to ensure server picks up the user data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from server.models.users import user_manager, UserType

def create_user_via_api():
    """Create the tester user as pro type via the server's UserManager"""
    user_id = "tester"
    
    # Delete existing user if exists
    if user_manager.get_user(user_id):
        user_manager.delete_user(user_id)
        print(f"✅ Deleted existing user: {user_id}")
    
    # Create fresh user as PRO type for higher storage entitlements
    user_manager.create_user(
        user_id=user_id,
        user_type=UserType.PRO,
        name=f"Test User {user_id}"
    )
    print(f"✅ Created fresh user: {user_id}")
    
    # Verify user state
    user = user_manager.get_user(user_id)
    entitlements = user_manager.get_user_entitlements(user_id)
    
    print(f"📊 User state:")
    print(f"   User ID: {user.user_id}")
    print(f"   Type: {user.user_type.value}")
    print(f"   Current buckets: {len(user.current_buckets)}")
    print(f"   Current PVCs: {len(user.current_persistent_storage)}")
    print(f"   Current storage: {user.current_storage_size_gb}GB")
    print(f"   Max buckets: {entitlements.max_buckets}")
    print(f"   Max PVCs: {entitlements.max_persistent_storage}")
    print(f"   Max storage: {entitlements.max_storage_size_gb}GB")
    
    print("\n🔄 This should trigger server reload and update the UserManager...")

if __name__ == "__main__":
    create_user_via_api()
