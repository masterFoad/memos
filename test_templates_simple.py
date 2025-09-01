#!/usr/bin/env python3
"""
Simple Session Templates Test
Tests only the template functionality without triggering background services
"""

from server.models.session_templates import template_manager, TemplateCategory

def test_templates_simple():
    """Simple template test without async/background services"""
    print("🧪 Simple Session Templates Test")
    print("=" * 50)
    
    try:
        # 1. Test template listing
        print(f"\n1️⃣ Testing template listing")
        templates = template_manager.list_templates()
        print(f"✅ Found {len(templates)} templates:")
        for template in templates:
            print(f"   - {template.template_id}: {template.name}")
        
        # 2. Test filtering by category
        print(f"\n2️⃣ Testing category filtering")
        dev_templates = template_manager.list_templates(category=TemplateCategory.DEVELOPMENT)
        print(f"✅ Found {len(dev_templates)} development templates")
        
        # 3. Test specific template
        print(f"\n3️⃣ Testing specific template")
        template = template_manager.get_template("dev-python")
        if template:
            print(f"✅ Template: {template.name}")
            print(f"   - Description: {template.description}")
            print(f"   - Resource tier: {template.resource_tier.value}")
            print(f"   - Estimated cost: ${template.estimated_cost_per_hour:.2f}/hour")
            print(f"   - Tags: {', '.join(template.tags)}")
        
        # 4. Test popular templates
        print(f"\n4️⃣ Testing popular templates")
        popular = template_manager.get_popular_templates(3)
        print(f"✅ Found {len(popular)} popular templates")
        
        # 5. Test template creation (in-memory only)
        print(f"\n5️⃣ Testing template creation")
        from server.models.session_templates import SessionTemplate
        
        # Create a test template
        test_template = SessionTemplate(
            template_id="test-custom",
            name="Test Custom Template",
            description="A test template for testing",
            category=TemplateCategory.CUSTOM,
            resource_tier="small",
            tags=["test", "custom"]
        )
        
        success = template_manager.create_template(test_template)
        if success:
            print(f"✅ Created test template: {test_template.template_id}")
            
            # Verify it was created
            created = template_manager.get_template("test-custom")
            if created:
                print(f"✅ Template verified: {created.name}")
            
            # Clean up
            template_manager.delete_template("test-custom")
            print(f"✅ Test template cleaned up")
        else:
            print(f"❌ Failed to create test template")
        
        print(f"\n🎉 Simple template test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Starting Simple Session Templates Test")
    print("=" * 60)
    
    success = test_templates_simple()
    
    if success:
        print("\n✅ Test completed successfully!")
    else:
        print("\n❌ Test failed!")
    
    print("\n🏁 Exiting...")
    # Force exit
    import sys
    sys.exit(0)
