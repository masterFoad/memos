from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, Optional, List, Any

class CreateWorkspace(BaseModel):
    template: str = Field(..., examples=["python"])
    namespace: str
    user: str
    ttl_minutes: int = 180
    env: Dict[str, str] = {}
    bucket_mounts: Optional[List[Dict[str, Any]]] = None
    bucket_prefix: Optional[str] = None

# Alias for compatibility with server models
CreateWorkspaceRequest = CreateWorkspace

class ExecCode(BaseModel):
    code: str
    env: Dict[str, str] = {}
    timeout: float = 30.0

class BucketMountConfig(BaseModel):
    """Configuration for bucket mounting"""
    bucket_name: str
    mount_path: str = "/bucket"
    prefix: Optional[str] = None
    read_only: bool = False

class CreateBucketRequest(BaseModel):
    """Request to create a new bucket"""
    bucket_name: str
    namespace: str
    user: str
    region: Optional[str] = None
    storage_class: str = "STANDARD"

class BucketOperationRequest(BaseModel):
    """Request for bucket operations"""
    bucket_name: str
    operation: str  # "list", "upload", "download", "delete"
    path: Optional[str] = None
    prefix: Optional[str] = None
    recursive: bool = False

class WorkspaceInfo(BaseModel):
    id: str
    template: str
    namespace: str
    user: str
    shell_ws: str
    expires_at: str
    bucket_mounts: Optional[List[Dict[str, Any]]] = None
    bucket_prefix: Optional[str] = None

class BucketInfo(BaseModel):
    """Information about a bucket"""
    name: str
    namespace: str
    user: str
    region: Optional[str]
    storage_class: str
    created_at: str
    size_bytes: Optional[int] = None
    object_count: Optional[int] = None
