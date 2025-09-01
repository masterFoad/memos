"""
Template models for OnMemOS SDK
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from .base import OnMemOSModel, TemplateCategory, ResourceTier, StorageType, GPUType, ImageType, UserType


class SessionTemplate(OnMemOSModel):
    """Session template model"""
    template_id: str = Field(..., description="Template identifier")
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Template description")
    category: TemplateCategory = Field(..., description="Template category")
    user_types: List[UserType] = Field(default=[UserType.FREE], description="Allowed user types")
    is_public: bool = Field(True, description="Public availability")
    created_by: Optional[str] = Field(None, description="User who created the template")
    
    # Resource configuration
    resource_tier: ResourceTier = Field(ResourceTier.MEDIUM, description="Resource allocation tier")
    image_type: ImageType = Field(ImageType.ALPINE_BASIC, description="Container image type")
    gpu_type: GPUType = Field(GPUType.NONE, description="GPU configuration")
    
    # Storage configuration
    storage_type: StorageType = Field(StorageType.EPHEMERAL, description="Storage type")
    storage_size_gb: int = Field(0, description="Storage size in GB")
    mount_path: str = Field("/workspace", description="Storage mount path")
    
    # Session configuration
    default_ttl_minutes: int = Field(60, description="Default session TTL")
    max_ttl_minutes: int = Field(1440, description="Maximum session TTL")
    
    # Environment and tools
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Default environment variables")
    pre_install_commands: List[str] = Field(default_factory=list, description="Commands to run before session start")
    
    # Metadata
    tags: List[str] = Field(default_factory=list, description="Template tags for search")
    estimated_cost_per_hour: float = Field(0.05, description="Estimated cost per hour")
    
    # Usage statistics
    usage_count: int = Field(0, description="Number of times template was used")
    last_used: Optional[datetime] = Field(None, description="Last usage timestamp")
    
    # Template properties
    is_featured: bool = Field(False, description="Is featured template")
    is_experimental: bool = Field(False, description="Is experimental template")
    requires_gpu: bool = Field(False, description="Requires GPU")
    requires_storage: bool = Field(False, description="Requires persistent storage")
    
    @property
    def is_gpu_template(self) -> bool:
        """Check if template requires GPU"""
        return self.gpu_type != GPUType.NONE
    
    @property
    def is_storage_template(self) -> bool:
        """Check if template requires persistent storage"""
        return self.storage_type != StorageType.EPHEMERAL
    
    @property
    def is_enterprise_only(self) -> bool:
        """Check if template is enterprise-only"""
        return UserType.ENTERPRISE in self.user_types and len(self.user_types) == 1
    
    @property
    def is_pro_only(self) -> bool:
        """Check if template is pro-only or higher"""
        return UserType.FREE not in self.user_types
    
    @property
    def estimated_daily_cost(self) -> float:
        """Estimated cost for 24 hours"""
        return self.estimated_cost_per_hour * 24
    
    @property
    def estimated_weekly_cost(self) -> float:
        """Estimated cost for 168 hours (1 week)"""
        return self.estimated_cost_per_hour * 168


class TemplateList(OnMemOSModel):
    """List of templates with metadata"""
    templates: List[SessionTemplate] = Field(..., description="List of templates")
    total: int = Field(..., description="Total number of templates")
    categories: List[TemplateCategory] = Field(default_factory=list, description="Available categories")
    featured_count: int = Field(0, description="Number of featured templates")
    experimental_count: int = Field(0, description="Number of experimental templates")
    
    @property
    def featured_templates(self) -> List[SessionTemplate]:
        """Get featured templates"""
        return [t for t in self.templates if t.is_featured]
    
    @property
    def experimental_templates(self) -> List[SessionTemplate]:
        """Get experimental templates"""
        return [t for t in self.templates if t.is_experimental]
    
    @property
    def gpu_templates(self) -> List[SessionTemplate]:
        """Get GPU-requiring templates"""
        return [t for t in self.templates if t.is_gpu_template]
    
    @property
    def storage_templates(self) -> List[SessionTemplate]:
        """Get storage-requiring templates"""
        return [t for t in self.templates if t.is_storage_template]
    
    @property
    def enterprise_templates(self) -> List[SessionTemplate]:
        """Get enterprise-only templates"""
        return [t for t in self.templates if t.is_enterprise_only]
    
    @property
    def pro_templates(self) -> List[SessionTemplate]:
        """Get pro-only templates"""
        return [t for t in self.templates if t.is_pro_only]
    
    def get_by_category(self, category: TemplateCategory) -> List[SessionTemplate]:
        """Get templates by category"""
        return [t for t in self.templates if t.category == category]
    
    def get_by_tags(self, tags: List[str]) -> List[SessionTemplate]:
        """Get templates matching tags"""
        return [t for t in self.templates if any(tag in t.tags for tag in tags)]
    
    def get_by_resource_tier(self, tier: ResourceTier) -> List[SessionTemplate]:
        """Get templates by resource tier"""
        return [t for t in self.templates if t.resource_tier == tier]
    
    def get_by_gpu_type(self, gpu_type: GPUType) -> List[SessionTemplate]:
        """Get templates by GPU type"""
        return [t for t in self.templates if t.gpu_type == gpu_type]
    
    def search(self, query: str) -> List[SessionTemplate]:
        """Search templates by query"""
        query_lower = query.lower()
        return [
            t for t in self.templates
            if (query_lower in t.name.lower() or
                query_lower in t.description.lower() or
                any(query_lower in tag.lower() for tag in t.tags))
        ]


class TemplateCategoryInfo(OnMemOSModel):
    """Template category information"""
    category: TemplateCategory = Field(..., description="Category")
    name: str = Field(..., description="Category display name")
    description: str = Field(..., description="Category description")
    template_count: int = Field(0, description="Number of templates in category")
    icon: str = Field("📁", description="Category icon")
    color: str = Field("#6B7280", description="Category color")
    is_featured: bool = Field(False, description="Is featured category")
    
    # Category-specific properties
    default_resource_tier: Optional[ResourceTier] = Field(None, description="Default resource tier")
    default_storage_type: Optional[StorageType] = Field(None, description="Default storage type")
    common_tags: List[str] = Field(default_factory=list, description="Common tags in category")
    estimated_cost_range: Dict[str, float] = Field(default_factory=dict, description="Cost range (min, max)")


class TemplateUsageStats(OnMemOSModel):
    """Template usage statistics"""
    template_id: str = Field(..., description="Template identifier")
    total_usage: int = Field(0, description="Total usage count")
    unique_users: int = Field(0, description="Unique users")
    total_hours: float = Field(0.0, description="Total hours used")
    total_cost: float = Field(0.0, description="Total cost")
    average_session_length: float = Field(0.0, description="Average session length in hours")
    
    # Time-based stats
    usage_today: int = Field(0, description="Usage today")
    usage_this_week: int = Field(0, description="Usage this week")
    usage_this_month: int = Field(0, description="Usage this month")
    
    # User type breakdown
    usage_by_user_type: Dict[str, int] = Field(default_factory=dict, description="Usage by user type")
    
    # Resource usage
    resource_tier_usage: Dict[str, int] = Field(default_factory=dict, description="Usage by resource tier")
    storage_type_usage: Dict[str, int] = Field(default_factory=dict, description="Usage by storage type")
    
    # Popular configurations
    popular_configs: List[Dict[str, Any]] = Field(default_factory=list, description="Popular configurations")
    
    @property
    def average_cost_per_session(self) -> float:
        """Average cost per session"""
        if self.total_usage == 0:
            return 0.0
        return self.total_cost / self.total_usage
    
    @property
    def cost_per_hour(self) -> float:
        """Cost per hour of usage"""
        if self.total_hours == 0:
            return 0.0
        return self.total_cost / self.total_hours


class TemplateValidationResult(OnMemOSModel):
    """Template configuration validation result"""
    template_id: str = Field(..., description="Template identifier")
    is_valid: bool = Field(..., description="Is configuration valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    suggestions: List[str] = Field(default_factory=list, description="Configuration suggestions")
    
    # Validation details
    resource_validation: Dict[str, Any] = Field(default_factory=dict, description="Resource validation")
    storage_validation: Dict[str, Any] = Field(default_factory=dict, description="Storage validation")
    environment_validation: Dict[str, Any] = Field(default_factory=dict, description="Environment validation")
    
    # Cost estimation
    estimated_cost: Optional[float] = Field(None, description="Estimated cost for configuration")
    cost_breakdown: Dict[str, Any] = Field(default_factory=dict, description="Cost breakdown")
    
    @property
    def has_errors(self) -> bool:
        """Check if validation has errors"""
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if validation has warnings"""
        return len(self.warnings) > 0
    
    @property
    def is_ready(self) -> bool:
        """Check if template is ready to use"""
        return self.is_valid and not self.has_errors
