"""
Storage models for OnMemOS SDK
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from datetime import datetime

from .base import OnMemOSModel, MountType


class MountRequest(OnMemOSModel):
    """Request model for mounting storage"""
    mount_type: MountType = Field(..., description="Type of storage to mount")
    source_name: str = Field(..., description="Storage source name (bucket/filestore)")
    mount_path: str = Field(..., description="Mount path in container")
    read_only: bool = Field(False, description="Mount as read-only")
    options: Dict[str, Any] = Field(default_factory=dict, description="Mount options")
    
    @validator('mount_path')
    def validate_mount_path(cls, v):
        """Validate mount path"""
        if not v.startswith('/'):
            raise ValueError("Mount path must be absolute (start with /)")
        if v in ['/', '/root', '/home', '/etc', '/var', '/usr']:
            raise ValueError(f"Cannot mount to system directory: {v}")
        return v


class Mount(OnMemOSModel):
    """Storage mount model"""
    mount_id: str = Field(..., description="Unique mount identifier")
    session_id: str = Field(..., description="Associated session ID")
    mount_type: MountType = Field(..., description="Storage type")
    source_name: str = Field(..., description="Storage source name")
    mount_path: str = Field(..., description="Mount path in container")
    read_only: bool = Field(..., description="Read-only flag")
    status: str = Field(..., description="Mount status")
    created_at: datetime = Field(..., description="Mount timestamp")
    options: Dict[str, Any] = Field(default_factory=dict, description="Mount options")
    
    # Mount-specific fields
    bucket_name: Optional[str] = Field(None, description="GCS bucket name")
    filestore_name: Optional[str] = Field(None, description="Filestore name")
    persistent_volume_name: Optional[str] = Field(None, description="Persistent volume name")
    
    @property
    def is_active(self) -> bool:
        """Check if mount is active"""
        return self.status in ["mounted", "active", "ready"]
    
    @property
    def is_gcs_bucket(self) -> bool:
        """Check if this is a GCS bucket mount"""
        return self.mount_type == MountType.GCS_BUCKET
    
    @property
    def is_filestore(self) -> bool:
        """Check if this is a filestore mount"""
        return self.mount_type == MountType.FILESTORE
    
    @property
    def is_persistent_volume(self) -> bool:
        """Check if this is a persistent volume mount"""
        return self.mount_type == MountType.PERSISTENT_VOLUME


class MountList(OnMemOSModel):
    """List of mounts"""
    mounts: List[Mount] = Field(..., description="List of mounts")
    total: int = Field(..., description="Total number of mounts")
    
    @property
    def active_mounts(self) -> List[Mount]:
        """Get only active mounts"""
        return [m for m in self.mounts if m.is_active]
    
    @property
    def gcs_mounts(self) -> List[Mount]:
        """Get only GCS bucket mounts"""
        return [m for m in self.mounts if m.is_gcs_bucket]
    
    @property
    def filestore_mounts(self) -> List[Mount]:
        """Get only filestore mounts"""
        return [m for m in self.mounts if m.is_filestore]


class FileInfo(OnMemOSModel):
    """File information model"""
    name: str = Field(..., description="File name")
    path: str = Field(..., description="File path")
    size: int = Field(..., description="File size in bytes")
    is_directory: bool = Field(..., description="Is directory flag")
    modified_at: datetime = Field(..., description="Last modification time")
    permissions: str = Field(..., description="File permissions")
    owner: str = Field(..., description="File owner")
    mount_path: Optional[str] = Field(None, description="Associated mount path")
    
    @property
    def size_mb(self) -> float:
        """File size in MB"""
        return self.size / (1024 * 1024)
    
    @property
    def size_gb(self) -> float:
        """File size in GB"""
        return self.size / (1024 * 1024 * 1024)
    
    @property
    def is_file(self) -> bool:
        """Check if this is a file"""
        return not self.is_directory
    
    @property
    def extension(self) -> Optional[str]:
        """Get file extension"""
        if self.is_directory:
            return None
        parts = self.name.split('.')
        return parts[-1] if len(parts) > 1 else None


class FileList(OnMemOSModel):
    """List of files with directory information"""
    files: List[FileInfo] = Field(..., description="List of files")
    directory: str = Field(..., description="Current directory path")
    total_files: int = Field(..., description="Total number of files")
    total_directories: int = Field(..., description="Total number of directories")
    total_size: int = Field(..., description="Total size in bytes")
    
    @property
    def directories(self) -> List[FileInfo]:
        """Get only directories"""
        return [f for f in self.files if f.is_directory]
    
    @property
    def regular_files(self) -> List[FileInfo]:
        """Get only regular files"""
        return [f for f in self.files if f.is_file]
    
    @property
    def total_size_mb(self) -> float:
        """Total size in MB"""
        return self.total_size / (1024 * 1024)
    
    @property
    def total_size_gb(self) -> float:
        """Total size in GB"""
        return self.total_size / (1024 * 1024 * 1024)


class UploadRequest(OnMemOSModel):
    """File upload request"""
    local_path: str = Field(..., description="Local file path")
    remote_path: str = Field(..., description="Remote file path")
    overwrite: bool = Field(False, description="Overwrite existing file")
    chunk_size: int = Field(8192, ge=1024, le=1048576, description="Upload chunk size")
    
    @validator('local_path')
    def validate_local_path(cls, v):
        """Validate local file path"""
        from pathlib import Path
        path = Path(v)
        if not path.exists():
            raise ValueError(f"Local file does not exist: {v}")
        if not path.is_file():
            raise ValueError(f"Local path is not a file: {v}")
        return str(path.absolute())
    
    @validator('remote_path')
    def validate_remote_path(cls, v):
        """Validate remote file path"""
        if not v.startswith('/'):
            raise ValueError("Remote path must be absolute (start with /)")
        return v


class DownloadRequest(OnMemOSModel):
    """File download request"""
    remote_path: str = Field(..., description="Remote file path")
    local_path: str = Field(..., description="Local file path")
    chunk_size: int = Field(8192, ge=1024, le=1048576, description="Download chunk size")
    
    @validator('remote_path')
    def validate_remote_path(cls, v):
        """Validate remote file path"""
        if not v.startswith('/'):
            raise ValueError("Remote path must be absolute (start with /)")
        return v
    
    @validator('local_path')
    def validate_local_path(cls, v):
        """Validate local file path"""
        from pathlib import Path
        path = Path(v)
        parent = path.parent
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)
        return str(path.absolute())


class StorageUsage(OnMemOSModel):
    """Storage usage information"""
    session_id: str = Field(..., description="Session identifier")
    total_size_gb: float = Field(..., description="Total storage size in GB")
    used_size_gb: float = Field(..., description="Used storage size in GB")
    available_size_gb: float = Field(..., description="Available storage size in GB")
    mount_count: int = Field(..., description="Number of active mounts")
    file_count: int = Field(..., description="Total number of files")
    directory_count: int = Field(..., description="Total number of directories")
    timestamp: datetime = Field(..., description="Usage timestamp")
    
    @property
    def usage_percent(self) -> float:
        """Calculate storage usage percentage"""
        if self.total_size_gb == 0:
            return 0.0
        return (self.used_size_gb / self.total_size_gb) * 100
    
    @property
    def is_near_limit(self) -> bool:
        """Check if storage usage is near limit (80%+)"""
        return self.usage_percent >= 80.0
    
    @property
    def is_full(self) -> bool:
        """Check if storage is full (95%+)"""
        return self.usage_percent >= 95.0


class BucketInfo(OnMemOSModel):
    """GCS bucket information"""
    bucket_name: str = Field(..., description="Bucket name")
    location: str = Field(..., description="Bucket location")
    storage_class: str = Field(..., description="Storage class")
    created_at: datetime = Field(..., description="Creation timestamp")
    size_gb: float = Field(..., description="Bucket size in GB")
    object_count: int = Field(..., description="Number of objects")
    is_public: bool = Field(..., description="Is public bucket")
    labels: Dict[str, str] = Field(default_factory=dict, description="Bucket labels")
    
    @property
    def size_mb(self) -> float:
        """Bucket size in MB"""
        return self.size_gb * 1024
    
    @property
    def size_bytes(self) -> int:
        """Bucket size in bytes"""
        return int(self.size_gb * 1024 * 1024 * 1024)


class FilestoreInfo(OnMemOSModel):
    """Filestore information"""
    filestore_name: str = Field(..., description="Filestore name")
    location: str = Field(..., description="Filestore location")
    tier: str = Field(..., description="Performance tier")
    capacity_gb: int = Field(..., description="Capacity in GB")
    used_gb: int = Field(..., description="Used space in GB")
    created_at: datetime = Field(..., description="Creation timestamp")
    network: str = Field(..., description="Network name")
    labels: Dict[str, str] = Field(default_factory=dict, description="Filestore labels")
    
    @property
    def available_gb(self) -> int:
        """Available space in GB"""
        return self.capacity_gb - self.used_gb
    
    @property
    def usage_percent(self) -> float:
        """Usage percentage"""
        if self.capacity_gb == 0:
            return 0.0
        return (self.used_gb / self.capacity_gb) * 100
