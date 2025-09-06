# server/services/sessions/manager.py
from __future__ import annotations
import time
import uuid
import logging
import inspect
import asyncio
from typing import Dict, Any, Optional

from server.models.sessions import CreateSessionRequest, SessionInfo, SessionProvider
from server.services.sessions.base import SessionProviderBase
from server.services.sessions.cloud_run_provider import CloudRunSessionProvider
from server.services.sessions.gke_provider import GkeSessionProvider
# NOTE: WorkstationsSessionProvider removed - only Cloud Run and GKE Autopilot supported

logger = logging.getLogger(__name__)


class SessionsManager:
    def __init__(self) -> None:
        self._sessions: Dict[str, SessionInfo] = {}
        self._providers: Dict[SessionProvider, SessionProviderBase] = {
            SessionProvider.cloud_run: CloudRunSessionProvider(),
            SessionProvider.gke: GkeSessionProvider(),
            # NOTE: Workstations provider removed - we only support Cloud Run and GKE Autopilot
        }
        self._startup_restoration_done = False

    # -------------------- internals -------------------- #

    def _normalize_provider(self, provider_val: Any) -> Optional[SessionProvider]:
        """Accepts enum, enum name, or value string; returns SessionProvider or None."""
        if isinstance(provider_val, SessionProvider):
            return provider_val
        if provider_val is None:
            return None
        # Try value (e.g. "gke", "cloud_run")
        try:
            return SessionProvider(provider_val)  # type: ignore[arg-type]
        except Exception:
            pass
        # Try name (e.g. "gke".upper() -> "GKE")
        try:
            return SessionProvider[ str(provider_val).upper() ]  # type: ignore[index]
        except Exception:
            return None

    # -------------------- restoration -------------------- #

    async def _ensure_startup_restoration(self):
        """Restore sessions from database on server startup (only once)"""
        if self._startup_restoration_done:
            return
        
        try:
            logger.info("🔄 Restoring sessions from database on startup...")
            from server.database.factory import get_database_client_async
            db = await get_database_client_async()
            db_sessions = await db.list_sessions()
            
            restored_count = 0
            for db_session in db_sessions:
                session_id = db_session.get('session_id')
                if not session_id:
                    continue
                if session_id not in self._sessions:
                    provider_type_raw = db_session.get('provider')
                    provider_type = self._normalize_provider(provider_type_raw)
                    if provider_type and provider_type in self._providers:
                        p = self._providers[provider_type]
                        fresh = p.get(session_id)
                        if fresh:
                            self._sessions[session_id] = fresh
                            restored_count += 1
                            logger.info(f"✅ Restored session {session_id} from {provider_type.value}")
                        else:
                            # Provider doesn't have it, create a placeholder from DB
                            s = SessionInfo(
                                id=session_id,
                                provider=provider_type,
                                workspace_id=db_session.get('workspace_id', 'unknown'),
                                namespace=db_session.get('namespace', 'unknown'),
                                user=db_session.get('user_id', 'unknown'),
                                status=db_session.get('status', 'unknown')
                            )
                            self._sessions[session_id] = s
                            restored_count += 1
                            logger.warning(f"⚠️  Restored session {session_id} from DB only (not in provider)")
                    else:
                        # Unknown provider; still reconstruct minimal session
                        s = SessionInfo(
                            id=session_id,
                            provider=self._normalize_provider('gke') or SessionProvider.gke,  # sensible default
                            workspace_id=db_session.get('workspace_id', 'unknown'),
                            namespace=db_session.get('namespace', 'unknown'),
                            user=db_session.get('user_id', 'unknown'),
                            status=db_session.get('status', 'unknown')
                        )
                        self._sessions[session_id] = s
                        restored_count += 1
                        logger.warning(f"⚠️  Session {session_id} has unknown provider={provider_type_raw}, defaulted to gke")
            
            logger.info(f"🔄 Startup restoration complete: {restored_count} sessions restored")
            self._startup_restoration_done = True
            
        except Exception as e:
            logger.error(f"❌ Startup restoration failed: {e}")
            self._startup_restoration_done = True  # Don't keep trying

    # -------------------- provider choice -------------------- #

    def _choose_provider(self, req: CreateSessionRequest) -> SessionProvider:
        if req.provider != SessionProvider.auto:
            # Validate that the requested provider is supported
            normalized = self._normalize_provider(req.provider)
            if not normalized or normalized not in self._providers:
                logger.warning(f"Requested provider {req.provider} not supported, using GKE instead")
                return SessionProvider.gke
            return normalized
        
        # AUTO PROVIDER SELECTION (only Cloud Run and GKE Autopilot supported)
        
        # WebSocket sessions (needs_ssh=True) MUST use GKE for proper WebSocket support
        if req.needs_ssh:
            return SessionProvider.gke
        
        # Long-lived sessions should use GKE (better for persistent workloads)
        if req.long_lived:
            return SessionProvider.gke
        
        # Very long duration sessions should use GKE (no workstations support)
        if req.expected_duration_minutes and req.expected_duration_minutes > 60:
            return SessionProvider.gke
        
        # Default to Cloud Run for short, stateless sessions
        return SessionProvider.cloud_run

    # -------------------- CRUD -------------------- #

    async def create_session(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        req = CreateSessionRequest(**spec)
        
        # Apply template configuration if template_id is provided
        if req.template_id:
            await self._apply_template_configuration(req)
        
        provider = self._choose_provider(req)
        p = self._providers[provider]
        
        # Update the request with the actual chosen provider
        req.provider = provider
        
        # Handle async vs sync providers
        if provider == SessionProvider.gke:
            info = await p.create(req)  # GKE provider is async
        else:
            info = p.create(req)        # Cloud Run provider is sync
        
        # Store in memory for quick access
        self._sessions[info.id] = info
        
        # Store in database for persistence
        try:
            from server.database.factory import get_database_client_async
            db = await get_database_client_async()
            storage_config = info.storage_config.dict() if info.storage_config else {}
            logger.info(f"🔍 STORING SESSION {info.id} in database")
            logger.info(f"   workspace_id: {info.workspace_id}")
            logger.info(f"   provider: {info.provider}")
            logger.info(f"   storage_config: {storage_config}")
            
            await db.create_session(
                workspace_id=info.workspace_id,
                session_id=info.id,
                provider=(info.provider.value if isinstance(info.provider, SessionProvider) else info.provider),
                storage_config=storage_config
            )
            # record user_id and any attachments
            try:
                await db.update_session(info.id, user_id=info.user)
            except Exception:
                pass
            # Attach additional storage if present
            try:
                if info.storage_config and info.storage_config.additional_storage:
                    for add in info.storage_config.additional_storage:
                        # We don't have storage_id mapping here; skip unless metadata exists
                        # This is a placeholder for future join-on resource resolution
                        pass
            except Exception:
                pass
            logger.info(f"✅ Session {info.id} stored in database successfully")
        except Exception as e:
            logger.error(f"💥 FAILED to store session {info.id} in database: {e}")
            import traceback
            logger.error(f"💥 TRACEBACK: {traceback.format_exc()}")
        
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
            
            # Apply environment variables (guard against None)
            req.env = req.env or {}
            req.env.update(template.env_vars or {})
            
            # Apply TTL if not explicitly set
            if req.ttl_minutes == 60:  # Default value
                req.ttl_minutes = template.default_ttl_minutes
            
            # Increment template usage
            template_manager.increment_usage(req.template_id)
            
            logger.info(f"Applied template {req.template_id} to session request")
            
        except Exception as e:
            logger.error(f"Failed to apply template {req.template_id}: {e}")
            raise ValueError(f"Template configuration failed: {e}")

    async def list_sessions(self) -> Dict[str, Any]:
        """List all active sessions"""
        sessions = []
        
        # First add sessions from memory
        for sid, session in list(self._sessions.items()):
            p = self._providers[self._normalize_provider(session.provider)]
            fresh = p.get(session.id) or session
            self._sessions[sid] = fresh
            sessions.append(fresh.dict())
        
        # Also check database for sessions not in memory
        try:
            from server.database.factory import get_database_client_async
            db = await get_database_client_async()
            db_sessions = await db.list_sessions()
            
            for db_session in db_sessions:
                session_id = db_session.get('session_id')
                if not session_id or session_id in self._sessions:
                    continue
                provider_type = self._normalize_provider(db_session.get('provider'))
                if provider_type and provider_type in self._providers:
                    p = self._providers[provider_type]
                    fresh = p.get(session_id)
                    if fresh:
                        self._sessions[session_id] = fresh
                        sessions.append(fresh.dict())
                    else:
                        # Provider doesn't have it, but we have DB record
                        s = SessionInfo(
                            id=session_id,
                            provider=provider_type,
                            workspace_id=db_session.get('workspace_id', 'unknown'),
                            status=db_session.get('status', 'unknown')
                        )
                        self._sessions[session_id] = s
                        sessions.append(s.dict())
                else:
                    # Unknown provider; still surface the DB record
                    s = SessionInfo(
                        id=session_id,
                        provider=self._normalize_provider('gke') or SessionProvider.gke,
                        workspace_id=db_session.get('workspace_id', 'unknown'),
                        status=db_session.get('status', 'unknown')
                    )
                    self._sessions[session_id] = s
                    sessions.append(s.dict())
        except Exception as e:
            logger.warning(f"Failed to load sessions from database: {e}")
        
        return {"sessions": sessions, "count": len(sessions)}

    async def get_session(self, sid: str) -> Optional[Dict[str, Any]]:
        # Ensure we've restored sessions from database on startup
        await self._ensure_startup_restoration()
        
        # First check memory
        s = self._sessions.get(sid)
        if not s:
            # Try to load from database
            try:
                from server.database.factory import get_database_client_async
                db = await get_database_client_async()
                db_session = await db.get_session(sid)
                if db_session:
                    logger.info(f"✅ Session {sid} loaded from database")
                    provider_type = self._normalize_provider(db_session.get('provider'))
                    if provider_type and provider_type in self._providers:
                        p = self._providers[provider_type]
                        fresh = p.get(sid)
                        if fresh:
                            self._sessions[sid] = fresh
                            return fresh.dict()
                        else:
                            # Provider doesn't have it, but we have DB record
                            s = SessionInfo(
                                id=db_session.get('session_id', sid),
                                provider=provider_type,
                                workspace_id=db_session.get('workspace_id', 'unknown'),
                                status=db_session.get('status', 'unknown')
                            )
                            self._sessions[sid] = s
                            return s.dict()
            except Exception as e:
                logger.warning(f"Failed to load session {sid} from database: {e}")
            return None
        
        # refresh if provider supports it
        p = self._providers[self._normalize_provider(s.provider)]
        fresh = p.get(s.id) or s
        self._sessions[sid] = fresh
        return fresh.dict()

    async def delete_session(self, sid: str) -> bool:
        logger.info(f"🗑️  DELETE SESSION REQUEST: {sid}")
        
        # Ensure we've restored sessions from database on startup
        await self._ensure_startup_restoration()
        
        logger.info(f"📋 Sessions currently in memory: {list(self._sessions.keys())}")
        
        # Add timestamp and stack trace to identify duplicate calls
        import traceback
        logger.info(f"⏰ Delete request timestamp: {time.time()}")
        logger.info(f"📞 Delete called from: {traceback.format_stack()[-3].strip()}")
        
        s = self._sessions.get(sid)
        if not s:
            logger.info(f"❌ Session {sid} not found in memory, trying to refresh from providers...")
            # Try to refresh from all providers
            for provider_type, provider in self._providers.items():
                try:
                    logger.info(f"🔍 Checking provider {provider_type.value} for session {sid}")
                    fresh_session = provider.get(sid)
                    if fresh_session:
                        self._sessions[sid] = fresh_session
                        s = fresh_session
                        logger.info(f"✅ Refreshed session {sid} from {provider_type.value} for deletion")
                        break
                    else:
                        logger.info(f"❌ Provider {provider_type.value} returned None for session {sid}")
                except Exception as e:
                    logger.warning(f"Failed to refresh session {sid} from {provider_type.value}: {e}")
                    continue
            
            # If still not found, try to load from database
            if not s:
                logger.info(f"🗄️  Session {sid} not found in providers, checking database...")
                try:
                    from server.database.factory import get_database_client_async
                    db = await get_database_client_async()
                    logger.info(f"   Database client obtained: {type(db)}")
                    
                    db_session = await db.get_session(sid)
                    logger.info(f"   Database query result: {db_session}")
                    
                    if db_session:
                        logger.info(f"✅ Session {sid} found in database!")
                        logger.info(f"   DB Session data: {db_session}")
                        
                        provider_type = self._normalize_provider(db_session.get('provider'))
                        s = SessionInfo(
                            id=db_session.get('session_id', sid),
                            provider=provider_type or SessionProvider.gke,
                            workspace_id=db_session.get('workspace_id', 'unknown'),
                            status=db_session.get('status', 'unknown')
                        )
                        self._sessions[sid] = s
                        logger.info(f"✅ Session {sid} reconstructed from database")
                    else:
                        logger.info(f"❌ Session {sid} not found in database")
                except Exception as e:
                    logger.error(f"💥 FAILED to load session {sid} from database: {e}")
                    import traceback
                    logger.error(f"💥 TRACEBACK: {traceback.format_exc()}")
        
        if not s:
            logger.warning(f"Session {sid} not found in any provider or database")
            return False
            
        # Remove from sessions dictionary
        self._sessions.pop(sid, None)
        
        # Remove from database
        logger.info(f"🗄️  Removing session {sid} from database...")
        try:
            from server.database.factory import get_database_client_async
            db = await get_database_client_async()
            result = await db.delete_session(sid)
            logger.info(f"✅ Session {sid} database deletion result: {result}")
        except Exception as e:
            logger.error(f"💥 FAILED to remove session {sid} from database: {e}")
            import traceback
            logger.error(f"💥 TRACEBACK: {traceback.format_exc()}")
        
        # Delete from provider (supports sync or async)
        p = self._providers[self._normalize_provider(s.provider)]
        try:
            deletion_result = p.delete(s.id)
            if inspect.isawaitable(deletion_result):
                # Fire-and-forget deletion to avoid blocking HTTP response
                asyncio.create_task(deletion_result)
                return True
            return bool(deletion_result)
        except Exception as e:
            logger.error(f"💥 Provider deletion error for session {sid}: {e}")
            return False

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
                        logger.info(f"✅ Refreshed session {sid} from {provider_type.value}")
                        break
                except Exception as e:
                    logger.warning(f"Failed to refresh session {sid} from {provider_type.value}: {e}")
                    continue
        
        if not s:
            raise ValueError("Session not found")
        prov = self._normalize_provider(s.provider)
        p = self._providers[prov]
        
        # Check if provider supports async execution
        if async_execution and hasattr(p, 'execute'):
            if prov == SessionProvider.gke:
                return p.execute(s.id, command, timeout, async_execution=True)
            elif prov == SessionProvider.cloud_run:
                return p.execute(s.id, command, timeout)  # already async-style
            else:
                return p.execute(s.id, command, timeout)
        else:
            return p.execute(s.id, command, timeout)

    def get_job_status(self, job_id: str, job_name: str, session_id: str) -> Dict[str, Any]:
        """Get status of a submitted job"""
        s = self._sessions.get(session_id)
        if not s:
            raise ValueError("Session not found")
        
        prov = self._normalize_provider(s.provider)
        p = self._providers[prov]
        if hasattr(p, 'get_job_status'):
            return p.get_job_status(job_id, job_name, session_id)
        else:
            raise ValueError(f"Provider {prov.value} does not support job status checking")

    def connect_info(self, sid: str) -> Dict[str, Any]:
        s = self._sessions.get(sid)
        if not s:
            return {}
        return {"url": s.url, "websocket": s.websocket, "ssh": s.ssh}


sessions_manager = SessionsManager()
