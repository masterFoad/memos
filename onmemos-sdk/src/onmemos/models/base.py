"""
Base models and enums for OnMemOS SDK
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class OnMemOSModel(BaseModel):
    """Base model for all OnMemOS entities"""
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        validate_assignment = True


class ResourceTier(str, Enum):
    """Resource allocation tiers"""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    XLARGE = "xlarge"


class StorageType(str, Enum):
    """Storage types"""
    EPHEMERAL = "ephemeral"
    GCS_FUSE = "gcs_fuse"
    PERSISTENT_VOLUME = "persistent_volume"


class GPUType(str, Enum):
    """GPU types"""
    NONE = "none"
    T4 = "t4"
    V100 = "v100"
    A100 = "a100"
    H100 = "h100"
    L4 = "l4"


class ImageType(str, Enum):
    """Container image types"""
    ALPINE_BASIC = "alpine_basic"
    UBUNTU_BASIC = "ubuntu_basic"
    PYTHON_DEV = "python_dev"
    NODEJS_DEV = "nodejs_dev"
    DATA_SCIENCE = "data_science"
    ML_TRAINING = "ml_training"
    CUSTOM = "custom"


class UserType(str, Enum):
    """User types"""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    ADMIN = "admin"


class SessionStatus(str, Enum):
    """Session status values"""
    CREATING = "creating"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class MountType(str, Enum):
    """Storage mount types"""
    GCS_BUCKET = "gcs_bucket"
    FILESTORE = "filestore"
    PERSISTENT_VOLUME = "persistent_volume"


class TemplateCategory(str, Enum):
    """Template categories"""
    DEVELOPMENT = "development"
    DATA_SCIENCE = "data_science"
    MACHINE_LEARNING = "machine_learning"
    TESTING = "testing"
    PRODUCTION = "production"


class CostEstimate(OnMemOSModel):
    """Cost estimation result"""
    estimated_hours: float = Field(..., description="Estimated duration in hours")
    estimated_cost: float = Field(..., description="Estimated total cost")
    hourly_rate: float = Field(..., description="Hourly rate")
    storage_cost: float = Field(..., description="Storage cost component")
    gpu_cost: float = Field(..., description="GPU cost component")
    total_cost: float = Field(..., description="Total estimated cost")
    confidence: str = Field(..., description="Confidence level (high/medium/low)")
    breakdown: Dict[str, Any] = Field(..., description="Cost breakdown")
    recommendations: list[str] = Field(..., description="Cost optimization recommendations")


class PaginationParams(OnMemOSModel):
    """Pagination parameters"""
    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(10, ge=1, le=100, description="Items per page")
    
    @property
    def offset(self) -> int:
        """Calculate offset from page and per_page"""
        return (self.page - 1) * self.per_page


class PaginatedResponse(OnMemOSModel):
    """Generic paginated response"""
    items: list[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")
    has_next: bool = Field(..., description="Has next page")
    has_prev: bool = Field(..., description="Has previous page")
    
    @property
    def total_pages(self) -> int:
        """Calculate total number of pages"""
        return (self.total + self.per_page - 1) // self.per_page
    
    @property
    def is_first_page(self) -> bool:
        """Check if this is the first page"""
        return self.page == 1
    
    @property
    def is_last_page(self) -> bool:
        """Check if this is the last page"""
        return self.page >= self.total_pages


class ErrorResponse(OnMemOSModel):
    """Error response model"""
    error: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class SuccessResponse(OnMemOSModel):
    """Success response model"""
    message: str = Field(..., description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
