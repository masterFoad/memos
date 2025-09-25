#!/usr/bin/env python3
"""
Simple test script to debug admin API issues
"""
import requests
import json

def test_admin_api():
    base_url = "http://localhost:8001"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": "onmemos-internal-key-2024-secure"
    }
    
    # Test health endpoint first
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/admin/health", headers=headers)
        print(f"Health check: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Health check failed: {e}")
        return
    
    # Test create user endpoint
    print("\nTesting create user endpoint...")
    user_data = {
        "email": "test@example.com",
        "name": "Test User",
        "user_type": "pro"
    }
    
    try:
        response = requests.post(
            f"{base_url}/admin/v1/admin/users",
            headers=headers,
            json=user_data
        )
        print(f"Create user: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"User created: {result}")
            return result.get("user", {}).get("user_id")
        else:
            print(f"Error creating user: {response.text}")
            
    except Exception as e:
        print(f"Create user failed: {e}")

if __name__ == "__main__":
    test_admin_api()
