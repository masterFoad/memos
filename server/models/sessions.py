# server/models/sessions.py
from __future__ import annotations
from enum import Enum
from typing import Optional, Dict, Any, Literal, List, ClassVar
from pydantic import BaseModel, Field, validator, model_validator
from datetime import datetime, timedelta
from .users import UserType, WorkspaceStorageRequest, WorkspaceStorageAllocation, WorkspaceResourcePackage


class SessionProvider(str, Enum):
    cloud_run = "cloud_run"
    gke = "gke"
    workstations = "workstations"
    auto = "auto"


class StorageType(str, Enum):
    """Types of storage available for sessions"""
    EPHEMERAL = "ephemeral"         # Temporary storage (default)
    GCS_FUSE = "gcs_fuse"           # Google Cloud Storage via FUSE
    PERSISTENT_VOLUME = "persistent_volume"  # Kubernetes Persistent Volume


class ResourceTier(str, Enum):
    """Resource allocation tiers (backward compatibility)"""
    SMALL = "small"      # 250m CPU, 512Mi RAM
    MEDIUM = "medium"    # 500m CPU, 1Gi RAM  
    LARGE = "large"      # 1 CPU, 2Gi RAM
    XLARGE = "xlarge"    # 2 CPU, 4Gi RAM


class CPUSize(str, Enum):
    """CPU size specifications"""
    MICRO = "micro"      # 250m CPU
    SMALL = "small"      # 500m CPU
    MEDIUM = "medium"    # 1 CPU
    LARGE = "large"      # 2 CPU
    XLARGE = "xlarge"    # 4 CPU
    XXLARGE = "xxlarge"  # 8 CPU
    CUSTOM = "custom"    # Custom CPU specification


class MemorySize(str, Enum):
    """Memory size specifications"""
    MICRO = "micro"      # 512Mi RAM
    SMALL = "small"      # 1Gi RAM
    MEDIUM = "medium"    # 2Gi RAM
    LARGE = "large"      # 4Gi RAM
    XLARGE = "xlarge"    # 8Gi RAM
    XXLARGE = "xxlarge"  # 16Gi RAM
    XXXLARGE = "xxxlarge" # 32Gi RAM
    CUSTOM = "custom"    # Custom memory specification


class ImageType(str, Enum):
    """Supported container image types with tier-based access"""
    # Free tier images (basic)
    ALPINE_BASIC = "alpine_basic"       # Alpine Linux (free tier)
    PYTHON_BASIC = "python_basic"       # Python 3.9 (free tier)
    
    # Pro tier images (enhanced)
    UBUNTU_PRO = "ubuntu_pro"           # Ubuntu 22.04 LTS
    PYTHON_PRO = "python_pro"           # Python 3.11 with data science packages
    NODEJS_PRO = "nodejs_pro"           # Node.js 18 LTS
    GO_PRO = "go_pro"                   # Go 1.21
    RUST_PRO = "rust_pro"               # Rust 1.70
    
    # Enterprise tier images (premium)
    PYTHON_ENTERPRISE = "python_enterprise"  # Python 3.11 with full ML stack
    JUPYTER_ENTERPRISE = "jupyter_enterprise"  # Jupyter with full data science stack
    CUDA_ENTERPRISE = "cuda_enterprise"  # CUDA-enabled with ML frameworks
    JAVA_ENTERPRISE = "java_enterprise"  # Java 17 with enterprise tools
    
    # Custom images
    CUSTOM = "custom"                   # Custom image URL


class GPUType(str, Enum):
    """Supported GPU types"""
    NONE = "none"               # No GPU (default)
    T4 = "t4"                   # NVIDIA T4
    V100 = "v100"               # NVIDIA V100
    A100 = "a100"               # NVIDIA A100
    H100 = "h100"               # NVIDIA H100
    L4 = "l4"                   # NVIDIA L4


