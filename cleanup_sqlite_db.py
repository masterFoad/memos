#!/usr/bin/env python3
"""
Cleanup script for SQLite database
Removes test data to allow fresh testing
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the server directory to the path
sys.path.insert(0, str(Path(__file__).parent / "server"))

from database.sqlite_temp_client import SQLiteTempClient

async def cleanup_database():
    """Clean up the SQLite database"""
    db_client = SQLiteTempClient()
    
    try:
        await db_client.connect()
        print("Connected to database")
        
        # Delete test users
        await db_client._execute_update("DELETE FROM users WHERE email LIKE '%test%' OR email LIKE '%demo%'")
        print("Cleaned up test users")
        
        # Delete test data from other tables
        await db_client._execute_update("DELETE FROM passports WHERE user_id LIKE '%test%' OR user_id LIKE '%demo%'")
        await db_client._execute_update("DELETE FROM credit_transactions WHERE user_id LIKE '%test%' OR user_id LIKE '%demo%'")
        await db_client._execute_update("DELETE FROM billing_transactions WHERE user_id LIKE '%test%' OR user_id LIKE '%demo%'")
        await db_client._execute_update("DELETE FROM session_billing WHERE user_id LIKE '%test%' OR user_id LIKE '%demo%'")
        await db_client._execute_update("DELETE FROM service_accounts WHERE user_id LIKE '%test%' OR user_id LIKE '%demo%'")
        await db_client._execute_update("DELETE FROM storage_resources WHERE user_id LIKE '%test%' OR user_id LIKE '%demo%'")
        await db_client._execute_update("DELETE FROM workspaces WHERE user_id LIKE '%test%' OR user_id LIKE '%demo%'")
        await db_client._execute_update("DELETE FROM sessions WHERE workspace_id LIKE '%test%' OR workspace_id LIKE '%demo%'")
        await db_client._execute_update("DELETE FROM usage_tracking WHERE user_id LIKE '%test%' OR user_id LIKE '%demo%'")
        await db_client._execute_update("DELETE FROM spaces WHERE space_id LIKE '%test%' OR space_id LIKE '%demo%'")
        await db_client._execute_update("DELETE FROM user_spaces WHERE user_id LIKE '%test%' OR user_id LIKE '%demo%'")
        
        print("Database cleaned up successfully")
        
    except Exception as e:
        print(f"Error cleaning up database: {e}")
    finally:
        await db_client.disconnect()

if __name__ == "__main__":
    os.environ["DATABASE_TYPE"] = "sqlite"
    asyncio.run(cleanup_database())
