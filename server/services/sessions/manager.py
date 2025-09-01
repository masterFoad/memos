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

    async def create_session(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        req = CreateSessionRequest(**spec)
        
        # Apply template configuration if template_id is provided
        if req.template_id:
            await self._apply_template_configuration(req)
        
        provider = self._choose_provider(req)
        p = self._providers[provider]
        info = await p.create(req)
        self._sessions[info.id] = info
        return info.dict()
    
    async def _apply_template_configuration(self, req: CreateSessionRequest):
        """Apply template configuration to session request"""
        try:
            from server.models.session_templates import template_manager
            
            # Get template
            template = template_manager.get_template(req.template_id)
            if not template:
                raise ValueError(f"Template {req.template_id} not found")
            
            # Apply template configuration
            req.resource_tier = template.resource_tier
            req.image_spec = template.image_type
            req.gpu_spec = template.gpu_type
            
            # Apply storage configuration
            if template.storage_type == "gcs_fuse":
                req.request_bucket = True
                req.bucket_size_gb = template.storage_size_gb
            elif template.storage_type == "persistent_volume":
                req.request_persistent_storage = True
                req.persistent_storage_size_gb = template.storage_size_gb
            
            # Apply environment variables
            req.env.update(template.env_vars)
            
            # Apply TTL if not explicitly set
            if req.ttl_minutes == 60:  # Default value
                req.ttl_minutes = template.default_ttl_minutes
            
            # Increment template usage
            template_manager.increment_usage(req.template_id)
            
            logger.info(f"Applied template {req.template_id} to session request")
            
        except Exception as e:
            logger.error(f"Failed to apply template {req.template_id}: {e}")
            raise ValueError(f"Template configuration failed: {e}")

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

    async def delete_session(self, sid: str) -> bool:
        s = self._sessions.pop(sid, None)
        if not s:
            return False
        p = self._providers[s.provider]
        return await p.delete(s.id)

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
