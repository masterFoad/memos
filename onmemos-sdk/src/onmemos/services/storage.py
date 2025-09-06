"""
Storage service for OnMemOS SDK (Legacy - Storage is now configured during session creation)
"""

from typing import Optional, List, Dict, Any
from ..core.http import HTTPClient
from ..core.exceptions import StorageError


class StorageService:
    """Storage management service"""
    
    def __init__(self, http_client: HTTPClient):
        self.http_client = http_client
    
    async def mount_storage(self, session_id: str, request) -> Dict[str, Any]:
        """Mount storage to session (LEGACY - Use storage_config during session creation instead)"""
        raise StorageError("Storage mounting is now handled during session creation. Use storage_config parameter in CreateSessionRequest instead.")
    
    async def list_mounts(self, session_id: str) -> Dict[str, Any]:
        """List storage mounts for session (LEGACY - Storage is configured during session creation)"""
        raise StorageError("Storage listing is not available. Storage is configured during session creation.")
    
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
    
    async def list_files(self, session_id: str, path: str = "/workspace") -> Dict[str, Any]:
        """List files in session storage (LEGACY - Not implemented)"""
        raise StorageError("File listing is not implemented. File operations happen within the session environment.")
    
    async def upload_file(
        self,
        session_id: str,
        local_path: str,
        remote_path: str,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """Upload file to session storage (LEGACY - Not implemented)"""
        raise StorageError("File upload is not implemented. File operations happen within the session environment.")
    
    async def download_file(
        self,
        session_id: str,
        remote_path: str,
        local_path: str
    ) -> Dict[str, Any]:
        """Download file from session storage (LEGACY - Not implemented)"""
        raise StorageError("File download is not implemented. File operations happen within the session environment.")
    
    async def get_storage_usage(self, session_id: str) -> Dict[str, Any]:
        """Get storage usage information (LEGACY - Not implemented)"""
        raise StorageError("Storage usage is not implemented. Storage metrics are available through session metrics.")
