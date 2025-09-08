"""
Storage Management API for OnMemOS v3
User-facing endpoints for managing reusable storage resources (buckets, filestores)
"""

import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..core.security import require_passport
from ..database.base import StorageType
from ..database.factory import get_database_client_async

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/storage", tags=["storage"])

# ============================================================================
# Request/Response Models
# ============================================================================

class CreateBucketRequest(BaseModel):
    workspace_id: str
    name: str
    size_gb: int = 10
    auto_mount: bool = True
    mount_path: str = "/workspace"
    access_mode: str = "RW"

class CreateFilestoreRequest(BaseModel):
    workspace_id: str
    name: str
    size_gb: int = 10
    auto_mount: bool = True
    mount_path: str = "/data"
    access_mode: str = "RW"

class UpdateStorageRequest(BaseModel):
    is_default: Optional[bool] = None
    auto_mount: Optional[bool] = None
    mount_path: Optional[str] = None
    access_mode: Optional[str] = None

class SetDefaultsRequest(BaseModel):
    bucket_id: Optional[str] = None
    filestore_id: Optional[str] = None

# ============================================================================
# Storage Management Endpoints
# ============================================================================

@router.post("/buckets")
async def create_bucket(
    request: CreateBucketRequest,
    user: dict = Depends(require_passport)
) -> Dict[str, Any]:
    """Create a reusable GCS bucket for a workspace"""
    try:
        db = await get_database_client_async()
        
        # Verify workspace ownership
        workspace = await db.get_workspace(request.workspace_id)
        if not workspace or workspace.get('user_id') != user.get('user_id'):
            raise HTTPException(403, "Workspace not found or access denied")
        
        # Check storage quota
        can_create = await db.check_user_storage_quota(user['user_id'], StorageType.GCS_BUCKET)
        if not can_create:
            raise HTTPException(403, "Storage quota exceeded")
        
        # Create storage resource
        resource = await db.create_storage_resource(
            user_id=user['user_id'],
            storage_type=StorageType.GCS_BUCKET,
            resource_name=request.name,
            size_gb=request.size_gb
        )
        
        # Associate with workspace
        await db.assign_storage_to_workspace(resource['resource_id'], request.workspace_id)
        
        # Set flags
        await db.update_storage_flags(
            resource_id=resource['resource_id'],
            auto_mount=request.auto_mount,
            mount_path=request.mount_path,
            access_mode=request.access_mode
        )
        
        # If this is the first bucket for the workspace, make it default
        existing_buckets = await db.list_workspace_storage(request.workspace_id)
        bucket_count = len([r for r in existing_buckets if r['storage_type'] == StorageType.GCS_BUCKET.value])
        if bucket_count == 1:
            await db.set_workspace_default_storage(request.workspace_id, resource['resource_id'])
        
        return {
            "resource_id": resource['resource_id'],
            "name": request.name,
            "storage_type": "bucket",
            "size_gb": request.size_gb,
            "workspace_id": request.workspace_id,
            "auto_mount": request.auto_mount,
            "mount_path": request.mount_path,
            "access_mode": request.access_mode,
            "is_default": bucket_count == 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_bucket failed: {e}")
        raise HTTPException(500, f"create_bucket failed: {e}")

@router.post("/filestores")
async def create_filestore(
    request: CreateFilestoreRequest,
    user: dict = Depends(require_passport)
) -> Dict[str, Any]:
    """Create a reusable Filestore PVC for a workspace"""
    try:
        db = await get_database_client_async()
        
        # Verify workspace ownership
        workspace = await db.get_workspace(request.workspace_id)
        if not workspace or workspace.get('user_id') != user.get('user_id'):
            raise HTTPException(403, "Workspace not found or access denied")
        
        # Check storage quota
        can_create = await db.check_user_storage_quota(user['user_id'], StorageType.FILESTORE_PVC)
        if not can_create:
            raise HTTPException(403, "Storage quota exceeded")
        
        # Create storage resource
        resource = await db.create_storage_resource(
            user_id=user['user_id'],
            storage_type=StorageType.FILESTORE_PVC,
            resource_name=request.name,
            size_gb=request.size_gb
        )
        
        # Associate with workspace
        await db.assign_storage_to_workspace(resource['resource_id'], request.workspace_id)
        
        # Set flags
        await db.update_storage_flags(
            resource_id=resource['resource_id'],
            auto_mount=request.auto_mount,
            mount_path=request.mount_path,
            access_mode=request.access_mode
        )
        
        # If this is the first filestore for the workspace, make it default
        existing_filestores = await db.list_workspace_storage(request.workspace_id)
        filestore_count = len([r for r in existing_filestores if r['storage_type'] == StorageType.FILESTORE_PVC.value])
        if filestore_count == 1:
            await db.set_workspace_default_storage(request.workspace_id, resource['resource_id'])
        
        return {
            "resource_id": resource['resource_id'],
            "name": request.name,
            "storage_type": "filestore",
            "size_gb": request.size_gb,
            "workspace_id": request.workspace_id,
            "auto_mount": request.auto_mount,
            "mount_path": request.mount_path,
            "access_mode": request.access_mode,
            "is_default": filestore_count == 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_filestore failed: {e}")
        raise HTTPException(500, f"create_filestore failed: {e}")

@router.get("/")
async def list_storage(
    workspace_id: str = Query(..., description="Workspace ID to list storage for"),
    user: dict = Depends(require_passport)
) -> Dict[str, Any]:
    """List all storage resources for a workspace"""
    try:
        db = await get_database_client_async()
        
        # Verify workspace ownership
        workspace = await db.get_workspace(workspace_id)
        if not workspace or workspace.get('user_id') != user.get('user_id'):
            raise HTTPException(403, "Workspace not found or access denied")
        
        # Get storage resources
        resources = await db.list_workspace_storage(workspace_id)
        
        # Get defaults
        defaults = await db.get_workspace_defaults(workspace_id)
        
        return {
            "workspace_id": workspace_id,
            "resources": resources,
            "defaults": {
                "bucket_id": defaults.get('bucket', {}).get('resource_id') if defaults.get('bucket') else None,
                "filestore_id": defaults.get('filestore', {}).get('resource_id') if defaults.get('filestore') else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_storage failed: {e}")
        raise HTTPException(500, f"list_storage failed: {e}")

@router.patch("/{resource_id}")
async def update_storage(
    resource_id: str,
    request: UpdateStorageRequest,
    user: dict = Depends(require_passport)
) -> Dict[str, Any]:
    """Update storage resource flags and settings"""
    try:
        db = await get_database_client_async()
        
        # Get resource and verify ownership
        resource = await db._execute_single(
            "SELECT * FROM storage_resources WHERE resource_id = ?",
            (resource_id,)
        )
        if not resource or resource.get('user_id') != user.get('user_id'):
            raise HTTPException(403, "Storage resource not found or access denied")
        
        # Update flags
        success = await db.update_storage_flags(
            resource_id=resource_id,
            is_default=request.is_default,
            auto_mount=request.auto_mount,
            mount_path=request.mount_path,
            access_mode=request.access_mode
        )
        
        if not success:
            raise HTTPException(500, "Failed to update storage resource")
        
        # Return updated resource
        updated_resource = await db._execute_single(
            "SELECT * FROM storage_resources WHERE resource_id = ?",
            (resource_id,)
        )
        
        return updated_resource
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_storage failed: {e}")
        raise HTTPException(500, f"update_storage failed: {e}")

@router.delete("/{resource_id}")
async def delete_storage(
    resource_id: str,
    user: dict = Depends(require_passport)
) -> Dict[str, Any]:
    """Delete a storage resource"""
    try:
        db = await get_database_client_async()
        
        # Get resource and verify ownership
        resource = await db._execute_single(
            "SELECT * FROM storage_resources WHERE resource_id = ?",
            (resource_id,)
        )
        if not resource or resource.get('user_id') != user.get('user_id'):
            raise HTTPException(403, "Storage resource not found or access denied")
        
        # Delete resource
        success = await db.delete_storage_resource(resource_id)
        
        if not success:
            raise HTTPException(500, "Failed to delete storage resource")
        
        return {"message": "Storage resource deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_storage failed: {e}")
        raise HTTPException(500, f"delete_storage failed: {e}")

# ============================================================================
# Workspace Defaults Management
# ============================================================================

@router.post("/workspaces/{workspace_id}/defaults")
async def set_workspace_defaults(
    workspace_id: str,
    request: SetDefaultsRequest,
    user: dict = Depends(require_passport)
) -> Dict[str, Any]:
    """Set default storage resources for a workspace"""
    try:
        db = await get_database_client_async()
        
        # Verify workspace ownership
        workspace = await db.get_workspace(workspace_id)
        if not workspace or workspace.get('user_id') != user.get('user_id'):
            raise HTTPException(403, "Workspace not found or access denied")
        
        results = {}
        
        # Set default bucket if provided
        if request.bucket_id:
            success = await db.set_workspace_default_storage(workspace_id, request.bucket_id)
            if not success:
                raise HTTPException(400, "Invalid bucket resource or not owned by workspace")
            results["bucket_set"] = True
        
        # Set default filestore if provided
        if request.filestore_id:
            success = await db.set_workspace_default_storage(workspace_id, request.filestore_id)
            if not success:
                raise HTTPException(400, "Invalid filestore resource or not owned by workspace")
            results["filestore_set"] = True
        
        # Get updated defaults
        defaults = await db.get_workspace_defaults(workspace_id)
        
        return {
            "workspace_id": workspace_id,
            "defaults": {
                "bucket_id": defaults.get('bucket', {}).get('resource_id') if defaults.get('bucket') else None,
                "filestore_id": defaults.get('filestore', {}).get('resource_id') if defaults.get('filestore') else None
            },
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"set_workspace_defaults failed: {e}")
        raise HTTPException(500, f"set_workspace_defaults failed: {e}")
