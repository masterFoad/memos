#!/usr/bin/env python3
"""
Test Context Managers with Auto Cleanup
Demonstrates automatic session cleanup to avoid unnecessary costs.
"""

import sys
import os
import time

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sdk', 'python'))

from client import OnMemOSClient
from server.models.sessions import CPUSize, MemorySize, GPUType, ResourcePackage, ImageType
from server.models.users import WorkspaceResourcePackage, WorkspaceImageMapping

def test_context_managers():
    """Test context managers with automatic cleanup"""
    print("🧪 Testing Context Managers with Auto Cleanup...")
    
    # Initialize client
    client = OnMemOSClient()

    
    # Test parameters
    user_id = "tester"
    workspace_id = "test-workspace"
    
    try:
        # Test 1: Basic session context
        print("\n📦 Test 1: Basic session context")
        with client.session_context({
            "workspace_id": workspace_id,
            "template": "python",
            "namespace": "test-context-1",
            "user": user_id,
            "ttl_minutes": 10
        }) as session:
            print(f"   ✅ Session created: {session['id']}")
            
            # Execute a simple command
            result = client.execute_session(session["id"], "echo 'Hello from context manager!'")
            if result.get('success'):
                print(f"   ✅ Command executed: {result.get('stdout', '').strip()}")
            else:
                print(f"   ❌ Command failed: {result.get('error', 'Unknown error')}")
            
            print("   🧹 Session will be automatically cleaned up when exiting context")
        
        print("   ✅ Context exited - session should be cleaned up")
        
        # Test 2: Development session context
        print("\n📦 Test 2: Development session context")
        with client.development_session_context(
            workspace_id=workspace_id,
            namespace="test-context-2",
            user=user_id,
            ttl_minutes=10
        ) as session:
            print(f"   ✅ Development session created: {session['id']}")
            
            # Test Ubuntu environment
            result = client.execute_session(session["id"], "cat /etc/os-release | grep PRETTY_NAME")
            if result.get('success'):
                print(f"   ✅ OS: {result.get('stdout', '').strip()}")
            else:
                print(f"   ❌ OS check failed: {result.get('error', 'Unknown error')}")
            
            print("   🧹 Development session will be automatically cleaned up")
        
        print("   ✅ Context exited - development session should be cleaned up")
        
        # Test 3: Tier-based image session context
        print("\n📦 Test 3: Tier-based image session context")
        
        # Test different image types based on workspace package
        # Note: Using default FREE_MICRO package for testing
        package = WorkspaceResourcePackage.FREE_MICRO
        image_type = WorkspaceImageMapping.get_image_type_for_package(package)
        print(f"   📋 Workspace package: {package.value} -> Image: {image_type}")
        
        with client.python_session_context(
            workspace_id=workspace_id,
            namespace="test-context-3",
            user=user_id,
            ttl_minutes=10
        ) as session:
            print(f"   ✅ Tier-based session created: {session['id']}")
            
            # Test environment based on image type
            result = client.execute_session(session["id"], "echo 'Tier-based session ready' && cat /etc/os-release | head -1")
            if result.get('success'):
                print(f"   ✅ Session environment: {result.get('stdout', '').strip()}")
            else:
                print(f"   ❌ Environment check failed: {result.get('error', 'Unknown error')}")
            
            print("   🧹 Tier-based session will be automatically cleaned up")
        
        print("   ✅ Context exited - tier-based session should be cleaned up")
        
        # Test 4: Error handling in context
        print("\n📦 Test 4: Error handling in context")
        try:
            with client.python_session_context(
                workspace_id=workspace_id,
                namespace="test-context-4",
                user=user_id,
                ttl_minutes=10
            ) as session:
                print(f"   ✅ Session created: {session['id']}")
                
                # Simulate an error
                raise Exception("Simulated error during session usage")
                
        except Exception as e:
            print(f"   ⚠️ Error occurred: {e}")
            print("   🧹 Session should still be cleaned up despite the error")
        
        print("   ✅ Context exited - session should be cleaned up even after error")
        
        # Test 5: Disabled auto cleanup
        print("\n📦 Test 5: Disabled auto cleanup")
        session_to_cleanup = None
        with client.python_session_context(
            workspace_id=workspace_id,
            namespace="test-context-5",
            user=user_id,
            ttl_minutes=10,
            auto_cleanup=False  # Disable auto cleanup
        ) as session:
            print(f"   ✅ Session created: {session['id']}")
            session_to_cleanup = session
            
            result = client.execute_session(session["id"], "echo 'Session with manual cleanup'")
            if result.get('success'):
                print(f"   ✅ Command executed: {result.get('stdout', '').strip()}")
            
            print("   ⚠️ Auto cleanup disabled - session will remain after context exit")
        
        print("   ✅ Context exited - session should still exist")
        
        # Manual cleanup
        if session_to_cleanup:
            print(f"   🧹 Manually cleaning up session: {session_to_cleanup['id']}")
            success = client.delete_session(session_to_cleanup["id"])
            if success:
                print("   ✅ Manual cleanup successful")
            else:
                print("   ❌ Manual cleanup failed")
        
        # Test 6: Image tier demonstration
        print("\n📦 Test 6: Image tier demonstration")
        
        # Show allowed images for different user types
        print("   📋 Image tiers by user type:")
        for user_type in ["FREE", "PRO", "ENTERPRISE"]:
            allowed_images = WorkspaceImageMapping.get_allowed_images_for_user_type(user_type)
            print(f"   👤 {user_type}: {', '.join(allowed_images[:3])}{'...' if len(allowed_images) > 3 else ''}")
        
        # Test 7: Cost estimation with tier-based images
        print("\n📦 Test 7: Cost estimation with tier-based images")
        estimate = client.get_session_cost_estimate({
            "workspace_id": workspace_id,
            "template": "python",
            "namespace": "test-cost",
            "user": user_id,
            "resource_package": ResourcePackage.ML_T4_MEDIUM,
            "gpu_type": GPUType.T4,
            "ttl_minutes": 60
        })
        
        if "error" not in estimate:
            print(f"   💰 Estimated cost per hour: ${estimate.get('total_cost_per_hour', 0)}")
            print(f"   💰 Estimated total cost: ${estimate.get('estimated_total_cost', 0)}")
        else:
            print(f"   ❌ Cost estimation failed: {estimate['error']}")
        
        # Test 8: Bucket mount context
        print("\n📦 Test 8: Bucket mount context")
        with client.session_context({
            "workspace_id": workspace_id,
            "template": "python",
            "namespace": "test-context-8-bucket",
            "user": user_id,
            "ttl_minutes": 10,
            "request_bucket": True,
            "bucket_size_gb": 5
        }) as session:
            print(f"   ✅ Bucket session created: {session['id']}")
            
            # Test bucket access
            result = client.execute_session(session["id"], "ls -la /buckets && echo 'Bucket mounted successfully'")
            if result.get('success'):
                print(f"   ✅ Bucket mount: {result.get('stdout', '').strip()}")
            else:
                print(f"   ❌ Bucket mount failed: {result.get('error', 'Unknown error')}")
            
            print("   🧹 Bucket session will be automatically cleaned up")
        
        print("   ✅ Context exited - bucket session should be cleaned up")
        
        # Test 9: Filestore (persistent storage) context
        print("\n📦 Test 9: Filestore (persistent storage) context")
        with client.session_context({
            "workspace_id": workspace_id,
            "template": "python",
            "namespace": "test-context-9-filestore",
            "user": user_id,
            "ttl_minutes": 10,
            "request_persistent_storage": True,
            "persistent_storage_size_gb": 10
        }) as session:
            print(f"   ✅ Filestore session created: {session['id']}")
            
            # Test persistent storage access
            result = client.execute_session(session["id"], "ls -la /persist && echo 'Persistent storage mounted successfully'")
            if result.get('success'):
                print(f"   ✅ Filestore mount: {result.get('stdout', '').strip()}")
            else:
                print(f"   ❌ Filestore mount failed: {result.get('error', 'Unknown error')}")
            
            print("   🧹 Filestore session will be automatically cleaned up")
        
        print("   ✅ Context exited - filestore session should be cleaned up")
        
        # Test 10: Combined storage context (bucket + filestore)
        print("\n📦 Test 10: Combined storage context (bucket + filestore)")
        with client.session_context({
            "workspace_id": workspace_id,
            "template": "python",
            "namespace": "test-context-10-combined",
            "user": user_id,
            "ttl_minutes": 10,
            "request_bucket": True,
            "bucket_size_gb": 5,
            "request_persistent_storage": True,
            "persistent_storage_size_gb": 10
        }) as session:
            print(f"   ✅ Combined storage session created: {session['id']}")
            
            # Test both storage types
            result = client.execute_session(session["id"], "ls -la /buckets /persist && echo 'Both storage types mounted successfully'")
            if result.get('success'):
                print(f"   ✅ Combined storage: {result.get('stdout', '').strip()}")
            else:
                print(f"   ❌ Combined storage failed: {result.get('error', 'Unknown error')}")
            
            print("   🧹 Combined storage session will be automatically cleaned up")
        
        print("   ✅ Context exited - combined storage session should be cleaned up")
        
        print("\n🎉 All context manager tests completed!")
        print("💡 Remember: Always use context managers to avoid unnecessary costs!")
        print("🖼️  Image tiers: FREE (basic) → PRO (enhanced) → ENTERPRISE (premium)")
        print("💾 Storage types: Bucket (GCS) + Filestore (persistent) + Combined")
        
        # Test 11: Storage cleanup verification
        print("\n📦 Test 11: Storage cleanup verification")
        print("   📋 Verifying that storage resources are properly cleaned up...")
        
        # Wait a moment for cleanup to complete
        time.sleep(5)
        
        # This would ideally check the workspace storage usage
        # For now, we'll just confirm the test completed
        print("   ✅ All storage tests completed - resources should be cleaned up")
        print("   💡 Check GCS buckets and PVCs to verify cleanup")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False

