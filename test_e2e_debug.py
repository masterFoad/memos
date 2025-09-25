#!/usr/bin/env python3
"""
Debug script to test the exact same request as the e2e test
"""
import requests
import json

def test_e2e_request():
    admin_host = "http://127.0.0.1:8001"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": "onmemos-internal-key-2024-secure"
    }
    
    # Test the exact same request as the e2e test
    user_data = {
        "email": "test@example.com",
        "name": "Test User",
        "user_type": "pro"
    }
    
    print(f"Testing admin API at: {admin_host}")
    print(f"Headers: {headers}")
    print(f"Data: {user_data}")
    
    try:
        response = requests.post(
            f"{admin_host}/admin/v1/admin/users",
            headers=headers,
            json=user_data
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ SUCCESS: User created: {result}")
            return result.get("user", {}).get("user_id")
        else:
            print(f"❌ ERROR: {response.text}")
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

if __name__ == "__main__":
    test_e2e_request()
