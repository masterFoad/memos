from __future__ import annotations

from typing import Dict, Any, List, Optional

from .http import HttpClient


class Vaults:
    """
    Vault (GCS bucket) management operations.
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def create_vault(
        self,
        dock_id: str,
        name: str,
        *,
        size_gb: int = 10,
        auto_mount: bool = True,
        mount_path: str = "/workspace",
        access_mode: str = "RW",
    ) -> Dict[str, Any]:
        """Create a reusable GCS bucket (vault) for a workspace"""
        body = {
            "workspace_id": dock_id,
            "name": name,
            "size_gb": size_gb,
            "auto_mount": auto_mount,
            "mount_path": mount_path,
            "access_mode": access_mode,
        }
        return self._http.request("POST", "/v1/storage/buckets", json=body)

    def list(self, dock_id: str) -> Dict[str, Any]:
        """List all vaults (buckets) for a workspace"""
        params = {"workspace_id": dock_id}
        return self._http.request("GET", "/v1/storage", params=params)

    def set_default(self, dock_id: str, vault_id: str) -> Dict[str, Any]:
        """Set a vault as the default for a workspace"""
        body = {"bucket_id": vault_id}
        return self._http.request("POST", f"/v1/storage/workspaces/{dock_id}/defaults", json=body)

    def update_flags(
        self,
        vault_id: str,
        *,
        is_default: Optional[bool] = None,
        auto_mount: Optional[bool] = None,
        mount_path: Optional[str] = None,
        access_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update vault flags and settings"""
        body = {}
        if is_default is not None:
            body["is_default"] = is_default
        if auto_mount is not None:
            body["auto_mount"] = auto_mount
        if mount_path is not None:
            body["mount_path"] = mount_path
        if access_mode is not None:
            body["access_mode"] = access_mode
        
        return self._http.request("PATCH", f"/v1/storage/{vault_id}", json=body)

    def delete(self, vault_id: str) -> Dict[str, Any]:
        """Delete a vault"""
        return self._http.request("DELETE", f"/v1/storage/{vault_id}")