class ResourcePackage(str, Enum):
    """Predefined resource packages for different use cases (session-level)"""
    # Development packages
    DEV_MICRO = "dev_micro"     # Micro development environment
    DEV_SMALL = "dev_small"     # Small development environment
    DEV_MEDIUM = "dev_medium"   # Medium development environment
    DEV_LARGE = "dev_large"     # Large development environment
    
    # Data Science packages
    DS_SMALL = "ds_small"       # Small data science (CPU only)
    DS_MEDIUM = "ds_medium"     # Medium data science (CPU only)
    DS_LARGE = "ds_large"       # Large data science (CPU only)
    
    # Machine Learning packages
    ML_T4_SMALL = "ml_t4_small"     # Small ML with T4 GPU
    ML_T4_MEDIUM = "ml_t4_medium"   # Medium ML with T4 GPU
    ML_T4_LARGE = "ml_t4_large"     # Large ML with T4 GPU
    ML_A100_SMALL = "ml_a100_small" # Small ML with A100 GPU
    ML_A100_MEDIUM = "ml_a100_medium" # Medium ML with A100 GPU
    ML_A100_LARGE = "ml_a100_large" # Large ML with A100 GPU
    ML_H100_SMALL = "ml_h100_small" # Small ML with H100 GPU
    ML_H100_MEDIUM = "ml_h100_medium" # Medium ML with H100 GPU
    ML_H100_LARGE = "ml_h100_large" # Large ML with H100 GPU
    
    # Compute packages
    COMPUTE_SMALL = "compute_small"   # Small compute
    COMPUTE_MEDIUM = "compute_medium" # Medium compute
    COMPUTE_LARGE = "compute_large"   # Large compute
    COMPUTE_XLARGE = "compute_xlarge" # Extra large compute


