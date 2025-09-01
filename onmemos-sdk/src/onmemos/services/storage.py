"""
Storage service for OnMemOS SDK
"""

from typing import Optional, List, Dict, Any
from ..core.http import HTTPClient
from ..models.storage import (
    MountRequest, Mount, MountList, FileInfo, FileList,
    UploadRequest, DownloadRequest, StorageUsage
)
from ..core.exceptions import StorageError


class StorageService:
    """Storage management service"""
    
    def __init__(self, http_client: HTTPClient):
        self.http_client = http_client
    
    async def mount_storage(self, session_id: str, request: MountRequest) -> Mount:
        """Mount storage to session"""
        try:
            response = await self.http_client.post(
                f"/v1/sessions/{session_id}/storage/mount",
                json=request.dict(exclude_none=True)
            )
            return Mount(**response)
        except Exception as e:
            raise StorageError(f"Failed to mount storage: {e}")
    
    async def list_mounts(self, session_id: str) -> MountList:
        """List storage mounts for session"""
        try:
            response = await self.http_client.get(f"/v1/sessions/{session_id}/storage/mounts")
            return MountList(**response)
        except Exception as e:
            raise StorageError(f"Failed to list mounts: {e}")
    
    async def unmount_storage(self, session_id: str, mount_path: str) -> bool:
        """Unmount storage from session"""
        try:
            await self.http_client.delete(
                f"/v1/sessions/{session_id}/storage/mounts",
                json={"mount_path": mount_path}
            )
            return True
        except Exception as e:
            raise StorageError(f"Failed to unmount storage: {e}")
    
    async def list_files(self, session_id: str, path: str = "/workspace") -> FileList:
        """List files in session storage"""
        try:
            params = {"path": path}
            response = await self.http_client.get(f"/v1/sessions/{session_id}/storage/files", params=params)
            return FileList(**response)
        except Exception as e:
            raise StorageError(f"Failed to list files: {e}")
    
    async def upload_file(
        self,
        session_id: str,
        local_path: str,
        remote_path: str,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """Upload file to session storage"""
        try:
            # TODO: Implement actual file upload
            response = await self.http_client.post(
                f"/v1/sessions/{session_id}/storage/upload",
                json={
                    "local_path": local_path,
                    "remote_path": remote_path,
                    "overwrite": overwrite
                }
            )
            return response
        except Exception as e:
            raise StorageError(f"Failed to upload file: {e}")
    
    async def download_file(
        self,
        session_id: str,
        remote_path: str,
        local_path: str
    ) -> Dict[str, Any]:
        """Download file from session storage"""
        try:
            # TODO: Implement actual file download
            response = await self.http_client.get(
                f"/v1/sessions/{session_id}/storage/download",
                params={
                    "remote_path": remote_path,
                    "local_path": local_path
                }
            )
            return response
        except Exception as e:
            raise StorageError(f"Failed to download file: {e}")
    
    async def get_storage_usage(self, session_id: str) -> StorageUsage:
        """Get storage usage information"""
        try:
            response = await self.http_client.get(f"/v1/sessions/{session_id}/storage/usage")
            return StorageUsage(**response)
        except Exception as e:
            raise StorageError(f"Failed to get storage usage: {e}")
