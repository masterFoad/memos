#!/usr/bin/env python3
"""
Debug script to test database operations directly
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from server.database.factory import get_database_client_async
from server.models.users import UserType

async def test_database():
    print("Testing database connection and user creation...")
    
    try:
        # Get database client
        db = await get_database_client_async()
        print(f"Database client: {type(db)}")
        
        # Connect to database
        connected = await db.connect()
        print(f"Database connected: {connected}")
        
        if not connected:
            print("Failed to connect to database")
            return
        
        # Test user creation
        user_id = "test-user-123"
        email = "test@example.com"
        user_type = UserType.PRO
        name = "Test User"
        
        print(f"Creating user: {user_id}, {email}, {user_type}, {name}")
        
        user = await db.create_user(user_id, email, user_type, name)
        print(f"User created: {user}")
        
        # Test getting the user
        retrieved_user = await db.get_user(user_id)
        print(f"Retrieved user: {retrieved_user}")
        
        # Disconnect
        await db.disconnect()
        print("Database disconnected")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_database())
