#!/usr/bin/env python3
"""
Test Enhanced Features - Bucket Mounting and Persistent Storage
Demonstrates the enhanced session system with GCS FUSE and PVC support
"""

import asyncio
import json
from datetime import datetime

from server.models.sessions import (
    CreateSessionRequest, SessionProvider, StorageConfig, StorageType, ResourceTier
)
from server.services.sessions.gke_provider import gke_provider

def test_enhanced_session_creation():
    """Test enhanced session creation with different storage types"""
    
    print("🚀 Testing Enhanced Session Features")
    print("=" * 50)
    
    # Test 1: Session with GCS FUSE (bucket mounting)
    print("\n📦 Test 1: Session with GCS FUSE (Bucket Mounting)")
    print("-" * 40)
    
    gcs_request = CreateSessionRequest(
        provider=SessionProvider.gke,
        template="python",
        namespace="test-enhanced",
        user="tester",
        ttl_minutes=30,
        resource_tier=ResourceTier.SMALL,
        storage_config=StorageConfig(
            storage_type=StorageType.GCS_FUSE,
            mount_path="/workspace",
            bucket_name="test-bucket",  # Provide a dummy bucket name for testing
            gcs_mount_options="implicit-dirs,only-dir=workspace/,file-mode=0644,dir-mode=0755"
        ),
        env={
            "CUSTOM_VAR": "test_value"
        }
    )
    
    try:
        session = gke_provider.create(gcs_request)
        print(f"✅ Created GCS FUSE session: {session.id}")
        print(f"   Bucket: {session.storage_config.bucket_name if session.storage_config else 'None'}")
        print(f"   Mount Path: {session.storage_config.mount_path if session.storage_config else 'None'}")
        print(f"   Status: {session.status}")
        print(f"   Provider: {session.provider}")
        print(f"   Resource Tier: {session.resource_tier}")
        print(f"   WebSocket: {session.websocket}")
        
        # Test session retrieval
        retrieved = gke_provider.get(session.id)
        print(f"   Retrieved: {retrieved.id if retrieved else 'None'}")
        
        # Cleanup
        success = gke_provider.delete(session.id)
        print(f"🗑️  Deleted session: {session.id} (success: {success})")
        
    except Exception as e:
        print(f"❌ GCS FUSE test failed: {e}")
    
    # Test 2: Session with Persistent Volume
    print("\n💾 Test 2: Session with Persistent Volume")
    print("-" * 40)
    
    pvc_request = CreateSessionRequest(
        provider=SessionProvider.gke,
        template="nodejs",
        namespace="test-enhanced",
        user="tester",
        ttl_minutes=30,
        resource_tier=ResourceTier.MEDIUM,
        storage_config=StorageConfig(
            storage_type=StorageType.PERSISTENT_VOLUME,
            mount_path="/workspace",
            pvc_name="test-pvc",  # Provide a dummy PVC name for testing
            pvc_size="5Gi",
            storage_class="standard-rwo"
        )
    )
    
    try:
        session = gke_provider.create(pvc_request)
        print(f"✅ Created PVC session: {session.id}")
        print(f"   PVC: {session.storage_config.pvc_name if session.storage_config else 'None'}")
        print(f"   Size: {session.storage_config.pvc_size if session.storage_config else 'None'}")
        print(f"   Mount Path: {session.storage_config.mount_path if session.storage_config else 'None'}")
        print(f"   Status: {session.status}")
        print(f"   Resource Tier: {session.resource_tier}")
        
        # Cleanup
        success = gke_provider.delete(session.id)
        print(f"🗑️  Deleted session: {session.id} (success: {success})")
        
    except Exception as e:
        print(f"❌ PVC test failed: {e}")
    
    # Test 3: Session with Ephemeral Storage (default)
    print("\n⚡ Test 3: Session with Ephemeral Storage")
    print("-" * 40)
    
    ephemeral_request = CreateSessionRequest(
        provider=SessionProvider.gke,
        template="golang",
        namespace="test-enhanced",
        user="tester",
        ttl_minutes=30,
        resource_tier=ResourceTier.SMALL,
        storage_config=StorageConfig(
            storage_type=StorageType.EPHEMERAL,
            mount_path="/workspace"
        )
    )
    
    try:
        session = gke_provider.create(ephemeral_request)
        print(f"✅ Created ephemeral session: {session.id}")
        print(f"   Storage Type: {session.storage_config.storage_type if session.storage_config else 'None'}")
        print(f"   Mount Path: {session.storage_config.mount_path if session.storage_config else 'None'}")
        print(f"   Status: {session.status}")
        print(f"   Resource Tier: {session.resource_tier}")
        
        # Cleanup
        success = gke_provider.delete(session.id)
        print(f"🗑️  Deleted session: {session.id} (success: {success})")
        
    except Exception as e:
        print(f"❌ Ephemeral test failed: {e}")
    
    # Test 4: Legacy storage dict compatibility
    print("\n🔄 Test 4: Legacy Storage Dict Compatibility")
    print("-" * 40)
    
    legacy_request = CreateSessionRequest(
        provider=SessionProvider.gke,
        template="python",
        namespace="test-enhanced",
        user="tester",
        ttl_minutes=30,
        storage={
            "type": "gcs_fuse",
            "bucket_name": "legacy-bucket",
            "mount_path": "/workspace"
        }
    )
    
    try:
        session = gke_provider.create(legacy_request)
        print(f"✅ Created legacy session: {session.id}")
        print(f"   Storage Type: {session.storage_config.storage_type if session.storage_config else 'None'}")
        print(f"   Bucket: {session.storage_config.bucket_name if session.storage_config else 'None'}")
        print(f"   Mount Path: {session.storage_config.mount_path if session.storage_config else 'None'}")
        
        # Cleanup
        success = gke_provider.delete(session.id)
        print(f"🗑️  Deleted session: {session.id} (success: {success})")
        
    except Exception as e:
        print(f"❌ Legacy test failed: {e}")

