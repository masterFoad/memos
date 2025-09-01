"""
GKE Session Provider - Enhanced with bucket mounting and persistent storage
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from server.core.logging import get_logger
from server.models.sessions import SessionInfo, CreateSessionRequest, StorageConfig, StorageType, ResourceTier
from server.services.gke.gke_service import gke_service
from server.models.users import user_manager, UserType
from server.database.factory import get_database_client
from server.services.billing_service import BillingService

logger = get_logger("session")

class GkeSessionProvider:
    """GKE session provider with enhanced storage and resource support"""
    
    def __init__(self):
        self._map: Dict[str, Dict[str, Any]] = {}
        self.db = None
        self.billing_service = None
    
    async def _ensure_db_connected(self):
        """Ensure database is connected"""
        if self.db is None:
            self.db = get_database_client()
            await self.db.connect()
        if self.billing_service is None:
            self.billing_service = BillingService()
    
    async def create(self, req: CreateSessionRequest) -> SessionInfo:
        """Create GKE session with enhanced features and billing integration"""
        logger.info(f"Creating GKE session for {req.user} in {req.namespace}")
        
        # Ensure database is connected
        await self._ensure_db_connected()
        
        # Handle user management and storage allocation
        user_type = req.user_type or UserType.FREE
        
        # Get or create user
        user = user_manager.get_user(req.user)
        if not user:
            user_manager.create_user(
                user_id=req.user,
                user_type=user_type,
                name=f"User {req.user}"
            )
            logger.info(f"Created new user: {req.user} with type: {user_type}")
        else:
            user_type = user.user_type  # Use existing user's type
            logger.info(f"Using existing user: {req.user} with type: {user_type}")
        
        # BILLING INTEGRATION: Check user credits before creating session
        try:
            # Get user's current credit balance
            current_credits = await self.db.get_user_credits(req.user)
            logger.info(f"User {req.user} has ${current_credits:.2f} credits")
            
            # Estimate session cost (we'll use a conservative estimate)
            # For now, estimate 1 hour of usage
            estimated_cost = 0.075  # PRO tier rate per hour
            if user_type == UserType.FREE:
                estimated_cost = 0.05
            elif user_type == UserType.ENTERPRISE:
                estimated_cost = 0.01
            elif user_type == UserType.ADMIN:
                estimated_cost = 0.0
            
            if estimated_cost > 0 and current_credits < estimated_cost:
                raise ValueError(f"Insufficient credits. Required: ${estimated_cost:.2f}, Available: ${current_credits:.2f}")
            
            logger.info(f"Credit check passed for user {req.user}")
            
        except Exception as e:
            logger.error(f"Credit validation failed for user {req.user}: {e}")
            raise ValueError(f"Credit validation failed: {e}")
        
        # Ensure workspace exists (for testing purposes)
        workspace = user_manager.get_workspace(req.user, req.workspace_id)
        if not workspace:
            # Create a default workspace for testing
            from server.models.users import WorkspaceResourcePackage
            # Use a package that the user can actually create
            user_entitlements = user_manager.get_user_entitlements(req.user)
            if user_entitlements and user_entitlements.allowed_packages:
                # Use the first available package
                resource_package = user_entitlements.allowed_packages[0]
            else:
                # Fallback to FREE_MICRO
                resource_package = WorkspaceResourcePackage.FREE_MICRO
            
            user_manager.create_workspace(
                user_id=req.user,
                workspace_id=req.workspace_id,
                name=f"Auto-created workspace for {req.user}",
                resource_package=resource_package
            )
            logger.info(f"Created workspace {req.workspace_id} for user {req.user} with package {resource_package}")
        
        # Generate session ID
        session_id = f"ws-{req.namespace}-{req.user}-{int(datetime.utcnow().timestamp())}"
        
        # Convert to storage request and validate entitlements
        storage_request = req.to_storage_request(session_id)
        
        if not user_manager.can_allocate_storage(req.workspace_id, storage_request):
            workspace = user_manager.get_workspace(req.user, req.workspace_id)
            if workspace:
                raise ValueError(
                    f"Workspace {req.workspace_id} cannot allocate requested storage. "
                    f"Current usage: {len(workspace.current_buckets)} buckets, {len(workspace.current_pvcs)} PVCs, "
                    f"{workspace.current_storage_gb}GB used."
                )
            else:
                raise ValueError(f"Workspace {req.workspace_id} not found for user {req.user}")
        
        # Allocate storage
        storage_allocation = user_manager.allocate_storage(req.workspace_id, storage_request)
        logger.info(f"Allocated storage for user {req.user}: {storage_allocation}")
        
        # Build storage configuration from allocation
        storage_config = req.storage_config
        if storage_config is None:
            if storage_allocation.bucket_name:
                storage_config = StorageConfig(
                    storage_type=StorageType.GCS_FUSE,
                    bucket_name=storage_allocation.bucket_name,
                    mount_path=storage_request.mount_path
                )
            elif storage_allocation.persistent_volume_name:
                storage_config = StorageConfig(
                    storage_type=StorageType.PERSISTENT_VOLUME,
                    pvc_name=storage_allocation.persistent_volume_name,
                    pvc_size=f"{storage_request.persistent_storage_size_gb}Gi",
                    mount_path=storage_request.mount_path
                )
            else:
                storage_config = StorageConfig(storage_type=StorageType.EPHEMERAL)
        
        # Create workspace
        ws = gke_service.create_workspace(
            template=req.template,
            namespace=req.namespace,
            user=req.user,
            storage_config=storage_config,
            resource_tier=req.resource_tier,
            env=req.env
        )
        
        # BILLING INTEGRATION: Start session billing after successful creation
        try:
            # Determine hourly rate based on user type and resource tier
            hourly_rate = 0.075  # Default PRO rate
            if user_type == UserType.FREE:
                hourly_rate = 0.05
            elif user_type == UserType.ENTERPRISE:
                hourly_rate = 0.01
            elif user_type == UserType.ADMIN:
                hourly_rate = 0.0
            
            # Start session billing
            billing_info = await self.billing_service.start_session_billing(
                session_id, req.user, "medium"  # Use resource tier for more accurate billing
            )
            logger.info(f"Started session billing for {session_id}: ${hourly_rate:.4f}/hour")
            
        except Exception as e:
            logger.error(f"Failed to start session billing for {session_id}: {e}")
            # Don't fail the session creation, but log the billing error
            # In production, you might want to fail here
        
        # Store session metadata
        sid = ws["workspace_id"]
        self._map[sid] = {
            "k8s_ns": ws["namespace"], 
            "pod": ws["pod"],
            "namespace": req.namespace,
            "user": req.user,
            "workspace_id": req.workspace_id,
            "storage_config": storage_config.dict() if storage_config else None,
            "resource_tier": req.resource_tier.value if req.resource_tier else None,
            "storage_allocation": storage_allocation.dict() if storage_allocation else None,
            "user_type": user_type.value,
            "session_id": session_id,  # Store for billing cleanup
            "hourly_rate": hourly_rate
        }
        
        # Create session info
        session_info = SessionInfo(
            id=sid,
            provider=req.provider,
            namespace=req.namespace,
            user=req.user,
            workspace_id=req.workspace_id,
            status="running",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=req.ttl_minutes),
            user_type=user_type,
            storage_allocation=storage_allocation,
            storage_config=storage_config,
            resource_tier=req.resource_tier,
            k8s_namespace=ws["namespace"],
            pod_name=ws["pod"],
            storage_status={
                "bucket_name": storage_config.bucket_name if storage_config and storage_config.storage_type == StorageType.GCS_FUSE else None,
                "pvc_name": storage_config.pvc_name if storage_config and storage_config.storage_type == StorageType.PERSISTENT_VOLUME else None,
                "mount_path": storage_config.mount_path if storage_config else "/workspace",
                "allocation_id": storage_allocation.session_id,
                "storage_size_gb": storage_allocation.storage_size_gb
            },
            details={
                "k8s_ns": ws["namespace"],
                "pod": ws["pod"],
                "storage_type": storage_config.storage_type.value if storage_config else "ephemeral",
                "resource_tier": req.resource_tier.value if req.resource_tier else "small",
                "user_type": user_type.value,
                "storage_allocation": storage_allocation.dict()
            }
        )
        
        # Add WebSocket URL
        if ws["namespace"] and ws["pod"]:
            session_info.websocket = f"/v1/gke/shell/{sid}?k8s_ns={ws['namespace']}&pod={ws['pod']}"
        
        logger.info(f"Created GKE session: {sid}")
        return session_info
    
    def get(self, session_id: str) -> Optional[SessionInfo]:
        """Get session information"""
        meta = self._map.get(session_id)
        if not meta:
            return None
        
        # Create session info from metadata
        session_info = SessionInfo(
            id=session_id,
            provider="gke",
            namespace=meta["namespace"],
            user=meta["user"],
            workspace_id=meta.get("workspace_id", "unknown"),  # Fallback for existing sessions
            status="running",
            k8s_namespace=meta["k8s_ns"],
            pod_name=meta["pod"],
            storage_config=StorageConfig(**meta["storage_config"]) if meta.get("storage_config") else None,
            resource_tier=ResourceTier(meta["resource_tier"]) if meta.get("resource_tier") else None,
            details={
                "k8s_ns": meta["k8s_ns"],
                "pod": meta["pod"],
                "storage_type": meta.get("storage_config", {}).get("storage_type", "ephemeral"),
                "resource_tier": meta.get("resource_tier", "small")
            }
        )
        
        # Add WebSocket URL
        if meta["k8s_ns"] and meta["pod"]:
            session_info.websocket = f"/v1/gke/shell/{session_id}?k8s_ns={meta['k8s_ns']}&pod={meta['pod']}"
        
        return session_info
    
    async def delete(self, session_id: str) -> bool:
        """Delete session and cleanup resources with billing integration"""
        # Ensure database is connected
        await self._ensure_db_connected()
        
        meta = self._map.get(session_id)
        if not meta:
            return False
        
        # BILLING INTEGRATION: Stop session billing and calculate final cost
        try:
            if meta.get("session_id"):
                # Stop session billing
                final_billing = await self.billing_service.stop_session_billing(meta["session_id"])
                if final_billing:
                    total_cost = final_billing.get('total_cost', 0)
                    total_hours = final_billing.get('total_hours', 0)
                    logger.info(f"Session {session_id} billing completed: {total_hours:.2f} hours = ${total_cost:.4f}")
                    
                    # Deduct credits from user account
                    if total_cost > 0:
                        await self.db.deduct_credits(
                            meta['user'], 
                            total_cost, 
                            f"Session {session_id} runtime",
                            session_id=meta["session_id"]
                        )
                        logger.info(f"Deducted ${total_cost:.4f} from user {meta['user']} for session {session_id}")
                else:
                    logger.warning(f"No billing info found for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to process billing for session {session_id}: {e}")
            # Don't fail the deletion, but log the billing error
        
        # Get storage config for cleanup
        storage_config = None
        if meta.get("storage_config"):
            storage_config = StorageConfig(**meta["storage_config"])
        
        # Deallocate storage from user management
        if meta.get("storage_allocation"):
            try:
                storage_allocation_dict = meta["storage_allocation"]
                # Convert dictionary to WorkspaceStorageAllocation object
                from server.models.users import WorkspaceStorageAllocation
                storage_allocation = WorkspaceStorageAllocation(**storage_allocation_dict)
                user_manager.deallocate_storage(storage_allocation.workspace_id, storage_allocation)
                logger.info(f"Deallocated storage for user {meta['user']}: {storage_allocation}")
            except Exception as e:
                logger.warning(f"Failed to deallocate storage for session {session_id}: {e}")
        
        # Delete workspace
        success = gke_service.delete_workspace(
            meta["k8s_ns"], 
            meta["pod"], 
            storage_config
        )
        
        # Remove from tracking
        if session_id in self._map:
            del self._map[session_id]
        
        logger.info(f"Deleted GKE session: {session_id}")
        return success
    
    def execute(self, session_id: str, command: str, timeout: int = 120, async_execution: bool = False) -> Dict[str, Any]:
        """Execute command in session
        
        Args:
            session_id: Session ID
            command: Command to execute
            timeout: Timeout for synchronous execution
            async_execution: If True, submit as job and return job ID for polling
        """
        meta = self._map.get(session_id)
        if not meta:
            return {"success": False, "error": "Session not found"}
        
        if async_execution:
            # Submit as job for asynchronous execution
            return gke_service.submit_job(
                session_id, 
                meta["k8s_ns"], 
                meta["pod"], 
                command
            )
        else:
            # Execute synchronously
            return gke_service.exec_in_workspace(
                session_id, 
                meta["k8s_ns"], 
                meta["pod"], 
                command, 
                timeout
            )

    def get_job_status(self, job_id: str, job_name: str, session_id: str) -> Dict[str, Any]:
        """Get status of a submitted job"""
        meta = self._map.get(session_id)
        if not meta:
            return {"success": False, "error": "Session not found"}
        
        return gke_service.get_job_status(job_id, meta["k8s_ns"], job_name)


gke_provider = GkeSessionProvider()
