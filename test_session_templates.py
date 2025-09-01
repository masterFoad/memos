#!/usr/bin/env python3
"""
Test Session Templates Functionality
Tests template management and template-based session creation
"""

import asyncio
import json
import time
from datetime import datetime

from server.database.factory import get_database_client
from server.services.sessions.manager import sessions_manager
from server.models.users import UserType
from server.models.session_templates import template_manager, TemplateCategory

async def test_template_management():
    """Test template management functionality"""
    print("🧪 Testing Session Template Management")
    print("=" * 50)
    
    try:
        # 1. Test listing templates
        print(f"\n1️⃣ Listing all templates")
        templates = template_manager.list_templates()
        print(f"✅ Found {len(templates)} templates:")
        for template in templates:
            print(f"   - {template.template_id}: {template.name} ({template.category.value})")
        
        # 2. Test filtering by category
        print(f"\n2️⃣ Filtering by category")
        dev_templates = template_manager.list_templates(category=TemplateCategory.DEVELOPMENT)
        print(f"✅ Found {len(dev_templates)} development templates:")
        for template in dev_templates:
            print(f"   - {template.template_id}: {template.name}")
        
        # 3. Test filtering by user type
        print(f"\n3️⃣ Filtering by user type")
        pro_templates = template_manager.list_templates(user_type=UserType.PRO)
        print(f"✅ Found {len(pro_templates)} PRO templates:")
        for template in pro_templates:
            print(f"   - {template.template_id}: {template.name}")
        
        # 4. Test getting specific template
        print(f"\n4️⃣ Getting specific template")
        template = template_manager.get_template("dev-python")
        if template:
            print(f"✅ Found template: {template.name}")
            print(f"   - Description: {template.description}")
            print(f"   - Resource tier: {template.resource_tier.value}")
            print(f"   - Estimated cost: ${template.estimated_cost_per_hour:.2f}/hour")
            print(f"   - Tags: {', '.join(template.tags)}")
        else:
            print("❌ Template not found")
        
        # 5. Test popular templates
        print(f"\n5️⃣ Getting popular templates")
        popular = template_manager.get_popular_templates(3)
        print(f"✅ Found {len(popular)} popular templates:")
        for template in popular:
            print(f"   - {template.template_id}: {template.usage_count} uses")
        
        print(f"\n🎉 Template management test completed successfully!")
        
    except Exception as e:
        print(f"❌ Template management test failed: {e}")
        import traceback
        traceback.print_exc()

async def test_template_based_session():
    """Test template-based session creation"""
    print("\n🧪 Testing Template-Based Session Creation")
    print("=" * 50)
    
    # Initialize database
    db = get_database_client()
    await db.connect()
    
    # Test user
    test_user = "template_test_user"
    
    try:
        # 1. Create test user
        print(f"\n1️⃣ Creating test user: {test_user}")
        try:
            await db.create_user(
                user_id=test_user,
                email=f"{test_user}@test.com",
                user_type=UserType.PRO,
                name="Template Test User"
            )
            print(f"✅ Created user: {test_user}")
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                print(f"ℹ️ User {test_user} already exists")
            else:
                raise
        
        # 2. Add credits
        print(f"\n2️⃣ Adding credits")
        await db.add_credits(test_user, 10.0, "test", "Credits for template test")
        current_credits = await db.get_user_credits(test_user)
        print(f"✅ Added credits. Current balance: ${current_credits:.2f}")
        
        # 3. Create session using template
        print(f"\n3️⃣ Creating session using template")
        session_spec = {
            "user": test_user,
            "namespace": "test",
            "workspace_id": "template-test-ws",
            "template": "alpine_basic",  # Required field
            "template_id": "dev-python",  # Use template
            "provider": "gke",
            "ttl_minutes": 60
        }
        
        session_info = await sessions_manager.create_session(session_spec)
        session_id = session_info["id"]
        print(f"✅ Created session: {session_id}")
        print(f"   - Namespace: {session_info.get('k8s_namespace')}")
        print(f"   - Pod: {session_info.get('pod_name')}")
        print(f"   - WebSocket URL: {session_info.get('websocket')}")
        
        # 4. Check template usage was incremented
        print(f"\n4️⃣ Checking template usage")
        template = template_manager.get_template("dev-python")
        if template:
            print(f"✅ Template usage count: {template.usage_count}")
        
        # 5. Clean up session
        print(f"\n5️⃣ Cleaning up session")
        success = await sessions_manager.delete_session(session_id)
        print(f"✅ Session cleanup: {'Success' if success else 'Failed'}")
        
        print(f"\n🎉 Template-based session test completed successfully!")
        
    except Exception as e:
        print(f"❌ Template-based session test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up test user
        try:
            print(f"\n🧹 Cleaning up test user")
            await db.delete_user(test_user)
            print(f"✅ Deleted test user: {test_user}")
        except Exception as e:
            print(f"⚠️ Could not delete test user: {e}")

async def test_template_api():
    """Test template API endpoints"""
    print("\n🧪 Testing Template API Endpoints")
    print("=" * 50)
    
    try:
        # This would test the actual API endpoints
        # For now, we'll just verify the template manager works
        print(f"\n1️⃣ Testing template listing")
        templates = template_manager.list_templates()
        print(f"✅ API would return {len(templates)} templates")
        
        print(f"\n2️⃣ Testing template categories")
        categories = [cat.value for cat in TemplateCategory]
        print(f"✅ Available categories: {', '.join(categories)}")
        
        print(f"\n3️⃣ Testing template filtering")
        python_templates = template_manager.list_templates(tags=["python"])
        print(f"✅ Found {len(python_templates)} Python templates")
        
        print(f"\n🎉 Template API test completed successfully!")
        
    except Exception as e:
        print(f"❌ Template API test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Starting Session Templates Tests")
    print("=" * 60)
    
    # Run tests
    asyncio.run(test_template_management())
    asyncio.run(test_template_based_session())
    asyncio.run(test_template_api())
    
    print("\n✅ All session template tests completed!")