def test_validation():
    """Test Pydantic validation"""
    
    print("\n🔍 Test 5: Pydantic Validation")
    print("=" * 50)
    
    # Test invalid TTL
    print("\n📝 Testing invalid TTL...")
    try:
        invalid_request = CreateSessionRequest(
            provider=SessionProvider.gke,
            template="python",
            namespace="test-validation",
            user="tester",
            ttl_minutes=0  # Invalid: must be >= 1
        )
        print("   ❌ Should have failed validation")
    except Exception as e:
        print(f"   ✅ Correctly rejected invalid TTL: {e}")
    
    # Test invalid namespace
    print("\n📝 Testing invalid namespace...")
    try:
        invalid_request = CreateSessionRequest(
            provider=SessionProvider.gke,
            template="python",
            namespace="test@validation",  # Invalid: contains @
            user="tester",
            ttl_minutes=10
        )
        print("   ❌ Should have failed validation")
    except Exception as e:
        print(f"   ✅ Correctly rejected invalid namespace: {e}")
    
    # Test invalid storage config
    print("\n📝 Testing invalid storage config...")
    try:
        invalid_request = CreateSessionRequest(
            provider=SessionProvider.gke,
            template="python",
            namespace="test-validation",
            user="tester",
            storage_config=StorageConfig(
                storage_type=StorageType.GCS_FUSE,
                # Missing bucket_name - should fail validation
            )
        )
        print("   ❌ Should have failed validation")
    except Exception as e:
        print(f"   ✅ Correctly rejected invalid storage config: {e}")

def main():
    """Main test function"""
    print("🚀 OnMemOS v3 Enhanced Features Test")
    print("=" * 60)
    print(f"Started at: {datetime.now()}")
    
    try:
        test_enhanced_session_creation()
        test_validation()
        
        print("\n✅ All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\nFinished at: {datetime.now()}")

if __name__ == "__main__":
    main()
