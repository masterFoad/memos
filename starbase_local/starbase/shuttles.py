from __future__ import annotations

from typing import Literal, Optional, Dict, Any, List

from .models import Shuttle, CommandResult, WSToken
from .http import HttpClient


class Shuttles:
    """
    Shuttle (session) operations.

    All methods are design-only and raise NotImplementedError.
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def launch(
        self,
        dock_id: str,
        *,
        provider: Literal["gke", "cloud_run"] = "gke",
        template_id: str = "dev-python",
        use_vault: bool = False,
        vault_size_gb: Optional[int] = None,
        vault_id: Optional[str] = None,
        vault_name: Optional[str] = None,
        use_drive: bool = False,
        drive_size_gb: Optional[int] = None,
        drive_id: Optional[str] = None,
        drive_name: Optional[str] = None,
        ttl_minutes: int = 60,
        env: Optional[Dict[str, str]] = None,
    ) -> Shuttle:
        body: Dict[str, Any] = {
            "workspace_id": dock_id,
            "provider": provider,
            "template": "python",  # to satisfy server's CreateSessionRequest
            "template_id": template_id,
            "namespace": dock_id,
            "ttl_minutes": ttl_minutes,
            "env": env or {},
        }
        
        # Handle reusable storage resources
        if vault_id or vault_name:
            body["vault_id"] = vault_id
            body["vault_name"] = vault_name
        elif use_vault:
            body["request_bucket"] = True
            body["bucket_size_gb"] = vault_size_gb
        
        if drive_id or drive_name:
            body["drive_id"] = drive_id
            body["drive_name"] = drive_name
        elif use_drive:
            body["request_persistent_storage"] = True
            body["persistent_storage_size_gb"] = drive_size_gb
        res = self._http.request("POST", "/v1/sessions", json=body)
        data = res.get("session") or res
        mounts = {
            "vault": bool(((data.get("storage_config") or {}).get("bucket_name")) or ((data.get("storage_status") or {}).get("bucket_name"))),
            "drive": bool(((data.get("storage_config") or {}).get("pvc_name")) or ((data.get("storage_status") or {}).get("pvc_name"))),
        }
        return Shuttle(
            id=data.get("id") or data.get("session_id"),
            dock_id=data.get("workspace_id"),
            provider=(data.get("provider") or "").lower(),
            status=data.get("status") or data.get("state") or "unknown",
            launchpad=(data.get("k8s_namespace") or (data.get("details") or {}).get("k8s_ns")),
            pod=(data.get("pod_name") or (data.get("details") or {}).get("pod")),
            mounts=mounts,
            created_at=data.get("created_at"),
            ttl_minutes=ttl_minutes,
        )

    def get(self, shuttle_id: str) -> Shuttle:
        res = self._http.request("GET", f"/v1/sessions/{shuttle_id}")
        data = res.get("session") or res
        mounts = {
            "vault": bool(((data.get("storage_config") or {}).get("bucket_name")) or ((data.get("storage_status") or {}).get("bucket_name"))),
            "drive": bool(((data.get("storage_config") or {}).get("pvc_name")) or ((data.get("storage_status") or {}).get("pvc_name"))),
        }
        return Shuttle(
            id=data.get("id") or data.get("session_id") or shuttle_id,
            dock_id=data.get("workspace_id"),
            provider=(data.get("provider") or "").lower(),
            status=data.get("status") or data.get("state") or "unknown",
            launchpad=(data.get("k8s_namespace") or (data.get("details") or {}).get("k8s_ns")),
            pod=(data.get("pod_name") or (data.get("details") or {}).get("pod")),
            mounts=mounts,
            created_at=data.get("created_at"),
            ttl_minutes=data.get("ttl_minutes"),
        )

    def list(self) -> List[Shuttle]:
        res = self._http.request("GET", "/v1/sessions")
        items = res.get("sessions") or []
        out: List[Shuttle] = []
        for data in items:
            mounts = {
                "vault": bool(((data.get("storage_config") or {}).get("bucket_name")) or ((data.get("storage_status") or {}).get("bucket_name"))),
                "drive": bool(((data.get("storage_config") or {}).get("pvc_name")) or ((data.get("storage_status") or {}).get("pvc_name"))),
            }
            out.append(Shuttle(
                id=data.get("id") or data.get("session_id"),
                dock_id=data.get("workspace_id"),
                provider=(data.get("provider") or "").lower(),
                status=data.get("status") or data.get("state") or "unknown",
                launchpad=(data.get("k8s_namespace") or (data.get("details") or {}).get("k8s_ns")),
                pod=(data.get("pod_name") or (data.get("details") or {}).get("pod")),
                mounts=mounts,
                created_at=data.get("created_at"),
                ttl_minutes=data.get("ttl_minutes"),
            ))
        return out

    def terminate(self, shuttle_id: str) -> None:
        self._http.request("DELETE", f"/v1/sessions/{shuttle_id}")
        return None

    def execute(self, shuttle_id: str, command: str, *, timeout_s: int = 120) -> CommandResult:
        params = {"command": command, "timeout": str(int(timeout_s)), "async_execution": "false"}
        res = self._http.request("POST", f"/v1/sessions/{shuttle_id}/execute", params=params)
        return CommandResult(
            stdout=(res.get("stdout") or ""),
            stderr=(res.get("stderr") or ""),
            returncode=int(res.get("returncode") or 0),
        )

    def ws_token(self, shuttle_id: str) -> WSToken:
        res = self._http.request("POST", f"/v1/sessions/{shuttle_id}/ws-token")
        return WSToken(token=res.get("token"), expires_in=int(res.get("expires_in") or 0))


