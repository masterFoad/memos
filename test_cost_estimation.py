#!/usr/bin/env python3
"""
Simple Test for Cost Estimation Functionality
Tests cost estimation without triggering background services
"""

import asyncio
import sys
from server.services.cost_estimation import cost_estimation_service
from server.models.session_templates import template_manager
from server.models.sessions import ResourceTier, StorageType
from server.models.users import UserType

async def test_cost_estimation():
    """Test cost estimation functionality"""
    print("🧪 Testing Cost Estimation Service")
    print("=" * 50)
    
    try:
        # 1. Test basic cost estimation
        print(f"\n1️⃣ Testing basic cost estimation")
        estimate = await cost_estimation_service.estimate_session_cost(
            resource_tier=ResourceTier.SMALL,
            storage_type=StorageType.EPHEMERAL,
            expected_duration_hours=2.0
        )
        print(f"✅ Basic estimate: ${estimate.total_cost:.4f} for 2 hours")
        print(f"   - Hourly rate: ${estimate.hourly_rate:.4f}")
        print(f"   - Confidence: {estimate.confidence}")
        
        # 2. Test template-based estimation
        print(f"\n2️⃣ Testing template-based estimation")
        template_estimate = await cost_estimation_service.estimate_template_cost(
            template_id="dev-python",
            duration_hours=4.0
        )
        print(f"✅ Template estimate: ${template_estimate.total_cost:.4f} for 4 hours")
        print(f"   - Template: dev-python")
        print(f"   - Confidence: {template_estimate.confidence}")
        
        # 3. Test storage cost calculation
        print(f"\n3️⃣ Testing storage cost calculation")
        storage_estimate = await cost_estimation_service.estimate_session_cost(
            resource_tier=ResourceTier.MEDIUM,
            storage_type=StorageType.GCS_FUSE,
            storage_size_gb=50,
            expected_duration_hours=1.0
        )
        print(f"✅ Storage estimate: ${storage_estimate.total_cost:.4f} for 1 hour")
        print(f"   - Storage cost: ${storage_estimate.storage_cost:.4f}")
        print(f"   - Compute cost: ${storage_estimate.estimated_cost:.4f}")
        
        # 4. Test GPU cost calculation
        print(f"\n4️⃣ Testing GPU cost calculation")
        gpu_estimate = await cost_estimation_service.estimate_session_cost(
            resource_tier=ResourceTier.LARGE,
            gpu_type="t4",
            expected_duration_hours=1.0
        )
        print(f"✅ GPU estimate: ${gpu_estimate.total_cost:.4f} for 1 hour")
        print(f"   - GPU cost: ${gpu_estimate.gpu_cost:.4f}")
        print(f"   - Compute cost: ${gpu_estimate.estimated_cost:.4f}")
        
        # 5. Test cost comparison
        print(f"\n5️⃣ Testing cost comparison")
        configs = [
            {"resource_tier": ResourceTier.SMALL, "storage_type": StorageType.EPHEMERAL},
            {"resource_tier": ResourceTier.MEDIUM, "storage_type": StorageType.EPHEMERAL},
            {"resource_tier": ResourceTier.LARGE, "storage_type": StorageType.EPHEMERAL}
        ]
        
        comparison = await cost_estimation_service.compare_costs(
            configurations=configs,
            duration_hours=1.0
        )
        
        print(f"✅ Cost comparison:")
        for i, est in enumerate(comparison):
            print(f"   - Config {i+1}: ${est.total_cost:.4f}")
        
        # 6. Test recommendations
        print(f"\n6️⃣ Testing cost recommendations")
        high_cost_estimate = await cost_estimation_service.estimate_session_cost(
            resource_tier=ResourceTier.XLARGE,
            gpu_type="a100",
            storage_type=StorageType.PERSISTENT_VOLUME,
            storage_size_gb=100,
            expected_duration_hours=8.0
        )
        print(f"✅ High-cost estimate: ${high_cost_estimate.total_cost:.4f} for 8 hours")
        print(f"   - Recommendations:")
        for rec in high_cost_estimate.recommendations:
            print(f"     • {rec}")
        
        print(f"\n🎉 Cost estimation test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    print("🚀 Starting Cost Estimation Test")
    print("=" * 60)
    
    try:
        success = await test_cost_estimation()
        if success:
            print("\n✅ Test completed successfully!")
        else:
            print("\n❌ Test failed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    finally:
        print("\n🏁 Exiting cleanly...")
        sys.exit(0)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)
