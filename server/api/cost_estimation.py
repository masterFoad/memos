"""
Cost Estimation API - Session cost prediction endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from server.core.logging import get_api_logger
from server.core.security import require_passport
from server.services.cost_estimation import cost_estimation_service, CostEstimate
from server.models.sessions import ResourceTier, StorageType
from server.models.users import UserType

logger = get_api_logger()
router = APIRouter(prefix="/v1/cost-estimation", tags=["cost-estimation"])


class CostEstimationRequest(BaseModel):
    """Request model for cost estimation"""
    template_id: Optional[str] = None
    resource_tier: Optional[str] = None
    storage_type: Optional[str] = None
    storage_size_gb: int = 0
    gpu_type: str = "none"
    expected_duration_hours: float = 1.0
    user_type: Optional[str] = None


class CostComparisonRequest(BaseModel):
    """Request model for cost comparison"""
    configurations: List[Dict[str, Any]]
    duration_hours: float = 1.0


@router.post("/estimate")
async def estimate_session_cost(
    request: CostEstimationRequest,
    user_info: dict = Depends(require_passport)
):
    """Estimate cost for a session configuration"""
    try:
        # Parse enums
        resource_tier = None
        if request.resource_tier:
            try:
                resource_tier = ResourceTier(request.resource_tier)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid resource tier: {request.resource_tier}")
        
        storage_type = None
        if request.storage_type:
            try:
                storage_type = StorageType(request.storage_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid storage type: {request.storage_type}")
        
        user_type = None
        if request.user_type:
            try:
                user_type = UserType(request.user_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid user type: {request.user_type}")
        
        # Get cost estimate
        estimate = await cost_estimation_service.estimate_session_cost(
            template_id=request.template_id,
            resource_tier=resource_tier,
            storage_type=storage_type,
            storage_size_gb=request.storage_size_gb,
            gpu_type=request.gpu_type,
            expected_duration_hours=request.expected_duration_hours,
            user_type=user_type
        )
        
        # Convert to dict for response
        result = {
            "estimated_hours": estimate.estimated_hours,
            "estimated_cost": estimate.estimated_cost,
            "hourly_rate": estimate.hourly_rate,
            "storage_cost": estimate.storage_cost,
            "gpu_cost": estimate.gpu_cost,
            "total_cost": estimate.total_cost,
            "confidence": estimate.confidence,
            "breakdown": estimate.breakdown,
            "recommendations": estimate.recommendations
        }
        
        logger.info(f"Cost estimation for user {user_info.get('user_id')}: ${estimate.total_cost:.4f}")
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error estimating session cost: {e}")
        raise HTTPException(status_code=500, detail="Failed to estimate session cost")


@router.get("/template/{template_id}")
async def estimate_template_cost(
    template_id: str,
    duration_hours: float = Query(1.0, description="Expected duration in hours"),
    user_info: dict = Depends(require_passport)
):
    """Estimate cost for a specific template"""
    try:
        estimate = await cost_estimation_service.estimate_template_cost(
            template_id=template_id,
            duration_hours=duration_hours
        )
        
        result = {
            "template_id": template_id,
            "estimated_hours": estimate.estimated_hours,
            "estimated_cost": estimate.estimated_cost,
            "hourly_rate": estimate.hourly_rate,
            "storage_cost": estimate.storage_cost,
            "gpu_cost": estimate.gpu_cost,
            "total_cost": estimate.total_cost,
            "confidence": estimate.confidence,
            "breakdown": estimate.breakdown,
            "recommendations": estimate.recommendations
        }
        
        logger.info(f"Template cost estimation for {template_id}: ${estimate.total_cost:.4f}")
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error estimating template cost: {e}")
        raise HTTPException(status_code=500, detail="Failed to estimate template cost")


@router.post("/compare")
async def compare_costs(
    request: CostComparisonRequest,
    user_info: dict = Depends(require_passport)
):
    """Compare costs between different configurations"""
    try:
        estimates = await cost_estimation_service.compare_costs(
            configurations=request.configurations,
            duration_hours=request.duration_hours
        )
        
        # Convert to list of dicts for response
        results = []
        for i, estimate in enumerate(estimates):
            result = {
                "configuration_index": i,
                "estimated_hours": estimate.estimated_hours,
                "estimated_cost": estimate.estimated_cost,
                "hourly_rate": estimate.hourly_rate,
                "storage_cost": estimate.storage_cost,
                "gpu_cost": estimate.gpu_cost,
                "total_cost": estimate.total_cost,
                "confidence": estimate.confidence,
                "breakdown": estimate.breakdown,
                "recommendations": estimate.recommendations
            }
            results.append(result)
        
        logger.info(f"Cost comparison for user {user_info.get('user_id')}: {len(results)} configurations")
        return {
            "comparison": results,
            "duration_hours": request.duration_hours,
            "best_option": results[0] if results else None,
            "total_configurations": len(results)
        }
        
    except Exception as e:
        logger.error(f"Error comparing costs: {e}")
        raise HTTPException(status_code=500, detail="Failed to compare costs")


@router.get("/rates")
async def get_cost_rates():
    """Get current cost rates for different resources"""
    try:
        rates = {
            "compute": {
                "small": "$0.05/hour",
                "medium": "$0.10/hour", 
                "large": "$0.20/hour",
                "xlarge": "$0.40/hour"
            },
            "storage": {
                "ephemeral": "Free",
                "gcs_fuse": "$0.02/GB/hour",
                "persistent_volume": "$0.03/GB/hour"
            },
            "gpu": {
                "none": "Free",
                "t4": "$0.15/hour",
                "v100": "$0.50/hour",
                "a100": "$1.20/hour",
                "h100": "$3.00/hour",
                "l4": "$0.25/hour"
            },
            "discounts": {
                "enterprise": "20% off base rates",
                "admin": "Free for admin users"
            }
        }
        
        return rates
        
    except Exception as e:
        logger.error(f"Error getting cost rates: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cost rates")


@router.get("/calculator")
async def cost_calculator(
    resource_tier: str = Query(..., description="Resource tier (small, medium, large, xlarge)"),
    storage_type: str = Query("ephemeral", description="Storage type (ephemeral, gcs_fuse, persistent_volume)"),
    storage_size_gb: int = Query(0, description="Storage size in GB"),
    gpu_type: str = Query("none", description="GPU type (none, t4, v100, a100, h100, l4)"),
    duration_hours: float = Query(1.0, description="Duration in hours"),
    user_type: str = Query("free", description="User type (free, pro, enterprise, admin)")
):
    """Simple cost calculator endpoint"""
    try:
        # Parse enums
        try:
            resource_tier_enum = ResourceTier(resource_tier)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid resource tier: {resource_tier}")
        
        try:
            storage_type_enum = StorageType(storage_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid storage type: {storage_type}")
        
        try:
            user_type_enum = UserType(user_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid user type: {user_type}")
        
        # Get cost estimate
        estimate = await cost_estimation_service.estimate_session_cost(
            resource_tier=resource_tier_enum,
            storage_type=storage_type_enum,
            storage_size_gb=storage_size_gb,
            gpu_type=gpu_type,
            expected_duration_hours=duration_hours,
            user_type=user_type_enum
        )
        
        return {
            "configuration": {
                "resource_tier": resource_tier,
                "storage_type": storage_type,
                "storage_size_gb": storage_size_gb,
                "gpu_type": gpu_type,
                "duration_hours": duration_hours,
                "user_type": user_type
            },
            "cost_estimate": {
                "total_cost": estimate.total_cost,
                "hourly_rate": estimate.hourly_rate,
                "storage_cost": estimate.storage_cost,
                "gpu_cost": estimate.gpu_cost,
                "confidence": estimate.confidence
            },
            "recommendations": estimate.recommendations
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in cost calculator: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate cost")
