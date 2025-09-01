#!/usr/bin/env python3
"""
Simple test to demonstrate fractional billing
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add the server directory to the path
sys.path.insert(0, str(Path(__file__).parent / "server"))

from database.sqlite_temp_client import SQLiteTempClient
from database.base import UserType

async def test_fractional_billing():
    """Test fractional hour billing"""
    
    # Create SQLite client
    db_client = SQLiteTempClient()
    
    try:
        # Connect to database
        await db_client.connect()
        print("✅ Connected to database")
        
        # Create test user
        user_id = "test_fractional_user"
        user = await db_client.create_user(user_id, "fractional@test.com", UserType.PRO, "Fractional Test User")
        print(f"✅ Created user: {user['id']}")
        
        # Create workspace and session
        workspace_id = "test_workspace_fractional"
        workspace = await db_client.create_workspace(user_id, workspace_id, "Test Workspace", "basic")
        print(f"✅ Created workspace: {workspace['name']}")
        
        # Test different session durations
        test_durations = [
            ("30 seconds", 30),
            ("1 minute", 60),
            ("5 minutes", 300),
            ("15 minutes", 900),
            ("30 minutes", 1800),
            ("45 minutes", 2700),
            ("1 hour", 3600),
            ("2 hours", 7200)
        ]
        
        hourly_rate = 0.075  # PRO tier rate
        
        for duration_name, seconds in test_durations:
            print(f"\n--- Testing {duration_name} session ---")
            
            # Create a new session for each test
            test_session_id = f"test_session_{seconds}"
            test_session = await db_client.create_session(workspace_id, test_session_id, "gke", {"storage": "test"})
            
            # Start billing
            billing_info = await db_client.start_session_billing(test_session_id, user_id, hourly_rate)
            start_time = billing_info['start_time']
            
            # Calculate expected duration and cost
            duration_hours = seconds / 3600.0
            expected_cost = hourly_rate * duration_hours
            
            print(f"   Expected duration: {duration_hours:.4f} hours")
            print(f"   Expected cost: ${expected_cost:.6f}")
            
            # Stop billing with the calculated duration
            await db_client.stop_session_billing(test_session_id, duration_hours)
            
            # Get final billing info
            final_billing = await db_client.get_session_billing_info(test_session_id)
            if final_billing:
                actual_hours = final_billing['total_hours']
                actual_cost = final_billing['total_cost']
                
                print(f"   Actual duration: {actual_hours:.4f} hours")
                print(f"   Actual cost: ${actual_cost:.6f}")
                
                # Verify the calculations are correct
                if abs(actual_hours - duration_hours) < 0.0001:
                    print("   ✅ Duration calculation correct")
                else:
                    print(f"   ❌ Duration mismatch: expected {duration_hours}, got {actual_hours}")
                
                if abs(actual_cost - expected_cost) < 0.0001:
                    print("   ✅ Cost calculation correct")
                else:
                    print(f"   ❌ Cost mismatch: expected ${expected_cost}, got ${actual_cost}")
            else:
                print("   ❌ Failed to get billing info")
        
        print(f"\n🎉 Fractional billing test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db_client.disconnect()

if __name__ == "__main__":
    os.environ["DATABASE_TYPE"] = "sqlite"
    asyncio.run(test_fractional_billing())

