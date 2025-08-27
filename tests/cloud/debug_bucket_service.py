#!/usr/bin/env python3
"""
🔍 Debug Bucket Service
=======================

Test the bucket service directly to see what's happening
"""

import os
import sys
sys.path.append('.')

from server.bucket_service import bucket_service
from server.config import load_settings

def main():
    print("🔍 Debug Bucket Service")
    print("=" * 30)
    
    # Test settings
    settings = load_settings()
    print(f"✅ Settings loaded")
    print(f"   Bucket service enabled: {settings.buckets.enabled}")
    print(f"   Provider: {settings.buckets.provider}")
    print(f"   Default region: {settings.buckets.default_region}")
    
    # Test bucket service initialization
    print(f"\n🔧 Bucket service status:")
    print(f"   Storage client available: {bucket_service.storage_client is not None}")
    print(f"   Project ID: {bucket_service.project_id}")
    
    # Test namespace and user
    namespace = "clone-test"
    user = "demo-user-123"
    
    print(f"\n📦 Testing bucket operations for namespace '{namespace}', user '{user}'")
    
    # Test bucket creation
    try:
        bucket_name = f"debug-bucket-{int(time.time())}"
        print(f"\n🔧 Creating bucket '{bucket_name}'...")
        
        bucket = bucket_service.create_bucket(
            bucket_name=bucket_name,
            namespace=namespace,
            user=user
        )
        print(f"✅ Bucket created: {bucket}")
        
        # Test bucket listing
        print(f"\n📋 Listing buckets...")
        buckets = bucket_service.list_buckets(namespace, user)
        print(f"✅ Found {len(buckets)} buckets:")
        for i, bucket in enumerate(buckets, 1):
            print(f"   {i}. {bucket.get('name', 'Unknown')}")
        
        # Test namespace metadata update
        print(f"\n💾 Testing namespace metadata update...")
        bucket_service._update_namespace_bucket_metadata(namespace, user, bucket)
        print(f"✅ Namespace metadata updated")
        
        # Test bucket listing again
        print(f"\n📋 Listing buckets after metadata update...")
        buckets = bucket_service.list_buckets(namespace, user)
        print(f"✅ Found {len(buckets)} buckets:")
        for i, bucket in enumerate(buckets, 1):
            print(f"   {i}. {bucket.get('name', 'Unknown')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import time
    main()
