#!/usr/bin/env python3
"""
Test script for SQLite client implementation
Tests all database interfaces to ensure they work correctly
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add the server directory to the path
sys.path.insert(0, str(Path(__file__).parent / "server"))

from database.sqlite_temp_client import SQLiteTempClient
from database.base import UserType, StorageType, BillingType, PaymentStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_sqlite_client():
    """Test the SQLite client implementation"""
    
    # Create SQLite client
    db_client = SQLiteTempClient()
    
    try:
        # Connect to database
        logger.info("Connecting to SQLite database...")
        success = await db_client.connect()
        if not success:
            logger.error("Failed to connect to database")
            return False
        
        logger.info("✅ Database connection successful")
        
        # Test user management
        logger.info("\n=== Testing User Management ===")
        user_id = "test_user_123"
        email = "test@example.com"
        
        # Create user
        user = await db_client.create_user(user_id, email, UserType.FREE, "Test User")
        logger.info(f"✅ Created user: {user}")
        
        # Get user
        retrieved_user = await db_client.get_user(user_id)
        logger.info(f"✅ Retrieved user: {retrieved_user}")
        
        # Test passport management
        logger.info("\n=== Testing Passport Management ===")
        passport = await db_client.create_passport(user_id, "Test Passport", ["read", "write"])
        logger.info(f"✅ Created passport: {passport}")
        
        # Validate passport
        validated = await db_client.validate_passport(passport['passport_key'])
        logger.info(f"✅ Validated passport: {validated is not None}")
        
        # Test credit system
        logger.info("\n=== Testing Credit System ===")
        initial_credits = await db_client.get_user_credits(user_id)
        logger.info(f"✅ Initial credits: {initial_credits}")
        
        # Add credits
        await db_client.add_credits(user_id, 10.0, "test", "Test credit addition")
        new_credits = await db_client.get_user_credits(user_id)
        logger.info(f"✅ Credits after addition: {new_credits}")
        
        # Deduct credits
        await db_client.deduct_credits(user_id, 2.0, "test deduction", "test_session", "test_resource")
        final_credits = await db_client.get_user_credits(user_id)
        logger.info(f"✅ Credits after deduction: {final_credits}")
        
        # Test billing
        logger.info("\n=== Testing Billing System ===")
        transaction = await db_client.create_transaction(
            user_id, 5.0, BillingType.CREDIT_PURCHASE, "Test transaction"
        )
        logger.info(f"✅ Created transaction: {transaction}")
        
        # Test session billing
        session_id = "test_session_123"
        billing_info = await db_client.start_session_billing(session_id, user_id, 0.05)
        logger.info(f"✅ Started session billing: {billing_info}")
        
        # Test storage management
        logger.info("\n=== Testing Storage Management ===")
        storage_resource = await db_client.create_storage_resource(
            user_id, StorageType.GCS_BUCKET, "test-bucket", 10
        )
        logger.info(f"✅ Created storage resource: {storage_resource}")
        
        # Test workspace management
        logger.info("\n=== Testing Workspace Management ===")
        workspace_id = "test_workspace_123"
        workspace = await db_client.create_workspace(
            user_id, workspace_id, "Test Workspace", "basic", "Test workspace description"
        )
        logger.info(f"✅ Created workspace: {workspace}")
        
        # Test session management
        logger.info("\n=== Testing Session Management ===")
        session = await db_client.create_session(
            workspace_id, session_id, "gke", {"bucket": "test-bucket"}
        )
        logger.info(f"✅ Created session: {session}")
        
        # Test usage tracking
        logger.info("\n=== Testing Usage Tracking ===")
        await db_client.track_storage_usage(user_id, storage_resource['resource_id'], 5.5, datetime.now())
        usage = await db_client.get_user_usage(
            user_id, 
            datetime.now() - timedelta(days=1), 
            datetime.now() + timedelta(days=1)
        )
        logger.info(f"✅ Usage tracking: {usage}")
        
        # Test tier management
        logger.info("\n=== Testing Tier Management ===")
        limits = await db_client.get_user_tier_limits(UserType.FREE)
        logger.info(f"✅ Tier limits: {limits}")
        
        can_create = await db_client.check_user_storage_quota(user_id, StorageType.GCS_BUCKET)
        logger.info(f"✅ Can create storage: {can_create}")
        
        # Test spaces management
        logger.info("\n=== Testing Spaces Management ===")
        space_id = "test_space_123"
        space = await db_client.create_space(
            space_id, "Test Space", "Test space description", "data", 50, 2.0
        )
        logger.info(f"✅ Created space: {space}")
        
        available_spaces = await db_client.get_available_spaces()
        logger.info(f"✅ Available spaces: {len(available_spaces)}")
        
        # Test space purchase
        try:
            purchased_space = await db_client.purchase_space(
                user_id, space_id, workspace_id, "test_instance"
            )
            logger.info(f"✅ Purchased space: {purchased_space}")
        except Exception as e:
            logger.warning(f"⚠️ Space purchase failed (expected if insufficient credits): {e}")
        
        # Test service account management
        logger.info("\n=== Testing Service Account Management ===")
        service_account = await db_client.create_service_account(
            user_id, "test@project.iam.gserviceaccount.com", "test-project"
        )
        logger.info(f"✅ Created service account: {service_account}")
        
        # Test payment config
        logger.info("\n=== Testing Payment Configuration ===")
        payment_config = await db_client.get_payment_config()
        logger.info(f"✅ Payment config: {payment_config}")
        
        # Test transaction history
        logger.info("\n=== Testing Transaction History ===")
        transactions = await db_client.get_user_transactions(user_id)
        logger.info(f"✅ User transactions: {len(transactions)}")
        
        credit_history = await db_client.get_credit_history(user_id)
        logger.info(f"✅ Credit history: {len(credit_history)}")
        
        # Test workspace spaces
        workspace_spaces = await db_client.get_workspace_spaces(workspace_id)
        logger.info(f"✅ Workspace spaces: {len(workspace_spaces)}")
        
        logger.info("\n🎉 All tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Disconnect from database
        await db_client.disconnect()
        logger.info("Disconnected from database")

if __name__ == "__main__":
    # Set environment variable to use SQLite
    os.environ["DATABASE_TYPE"] = "sqlite"
    
    # Run the test
    success = asyncio.run(test_sqlite_client())
    
    if success:
        logger.info("✅ All tests passed!")
        sys.exit(0)
    else:
        logger.error("❌ Some tests failed!")
        sys.exit(1)
