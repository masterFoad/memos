#!/usr/bin/env python3
"""
Test billing integration with session creation and deletion
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add the server directory to the path
sys.path.insert(0, str(Path(__file__).parent / "server"))

from database.sqlite_temp_client import SQLiteTempClient
from database.base import UserType, StorageType, BillingType
from server.services.sessions.gke_provider import GkeSessionProvider
from server.models.sessions import CreateSessionRequest, StorageConfig, StorageType as SessionStorageType, ResourceTier

async def test_billing_integration():
    """Test billing integration with session creation and deletion"""
    
    # Create SQLite client
    db_client = SQLiteTempClient()
    
    try:
        # Connect to database
        await db_client.connect()
        print("✅ Connected to database")
        
        # Create test user with credits
        user_id = "test_billing_user"
        user = await db_client.create_user(user_id, "billing@test.com", UserType.PRO, "Billing Test User")
        print(f"✅ Created user: {user['id']}")
        
        # Add credits to user (PRO users start with 0 credits)
        await db_client.add_credits(user_id, 10.0, "test", "Test credit addition")
        current_credits = await db_client.get_user_credits(user_id)
        print(f"✅ User has ${current_credits:.2f} credits")
        
        # Create workspace
        workspace_id = "test_workspace_billing"
        workspace = await db_client.create_workspace(user_id, workspace_id, "Test Workspace", "basic")
        print(f"✅ Created workspace: {workspace['name']}")
        
        # Create GKE session provider
        provider = GkeSessionProvider()
        
        # Create session request
        session_request = CreateSessionRequest(
            user=user_id,
            namespace="test-namespace",
            workspace_id=workspace_id,
            template="python_pro",
            provider="gke",
            resource_tier=ResourceTier.SMALL,
            ttl_minutes=60,
            storage_config=StorageConfig(
                storage_type=SessionStorageType.EPHEMERAL,
                mount_path="/workspace"
            )
        )
        
        print(f"\n--- Testing Session Creation with Billing ---")
        
        # Create session (this should trigger billing)
        try:
            session_info = await provider.create(session_request)
            print(f"✅ Created session: {session_info.id}")
            print(f"   Status: {session_info.status}")
            print(f"   Provider: {session_info.provider}")
            
            # Check if billing was started
            billing_info = await db_client.get_session_billing_info(session_info.id)
            if billing_info:
                print(f"   Billing started: ${billing_info['hourly_rate']:.4f}/hour")
                print(f"   Billing status: {billing_info['status']}")
            else:
                print("   ⚠️ No billing info found")
            
            # Simulate session running for 30 minutes
            print(f"\n--- Simulating 30-minute session ---")
            await asyncio.sleep(2)  # Simulate time passing
            
            # Check credits after session creation
            credits_after_creation = await db_client.get_user_credits(user_id)
            print(f"   Credits after creation: ${credits_after_creation:.2f}")
            
            # Delete session (this should trigger billing cleanup)
            print(f"\n--- Testing Session Deletion with Billing ---")
            success = await provider.delete(session_info.id)
            print(f"✅ Session deleted: {success}")
            
            # Check final billing info
            final_billing = await db_client.get_session_billing_info(session_info.id)
            if final_billing:
                print(f"   Final billing: {final_billing['total_hours']:.4f} hours = ${final_billing['total_cost']:.4f}")
                print(f"   Billing status: {final_billing['status']}")
            else:
                print("   ⚠️ No final billing info found")
            
            # Check credits after session deletion
            credits_after_deletion = await db_client.get_user_credits(user_id)
            print(f"   Credits after deletion: ${credits_after_deletion:.2f}")
            
            # Check credit history
            credit_history = await db_client.get_credit_history(user_id)
            print(f"   Credit transactions: {len(credit_history)}")
            for transaction in credit_history:
                print(f"     {transaction['amount']:+.2f} - {transaction['source']}")
            
        except Exception as e:
            print(f"❌ Session creation failed: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n🎉 Billing integration test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db_client.disconnect()

if __name__ == "__main__":
    os.environ["DATABASE_TYPE"] = "sqlite"
    asyncio.run(test_billing_integration())