class ResourceSpec(BaseModel):
    """Fine-grained resource specification using enums"""
    cpu_size: CPUSize = Field(default=CPUSize.SMALL, description="CPU size specification")
    memory_size: MemorySize = Field(default=MemorySize.SMALL, description="Memory size specification")
    custom_cpu_request: Optional[str] = Field(default=None, description="Custom CPU request (when cpu_size is CUSTOM)")
    custom_cpu_limit: Optional[str] = Field(default=None, description="Custom CPU limit")
    custom_memory_request: Optional[str] = Field(default=None, description="Custom memory request (when memory_size is CUSTOM)")
    custom_memory_limit: Optional[str] = Field(default=None, description="Custom memory limit")
    
    # Resource package mappings
    PACKAGE_SPECS: ClassVar[Dict[ResourcePackage, Dict[str, Any]]] = {
        # Development packages
        ResourcePackage.DEV_MICRO: {"cpu_size": CPUSize.MICRO, "memory_size": MemorySize.MICRO},
        ResourcePackage.DEV_SMALL: {"cpu_size": CPUSize.SMALL, "memory_size": MemorySize.SMALL},
        ResourcePackage.DEV_MEDIUM: {"cpu_size": CPUSize.MEDIUM, "memory_size": MemorySize.MEDIUM},
        ResourcePackage.DEV_LARGE: {"cpu_size": CPUSize.LARGE, "memory_size": MemorySize.LARGE},
        
        # Data Science packages
        ResourcePackage.DS_SMALL: {"cpu_size": CPUSize.MEDIUM, "memory_size": MemorySize.MEDIUM},
        ResourcePackage.DS_MEDIUM: {"cpu_size": CPUSize.LARGE, "memory_size": MemorySize.LARGE},
        ResourcePackage.DS_LARGE: {"cpu_size": CPUSize.XLARGE, "memory_size": MemorySize.XLARGE},
        
        # Machine Learning packages
        ResourcePackage.ML_T4_SMALL: {"cpu_size": CPUSize.MEDIUM, "memory_size": MemorySize.LARGE},
        ResourcePackage.ML_T4_MEDIUM: {"cpu_size": CPUSize.LARGE, "memory_size": MemorySize.XLARGE},
        ResourcePackage.ML_T4_LARGE: {"cpu_size": CPUSize.XLARGE, "memory_size": MemorySize.XXLARGE},
        ResourcePackage.ML_A100_SMALL: {"cpu_size": CPUSize.LARGE, "memory_size": MemorySize.XLARGE},
        ResourcePackage.ML_A100_MEDIUM: {"cpu_size": CPUSize.XLARGE, "memory_size": MemorySize.XXLARGE},
        ResourcePackage.ML_A100_LARGE: {"cpu_size": CPUSize.XXLARGE, "memory_size": MemorySize.XXXLARGE},
        ResourcePackage.ML_H100_SMALL: {"cpu_size": CPUSize.XLARGE, "memory_size": MemorySize.XXLARGE},
        ResourcePackage.ML_H100_MEDIUM: {"cpu_size": CPUSize.XXLARGE, "memory_size": MemorySize.XXXLARGE},
        ResourcePackage.ML_H100_LARGE: {"cpu_size": CPUSize.XXLARGE, "memory_size": MemorySize.XXXLARGE},
        
        # Compute packages
        ResourcePackage.COMPUTE_SMALL: {"cpu_size": CPUSize.SMALL, "memory_size": MemorySize.SMALL},
        ResourcePackage.COMPUTE_MEDIUM: {"cpu_size": CPUSize.MEDIUM, "memory_size": MemorySize.MEDIUM},
        ResourcePackage.COMPUTE_LARGE: {"cpu_size": CPUSize.LARGE, "memory_size": MemorySize.LARGE},
        ResourcePackage.COMPUTE_XLARGE: {"cpu_size": CPUSize.XLARGE, "memory_size": MemorySize.XLARGE},
    }
    
    # CPU size to Kubernetes CPU mapping
    CPU_MAPPING: ClassVar[Dict[CPUSize, Dict[str, str]]] = {
        CPUSize.MICRO: {"request": "250m", "limit": "500m"},
        CPUSize.SMALL: {"request": "500m", "limit": "1"},
        CPUSize.MEDIUM: {"request": "1", "limit": "2"},
        CPUSize.LARGE: {"request": "2", "limit": "4"},
        CPUSize.XLARGE: {"request": "4", "limit": "8"},
        CPUSize.XXLARGE: {"request": "8", "limit": "16"},
    }
    
    # Memory size to Kubernetes memory mapping
    MEMORY_MAPPING: ClassVar[Dict[MemorySize, Dict[str, str]]] = {
        MemorySize.MICRO: {"request": "512Mi", "limit": "1Gi"},
        MemorySize.SMALL: {"request": "1Gi", "limit": "2Gi"},
        MemorySize.MEDIUM: {"request": "2Gi", "limit": "4Gi"},
        MemorySize.LARGE: {"request": "4Gi", "limit": "8Gi"},
        MemorySize.XLARGE: {"request": "8Gi", "limit": "16Gi"},
        MemorySize.XXLARGE: {"request": "16Gi", "limit": "32Gi"},
        MemorySize.XXXLARGE: {"request": "32Gi", "limit": "64Gi"},
    }
    
    @validator('custom_cpu_request', 'custom_cpu_limit')
    def validate_custom_cpu(cls, v):
        if v is not None:
            if not v.endswith('m') and not v.replace('.', '').isdigit():
                raise ValueError('CPU must be in format "250m" or "1" or "2.5"')
        return v
    
    @validator('custom_memory_request', 'custom_memory_limit')
    def validate_custom_memory(cls, v):
        if v is not None:
            if not any(v.endswith(suffix) for suffix in ['Ki', 'Mi', 'Gi', 'Ti']):
                raise ValueError('Memory must be in format "512Mi", "1Gi", etc.')
        return v
    
    @classmethod
    def from_package(cls, package: ResourcePackage) -> 'ResourceSpec':
        """Create ResourceSpec from ResourcePackage"""
        if package not in cls.PACKAGE_SPECS:
            raise ValueError(f"Unknown resource package: {package}")
        
        spec = cls.PACKAGE_SPECS[package]
        return cls(cpu_size=spec["cpu_size"], memory_size=spec["memory_size"])
    
    @classmethod
    def from_workspace_package(cls, workspace_package: WorkspaceResourcePackage) -> 'ResourceSpec':
        """Create ResourceSpec from WorkspaceResourcePackage"""
        # Map workspace packages to session packages
        package_mapping = {
            WorkspaceResourcePackage.FREE_MICRO: ResourcePackage.DEV_MICRO,
            WorkspaceResourcePackage.DEV_MICRO: ResourcePackage.DEV_MICRO,
            WorkspaceResourcePackage.DEV_SMALL: ResourcePackage.DEV_SMALL,
            WorkspaceResourcePackage.DEV_MEDIUM: ResourcePackage.DEV_MEDIUM,
            WorkspaceResourcePackage.DEV_LARGE: ResourcePackage.DEV_LARGE,
            WorkspaceResourcePackage.DS_SMALL: ResourcePackage.DS_SMALL,
            WorkspaceResourcePackage.DS_MEDIUM: ResourcePackage.DS_MEDIUM,
            WorkspaceResourcePackage.DS_LARGE: ResourcePackage.DS_LARGE,
            WorkspaceResourcePackage.ML_T4_SMALL: ResourcePackage.ML_T4_SMALL,
            WorkspaceResourcePackage.ML_T4_MEDIUM: ResourcePackage.ML_T4_MEDIUM,
            WorkspaceResourcePackage.ML_T4_LARGE: ResourcePackage.ML_T4_LARGE,
            WorkspaceResourcePackage.ML_A100_SMALL: ResourcePackage.ML_A100_SMALL,
            WorkspaceResourcePackage.ML_A100_MEDIUM: ResourcePackage.ML_A100_MEDIUM,
            WorkspaceResourcePackage.ML_A100_LARGE: ResourcePackage.ML_A100_LARGE,
            WorkspaceResourcePackage.ML_H100_SMALL: ResourcePackage.ML_H100_SMALL,
            WorkspaceResourcePackage.ML_H100_MEDIUM: ResourcePackage.ML_H100_MEDIUM,
            WorkspaceResourcePackage.ML_H100_LARGE: ResourcePackage.ML_H100_LARGE,
            WorkspaceResourcePackage.COMPUTE_SMALL: ResourcePackage.COMPUTE_SMALL,
            WorkspaceResourcePackage.COMPUTE_MEDIUM: ResourcePackage.COMPUTE_MEDIUM,
            WorkspaceResourcePackage.COMPUTE_LARGE: ResourcePackage.COMPUTE_LARGE,
            WorkspaceResourcePackage.COMPUTE_XLARGE: ResourcePackage.COMPUTE_XLARGE,
        }
        
        session_package = package_mapping.get(workspace_package, ResourcePackage.DEV_SMALL)
        return cls.from_package(session_package)
    
    @classmethod
    def from_tier(cls, tier: ResourceTier) -> 'ResourceSpec':
        """Create ResourceSpec from ResourceTier (backward compatibility)"""
        tier_mapping = {
            ResourceTier.SMALL: cls(cpu_size=CPUSize.SMALL, memory_size=MemorySize.SMALL),
            ResourceTier.MEDIUM: cls(cpu_size=CPUSize.MEDIUM, memory_size=MemorySize.MEDIUM),
            ResourceTier.LARGE: cls(cpu_size=CPUSize.LARGE, memory_size=MemorySize.LARGE),
            ResourceTier.XLARGE: cls(cpu_size=CPUSize.XLARGE, memory_size=MemorySize.XLARGE),
        }
        return tier_mapping.get(tier, tier_mapping[ResourceTier.SMALL])
    
    def get_cpu_request(self) -> str:
        """Get CPU request string for Kubernetes"""
        if self.cpu_size == CPUSize.CUSTOM and self.custom_cpu_request:
            return self.custom_cpu_request
        return self.CPU_MAPPING.get(self.cpu_size, {"request": "500m"})["request"]
    
    def get_cpu_limit(self) -> str:
        """Get CPU limit string for Kubernetes"""
        if self.cpu_size == CPUSize.CUSTOM and self.custom_cpu_limit:
            return self.custom_cpu_limit
        return self.CPU_MAPPING.get(self.cpu_size, {"limit": "1"})["limit"]
    
    def get_memory_request(self) -> str:
        """Get memory request string for Kubernetes"""
        if self.memory_size == MemorySize.CUSTOM and self.custom_memory_request:
            return self.custom_memory_request
        return self.MEMORY_MAPPING.get(self.memory_size, {"request": "1Gi"})["request"]
    
    def get_memory_limit(self) -> str:
        """Get memory limit string for Kubernetes"""
        if self.memory_size == MemorySize.CUSTOM and self.custom_memory_limit:
            return self.custom_memory_limit
        return self.MEMORY_MAPPING.get(self.memory_size, {"limit": "2Gi"})["limit"]


