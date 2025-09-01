"""
Cost estimation service for OnMemOS SDK
"""

from typing import Optional, List, Dict, Any
from ..core.http import HTTPClient
from ..models.base import CostEstimate
from ..core.exceptions import CostEstimationError


class CostEstimationService:
    """Cost estimation service"""
    
    def __init__(self, http_client: HTTPClient):
        self.http_client = http_client
    
    async def estimate_template_cost(
        self,
        template_id: str,
        duration_hours: float = 1.0
    ) -> CostEstimate:
        """Estimate cost for a specific template"""
        try:
            params = {"duration_hours": duration_hours}
            response = await self.http_client.get(f"/v1/cost-estimation/template/{template_id}", params=params)
            return CostEstimate(**response)
        except Exception as e:
            raise CostEstimationError(f"Failed to estimate template cost: {e}")
    
    async def estimate_session_cost(
        self,
        template_id: Optional[str] = None,
        resource_tier: Optional[str] = None,
        storage_type: Optional[str] = None,
        storage_size_gb: int = 0,
        gpu_type: str = "none",
        duration_hours: float = 1.0
    ) -> CostEstimate:
        """Estimate cost for a session configuration"""
        try:
            data = {
                "duration_hours": duration_hours,
                "storage_size_gb": storage_size_gb,
                "gpu_type": gpu_type
            }
            if template_id:
                data["template_id"] = template_id
            if resource_tier:
                data["resource_tier"] = resource_tier
            if storage_type:
                data["storage_type"] = storage_type
            
            response = await self.http_client.post("/v1/cost-estimation/estimate", json=data)
            return CostEstimate(**response)
        except Exception as e:
            raise CostEstimationError(f"Failed to estimate session cost: {e}")
    
    async def compare_costs(
        self,
        configurations: List[Dict[str, Any]],
        duration_hours: float = 1.0
    ) -> List[CostEstimate]:
        """Compare costs between different configurations"""
        try:
            data = {
                "configurations": configurations,
                "duration_hours": duration_hours
            }
            response = await self.http_client.post("/v1/cost-estimation/compare", json=data)
            return [CostEstimate(**est) for est in response.get("comparison", [])]
        except Exception as e:
            raise CostEstimationError(f"Failed to compare costs: {e}")
    
    async def get_cost_rates(self) -> Dict[str, Any]:
        """Get current cost rates"""
        try:
            response = await self.http_client.get("/v1/cost-estimation/rates")
            return response
        except Exception as e:
            raise CostEstimationError(f"Failed to get cost rates: {e}")
    
    async def calculate_cost(
        self,
        resource_tier: str,
        storage_type: str,
        storage_size_gb: int,
        gpu_type: str,
        duration_hours: float
    ) -> Dict[str, Any]:
        """Calculate cost using calculator endpoint"""
        try:
            params = {
                "resource_tier": resource_tier,
                "storage_type": storage_type,
                "storage_size_gb": storage_size_gb,
                "gpu_type": gpu_type,
                "duration_hours": duration_hours
            }
            response = await self.http_client.get("/v1/cost-estimation/calculator", params=params)
            return response
        except Exception as e:
            raise CostEstimationError(f"Failed to calculate cost: {e}")
