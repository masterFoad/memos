"""
Storage models for OnMemOS SDK
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator, model_validator
from enum import Enum

from .base import OnMemOSModel


class StorageType(str, Enum):
    """Storage types supported by OnMemOS (matching server)"""
    EPHEMERAL = "ephemeral"
    PERSISTENT_VOLUME = "persistent_volume"
    GCS_FUSE = "gcs_fuse"


class StorageClass(str, Enum):
    """Kubernetes storage classes"""
    STANDARD = "standard"
    STANDARD_RWO = "standard-rwo"
    FAST_SSD = "fast-ssd"
    PREMIUM_SSD = "premium-ssd"


class AdditionalStorage(OnMemOSModel):
    """Configuration for additional storage mounts"""
    storage_type: StorageType = Field(..., description="Type of storage")
    mount_path: str = Field(..., description="Path where storage will be mounted")
    
    # GCS FUSE specific fields
    bucket_name: Optional[str] = Field(None, description="GCS bucket name")
    gcs_mount_options: Optional[str] = Field(None, description="GCS FUSE mount options")
    

    
    # Generic fields
    read_only: bool = Field(False, description="Mount as read-only")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @model_validator(mode='after')
    def validate_storage_type_fields(self):
        """Validate that required fields are present for each storage type"""
        if self.storage_type == StorageType.GCS_FUSE:
            if not self.bucket_name:
                raise ValueError("bucket_name is required for GCS_FUSE storage")
        elif self.storage_type == StorageType.FILESTORE:
            if not self.filestore_instance:
                raise ValueError("filestore_instance is required for FILESTORE storage")
        return self


class StorageConfig(OnMemOSModel):
    """Complete storage configuration for a session"""
    storage_type: StorageType = Field(..., description="Primary storage type")
    mount_path: str = Field(..., description="Primary mount path")
    
    # Persistent volume specific fields
    pvc_name: Optional[str] = Field(None, description="Persistent Volume Claim name")
    pvc_size: Optional[str] = Field(None, description="PVC size (e.g., '10Gi')")
    storage_class: Optional[StorageClass] = Field(None, description="Storage class")
    
    # GCS FUSE specific fields (for primary storage)
    bucket_name: Optional[str] = Field(None, description="GCS bucket name")
    gcs_mount_options: Optional[str] = Field(None, description="GCS FUSE mount options")
    
    # Filestore specific fields (for primary storage)
    filestore_instance: Optional[str] = Field(None, description="Filestore instance name")
    filestore_share: Optional[str] = Field(None, description="Filestore share name")
    
    # Additional storage mounts
    additional_storage: List[AdditionalStorage] = Field(
        default_factory=list, 
        description="Additional storage mounts"
    )
    
    # Generic fields
    read_only: bool = Field(False, description="Mount as read-only")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @model_validator(mode='after')
    def validate_storage_config(self):
        """Validate storage configuration after all fields are set"""
        if self.storage_type == StorageType.PERSISTENT_VOLUME:
            if not self.pvc_name:
                raise ValueError("pvc_name is required for PERSISTENT_VOLUME storage")
            if not self.pvc_size:
                raise ValueError("pvc_size is required for PERSISTENT_VOLUME storage")
        elif self.storage_type == StorageType.GCS_FUSE:
            if not self.bucket_name:
                raise ValueError("bucket_name is required for GCS_FUSE storage")
        elif self.storage_type == StorageType.FILESTORE:
            if not self.filestore_instance:
                raise ValueError("filestore_instance is required for FILESTORE storage")
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format expected by server"""
        result = {
            "storage_type": self.storage_type.value if hasattr(self.storage_type, 'value') else str(self.storage_type),
            "mount_path": self.mount_path,
            "read_only": self.read_only
        }
        
        # Add type-specific fields
        if self.storage_type == StorageType.PERSISTENT_VOLUME:
            result.update({
                "pvc_name": self.pvc_name,
                "pvc_size": self.pvc_size,
                "storage_class": self.storage_class.value if self.storage_class and hasattr(self.storage_class, 'value') else str(self.storage_class) if self.storage_class else None
            })
        elif self.storage_type == StorageType.GCS_FUSE:
            result.update({
                "bucket_name": self.bucket_name,
                "gcs_mount_options": self.gcs_mount_options
            })
        elif self.storage_type == StorageType.FILESTORE:
            result.update({
                "filestore_instance": self.filestore_instance,
                "filestore_share": self.filestore_share
            })
        
        # Add additional storage
        if self.additional_storage:
            result["additional_storage"] = [
                storage.dict(exclude_none=True) for storage in self.additional_storage
            ]
        
        # Add metadata
        if self.metadata:
            result["metadata"] = self.metadata
        
        return result


# Convenience functions for common storage configurations
def create_persistent_storage_config(
    mount_path: str = "/workspace",
    pvc_name: Optional[str] = None,
    pvc_size: str = "10Gi",
    storage_class: StorageClass = StorageClass.STANDARD_RWO,
    additional_storage: Optional[List[AdditionalStorage]] = None
) -> StorageConfig:
    """Create a persistent volume storage configuration"""
    if pvc_name is None:
        import time
        pvc_name = f"pvc-{int(time.time())}"
    
    return StorageConfig(
        storage_type=StorageType.PERSISTENT_VOLUME,
        mount_path=mount_path,
        pvc_name=pvc_name,
        pvc_size=pvc_size,
        storage_class=storage_class,
        additional_storage=additional_storage or []
    )


def create_gcs_storage_config(
    bucket_name: str,
    mount_path: str = "/data",
    gcs_mount_options: str = "implicit-dirs,file-mode=0644,dir-mode=0755",
    additional_storage: Optional[List[AdditionalStorage]] = None
) -> StorageConfig:
    """Create a GCS FUSE storage configuration"""
    return StorageConfig(
        storage_type=StorageType.GCS_FUSE,
        mount_path=mount_path,
        bucket_name=bucket_name,
        gcs_mount_options=gcs_mount_options,
        additional_storage=additional_storage or []
    )


def create_multi_storage_config(
    primary_storage: StorageConfig,
    additional_storage: List[AdditionalStorage]
) -> StorageConfig:
    """Create a multi-storage configuration"""
    return StorageConfig(
        storage_type=primary_storage.storage_type,
        mount_path=primary_storage.mount_path,
        pvc_name=primary_storage.pvc_name,
        pvc_size=primary_storage.pvc_size,
        storage_class=primary_storage.storage_class,
        bucket_name=primary_storage.bucket_name,
        gcs_mount_options=primary_storage.gcs_mount_options,
        filestore_instance=primary_storage.filestore_instance,
        filestore_share=primary_storage.filestore_share,
        additional_storage=additional_storage,
        read_only=primary_storage.read_only,
        metadata=primary_storage.metadata
    )
