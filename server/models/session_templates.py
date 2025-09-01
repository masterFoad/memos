"""
Session Templates - Predefined session configurations for better UX
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from .sessions import ResourceTier, StorageType, ImageType, GPUType
from .users import UserType


class TemplateCategory(str, Enum):
    """Categories for session templates"""
    DEVELOPMENT = "development"
    DATA_SCIENCE = "data_science"
    WEB_DEVELOPMENT = "web_development"
    MACHINE_LEARNING = "machine_learning"
    TESTING = "testing"
    CUSTOM = "custom"


class SessionTemplate(BaseModel):
    """Predefined session configuration template"""
    
    # Template identification
    template_id: str = Field(..., description="Unique template identifier")
    name: str = Field(..., description="Human-readable template name")
    description: str = Field(..., description="Template description")
    category: TemplateCategory = Field(..., description="Template category")
    
    # Access control
    user_types: List[UserType] = Field(default=[UserType.FREE], description="Allowed user types")
    is_public: bool = Field(default=True, description="Whether template is publicly available")
    created_by: Optional[str] = Field(default=None, description="User who created the template")
    
    # Resource configuration
    resource_tier: ResourceTier = Field(default=ResourceTier.SMALL, description="Resource allocation tier")
    image_type: ImageType = Field(default=ImageType.ALPINE_BASIC, description="Container image type")
    gpu_type: GPUType = Field(default=GPUType.NONE, description="GPU configuration")
    
    # Storage configuration
    storage_type: StorageType = Field(default=StorageType.EPHEMERAL, description="Storage type")
    storage_size_gb: int = Field(default=0, description="Storage size in GB")
    mount_path: str = Field(default="/workspace", description="Storage mount path")
    
    # Session configuration
    default_ttl_minutes: int = Field(default=60, description="Default session TTL")
    max_ttl_minutes: int = Field(default=1440, description="Maximum session TTL")
    
    # Environment and tools
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Default environment variables")
    pre_install_commands: List[str] = Field(default_factory=list, description="Commands to run before session start")
    
    # Metadata
    tags: List[str] = Field(default_factory=list, description="Template tags for search")
    estimated_cost_per_hour: float = Field(default=0.05, description="Estimated cost per hour")
    
    # Usage statistics
    usage_count: int = Field(default=0, description="Number of times template was used")
    last_used: Optional[str] = Field(default=None, description="Last usage timestamp")
    
    class Config:
        json_encoders = {
            UserType: lambda v: v.value,
            ResourceTier: lambda v: v.value,
            ImageType: lambda v: v.value,
            GPUType: lambda v: v.value,
            StorageType: lambda v: v.value,
            TemplateCategory: lambda v: v.value,
        }


class TemplateManager:
    """Manages session templates"""
    
    def __init__(self):
        self._templates: Dict[str, SessionTemplate] = {}
        self._load_default_templates()
    
    def _load_default_templates(self):
        """Load default session templates"""
        
        # Development templates
        self._templates["dev-python"] = SessionTemplate(
            template_id="dev-python",
            name="Python Development",
            description="Python development environment with common tools",
            category=TemplateCategory.DEVELOPMENT,
            user_types=[UserType.FREE, UserType.PRO, UserType.ENTERPRISE],
            resource_tier=ResourceTier.SMALL,
            image_type=ImageType.PYTHON_BASIC,
            storage_type=StorageType.EPHEMERAL,
            env_vars={
                "PYTHONPATH": "/workspace",
                "PYTHONUNBUFFERED": "1"
            },
            pre_install_commands=[
                "pip install --upgrade pip",
                "pip install pytest black flake8"
            ],
            tags=["python", "development", "coding"],
            estimated_cost_per_hour=0.05
        )
        
        self._templates["dev-nodejs"] = SessionTemplate(
            template_id="dev-nodejs",
            name="Node.js Development",
            description="Node.js development environment with npm and common tools",
            category=TemplateCategory.WEB_DEVELOPMENT,
            user_types=[UserType.PRO, UserType.ENTERPRISE],
            resource_tier=ResourceTier.SMALL,
            image_type=ImageType.NODEJS_PRO,
            storage_type=StorageType.EPHEMERAL,
            env_vars={
                "NODE_ENV": "development",
                "NPM_CONFIG_CACHE": "/workspace/.npm"
            },
            pre_install_commands=[
                "npm install -g yarn typescript",
                "npm install -g @angular/cli"
            ],
            tags=["nodejs", "javascript", "web", "npm"],
            estimated_cost_per_hour=0.075
        )
        
        # Data Science templates
        self._templates["ds-python"] = SessionTemplate(
            template_id="ds-python",
            name="Data Science (Python)",
            description="Python data science environment with ML libraries",
            category=TemplateCategory.DATA_SCIENCE,
            user_types=[UserType.PRO, UserType.ENTERPRISE],
            resource_tier=ResourceTier.MEDIUM,
            image_type=ImageType.PYTHON_PRO,
            storage_type=StorageType.GCS_FUSE,
            storage_size_gb=10,
            env_vars={
                "PYTHONPATH": "/workspace",
                "JUPYTER_ENABLE_LAB": "yes"
            },
            pre_install_commands=[
                "pip install pandas numpy matplotlib seaborn",
                "pip install scikit-learn jupyter",
                "pip install plotly dash"
            ],
            tags=["python", "data-science", "ml", "jupyter"],
            estimated_cost_per_hour=0.10
        )
        
        self._templates["ds-r"] = SessionTemplate(
            template_id="ds-r",
            name="Data Science (R)",
            description="R data science environment with statistical packages",
            category=TemplateCategory.DATA_SCIENCE,
            user_types=[UserType.ENTERPRISE],
            resource_tier=ResourceTier.MEDIUM,
            image_type=ImageType.CUSTOM,  # Would need R base image
            storage_type=StorageType.GCS_FUSE,
            storage_size_gb=10,
            env_vars={
                "R_LIBS_USER": "/workspace/R/library"
            },
            pre_install_commands=[
                "R -e 'install.packages(c(\"tidyverse\", \"ggplot2\", \"dplyr\"))'"
            ],
            tags=["r", "data-science", "statistics"],
            estimated_cost_per_hour=0.10
        )
        
        # Machine Learning templates
        self._templates["ml-pytorch"] = SessionTemplate(
            template_id="ml-pytorch",
            name="PyTorch ML",
            description="PyTorch machine learning environment with GPU support",
            category=TemplateCategory.MACHINE_LEARNING,
            user_types=[UserType.ENTERPRISE],
            resource_tier=ResourceTier.LARGE,
            image_type=ImageType.PYTHON_ENTERPRISE,
            gpu_type=GPUType.T4,
            storage_type=StorageType.GCS_FUSE,
            storage_size_gb=50,
            env_vars={
                "CUDA_VISIBLE_DEVICES": "0",
                "PYTHONPATH": "/workspace"
            },
            pre_install_commands=[
                "pip install torch torchvision torchaudio",
                "pip install transformers datasets",
                "pip install wandb mlflow"
            ],
            tags=["pytorch", "ml", "gpu", "deep-learning"],
            estimated_cost_per_hour=0.25
        )
        
        self._templates["ml-tensorflow"] = SessionTemplate(
            template_id="ml-tensorflow",
            name="TensorFlow ML",
            description="TensorFlow machine learning environment with GPU support",
            category=TemplateCategory.MACHINE_LEARNING,
            user_types=[UserType.ENTERPRISE],
            resource_tier=ResourceTier.LARGE,
            image_type=ImageType.PYTHON_ENTERPRISE,
            gpu_type=GPUType.T4,
            storage_type=StorageType.GCS_FUSE,
            storage_size_gb=50,
            env_vars={
                "CUDA_VISIBLE_DEVICES": "0",
                "PYTHONPATH": "/workspace"
            },
            pre_install_commands=[
                "pip install tensorflow tensorflow-gpu",
                "pip install keras transformers",
                "pip install wandb mlflow"
            ],
            tags=["tensorflow", "ml", "gpu", "deep-learning"],
            estimated_cost_per_hour=0.25
        )
        
        # Testing templates
        self._templates["test-quick"] = SessionTemplate(
            template_id="test-quick",
            name="Quick Testing",
            description="Lightweight environment for quick tests and experiments",
            category=TemplateCategory.TESTING,
            user_types=[UserType.FREE, UserType.PRO, UserType.ENTERPRISE],
            resource_tier=ResourceTier.SMALL,
            image_type=ImageType.ALPINE_BASIC,
            storage_type=StorageType.EPHEMERAL,
            default_ttl_minutes=30,
            max_ttl_minutes=120,
            tags=["testing", "quick", "experiment"],
            estimated_cost_per_hour=0.05
        )
    
    def get_template(self, template_id: str) -> Optional[SessionTemplate]:
        """Get template by ID"""
        return self._templates.get(template_id)
    
    def list_templates(self, 
                      category: Optional[TemplateCategory] = None,
                      user_type: Optional[UserType] = None,
                      tags: Optional[List[str]] = None) -> List[SessionTemplate]:
        """List templates with optional filtering"""
        templates = list(self._templates.values())
        
        # Filter by category
        if category:
            templates = [t for t in templates if t.category == category]
        
        # Filter by user type
        if user_type:
            templates = [t for t in templates if user_type in t.user_types]
        
        # Filter by tags
        if tags:
            templates = [t for t in templates if any(tag in t.tags for tag in tags)]
        
        return templates
    
    def create_template(self, template: SessionTemplate) -> bool:
        """Create a new template"""
        if template.template_id in self._templates:
            return False
        
        self._templates[template.template_id] = template
        return True
    
    def update_template(self, template: SessionTemplate) -> bool:
        """Update an existing template"""
        if template.template_id not in self._templates:
            return False
        
        self._templates[template.template_id] = template
        return True
    
    def delete_template(self, template_id: str) -> bool:
        """Delete a template"""
        if template_id not in self._templates:
            return False
        
        del self._templates[template_id]
        return True
    
    def increment_usage(self, template_id: str):
        """Increment usage count for a template"""
        if template_id in self._templates:
            self._templates[template_id].usage_count += 1
            from datetime import datetime
            self._templates[template_id].last_used = datetime.utcnow().isoformat()
    
    def get_popular_templates(self, limit: int = 5) -> List[SessionTemplate]:
        """Get most popular templates by usage count"""
        templates = list(self._templates.values())
        templates.sort(key=lambda t: t.usage_count, reverse=True)
        return templates[:limit]


# Global template manager instance
template_manager = TemplateManager()