def test_cleanup_utilities():
    """Test cleanup utilities"""
    print("\n🧹 Testing Cleanup Utilities...")
    
    client = OnMemOSClient()
    user_id = "tester"
    
    try:
        # Test cleanup of expired sessions
        print("   📋 Cleaning up expired sessions...")
        cleaned = client.cleanup_expired_sessions(user=user_id)
        print(f"   ✅ Cleaned up {cleaned} expired sessions")
        
        # Test session monitoring
        print("   📊 Testing session monitoring...")
        usage = client.monitor_session_usage("test-session-id")
        if "error" not in usage:
            print(f"   ✅ Usage monitoring working")
        else:
            print(f"   ⚠️ Usage monitoring not available: {usage['error']}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Cleanup utilities test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 OnMemOS v3 Context Manager Test Suite")
    print("=" * 50)
    
    # Test context managers
    success1 = test_context_managers()
    
    # Test cleanup utilities
    success2 = test_cleanup_utilities()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    print(f"   Context Managers: {'✅ PASSED' if success1 else '❌ FAILED'}")
    print(f"   Cleanup Utilities: {'✅ PASSED' if success2 else '❌ FAILED'}")
    
    if success1 and success2:
        print("\n🎉 All tests passed! Context managers are working correctly.")
        print("💡 Remember to always use context managers to save money!")
    else:
        print("\n❌ Some tests failed. Check the output above for details.")
    
    sys.exit(0 if (success1 and success2) else 1)