class ImageSpec(BaseModel):
    """Container image specification"""
    image_type: ImageType = Field(default=ImageType.ALPINE_BASIC, description="Image type")
    image_url: Optional[str] = Field(default=None, description="Custom image URL")
    image_tag: str = Field(default="latest", description="Image tag")
    
    # Predefined images for each type with tier-based access
    PREDEFINED_IMAGES: ClassVar[Dict[ImageType, str]] = {
        # Free tier images (basic)
        ImageType.ALPINE_BASIC: "alpine:3.18",
        ImageType.PYTHON_BASIC: "python:3.9-slim",
        
        # Pro tier images (enhanced)
        ImageType.UBUNTU_PRO: "ubuntu:22.04",
        ImageType.PYTHON_PRO: "python:3.11-slim",
        ImageType.NODEJS_PRO: "node:18-alpine",
        ImageType.GO_PRO: "golang:1.21-alpine",
        ImageType.RUST_PRO: "rust:1.70-alpine",
        
        # Enterprise tier images (premium)
        ImageType.PYTHON_ENTERPRISE: "python:3.11-slim",
        ImageType.JUPYTER_ENTERPRISE: "jupyter/datascience-notebook:latest",
        ImageType.CUDA_ENTERPRISE: "nvidia/cuda:11.8-devel-ubuntu22.04",
        ImageType.JAVA_ENTERPRISE: "openjdk:17-alpine",
        
        # Legacy support (backward compatibility) - map old names to new ones
        ImageType.ALPINE_BASIC: "alpine:latest",  # ALPINE -> ALPINE_BASIC
        ImageType.UBUNTU_PRO: "ubuntu:22.04",     # UBUNTU -> UBUNTU_PRO
        ImageType.PYTHON_PRO: "python:3.11-slim", # PYTHON -> PYTHON_PRO
        ImageType.NODEJS_PRO: "node:18-slim",     # NODEJS -> NODEJS_PRO
        ImageType.GO_PRO: "golang:1.21-alpine",   # GO -> GO_PRO
        ImageType.RUST_PRO: "rust:1.70-alpine",   # RUST -> RUST_PRO
        ImageType.JAVA_ENTERPRISE: "openjdk:17-alpine", # JAVA -> JAVA_ENTERPRISE
    }
    
    @model_validator(mode='after')
    def validate_image(self):
        if self.image_type == ImageType.CUSTOM and not self.image_url:
            raise ValueError('image_url is required for CUSTOM image type')
        return self
    
    def get_image_url(self) -> str:
        """Get the full image URL"""
        if self.image_type == ImageType.CUSTOM:
            return self.image_url
        else:
            base_image = self.PREDEFINED_IMAGES.get(self.image_type, "alpine:latest")
            if self.image_tag != "latest":
                # Replace tag in base image
                base_parts = base_image.split(':')
                return f"{base_parts[0]}:{self.image_tag}"
            return base_image
    
    @classmethod
    def from_string(cls, image_str: str) -> 'ImageSpec':
        """Create ImageSpec from string (backward compatibility)"""
        if image_str.startswith('alpine'):
            return cls(image_type=ImageType.ALPINE_BASIC, image_tag=image_str.split(':')[-1] if ':' in image_str else "latest")
        elif image_str.startswith('ubuntu'):
            return cls(image_type=ImageType.UBUNTU_PRO, image_tag=image_str.split(':')[-1] if ':' in image_str else "latest")
        elif image_str.startswith('python'):
            return cls(image_type=ImageType.PYTHON_PRO, image_tag=image_str.split(':')[-1] if ':' in image_str else "latest")
        elif image_str.startswith('node'):
            return cls(image_type=ImageType.NODEJS_PRO, image_tag=image_str.split(':')[-1] if ':' in image_str else "latest")
        elif image_str.startswith('golang'):
            return cls(image_type=ImageType.GO_PRO, image_tag=image_str.split(':')[-1] if ':' in image_str else "latest")
        elif image_str.startswith('rust'):
            return cls(image_type=ImageType.RUST_PRO, image_tag=image_str.split(':')[-1] if ':' in image_str else "latest")
        elif image_str.startswith('openjdk'):
            return cls(image_type=ImageType.JAVA_ENTERPRISE, image_tag=image_str.split(':')[-1] if ':' in image_str else "latest")
        else:
            # Assume custom image
            return cls(image_type=ImageType.CUSTOM, image_url=image_str)


