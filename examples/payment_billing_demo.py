#!/usr/bin/env python3
"""
Payment & Billing System Demo for OnMemOS v3
Demonstrates the complete payment configuration, passport system, and billing infrastructure
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import time

# Add the project root to Python path
sys.path.insert(0, '/home/foad/data/memos/onmemos-v3')

from server.database.factory import initialize_database, get_database_client
from server.database.base import UserType, StorageType, BillingType
from server.services.billing_service import BillingService
from server.services.user_management import UserManagementService

async def main():
    """Main demo function"""
    print("🚀 Payment & Billing System Demo")
    print("=" * 50)
    
    # Initialize database
    print("\n1️⃣ Initializing database...")
    success = await initialize_database()
    if not success:
        print("❌ Failed to initialize database")
        return
    
    db = get_database_client()
    billing_service = BillingService()
    user_service = UserManagementService()
    
    print("✅ Database initialized")
    
    # Create test user
    print("\n2️⃣ Creating test user...")
    user_email = "demo@onmemos.com"
    user_name = "Demo User"
    
    try:
        user_infrastructure = await user_service.create_user_with_infrastructure(
            user_email, user_name, UserType.PRO
        )
        user_id = user_infrastructure["user"]["id"]
        print(f"✅ Created user: {user_id}")
        print(f"   Email: {user_email}")
        print(f"   Type: {user_infrastructure['user']['user_type']}")
    except Exception as e:
        print(f"❌ Failed to create user: {e}")
        return
    
    # Create passport (API key)
    print("\n3️⃣ Creating passport (API key)...")
    try:
        passport = await db.create_passport(
            user_id, "Demo API Key", ["read", "write", "billing"]
        )
        print(f"✅ Created passport: {passport['name']}")
        print(f"   Key: {passport['passport_key'][:20]}...")
        print(f"   Permissions: {passport['permissions']}")
    except Exception as e:
        print(f"❌ Failed to create passport: {e}")
        return
    
    # Validate passport
    print("\n4️⃣ Validating passport...")
    try:
        user_info = await db.validate_passport(passport["passport_key"])
        if user_info:
            print(f"✅ Passport validated successfully")
            print(f"   User: {user_info['email']}")
            print(f"   Type: {user_info['user_type']}")
            print(f"   Credits: ${user_info['credits']:.2f}")
        else:
            print("❌ Passport validation failed")
            return
    except Exception as e:
        print(f"❌ Failed to validate passport: {e}")
        return
    
    # Purchase credits
    print("\n5️⃣ Purchasing credits...")
    try:
        credit_purchase = await billing_service.purchase_credits(user_id, 25.0, "stripe")
        print(f"✅ Credit purchase successful")
        print(f"   Amount: ${credit_purchase['amount_usd']}")
        print(f"   Credits received: {credit_purchase['total_credits']:.2f}")
        print(f"   Bonus credits: {credit_purchase['bonus_credits']:.2f}")
        
        # Check updated balance
        new_balance = await db.get_user_credits(user_id)
        print(f"   New balance: ${new_balance:.2f}")
    except Exception as e:
        print(f"❌ Failed to purchase credits: {e}")
        return
    
    # Create storage resources
    print("\n6️⃣ Creating storage resources...")
    try:
        # Create a bucket
        bucket_resource = await db.create_storage_resource(
            user_id, StorageType.GCS_BUCKET, "demo-bucket-2024", 50
        )
        print(f"✅ Created bucket: {bucket_resource['resource_name']}")
        
        # Create a filestore
        pvc_resource = await db.create_storage_resource(
            user_id, StorageType.FILESTORE_PVC, "demo-pvc-2024", 100
        )
        print(f"✅ Created PVC: {pvc_resource['resource_name']}")
        
        # Calculate storage costs
        bucket_cost = await billing_service.calculate_storage_cost(
            StorageType.GCS_BUCKET, 50, 30
        )
        pvc_cost = await billing_service.calculate_storage_cost(
            StorageType.FILESTORE_PVC, 100, 30
        )
        
        print(f"   Bucket cost (30 days): ${bucket_cost:.4f}")
        print(f"   PVC cost (30 days): ${pvc_cost:.4f}")
        
    except Exception as e:
        print(f"❌ Failed to create storage resources: {e}")
        return
    
    # Simulate session billing
    print("\n7️⃣ Simulating session billing...")
    try:
        # Create a workspace
        workspace_id = f"demo-workspace-{int(time.time())}"
        workspace = await db.create_workspace(
            user_id, workspace_id, "Demo Workspace", "dev_small", "Demo workspace for billing test"
        )
        print(f"✅ Created workspace: {workspace['name']}")
        
        # Create a session
        session_id = f"demo-session-{int(time.time())}"
        session = await db.create_session(
            workspace_id, session_id, "gke", {"storage_type": "persistent_volume"}
        )
        print(f"✅ Created session: {session_id}")
        
        # Start billing
        billing_info = await billing_service.start_session_billing(
            session_id, user_id, "medium"
        )
        print(f"✅ Started session billing")
        print(f"   Hourly rate: ${billing_info['hourly_rate']:.4f}")
        
        # Simulate session running for 2 hours
        print("   Simulating 2-hour session...")
        await asyncio.sleep(2)  # Simulate time passing
        
        # Stop billing
        final_billing = await billing_service.stop_session_billing(session_id)
        print(f"✅ Session billing completed")
        print(f"   Duration: {final_billing['total_hours']:.2f} hours")
        print(f"   Total cost: ${final_billing['total_cost']:.4f}")
        
        # Check updated balance
        final_balance = await db.get_user_credits(user_id)
        print(f"   Final balance: ${final_balance:.2f}")
        
    except Exception as e:
        print(f"❌ Failed to simulate session billing: {e}")
        return
    
    # Purchase a space
    print("\n8️⃣ Purchasing a space...")
    try:
        # Get available spaces
        spaces = await db.get_available_spaces()
        if spaces:
            space = spaces[0]  # Get first available space
            print(f"   Available space: {space['name']} (${space['cost_usd']})")
            
            # Purchase the space
            user_space = await db.purchase_space(
                user_id, space['space_id'], workspace_id, "my-ml-dataset"
            )
            print(f"✅ Purchased space successfully")
            print(f"   Space: {space['name']}")
            print(f"   Instance: {user_space['instance_name']}")
            print(f"   Cost: ${user_space['cost_usd']}")
            
            # Check workspace spaces
            workspace_spaces = await db.get_workspace_spaces(workspace_id)
            print(f"   Spaces attached to workspace: {len(workspace_spaces)}")
            
        else:
            print("   No spaces available for purchase")
            
    except Exception as e:
        print(f"❌ Failed to purchase space: {e}")
        return
    
    # Get billing summary
    print("\n9️⃣ Getting billing summary...")
    try:
        summary = await billing_service.get_user_billing_summary(
            user_id, 
            start_date=datetime.now() - timedelta(days=1),
            end_date=datetime.now()
        )
        
        print(f"✅ Billing summary retrieved")
        print(f"   Current balance: ${summary['current_balance']:.2f}")
        print(f"   Credits added: ${summary['credits']['total_added']:.2f}")
        print(f"   Credits used: ${summary['credits']['total_used']:.2f}")
        print(f"   Total spent: ${summary['total_spent']:.2f}")
        print(f"   Transaction count: {summary['transaction_count']}")
        
        if summary['costs_by_type']:
            print("   Costs by type:")
            for billing_type, amount in summary['costs_by_type'].items():
                print(f"     {billing_type}: ${amount:.4f}")
                
    except Exception as e:
        print(f"❌ Failed to get billing summary: {e}")
        return
    
    # Get pricing information
    print("\n🔟 Getting pricing information...")
    try:
        pricing_info = await billing_service.get_pricing_info()
        
        print(f"✅ Pricing information retrieved")
        print("   Tier limits:")
        for tier, limits in pricing_info['tier_limits'].items():
            print(f"     {tier}: ${limits['hourly_rate']:.4f}/hour, {limits['max_buckets']} buckets, {limits['max_filestores']} filestores")
        
        print("   Storage pricing:")
        storage_pricing = pricing_info['pricing'].get('storage_pricing', {})
        print(f"     Bucket: ${storage_pricing.get('bucket_per_gb_monthly', 0.02):.4f}/GB/month")
        print(f"     Filestore: ${storage_pricing.get('filestore_per_gb_monthly', 0.17):.4f}/GB/month")
        
    except Exception as e:
        print(f"❌ Failed to get pricing information: {e}")
        return
    
    # Get user passports
    print("\n1️⃣1️⃣ Getting user passports...")
    try:
        passports = await db.get_user_passports(user_id)
        print(f"✅ User has {len(passports)} active passport(s)")
        
        for i, passport in enumerate(passports, 1):
            print(f"   {i}. {passport['name']}")
            print(f"      Key: {passport['passport_key'][:20]}...")
            print(f"      Permissions: {passport['permissions']}")
            print(f"      Last used: {passport['last_used']}")
            
    except Exception as e:
        print(f"❌ Failed to get user passports: {e}")
        return
    
    # Get credit history
    print("\n1️⃣2️⃣ Getting credit history...")
    try:
        credit_history = await db.get_credit_history(user_id)
        print(f"✅ Credit history retrieved ({len(credit_history)} transactions)")
        
        for i, transaction in enumerate(credit_history[:5], 1):  # Show last 5
            print(f"   {i}. {transaction['transaction_type'].upper()}: ${transaction['amount']:.2f}")
            print(f"      Source: {transaction['source']}")
            print(f"      Description: {transaction['description']}")
            print(f"      Date: {transaction['created_at']}")
            
    except Exception as e:
        print(f"❌ Failed to get credit history: {e}")
        return
    
    print("\n🎉 Payment & Billing Demo Completed Successfully!")
    print("=" * 50)
    print("✅ Database interface working")
    print("✅ Passport system working")
    print("✅ Credit system working")
    print("✅ Billing calculations working")
    print("✅ Session billing working")
    print("✅ Space purchasing working")
    print("✅ Transaction tracking working")
    
    # Cleanup
    print("\n🧹 Cleaning up...")
    try:
        await db.delete_user(user_id)
        print("✅ Demo user deleted")
    except Exception as e:
        print(f"⚠️  Failed to cleanup: {e}")

if __name__ == "__main__":
    asyncio.run(main())
