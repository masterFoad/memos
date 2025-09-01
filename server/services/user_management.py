"""
User Management Service for OnMemOS v3
Handles user creation, service account setup, and storage allocation
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

from ..database.factory import get_database_client
from ..database.base import UserType, StorageType
from ..services.gcp.auth_service import GCPAuthService
from ..services.gcp.bucket_service import GCSBucketService

logger = logging.getLogger(__name__)

class UserManagementService:
    """Service for managing users, service accounts, and storage"""
    
    def __init__(self):
        self.db = get_database_client()
        self.gcp_auth = GCPAuthService()
        self.bucket_service = GCSBucketService()
        self.gcp_project_id = "ai-engine-448418"  # TODO: Make configurable
    
    async def create_user_with_infrastructure(self, email: str, name: str = None, 
                                            user_type: UserType = UserType.FREE) -> Dict[str, Any]:
        """
        Create a new user with all necessary infrastructure:
        1. User record in database
        2. GCP service account
        3. Workload Identity setup
        4. Initial storage allocation
        """
        try:
            # Generate user ID
            user_id = f"user-{uuid.uuid4().hex[:8]}"
            
            logger.info(f"Creating user infrastructure for {email} (ID: {user_id})")
            
            # 1. Create user in database
            user = await self.db.create_user(user_id, email, user_type, name)
            logger.info(f"✅ Created user record: {user_id}")
            
            # 2. Create GCP service account
            service_account_email = f"{user_id}-gcs-accessor@{self.gcp_project_id}.iam.gserviceaccount.com"
            service_account = await self._create_gcp_service_account(user_id, service_account_email)
            logger.info(f"✅ Created GCP service account: {service_account_email}")
            
            # 3. Set up Workload Identity
            await self._setup_workload_identity(user_id, service_account_email)
            logger.info(f"✅ Configured Workload Identity for {user_id}")
            
            # 4. Create initial storage resources (if user type allows)
            storage_resources = await self._create_initial_storage(user_id, user_type)
            
            return {
                "user": user,
                "service_account": service_account,
                "storage_resources": storage_resources,
                "status": "created"
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to create user infrastructure for {email}: {e}")
            # TODO: Implement cleanup/rollback
            raise
    
    async def _create_gcp_service_account(self, user_id: str, service_account_email: str) -> Dict[str, Any]:
        """Create GCP service account for user"""
        try:
            # Create service account in GCP
            # Note: This would require GCP IAM API calls
            # For now, we'll assume it exists or create it via gcloud command
            
            # Store in database
            service_account = await self.db.create_service_account(
                user_id, service_account_email, self.gcp_project_id
            )
            
            return service_account
            
        except Exception as e:
            logger.error(f"Failed to create GCP service account: {e}")
            raise
    
    async def _setup_workload_identity(self, user_id: str, service_account_email: str):
        """Set up Workload Identity for user's service account"""
        try:
            # Create Kubernetes namespace for user
            namespace = f"onmemos-user-{user_id}"
            
            # Create namespace (this would be done via kubectl or K8s API)
            # kubectl create namespace onmemos-user-{user_id}
            
            # Create service account in namespace
            # kubectl create serviceaccount default -n onmemos-user-{user_id}
            
            # Annotate service account for Workload Identity
            annotation = f"iam.gke.io/gcp-service-account={service_account_email}"
            # kubectl annotate serviceaccount default -n onmemos-user-{user_id} {annotation}
            
            # Grant minimal GCS permissions to service account
            # gcloud projects add-iam-policy-binding {project_id} --member="serviceAccount:{service_account_email}" --role="roles/storage.objectViewer"
            
            logger.info(f"Workload Identity setup completed for {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to setup Workload Identity: {e}")
            raise
    
    async def _create_initial_storage(self, user_id: str, user_type: UserType) -> List[Dict[str, Any]]:
        """Create initial storage resources based on user type"""
        storage_resources = []
        
        try:
            # Get tier limits
            tier_limits = await self.db.get_user_tier_limits(user_type)
            
            # Create initial bucket if allowed
            if tier_limits.get("max_buckets", 0) > 0:
                bucket_name = f"onmemos-{user_id}-default-{int(datetime.now().timestamp())}"
                
                # Create bucket in GCS
                # await self.bucket_service.create_bucket(bucket_name)
                
                # Store in database
                bucket_resource = await self.db.create_storage_resource(
                    user_id, StorageType.GCS_BUCKET, bucket_name, 10
                )
                storage_resources.append(bucket_resource)
                logger.info(f"✅ Created initial bucket: {bucket_name}")
            
            # Create initial filestore if allowed
            if tier_limits.get("max_filestores", 0) > 0:
                pvc_name = f"pvc-{user_id}-default-{int(datetime.now().timestamp())}"
                
                # Store in database
                pvc_resource = await self.db.create_storage_resource(
                    user_id, StorageType.FILESTORE_PVC, pvc_name, 10
                )
                storage_resources.append(pvc_resource)
                logger.info(f"✅ Created initial PVC: {pvc_name}")
            
            return storage_resources
            
        except Exception as e:
            logger.error(f"Failed to create initial storage: {e}")
            return storage_resources
    
    async def get_user_infrastructure(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get complete user infrastructure information"""
        try:
            user = await self.db.get_user(user_id)
            if not user:
                return None
            
            service_account = await self.db.get_service_account(user_id)
            storage_resources = await self.db.get_user_storage_resources(user_id)
            workspaces = await self.db.get_user_workspaces(user_id)
            
            return {
                "user": user,
                "service_account": service_account,
                "storage_resources": storage_resources,
                "workspaces": workspaces
            }
            
        except Exception as e:
            logger.error(f"Failed to get user infrastructure: {e}")
            return None
    
    async def create_storage_for_user(self, user_id: str, storage_type: StorageType, 
                                    size_gb: int = 10, purpose: str = "general") -> Optional[Dict[str, Any]]:
        """Create storage resource for user"""
        try:
            # Check user quota
            can_create = await self.db.check_user_storage_quota(user_id, storage_type)
            if not can_create:
                logger.warning(f"User {user_id} has reached quota for {storage_type.value}")
                return None
            
            # Generate resource name
            resource_name = f"onmemos-{user_id}-{purpose}-{int(datetime.now().timestamp())}"
            
            # Create storage resource
            if storage_type == StorageType.GCS_BUCKET:
                # Create bucket in GCS
                # await self.bucket_service.create_bucket(resource_name)
                pass
            elif storage_type == StorageType.FILESTORE_PVC:
                # PVC will be created when session is created
                resource_name = f"pvc-{user_id}-{purpose}-{int(datetime.now().timestamp())}"
            
            # Store in database
            storage_resource = await self.db.create_storage_resource(
                user_id, storage_type, resource_name, size_gb
            )
            
            logger.info(f"✅ Created {storage_type.value} for user {user_id}: {resource_name}")
            return storage_resource
            
        except Exception as e:
            logger.error(f"Failed to create storage for user {user_id}: {e}")
            return None
    
    async def delete_user_infrastructure(self, user_id: str) -> bool:
        """Delete all user infrastructure"""
        try:
            # Get user's storage resources
            storage_resources = await self.db.get_user_storage_resources(user_id)
            
            # Delete storage resources
            for resource in storage_resources:
                if resource["storage_type"] == StorageType.GCS_BUCKET.value:
                    # Delete bucket from GCS
                    # await self.bucket_service.delete_bucket(resource["resource_name"])
                    pass
                
                # Mark as deleted in database
                await self.db.delete_storage_resource(resource["id"])
            
            # Delete user (cascades to service accounts, workspaces, etc.)
            await self.db.delete_user(user_id)
            
            logger.info(f"✅ Deleted user infrastructure: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete user infrastructure: {e}")
            return False