class GPUSpec(BaseModel):
    """GPU specification"""
    gpu_type: GPUType = Field(default=GPUType.NONE, description="GPU type")
    gpu_count: int = Field(default=1, ge=1, le=8, description="Number of GPUs")
    
    @validator('gpu_count')
    def validate_gpu_count(cls, v):
        if v < 1 or v > 8:
            raise ValueError('GPU count must be between 1 and 8')
        return v
    
    def is_enabled(self) -> bool:
        """Check if GPU is enabled"""
        return self.gpu_type != GPUType.NONE
    
    def get_gpu_requests(self) -> Dict[str, str]:
        """Get GPU resource requests for Kubernetes"""
        if not self.is_enabled():
            return {}
        
        gpu_resource_map = {
            GPUType.T4: "nvidia.com/gpu",
            GPUType.V100: "nvidia.com/gpu",
            GPUType.A100: "nvidia.com/gpu",
            GPUType.H100: "nvidia.com/gpu",
            GPUType.L4: "nvidia.com/gpu",
        }
        
        resource_name = gpu_resource_map.get(self.gpu_type, "nvidia.com/gpu")
        return {resource_name: str(self.gpu_count)}


class StorageConfig(BaseModel):
    """Enhanced storage configuration for sessions"""
    storage_type: StorageType = Field(default=StorageType.EPHEMERAL)
    mount_path: str = Field(default="/workspace", description="Mount path in container")
    
    # GCS FUSE specific
    bucket_name: Optional[str] = Field(default=None, description="GCS bucket name")
    gcs_prefix: Optional[str] = Field(default="", description="GCS prefix for workspace files")
    gcs_mount_options: str = Field(
        default="implicit-dirs,only-dir=workspace/,file-mode=0644,dir-mode=0755",
        description="GCS FUSE mount options"
    )
    
    # Persistent Volume specific
    pvc_name: Optional[str] = Field(default=None, description="Persistent Volume Claim name")
    pvc_size: Optional[str] = Field(default="10Gi", description="PVC size")
    storage_class: Optional[str] = Field(default="standard-rwo", description="Storage class")
    
    # Additional storage configurations for multiple mounts
    additional_storage: Optional[List['StorageConfig']] = Field(default=None, description="Additional storage configurations")
    
    @model_validator(mode='after')
    def validate_storage_config(self):
        storage_type = self.storage_type
        
        if storage_type == StorageType.GCS_FUSE:
            if not self.bucket_name:
                raise ValueError('bucket_name is required for GCS_FUSE storage')
        
        elif storage_type == StorageType.PERSISTENT_VOLUME:
            if not self.pvc_name:
                raise ValueError('pvc_name is required for PERSISTENT_VOLUME storage')
        
        # Validate additional storage configurations
        if self.additional_storage:
            for i, additional in enumerate(self.additional_storage):
                if additional.storage_type == StorageType.GCS_FUSE:
                    if not additional.bucket_name:
                        raise ValueError(f'bucket_name is required for additional GCS_FUSE storage at index {i}')
                
                elif additional.storage_type == StorageType.PERSISTENT_VOLUME:
                    if not additional.pvc_name:
                        raise ValueError(f'pvc_name is required for additional PERSISTENT_VOLUME storage at index {i}')
        
        return self


