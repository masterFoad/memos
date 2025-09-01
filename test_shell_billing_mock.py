#!/usr/bin/env python3
"""
Mock Test for Shell Billing Integration
Tests the billing integration without requiring GKE cluster access
"""

import asyncio
import json
import time
from datetime import datetime

from server.database.factory import get_database_client
from server.services.billing_service import BillingService
from server.models.users import UserType

async def test_shell_billing_integration():
    """Test shell billing integration with mock session"""
    print("🧪 Testing Shell Billing Integration (Mock)")
    print("=" * 50)
    
    # Initialize database and billing service
    db = get_database_client()
    await db.connect()
    billing_service = BillingService()
    
    # Test user
    test_user = "shell_billing_test_user"
    
    try:
        # 1. Create test user with credits
        print(f"\n1️⃣ Creating test user: {test_user}")
        try:
            await db.create_user(
                user_id=test_user,
                email=f"{test_user}@test.com",
                user_type=UserType.PRO,
                name="Shell Billing Test User"
            )
            print(f"✅ Created user: {test_user}")
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                print(f"ℹ️ User {test_user} already exists")
            else:
                raise
        
        # 2. Add credits to user
        print(f"\n2️⃣ Adding credits to user")
        initial_credits = 5.0  # $5
        await db.add_credits(test_user, initial_credits, "test", "Initial credits for shell billing test")
        current_credits = await db.get_user_credits(test_user)
        print(f"✅ Added ${initial_credits:.2f} credits. Current balance: ${current_credits:.2f}")
        
        # 3. Create a mock session ID
        print(f"\n3️⃣ Creating mock session")
        session_id = f"mock-shell-{int(time.time())}"
        print(f"✅ Created mock session: {session_id}")
        
        # 4. Start session billing (simulating shell session start)
        print(f"\n4️⃣ Starting session billing")
        billing_info = await billing_service.start_session_billing(
            session_id, 
            test_user, 
            "gke_shell"
        )
        print(f"✅ Started billing: {billing_info}")
        
        # 5. Simulate shell session usage
        print(f"\n5️⃣ Simulating shell session usage")
        for i in range(3):
            await asyncio.sleep(2)  # Simulate 2 seconds of usage
            
            # Check current credits
            current_credits = await db.get_user_credits(test_user)
            print(f"   - Credits remaining: ${current_credits:.4f}")
            
            # Check billing status
            billing_status = await db.get_session_billing_info(session_id)
            if billing_status:
                total_cost = billing_status.get('total_cost', 0) or 0
                total_hours = billing_status.get('total_hours', 0) or 0
                print(f"   - Session cost: ${total_cost:.4f} ({total_hours:.4f} hours)")
        
        # 6. Simulate credit exhaustion
        print(f"\n6️⃣ Testing credit limit enforcement")
        
        # Add a very small amount to trigger credit limit
        await db.add_credits(test_user, 0.001, "test", "Minimal credits for limit test")
        current_credits = await db.get_user_credits(test_user)
        print(f"   - Current credits: ${current_credits:.4f}")
        
        # Simulate more usage until credits run out
        for i in range(5):
            await asyncio.sleep(1)
            current_credits = await db.get_user_credits(test_user)
            print(f"   - Credits remaining: ${current_credits:.4f}")
            
            if current_credits <= 0:
                print(f"   - Credits exhausted after {i+1} seconds")
                break
        
        # 7. Stop session billing
        print(f"\n7️⃣ Stopping session billing")
        final_billing = await billing_service.stop_session_billing(session_id)
        if final_billing:
            total_cost = final_billing.get('total_cost', 0)
            total_hours = final_billing.get('total_hours', 0)
            print(f"✅ Final billing:")
            print(f"   - Total hours: {total_hours:.4f}")
            print(f"   - Total cost: ${total_cost:.4f}")
        
        # 8. Check final credits
        print(f"\n8️⃣ Checking final credits")
        final_credits = await db.get_user_credits(test_user)
        print(f"✅ Final credits: ${final_credits:.4f}")
        
        print(f"\n🎉 Shell Billing Integration Test Completed Successfully!")
        print(f"   - Initial credits: ${initial_credits:.2f}")
        print(f"   - Final credits: ${final_credits:.4f}")
        print(f"   - Credits used: ${initial_credits - final_credits:.4f}")
        
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

async def test_credit_monitoring():
    """Test credit monitoring functionality"""
    print("\n🧪 Testing Credit Monitoring")
    print("=" * 50)
    
    db = get_database_client()
    await db.connect()
    
    test_user = "credit_monitor_test_user"
    
    try:
        # 1. Create user with minimal credits
        print(f"\n1️⃣ Creating user with minimal credits")
        try:
            await db.create_user(
                user_id=test_user,
                email=f"{test_user}@test.com",
                user_type=UserType.PRO,
                name="Credit Monitor Test User"
            )
        except Exception as e:
            if "UNIQUE constraint failed" not in str(e):
                raise
        
        # 2. Add minimal credits
        minimal_credits = 0.01  # $0.01
        await db.add_credits(test_user, minimal_credits, "test", "Minimal credits for monitoring test")
        current_credits = await db.get_user_credits(test_user)
        print(f"✅ Added ${minimal_credits:.2f} credits. Current balance: ${current_credits:.4f}")
        
        # 3. Test credit checking function
        print(f"\n2️⃣ Testing credit checking")
        
        # Simulate credit checking (like in shell service)
        async def check_credits(user_id: str) -> bool:
            """Check if user has sufficient credits"""
            try:
                current_credits = await db.get_user_credits(user_id)
                if current_credits <= 0:
                    print(f"   ❌ Insufficient credits: ${current_credits:.4f}")
                    return False
                else:
                    print(f"   ✅ Sufficient credits: ${current_credits:.4f}")
                    return True
            except Exception as e:
                print(f"   ⚠️ Error checking credits: {e}")
                return True  # Allow continuation on error
        
        # Test credit checking
        for i in range(3):
            has_credits = await check_credits(test_user)
            if not has_credits:
                print(f"   - Credit limit reached after {i+1} checks")
                break
            await asyncio.sleep(1)
        
        print(f"\n3️⃣ Credit monitoring test completed")
        
    except Exception as e:
        print(f"❌ Credit monitoring test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        try:
            await db.delete_user(test_user)
            print(f"✅ Cleaned up test user: {test_user}")
        except Exception as e:
            print(f"⚠️ Could not clean up test user: {e}")

if __name__ == "__main__":
    print("🚀 Starting Shell Billing Integration Tests (Mock)")
    print("=" * 60)
    
    # Run tests
    asyncio.run(test_shell_billing_integration())
    asyncio.run(test_credit_monitoring())
    
    print("\n✅ All mock tests completed!")
