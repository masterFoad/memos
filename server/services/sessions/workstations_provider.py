# server/services/sessions/workstations_provider.py
from __future__ import annotations
from typing import Optional, Dict, Any
from server.services.sessions.base import SessionProviderBase
from server.models.sessions import SessionInfo, CreateSessionRequest, SessionProvider
from server.services.workstations.workstations_service import workstations_service


class WorkstationsSessionProvider(SessionProviderBase):
    def __init__(self) -> None:
        # session_id -> ws_name
        self._map: Dict[str, str] = {}

    def create(self, req: CreateSessionRequest) -> SessionInfo:
        ws = workstations_service.create_workspace(
            namespace=req.namespace,
            user=req.user,
            bucket_name=req.storage.get("bucket") if req.storage else None,
            filestore_ip=(req.storage or {}).get("filestore", {}).get("ip"),
            filestore_share=(req.storage or {}).get("filestore", {}).get("share", "workspace"),
        )
        sid = ws["workstation_name"]
        self._map[sid] = sid
        return SessionInfo(
            id=sid,
            provider=SessionProvider.workstations,
            namespace=req.namespace,
            user=req.user,
            status=ws["status"],
            url=ws.get("url"),
            ssh=bool(ws.get("ssh")),
            details=ws,
        )

    def get(self, session_id: str) -> Optional[SessionInfo]:
        if session_id not in self._map:
            return None
        ws = workstations_service.get_workspace(session_id)
        if not ws:
            return None
        return SessionInfo(
            id=session_id,
            provider=SessionProvider.workstations,
            namespace="",
            user="",
            status=ws.get("status", "UNKNOWN"),
            url=ws.get("url"),
            ssh=True,
            details=ws,
        )

    def delete(self, session_id: str) -> bool:
        if session_id not in self._map:
            return False
        workstations_service.delete_workspace(session_id)
        self._map.pop(session_id, None)
        return True

    # No execute() for Workstations; interactive via URL/SSH
