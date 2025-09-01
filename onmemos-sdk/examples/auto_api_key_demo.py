#!/usr/bin/env python3
"""
Auto API Key Detection Demo
Demonstrates how the SDK automatically detects API keys from .env files
"""

import asyncio
import os
from pathlib import Path

# Add src to path for development
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from onmemos import OnMemOSClient, get_api_key, get_base_url


def create_env_file():
    """Create a sample .env file for testing"""
    env_content = """# OnMemOS SDK Configuration
ONMEMOS_API_KEY=your_api_key_here
ONMEMOS_BASE_URL=http://localhost:8080
ONMEMOS_TIMEOUT=60.0
"""
    
    env_file = Path.cwd() / ".env"
    with open(env_file, "w") as f:
        f.write(env_content)
    
    print(f"✅ Created .env file: {env_file}")
    return env_file


def cleanup_env_file(env_file):
    """Clean up the test .env file"""
    if env_file.exists():
        env_file.unlink()
        print(f"🧹 Cleaned up .env file: {env_file}")


async def demo_auto_detection():
    """Demonstrate auto API key detection"""
    print("🔑 Auto API Key Detection Demo")
    print("=" * 40)
    
    # Create test .env file
    env_file = create_env_file()
    
    try:
        # Test auto-detection functions
        print("\n📋 Testing Auto-Detection Functions:")
        print("-" * 30)
        
        api_key = get_api_key()
        base_url = get_base_url()
        
        print(f"🔑 Detected API Key: {api_key[:8]}..." if api_key else "❌ No API key found")
        print(f"🌐 Detected Base URL: {base_url}")
        
        # Test client creation with auto-detection
        print("\n🚀 Testing Client Creation:")
        print("-" * 30)
        
        try:
            # This should work with the .env file
            client = OnMemOSClient()
            print(f"✅ Client created successfully!")
            print(f"   Base URL: {client.config.base_url}")
            print(f"   API Key: {client.api_info['api_key']}")
            print(f"   Timeout: {client.config.timeout}s")
            
            # Test connection (will fail without real API key, but shows the setup works)
            print(f"\n🔌 Testing Connection:")
            print("-" * 30)
            
            is_connected = await client.test_connection()
            if is_connected:
                print("✅ Connection successful!")
            else:
                print("⚠️  Connection failed (expected without real API key)")
                print("   This is normal - the SDK structure is working correctly")
            
        except Exception as e:
            print(f"❌ Client creation failed: {e}")
        
        # Test with explicit parameters (overrides .env)
        print(f"\n🎯 Testing with Explicit Parameters:")
        print("-" * 30)
        
        explicit_client = OnMemOSClient(
            api_key="explicit_key_123",
            base_url="https://explicit-api.example.com"
        )
        
        print(f"✅ Explicit client created!")
        print(f"   Base URL: {explicit_client.config.base_url}")
        print(f"   API Key: {explicit_client.api_info['api_key']}")
        
        # Test configuration priority
        print(f"\n📊 Configuration Priority Test:")
        print("-" * 30)
        print("Priority order:")
        print("1. Explicit parameters (highest)")
        print("2. Environment variables")
        print("3. Default values (lowest)")
        
        # Show how environment variables override defaults
        print(f"\n🔧 Environment Override Test:")
        print("-" * 30)
        
        # Set environment variable
        os.environ["ONMEMOS_BASE_URL"] = "https://env-override.example.com"
        
        # Re-import to pick up new environment variable
        from onmemos.core.config import get_base_url as get_base_url_fresh
        env_override_url = get_base_url_fresh()
        
        print(f"Environment override: {env_override_url}")
        print("✅ Environment variables take precedence over defaults")
        
    finally:
        # Clean up
        cleanup_env_file(env_file)


async def demo_error_handling():
    """Demonstrate error handling when no API key is found"""
    print(f"\n🚨 Error Handling Demo")
    print("=" * 40)
    
    # Temporarily remove API key from environment
    original_api_key = os.environ.get("ONMEMOS_API_KEY")
    if "ONMEMOS_API_KEY" in os.environ:
        del os.environ["ONMEMOS_API_KEY"]
    
    try:
        print("Testing client creation without API key...")
        
        # This should raise a ConfigurationError
        try:
            client = OnMemOSClient()
            print("❌ Expected error was not raised")
        except Exception as e:
            print(f"✅ Expected error caught: {type(e).__name__}: {e}")
            print("   This demonstrates proper error handling")
        
    finally:
        # Restore original API key
        if original_api_key:
            os.environ["ONMEMOS_API_KEY"] = original_api_key


async def main():
    """Main demo function"""
    print("🎯 OnMemOS SDK Auto API Key Detection Demo")
    print("=" * 60)
    
    await demo_auto_detection()
    await demo_error_handling()
    
    print(f"\n🎉 Demo completed!")
    print("\n📝 Key Features Demonstrated:")
    print("• Auto-detection of API keys from .env files")
    print("• Environment variable overrides")
    print("• Explicit parameter overrides")
    print("• Proper error handling")
    print("• Configuration priority system")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()

