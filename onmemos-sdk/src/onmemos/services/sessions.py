"""
Session service for OnMemOS SDK
"""

from typing import Optional, List, Dict, Any
from ..core.http import HTTPClient
from ..models.sessions import (
    CreateSessionRequest, Session, SessionList, SessionUpdateRequest,
    SessionMetrics, SessionLogs, SessionStatus
)
from ..core.exceptions import SessionError


class SessionService:
    """Session management service"""
    
    def __init__(self, http_client: HTTPClient):
        self.http_client = http_client
    
    async def create_session(self, request: CreateSessionRequest) -> Session:
        """Create a new session"""
        try:
            response = await self.http_client.post(
                "/v1/sessions/create",
                json=request.dict(exclude_none=True)
            )
            return Session(**response)
        except Exception as e:
            raise SessionError(f"Failed to create session: {e}")
    
    async def get_session(self, session_id: str) -> Session:
        """Get session details"""
        try:
            response = await self.http_client.get(f"/v1/sessions/{session_id}")
            return Session(**response)
        except Exception as e:
            raise SessionError(f"Failed to get session {session_id}: {e}")
    
    async def list_sessions(
        self,
        status: Optional[SessionStatus] = None,
        limit: int = 10,
        offset: int = 0
    ) -> SessionList:
        """List user sessions"""
        try:
            params = {"limit": limit, "offset": offset}
            if status:
                params["status"] = status.value
            
            response = await self.http_client.get("/v1/sessions", params=params)
            return SessionList(**response)
        except Exception as e:
            raise SessionError(f"Failed to list sessions: {e}")
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        try:
            await self.http_client.delete(f"/v1/sessions/{session_id}")
            return True
        except Exception as e:
            raise SessionError(f"Failed to delete session {session_id}: {e}")
    
    async def update_session(
        self,
        session_id: str,
        request: SessionUpdateRequest
    ) -> Session:
        """Update a session"""
        try:
            response = await self.http_client.patch(
                f"/v1/sessions/{session_id}",
                json=request.dict(exclude_none=True)
            )
            return Session(**response)
        except Exception as e:
            raise SessionError(f"Failed to update session {session_id}: {e}")
    
    async def pause_session(self, session_id: str) -> Session:
        """Pause a session"""
        try:
            response = await self.http_client.post(f"/v1/sessions/{session_id}/pause")
            return Session(**response)
        except Exception as e:
            raise SessionError(f"Failed to pause session {session_id}: {e}")
    
    async def resume_session(self, session_id: str) -> Session:
        """Resume a paused session"""
        try:
            response = await self.http_client.post(f"/v1/sessions/{session_id}/resume")
            return Session(**response)
        except Exception as e:
            raise SessionError(f"Failed to resume session {session_id}: {e}")
    
    async def scale_session(
        self,
        session_id: str,
        resource_tier: str
    ) -> Session:
        """Scale session resources"""
        try:
            response = await self.http_client.patch(
                f"/v1/sessions/{session_id}/scale",
                json={"resource_tier": resource_tier}
            )
            return Session(**response)
        except Exception as e:
            raise SessionError(f"Failed to scale session {session_id}: {e}")
    
    async def get_session_metrics(self, session_id: str) -> SessionMetrics:
        """Get session performance metrics"""
        try:
            response = await self.http_client.get(f"/v1/sessions/{session_id}/metrics")
            return SessionMetrics(**response)
        except Exception as e:
            raise SessionError(f"Failed to get metrics for session {session_id}: {e}")
    
    async def get_session_logs(
        self,
        session_id: str,
        log_type: str = "stdout",
        lines: int = 100
    ) -> SessionLogs:
        """Get session logs"""
        try:
            params = {"type": log_type, "lines": lines}
            response = await self.http_client.get(f"/v1/sessions/{session_id}/logs", params=params)
            return SessionLogs(**response)
        except Exception as e:
            raise SessionError(f"Failed to get logs for session {session_id}: {e}")
    
    async def wait_for_ready(self, session_id: str, timeout: int = 300) -> Session:
        """Wait for session to be ready"""
        # TODO: Implement polling logic
        raise NotImplementedError("wait_for_ready not yet implemented")
