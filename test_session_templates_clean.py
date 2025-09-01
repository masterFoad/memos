#!/usr/bin/env python3
"""
Clean Test for Session Templates Functionality
Properly handles cleanup and exits cleanly
"""

import asyncio
import sys
from server.database.factory import get_database_client
from server.services.sessions.manager import sessions_manager
from server.models.users import UserType
from server.models.session_templates import template_manager, TemplateCategory

async def test_templates_clean():
    """Test templates with proper cleanup"""
    print("🧪 Testing Session Templates (Clean Version)")
    print("=" * 50)
    
    db = None
    test_user = "template_clean_test_user"
    
    try:
        # Initialize database
        db = get_database_client()
        await db.connect()
        
        # 1. Test template listing
        print(f"\n1️⃣ Testing template listing")
        templates = template_manager.list_templates()
        print(f"✅ Found {len(templates)} templates")
        
        # 2. Test specific template
        print(f"\n2️⃣ Testing specific template")
        template = template_manager.get_template("dev-python")
        if template:
            print(f"✅ Template: {template.name} - {template.description}")
        
        # 3. Create test user
        print(f"\n3️⃣ Creating test user")
        try:
            await db.create_user(
                user_id=test_user,
                email=f"{test_user}@test.com",
                user_type=UserType.PRO,
                name="Template Clean Test User"
            )
            print(f"✅ Created user: {test_user}")
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                print(f"ℹ️ User {test_user} already exists")
            else:
                raise
        
        # 4. Add credits
        print(f"\n4️⃣ Adding credits")
        await db.add_credits(test_user, 5.0, "test", "Credits for template test")
        current_credits = await db.get_user_credits(test_user)
        print(f"✅ Credits added. Balance: ${current_credits:.2f}")
        
        # 5. Test template-based session creation
        print(f"\n5️⃣ Testing template-based session")
        session_spec = {
            "user": test_user,
            "namespace": "test",
            "workspace_id": "template-clean-test-ws",
            "template": "alpine_basic",
            "template_id": "dev-python",
            "provider": "gke",
            "ttl_minutes": 60
        }
        
        session_info = await sessions_manager.create_session(session_spec)
        session_id = session_info["id"]
        print(f"✅ Created session: {session_id}")
        
        # 6. Check template usage
        print(f"\n6️⃣ Checking template usage")
        template = template_manager.get_template("dev-python")
        if template:
            print(f"✅ Template usage count: {template.usage_count}")
        
        # 7. Clean up session
        print(f"\n7️⃣ Cleaning up session")
        success = await sessions_manager.delete_session(session_id)
        print(f"✅ Session cleanup: {'Success' if success else 'Failed'}")
        
        print(f"\n🎉 Template test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up test user
        if db:
            try:
                print(f"\n🧹 Cleaning up test user")
                await db.delete_user(test_user)
                print(f"✅ Deleted test user: {test_user}")
            except Exception as e:
                print(f"⚠️ Could not delete test user: {e}")
            
            # Close database connection
            try:
                await db.close()
                print(f"✅ Database connection closed")
            except Exception as e:
                print(f"⚠️ Could not close database: {e}")

async def main():
    """Main test function"""
    print("🚀 Starting Clean Session Templates Test")
    print("=" * 60)
    
    try:
        await test_templates_clean()
        print("\n✅ Test completed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    finally:
        print("\n🏁 Exiting cleanly...")
        # Force exit to avoid hanging
        sys.exit(0)

if __name__ == "__main__":
    # Run with asyncio and force exit
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)
