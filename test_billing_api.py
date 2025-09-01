#!/usr/bin/env python3
"""
Test billing API endpoints with passport authentication
"""

import asyncio
import os
import sys
import requests
from pathlib import Path

# Add the server directory to the path
sys.path.insert(0, str(Path(__file__).parent / "server"))

from database.sqlite_temp_client import SQLiteTempClient
from database.base import UserType

async def setup_test_user():
    """Setup test user and return passport"""
    db_client = SQLiteTempClient()
    
    try:
        await db_client.connect()
        
        # Create test user
        user_id = "api_test_user"
        user = await db_client.create_user(user_id, "api@test.com", UserType.PRO, "API Test User")
        print(f"✅ Created user: {user['id']}")
        
        # Add credits
        await db_client.add_credits(user_id, 25.0, "test", "Test credit addition")
        current_credits = await db_client.get_user_credits(user_id)
        print(f"✅ User has ${current_credits:.2f} credits")
        
        # Create passport
        passport = await db_client.create_passport(
            user_id=user_id,
            name="API Test Passport",
            permissions=["read", "write", "billing"]
        )
        print(f"✅ Created passport: {passport['passport_key'][:20]}...")
        
        return passport['passport_key']
        
    finally:
        await db_client.disconnect()

def test_billing_api():
    """Test billing API endpoints"""
    
    # Setup test user and get passport
    print("🔧 Setting up test user...")
    passport_key = asyncio.run(setup_test_user())
    
    # API base URL
    base_url = "http://localhost:8080"
    headers = {
        "X-API-Key": passport_key,
        "Content-Type": "application/json"
    }
    
    print(f"\n--- Testing Billing API Endpoints ---")
    
    # Test 1: Get user credits
    print("\n1️⃣ Testing GET /v1/billing/credits")
    try:
        response = requests.get(f"{base_url}/v1/billing/credits", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Credits: ${data['credits']:.2f}")
        else:
            print(f"❌ Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: Get credit history
    print("\n2️⃣ Testing GET /v1/billing/history")
    try:
        response = requests.get(f"{base_url}/v1/billing/history", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ History: {data['total_transactions']} transactions")
            for tx in data['transactions'][:3]:  # Show first 3
                print(f"   {tx['amount']:+.2f} - {tx['source']}")
        else:
            print(f"❌ Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: Estimate session cost
    print("\n3️⃣ Testing GET /v1/billing/estimate")
    try:
        params = {
            "resource_tier": "medium",
            "duration_hours": 2.5
        }
        response = requests.get(f"{base_url}/v1/billing/estimate", headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Estimate: ${data['estimated_cost']:.4f} for {data['duration_hours']} hours")
            print(f"   Rate: ${data['hourly_rate']:.4f}/hour")
        else:
            print(f"❌ Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 4: Get billing summary
    print("\n4️⃣ Testing GET /v1/billing/summary")
    try:
        response = requests.get(f"{base_url}/v1/billing/summary", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Summary:")
            print(f"   Current balance: ${data['current_balance']:.2f}")
            print(f"   Credits added: ${data['credits_added']:.2f}")
            print(f"   Credits used: ${data['credits_used']:.2f}")
            print(f"   Total spent: ${data['total_spent']:.2f}")
        else:
            print(f"❌ Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 5: Purchase credits
    print("\n5️⃣ Testing POST /v1/billing/purchase")
    try:
        params = {"amount_usd": 10.0}
        response = requests.post(f"{base_url}/v1/billing/purchase", headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Purchase: {data['total_credits']} credits for ${data['amount_usd']}")
            print(f"   Bonus: {data['bonus_credits']} credits")
        else:
            print(f"❌ Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print(f"\n🎉 Billing API test completed!")

if __name__ == "__main__":
    # Set environment variables
    os.environ["DATABASE_TYPE"] = "sqlite"
    
    # Clean up database first
    print("🧹 Cleaning up database...")
    os.system("python cleanup_sqlite_db.py")
    
    # Test the API
    test_billing_api()