class CreateSessionRequest(BaseModel):
    provider: SessionProvider = SessionProvider.auto
    template: str
    namespace: str
    user: str
    workspace_id: str = Field(description="Workspace identifier for the session")
    ttl_minutes: int = 60
    
    # Template-based session creation
    template_id: Optional[str] = Field(default=None, description="Template ID to use for session configuration")
    
    # User management
    user_type: Optional[UserType] = Field(default=None, description="User type for entitlements")
    
    # Storage configuration (legacy and enhanced)
    storage: Dict[str, Any] = Field(default_factory=dict)  # Legacy storage dict
    storage_config: Optional[StorageConfig] = Field(default=None, description="Enhanced storage configuration")
    
    # Storage requests (new workspace-based approach)
    request_bucket: bool = Field(False, description="Request GCS bucket storage")
    request_persistent_storage: bool = Field(False, description="Request persistent storage (Filestore)")
    bucket_size_gb: Optional[int] = Field(None, description="Bucket size in GB")
    persistent_storage_size_gb: Optional[int] = Field(10, description="Persistent storage size in GB")
    
    # Resource configuration (enhanced with packages)
    resource_tier: Optional[ResourceTier] = Field(default=None, description="Resource allocation tier (legacy)")
    resource_package: Optional[ResourcePackage] = Field(default=None, description="Resource package for predefined configurations")
    resource_spec: Optional[ResourceSpec] = Field(default=None, description="Fine-grained resource specification")
    image_spec: Optional[ImageSpec] = Field(default=None, description="Container image specification")
    gpu_spec: Optional[GPUSpec] = Field(default=None, description="GPU specification")
    
    # Legacy fields
    needs_ssh: bool = False
    long_lived: bool = False
    expected_duration_minutes: Optional[int] = None
    
    # Custom environment variables
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    
    @validator('ttl_minutes')
    def validate_ttl(cls, v):
        if v < 1 or v > 1440:  # 1 minute to 24 hours
            raise ValueError('TTL must be between 1 and 1440 minutes')
        return v
    
    @validator('namespace')
    def validate_namespace(cls, v):
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Namespace must be alphanumeric with hyphens/underscores only')
        return v.lower()
    
    @model_validator(mode='after')
    def validate_resource_config(self):
        """Validate resource configuration with priority: resource_spec > resource_package > resource_tier"""
        if self.resource_spec is not None:
            # Use provided resource_spec
            pass
        elif self.resource_package is not None:
            # Create resource_spec from package
            self.resource_spec = ResourceSpec.from_package(self.resource_package)
        elif self.resource_tier is not None:
            # Create resource_spec from legacy tier
            self.resource_spec = ResourceSpec.from_tier(self.resource_tier)
        else:
            # Default to small package
            self.resource_spec = ResourceSpec.from_package(ResourcePackage.DEV_SMALL)
        
        # If image_spec is not provided, use default
        if self.image_spec is None:
            self.image_spec = ImageSpec()
        
        # If gpu_spec is not provided, use default (no GPU)
        if self.gpu_spec is None:
            self.gpu_spec = GPUSpec()
        
        return self
    
    def to_storage_request(self, session_id: str) -> WorkspaceStorageRequest:
        """Convert to WorkspaceStorageRequest for workspace management"""
        # Only allocate storage if explicitly requested
        # Default to 0 size if not requesting storage
        bucket_size = self.bucket_size_gb if self.request_bucket else 0
        persistent_size = self.persistent_storage_size_gb if self.request_persistent_storage else 0
        
        return WorkspaceStorageRequest(
            workspace_id=self.workspace_id,
            user_id=self.user,
            namespace=self.namespace,
            session_id=session_id,
            request_bucket=self.request_bucket,
            request_persistent_storage=self.request_persistent_storage,
            bucket_size_gb=bucket_size,
            persistent_storage_size_gb=persistent_size,
            mount_path=self.storage_config.mount_path if self.storage_config else "/workspace",
            storage_class=self.storage_config.storage_class if self.storage_config else "standard-rwo"
        )


