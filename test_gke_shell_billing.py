#!/usr/bin/env python3
"""
Test GKE Shell with Billing Integration
Tests the enhanced GKE WebSocket shell with credit monitoring and billing
"""

import asyncio
import json
import time
from datetime import datetime

from server.database.factory import get_database_client
from server.services.billing_service import BillingService
from server.services.sessions.manager import sessions_manager
from server.models.users import UserType

async def test_gke_shell_billing():
    """Test GKE shell with billing integration"""
    print("🧪 Testing GKE Shell with Billing Integration")
    print("=" * 50)
    
    # Initialize database and billing service
    db = get_database_client()
    await db.connect()
    billing_service = BillingService()
    
    # Test user
    test_user = "gke_shell_test_user"
    
    try:
        # 1. Create test user with credits
        print(f"\n1️⃣ Creating test user: {test_user}")
        try:
            await db.create_user(
                user_id=test_user,
                email=f"{test_user}@test.com",
                user_type=UserType.PRO,
                name="GKE Shell Test User"
            )
            print(f"✅ Created user: {test_user}")
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                print(f"ℹ️ User {test_user} already exists")
            else:
                raise
        
        # 2. Add credits to user
        print(f"\n2️⃣ Adding credits to user")
        initial_credits = 10.0  # $10
        await db.add_credits(test_user, initial_credits, "test", "Initial credits for GKE shell test")
        current_credits = await db.get_user_credits(test_user)
        print(f"✅ Added ${initial_credits:.2f} credits. Current balance: ${current_credits:.2f}")
        
        # 3. Create a test session
        print(f"\n3️⃣ Creating test session")
        session_spec = {
            "user": test_user,
            "namespace": "test",
            "workspace_id": "gke-shell-test-ws",
            "template": "alpine_basic",  # Required template field
            "provider": "gke",
            "ttl_minutes": 60,
            "resource_tier": "small"
        }
        
        session_info = await sessions_manager.create_session(session_spec)
        session_id = session_info["id"]
        print(f"✅ Created session: {session_id}")
        print(f"   - Namespace: {session_info.get('k8s_namespace')}")
        print(f"   - Pod: {session_info.get('pod_name')}")
        print(f"   - WebSocket URL: {session_info.get('websocket')}")
        
        # 4. Start session billing
        print(f"\n4️⃣ Starting session billing")
        billing_info = await billing_service.start_session_billing(
            session_id, 
            test_user, 
            "gke_shell"
        )
        print(f"✅ Started billing: {billing_info}")
        
        # 5. Simulate some usage time
        print(f"\n5️⃣ Simulating usage time (5 seconds)")
        await asyncio.sleep(5)
        
        # 6. Check billing status
        print(f"\n6️⃣ Checking billing status")
        billing_status = await db.get_session_billing_info(session_id)
        if billing_status:
            total_cost = billing_status.get('total_cost', 0) or 0
            total_hours = billing_status.get('total_hours', 0) or 0
            print(f"✅ Billing status:")
            print(f"   - Total hours: {total_hours:.4f}")
            print(f"   - Total cost: ${total_cost:.4f}")
        else:
            print("⚠️ No billing info found")
        
        # 7. Check user credits
        print(f"\n7️⃣ Checking user credits")
        current_credits = await db.get_user_credits(test_user)
        print(f"✅ Current credits: ${current_credits:.2f}")
        
        # 8. Stop session billing
        print(f"\n8️⃣ Stopping session billing")
        final_billing = await billing_service.stop_session_billing(session_id)
        if final_billing:
            total_cost = final_billing.get('total_cost', 0)
            total_hours = final_billing.get('total_hours', 0)
            print(f"✅ Final billing:")
            print(f"   - Total hours: {total_hours:.4f}")
            print(f"   - Total cost: ${total_cost:.4f}")
        
        # 9. Check final credits
        print(f"\n9️⃣ Checking final credits")
        final_credits = await db.get_user_credits(test_user)
        print(f"✅ Final credits: ${final_credits:.2f}")
        
        # 10. Clean up session
        print(f"\n🔟 Cleaning up session")
        success = await sessions_manager.delete_session(session_id)
        print(f"✅ Session cleanup: {'Success' if success else 'Failed'}")
        
        print(f"\n🎉 GKE Shell Billing Test Completed Successfully!")
        print(f"   - Initial credits: ${initial_credits:.2f}")
        print(f"   - Final credits: ${final_credits:.2f}")
        print(f"   - Credits used: ${initial_credits - final_credits:.2f}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up test user
        try:
            print(f"\n🧹 Cleaning up test user")
            await db.delete_user(test_user)
            print(f"✅ Deleted test user: {test_user}")
        except Exception as e:
            print(f"⚠️ Could not delete test user: {e}")

async def test_credit_limit():
    """Test credit limit enforcement"""
    print("\n🧪 Testing Credit Limit Enforcement")
    print("=" * 50)
    
    db = get_database_client()
    await db.connect()
    billing_service = BillingService()
    
    test_user = "credit_limit_test_user"
    
    try:
        # 1. Create user with minimal credits
        print(f"\n1️⃣ Creating user with minimal credits")
        try:
            await db.create_user(
                user_id=test_user,
                email=f"{test_user}@test.com",
                user_type=UserType.PRO,
                name="Credit Limit Test User"
            )
        except Exception as e:
            if "UNIQUE constraint failed" not in str(e):
                raise
        
        # 2. Add minimal credits
        minimal_credits = 0.01  # $0.01 (very small amount)
        await db.add_credits(test_user, minimal_credits, "test", "Minimal credits for limit test")
        current_credits = await db.get_user_credits(test_user)
        print(f"✅ Added ${minimal_credits:.2f} credits. Current balance: ${current_credits:.2f}")
        
        # 3. Create session
        print(f"\n2️⃣ Creating session")
        session_spec = {
            "user": test_user,
            "namespace": "test",
            "workspace_id": "credit-limit-test-ws",
            "template": "alpine_basic",  # Required template field
            "provider": "gke",
            "ttl_minutes": 60,
            "resource_tier": "small"
        }
        
        session_info = await sessions_manager.create_session(session_spec)
        session_id = session_info["id"]
        print(f"✅ Created session: {session_id}")
        
        # 4. Start billing
        print(f"\n3️⃣ Starting billing")
        billing_info = await billing_service.start_session_billing(
            session_id, 
            test_user, 
            "gke_shell"
        )
        print(f"✅ Started billing")
        
        # 5. Simulate usage until credits run out
        print(f"\n4️⃣ Simulating usage until credits run out")
        for i in range(10):
            await asyncio.sleep(1)
            current_credits = await db.get_user_credits(test_user)
            print(f"   - Credits remaining: ${current_credits:.4f}")
            
            if current_credits <= 0:
                print(f"   - Credits exhausted after {i+1} seconds")
                break
        
        # 6. Check final state
        print(f"\n5️⃣ Checking final state")
        final_credits = await db.get_user_credits(test_user)
        print(f"✅ Final credits: ${final_credits:.4f}")
        
        # 7. Clean up
        print(f"\n6️⃣ Cleaning up")
        await billing_service.stop_session_billing(session_id)
        await sessions_manager.delete_session(session_id)
        await db.delete_user(test_user)
        print(f"✅ Cleanup completed")
        
        print(f"\n🎉 Credit Limit Test Completed!")
        
    except Exception as e:
        print(f"❌ Credit limit test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Starting GKE Shell Billing Tests")
    print("=" * 60)
    
    # Run tests
    asyncio.run(test_gke_shell_billing())
    asyncio.run(test_credit_limit())
    
    print("\n✅ All tests completed!")
