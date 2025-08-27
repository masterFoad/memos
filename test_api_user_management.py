#!/usr/bin/env python3
"""
Test API integration with user management
"""

import requests
import json
import time

def test_api_user_management():
    """Test the API with user management"""
    base_url = "http://127.0.0.1:8080"
    headers = {"X-API-Key": "onmemos-internal-key-2024-secure", "Content-Type": "application/json"}
    
    print("🧪 Testing API with User Management")
    print("=" * 50)
    
    # Test 1: Normal user with no storage (should work)
    print("\n1. Testing Normal User - No Storage")
    payload1 = {
        "provider": "gke",
        "template": "python",
        "namespace": "api-test-1",
        "user": "api_normal_user",
        "user_type": "normal",
        "ttl_minutes": 30,
        "request_bucket": False,
        "request_persistent_storage": False
    }
    
    try:
        response1 = requests.post(f"{base_url}/v1/sessions", headers=headers, json=payload1)
        print(f"   Status: {response1.status_code}")
        if response1.status_code == 200:
            data1 = response1.json()
            print(f"   ✅ SUCCESS: Session created")
            print(f"   Session ID: {data1.get('id')}")
            print(f"   User Type: {data1.get('user_type')}")
            print(f"   Storage Type: {data1.get('storage_config', {}).get('storage_type', 'ephemeral')}")
            
            # Clean up
            delete_response = requests.delete(f"{base_url}/v1/sessions/{data1['id']}", headers=headers)
            print(f"   Cleanup: {delete_response.status_code}")
        else:
            print(f"   ❌ FAILED: {response1.text}")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
    
    # Test 2: Normal user with bucket (should work)
    print("\n2. Testing Normal User - Bucket Only")
    payload2 = {
        "provider": "gke",
        "template": "python",
        "namespace": "api-test-2",
        "user": "api_normal_user_2",
        "user_type": "normal",
        "ttl_minutes": 30,
        "request_bucket": True,
        "request_persistent_storage": False,
        "bucket_size_gb": 10
    }
    
    try:
        response2 = requests.post(f"{base_url}/v1/sessions", headers=headers, json=payload2)
        print(f"   Status: {response2.status_code}")
        if response2.status_code == 200:
            data2 = response2.json()
            print(f"   ✅ SUCCESS: Session created")
            print(f"   Session ID: {data2.get('id')}")
            print(f"   Bucket: {data2.get('storage_allocation', {}).get('bucket_name')}")
            
            # Clean up
            delete_response = requests.delete(f"{base_url}/v1/sessions/{data2['id']}", headers=headers)
            print(f"   Cleanup: {delete_response.status_code}")
        else:
            print(f"   ❌ FAILED: {response2.text}")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
    
    # Test 3: Normal user trying to get both (should fail)
    print("\n3. Testing Normal User - Both (Should Fail)")
    payload3 = {
        "provider": "gke",
        "template": "python",
        "namespace": "api-test-3",
        "user": "api_normal_user_3",
        "user_type": "normal",
        "ttl_minutes": 30,
        "request_bucket": True,
        "request_persistent_storage": True,
        "bucket_size_gb": 10,
        "persistent_storage_size_gb": 20
    }
    
    try:
        response3 = requests.post(f"{base_url}/v1/sessions", headers=headers, json=payload3)
        print(f"   Status: {response3.status_code}")
        if response3.status_code == 422:  # Validation error
            print(f"   ✅ EXPECTED FAILURE: User cannot have both storage types")
        elif response3.status_code == 500:  # Server error
            print(f"   ✅ EXPECTED FAILURE: {response3.text}")
        else:
            print(f"   ❌ UNEXPECTED: {response3.text}")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
    
    # Test 4: Pro user with both (should work)
    print("\n4. Testing Pro User - Both Storage Types")
    payload4 = {
        "provider": "gke",
        "template": "python",
        "namespace": "api-test-4",
        "user": "api_pro_user",
        "user_type": "pro",
        "ttl_minutes": 30,
        "request_bucket": True,
        "request_persistent_storage": True,
        "bucket_size_gb": 50,
        "persistent_storage_size_gb": 100
    }
    
    try:
        response4 = requests.post(f"{base_url}/v1/sessions", headers=headers, json=payload4)
        print(f"   Status: {response4.status_code}")
        if response4.status_code == 200:
            data4 = response4.json()
            print(f"   ✅ SUCCESS: Session created")
            print(f"   Session ID: {data4.get('id')}")
            print(f"   Bucket: {data4.get('storage_allocation', {}).get('bucket_name')}")
            print(f"   PVC: {data4.get('storage_allocation', {}).get('persistent_volume_name')}")
            
            # Clean up
            delete_response = requests.delete(f"{base_url}/v1/sessions/{data4['id']}", headers=headers)
            print(f"   Cleanup: {delete_response.status_code}")
        else:
            print(f"   ❌ FAILED: {response4.text}")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
    
    print("\n✅ API user management test completed!")

if __name__ == "__main__":
    test_api_user_management()