class ExecuteRequest(BaseModel):
    command: str
    timeout: int = 120


class SessionInfo(BaseModel):
    id: str
    provider: SessionProvider
    namespace: str
    user: str
    workspace_id: str = Field(description="Workspace identifier")
    status: str
    url: Optional[str] = None       # service URL or workstation URL
    websocket: Optional[str] = None # where relevant
    ssh: Optional[bool] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    
    # User management
    user_type: Optional[UserType] = Field(default=None, description="User type")
    storage_allocation: Optional[WorkspaceStorageAllocation] = Field(default=None, description="Storage allocation info")
    
    # Enhanced fields
    storage_config: Optional[StorageConfig] = Field(default=None, description="Storage configuration")
    resource_tier: Optional[ResourceTier] = Field(default=None, description="Resource tier (legacy)")
    resource_package: Optional[ResourcePackage] = Field(default=None, description="Resource package used")
    resource_spec: Optional[ResourceSpec] = Field(default=None, description="Resource specification")
    image_spec: Optional[ImageSpec] = Field(default=None, description="Image specification")
    gpu_spec: Optional[GPUSpec] = Field(default=None, description="GPU specification")
    created_at: Optional[datetime] = Field(default=None, description="Session creation time")
    expires_at: Optional[datetime] = Field(default=None, description="Session expiration time")
    
    # Backend-specific identifiers
    k8s_namespace: Optional[str] = Field(default=None, description="Kubernetes namespace (GKE)")
    pod_name: Optional[str] = Field(default=None, description="Pod name (GKE)")
    service_name: Optional[str] = Field(default=None, description="Service name (Cloud Run)")
    job_name: Optional[str] = Field(default=None, description="Job name (Cloud Run)")
    
    # Storage status
    storage_status: Dict[str, Any] = Field(default_factory=dict, description="Storage status information")
    
    @model_validator(mode='after')
    def set_expires_at(self):
        if self.expires_at is None and self.created_at:
            # We need to calculate from ttl_minutes, but we don't have it in the model
            # This will be set by the session provider
            pass
        return self


# Backward compatibility aliases
class WorkspaceRequest(CreateSessionRequest):
    """Alias for backward compatibility"""
    pass


class WorkspaceInfo(SessionInfo):
    """Alias for backward compatibility"""
    pass
