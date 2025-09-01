#!/usr/bin/env python3
"""
Basic OnMemOS SDK Usage Example
Demonstrates auto API key detection and basic operations
"""

import asyncio
import os
from pathlib import Path

# Add src to path for development
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from onmemos import (
    OnMemOSClient, 
    CreateSessionRequest, 
    ResourceTier, 
    StorageType,
    MountType
)


async def basic_example():
    """Basic SDK usage example"""
    print("🚀 OnMemOS SDK Basic Usage Example")
    print("=" * 50)
    
    try:
        # Create client with auto API key detection
        # Will automatically look for ONMEMOS_API_KEY in .env files
        async with OnMemOSClient() as client:
            print(f"✅ Connected to: {client.config.base_url}")
            print(f"🔑 API Key: {client.api_info['api_key']}")
            
            # Test connection
            if await client.test_connection():
                print("✅ API connection successful")
            else:
                print("❌ API connection failed")
                return
            
            # List available templates
            print("\n📋 Available Templates:")
            templates = await client.templates.list_templates()
            for template in templates.templates[:3]:  # Show first 3
                print(f"  • {template.name} ({template.category}) - ${template.estimated_cost_per_hour:.4f}/hour")
            
            # Create a session
            print("\n🔄 Creating Session...")
            session_request = CreateSessionRequest(
                template_id="dev-python",
                resource_tier=ResourceTier.MEDIUM,
                storage_type=StorageType.GCS_FUSE,
                storage_size_gb=20,
                ttl_minutes=120,
                env_vars={"PYTHONPATH": "/workspace"},
                labels={"purpose": "example", "sdk": "python"}
            )
            
            session = await client.sessions.create_session(session_request)
            print(f"✅ Created session: {session.session_id}")
            print(f"   Status: {session.status}")
            print(f"   Cost: ${session.cost_per_hour:.4f}/hour")
            print(f"   TTL: {session.ttl_minutes} minutes")
            
            # Wait for session to be ready
            print("\n⏳ Waiting for session to be ready...")
            # Note: This method needs to be implemented in SessionService
            # await client.sessions.wait_for_ready(session.session_id)
            
            # Mount storage
            print("\n💾 Mounting Storage...")
            mount_request = {
                "mount_type": MountType.GCS_BUCKET,
                "source_name": "my-dev-bucket",
                "mount_path": "/workspace",
                "read_only": False
            }
            
            # Note: This method needs to be implemented in StorageService
            # mount = await client.storage.mount_storage(session.session_id, mount_request)
            print("✅ Storage mounted (simulated)")
            
            # Get session info
            print("\n📊 Session Information:")
            session_info = await client.sessions.get_session(session.session_id)
            print(f"   Workspace ID: {session_info.workspace_id}")
            print(f"   Resource Tier: {session_info.resource_tier.value}")
            print(f"   Storage Type: {session_info.storage_type.value}")
            print(f"   GPU Type: {session_info.gpu_type.value}")
            
            # Get shell URL
            if session_info.k8s_namespace and session_info.pod_name:
                shell_url = client.get_shell_url(
                    session.session_id,
                    session_info.k8s_namespace,
                    session_info.pod_name
                )
                print(f"   Shell URL: {shell_url}")
            
            # Estimate costs
            print("\n💰 Cost Estimation:")
            estimate = await client.cost_estimation.estimate_template_cost(
                "dev-python", 
                duration_hours=2.0
            )
            print(f"   2-hour session: ${estimate.total_cost:.4f}")
            print(f"   Confidence: {estimate.confidence}")
            print(f"   Recommendations:")
            for rec in estimate.recommendations:
                print(f"     • {rec}")
            
            # List sessions
            print("\n📋 Your Sessions:")
            sessions = await client.sessions.list_sessions(limit=5)
            print(f"   Total: {sessions.total}")
            print(f"   Active: {len(sessions.active_sessions)}")
            print(f"   Stopped: {len(sessions.stopped_sessions)}")
            
            # Cleanup
            print("\n🧹 Cleaning up...")
            await client.sessions.delete_session(session.session_id)
            print("✅ Session deleted")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def quick_session_example():
    """Quick session creation example"""
    print("\n🚀 Quick Session Example")
    print("=" * 30)
    
    try:
        # Use convenience function
        session_info = await quick_session(
            template_id="dev-python",
            resource_tier=ResourceTier.SMALL,
            ttl_minutes=60
        )
        
        print(f"✅ Quick session created: {session_info['session_id']}")
        print(f"   Shell URL: {session_info['shell_url']}")
        print(f"   Session URL: {session_info['session_url']}")
        print(f"   Storage URL: {session_info['storage_url']}")
        
    except Exception as e:
        print(f"❌ Quick session error: {e}")


async def main():
    """Main example function"""
    print("🎯 OnMemOS SDK Examples")
    print("=" * 60)
    
    # Check environment
    api_key = os.getenv("ONMEMOS_API_KEY")
    if not api_key:
        print("⚠️  No ONMEMOS_API_KEY found in environment")
        print("   Create a .env file with:")
        print("   ONMEMOS_API_KEY=your_api_key_here")
        print("   ONMEMOS_BASE_URL=http://localhost:8080  # for local development")
        return
    
    print(f"🔑 API Key: {api_key[:8]}...")
    
    # Run examples
    await basic_example()
    await quick_session_example()
    
    print("\n🎉 Examples completed!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Examples interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
