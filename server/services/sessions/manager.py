# server/services/sessions/manager.py
from __future__ import annotations
import time
import uuid
import logging
from typing import Dict, Any, Optional

from server.models.sessions import CreateSessionRequest, SessionInfo, SessionProvider
from server.services.sessions.base import SessionProviderBase
from server.services.sessions.cloud_run_provider import CloudRunSessionProvider
from server.services.sessions.gke_provider import GkeSessionProvider
from server.services.sessions.workstations_provider import WorkstationsSessionProvider

logger = logging.getLogger(__name__)


class SessionsManager:
    def __init__(self) -> None:
        self._sessions: Dict[str, SessionInfo] = {}
        self._providers: Dict[SessionProvider, SessionProviderBase] = {
            SessionProvider.cloud_run: CloudRunSessionProvider(),
            SessionProvider.gke: GkeSessionProvider(),
            SessionProvider.workstations: WorkstationsSessionProvider(),
        }

    def _choose_provider(self, req: CreateSessionRequest) -> SessionProvider:
        if req.provider != SessionProvider.auto:
            return req.provider
        if req.needs_ssh or (req.expected_duration_minutes and req.expected_duration_minutes > 60):
            return SessionProvider.workstations
        if req.long_lived:
            return SessionProvider.gke
        return SessionProvider.cloud_run

    def create_session(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        req = CreateSessionRequest(**spec)
        provider = self._choose_provider(req)
        p = self._providers[provider]
        info = p.create(req)
        self._sessions[info.id] = info
        return info.dict()

    def list_sessions(self) -> Dict[str, Any]:
        """List all active sessions"""
        sessions = []
        for sid, session in self._sessions.items():
            # refresh if provider supports it
            p = self._providers[session.provider]
            fresh = p.get(session.id) or session
            self._sessions[sid] = fresh
            sessions.append(fresh.dict())
        return {"sessions": sessions, "count": len(sessions)}

    def get_session(self, sid: str) -> Optional[Dict[str, Any]]:
        s = self._sessions.get(sid)
        if not s:
            return None
        # refresh if provider supports it
        p = self._providers[s.provider]
        fresh = p.get(s.id) or s
        self._sessions[sid] = fresh
        return fresh.dict()

    def delete_session(self, sid: str) -> bool:
        s = self._sessions.pop(sid, None)
        if not s:
            return False
        p = self._providers[s.provider]
        return p.delete(s.id)

    def execute(self, sid: str, command: str, timeout: int = 120, async_execution: bool = False) -> Dict[str, Any]:
        s = self._sessions.get(sid)
        if not s:
            # Try to refresh from all providers
            for provider_type, provider in self._providers.items():
                try:
                    fresh_session = provider.get(sid)
                    if fresh_session:
                        self._sessions[sid] = fresh_session
                        s = fresh_session
                        logger.info(f"✅ Refreshed session {sid} from {provider_type}")
                        break
                except Exception as e:
                    logger.warning(f"Failed to refresh session {sid} from {provider_type}: {e}")
                    continue
        
        if not s:
            raise ValueError("Session not found")
        p = self._providers[s.provider]
        
        # Check if provider supports async execution
        if async_execution and hasattr(p, 'execute'):
            # For GKE provider, pass async_execution parameter
            if s.provider == "gke":
                return p.execute(s.id, command, timeout, async_execution=True)
            # For Cloud Run, it's already async
            elif s.provider == "cloud_run":
                return p.execute(s.id, command, timeout)
            else:
                # Fallback to sync execution
                return p.execute(s.id, command, timeout)
        else:
            return p.execute(s.id, command, timeout)

    def get_job_status(self, job_id: str, job_name: str, session_id: str) -> Dict[str, Any]:
        """Get status of a submitted job"""
        s = self._sessions.get(session_id)
        if not s:
            raise ValueError("Session not found")
        
        p = self._providers[s.provider]
        if hasattr(p, 'get_job_status'):
            return p.get_job_status(job_id, job_name, session_id)
        else:
            raise ValueError(f"Provider {s.provider} does not support job status checking")

    def connect_info(self, sid: str) -> Dict[str, Any]:
        s = self._sessions.get(sid)
        if not s:
            return {}
        return {"url": s.url, "websocket": s.websocket, "ssh": s.ssh}


sessions_manager = SessionsManager()
