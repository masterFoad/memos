"""
Session Cost Estimation Service
Provides cost prediction and forecasting for sessions
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass

from server.core.logging import get_logger
from server.models.session_templates import template_manager, SessionTemplate
from server.models.sessions import ResourceTier, StorageType
from server.models.users import UserType

logger = get_logger("cost_estimation")

@dataclass
class CostEstimate:
    """Cost estimation result"""
    estimated_hours: float
    estimated_cost: float
    hourly_rate: float
    storage_cost: float
    gpu_cost: float
    total_cost: float
    confidence: str  # "high", "medium", "low"
    breakdown: Dict[str, Any]
    recommendations: List[str]


class CostEstimationService:
    """Service for estimating session costs"""
    
    def __init__(self):
        # Base hourly rates by resource tier
        self.base_rates = {
            ResourceTier.SMALL: 0.05,      # $0.05/hour
            ResourceTier.MEDIUM: 0.10,     # $0.10/hour
            ResourceTier.LARGE: 0.20,      # $0.20/hour
            ResourceTier.XLARGE: 0.40,    # $0.40/hour
        }
        
        # Storage costs
        self.storage_rates = {
            StorageType.EPHEMERAL: 0.0,           # Free
            StorageType.GCS_FUSE: 0.02,           # $0.02/GB/hour
            StorageType.PERSISTENT_VOLUME: 0.03,  # $0.03/GB/hour
        }
        
        # GPU costs
        self.gpu_rates = {
            "none": 0.0,      # Free
            "t4": 0.15,       # $0.15/hour
            "v100": 0.50,     # $0.50/hour
            "a100": 1.20,     # $1.20/hour
            "h100": 3.00,     # $3.00/hour
            "l4": 0.25,       # $0.25/hour
        }
    
    async def estimate_session_cost(
        self,
        template_id: Optional[str] = None,
        resource_tier: Optional[ResourceTier] = None,
        storage_type: Optional[StorageType] = None,
        storage_size_gb: int = 0,
        gpu_type: str = "none",
        expected_duration_hours: float = 1.0,
        user_type: Optional[UserType] = None
    ) -> CostEstimate:
        """Estimate cost for a session"""
        try:
            # Get template if provided
            template = None
            if template_id:
                template = template_manager.get_template(template_id)
                if template:
                    # Use template values as defaults
                    resource_tier = resource_tier or template.resource_tier
                    storage_type = storage_type or template.storage_type
                    storage_size_gb = storage_size_gb or template.storage_size_gb
                    gpu_type = gpu_type or template.gpu_type.value
                    user_type = user_type or template.user_types[0] if template.user_types else None
            
            # Calculate base compute cost
            hourly_rate = self._get_hourly_rate(resource_tier, user_type)
            compute_cost = hourly_rate * expected_duration_hours
            
            # Calculate storage cost
            storage_cost = self._calculate_storage_cost(storage_type, storage_size_gb, expected_duration_hours)
            
            # Calculate GPU cost
            gpu_cost = self._calculate_gpu_cost(gpu_type, expected_duration_hours)
            
            # Calculate total cost
            total_cost = compute_cost + storage_cost + gpu_cost
            
            # Determine confidence level
            confidence = self._determine_confidence(
                template, resource_tier, storage_type, gpu_type, expected_duration_hours
            )
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                total_cost, hourly_rate, storage_cost, gpu_cost, user_type
            )
            
            # Create breakdown
            breakdown = {
                "compute": {
                    "hours": expected_duration_hours,
                    "hourly_rate": hourly_rate,
                    "cost": compute_cost
                },
                "storage": {
                    "type": storage_type.value if hasattr(storage_type, 'value') else str(storage_type) if storage_type else "ephemeral",
                    "size_gb": storage_size_gb,
                    "hourly_rate": self.storage_rates.get(storage_type, 0.0) if storage_type else 0.0,
                    "cost": storage_cost
                },
                "gpu": {
                    "type": gpu_type,
                    "hourly_rate": self.gpu_rates.get(gpu_type.lower(), 0.0),
                    "cost": gpu_cost
                }
            }
            
            return CostEstimate(
                estimated_hours=expected_duration_hours,
                estimated_cost=total_cost,
                hourly_rate=hourly_rate,
                storage_cost=storage_cost,
                gpu_cost=gpu_cost,
                total_cost=total_cost,
                confidence=confidence,
                breakdown=breakdown,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error estimating session cost: {e}")
            raise
    
    def _get_hourly_rate(self, resource_tier: ResourceTier, user_type: Optional[UserType] = None) -> float:
        """Get hourly rate based on resource tier and user type"""
        base_rate = self.base_rates.get(resource_tier, 0.05)
        
        # Apply user type discounts
        if user_type == UserType.ENTERPRISE:
            base_rate *= 0.8  # 20% discount
        elif user_type == UserType.ADMIN:
            base_rate *= 0.0  # Free for admins
        
        return base_rate
    
    def _calculate_storage_cost(self, storage_type: StorageType, size_gb: int, hours: float) -> float:
        """Calculate storage cost"""
        if not storage_type or size_gb <= 0:
            return 0.0
        
        hourly_rate = self.storage_rates.get(storage_type, 0.0)
        return hourly_rate * size_gb * hours
    
    def _calculate_gpu_cost(self, gpu_type: str, hours: float) -> float:
        """Calculate GPU cost"""
        hourly_rate = self.gpu_rates.get(gpu_type.lower(), 0.0)
        return hourly_rate * hours
    
    def _determine_confidence(
        self,
        template: Optional[SessionTemplate],
        resource_tier: Optional[ResourceTier],
        storage_type: Optional[StorageType],
        gpu_type: str,
        expected_duration: float
    ) -> str:
        """Determine confidence level of the estimate"""
        confidence_score = 0
        
        # Template-based estimates are more confident
        if template:
            confidence_score += 2
        
        # Resource tier confidence
        if resource_tier:
            confidence_score += 1
        
        # Storage type confidence
        if storage_type:
            confidence_score += 1
        
        # Duration confidence (shorter = more confident)
        if expected_duration <= 1.0:
            confidence_score += 2
        elif expected_duration <= 4.0:
            confidence_score += 1
        
        # GPU confidence
        if gpu_type.lower() != "none":
            confidence_score += 1
        
        if confidence_score >= 5:
            return "high"
        elif confidence_score >= 3:
            return "medium"
        else:
            return "low"
    
    def _generate_recommendations(
        self,
        total_cost: float,
        hourly_rate: float,
        storage_cost: float,
        gpu_cost: float,
        user_type: Optional[UserType]
    ) -> List[str]:
        """Generate cost optimization recommendations"""
        recommendations = []
        
        # High cost warnings
        if total_cost > 1.0:  # More than $1/hour
            recommendations.append("⚠️ High cost session - consider shorter duration or smaller resources")
        
        # Storage optimization
        if storage_cost > 0.1:  # More than $0.10/hour for storage
            recommendations.append("💾 High storage cost - consider using ephemeral storage for temporary work")
        
        # GPU optimization
        if gpu_cost > 0.5:  # More than $0.50/hour for GPU
            recommendations.append("🚀 High GPU cost - ensure GPU is necessary for your workload")
        
        # User type recommendations
        if user_type == UserType.FREE and total_cost > 0.1:
            recommendations.append("👤 Free tier user - consider upgrading to PRO for better rates")
        elif user_type == UserType.PRO and total_cost > 0.5:
            recommendations.append("👤 PRO user - consider Enterprise plan for volume discounts")
        
        # General recommendations
        if not recommendations:
            recommendations.append("✅ Cost-optimized configuration")
        
        return recommendations
    
    async def estimate_template_cost(self, template_id: str, duration_hours: float = 1.0) -> CostEstimate:
        """Estimate cost for a specific template"""
        template = template_manager.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        return await self.estimate_session_cost(
            template_id=template_id,
            expected_duration_hours=duration_hours
        )
    
    async def compare_costs(
        self,
        configurations: List[Dict[str, Any]],
        duration_hours: float = 1.0
    ) -> List[CostEstimate]:
        """Compare costs between different configurations"""
        estimates = []
        
        for config in configurations:
            estimate = await self.estimate_session_cost(
                template_id=config.get("template_id"),
                resource_tier=config.get("resource_tier"),
                storage_type=config.get("storage_type"),
                storage_size_gb=config.get("storage_size_gb", 0),
                gpu_type=config.get("gpu_type", "none"),
                expected_duration_hours=duration_hours,
                user_type=config.get("user_type")
            )
            estimates.append(estimate)
        
        # Sort by total cost
        estimates.sort(key=lambda x: x.total_cost)
        return estimates


# Global cost estimation service instance
cost_estimation_service = CostEstimationService()
