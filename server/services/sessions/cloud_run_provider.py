# server/services/sessions/cloud_run_provider.py
from __future__ import annotations
from typing import Optional, Dict, Any
from server.services.sessions.base import SessionProviderBase
from server.models.sessions import SessionInfo, CreateSessionRequest, SessionProvider
from server.services.cloudrun.cloudrun_service import cloudrun_service


class CloudRunSessionProvider(SessionProviderBase):
    def create(self, req: CreateSessionRequest) -> SessionInfo:
        ws = cloudrun_service.create_workspace(req.template, req.namespace, req.user, req.ttl_minutes, req.storage)
        return SessionInfo(
            id=ws["id"],
            provider=SessionProvider.cloud_run,
            namespace=req.namespace,
            user=req.user,
            workspace_id=req.workspace_id,
            status=ws["status"],
            url=ws["service_url"],
            websocket=f"/v1/cloudrun/workspaces/{ws['id']}/shell",  # if you have that websocket
            ssh=False,
            details=ws,
        )

    def get(self, session_id: str) -> Optional[SessionInfo]:
        ws = cloudrun_service.get_workspace(session_id)
        if not ws:
            return None
        return SessionInfo(
            id=ws["id"],
            provider=SessionProvider.cloud_run,
            namespace=ws["namespace"],
            user=ws["user"],
            workspace_id=ws.get("workspace_id", "unknown"),  # Fallback for existing sessions
            status=ws["status"],
            url=ws["service_url"],
            websocket=f"/v1/cloudrun/workspaces/{ws['id']}/shell",
            ssh=False,
            details=ws,
        )

    def delete(self, session_id: str) -> bool:
        return cloudrun_service.delete_workspace(session_id)

    def execute(self, session_id: str, command: str, timeout: int = 120) -> Dict[str, Any]:
        return cloudrun_service.execute_in_workspace(session_id, command, timeout)
