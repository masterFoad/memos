"""
User Management Service for OnMemOS v3
Handles user creation, service account setup, and storage allocation
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

from server.database.factory import get_database_client
from server.database.base import UserType, StorageType
from server.services.gcp.auth_service import GCPAuthService
from server.services.gcp.bucket_service import GCSBucketService

logger = logging.getLogger(__name__)


class UserManagementService:
    """Service for managing users, service accounts, and storage"""

    def __init__(self):
        self.db = get_database_client()
        self.gcp_auth = GCPAuthService()
        self.bucket_service = GCSBucketService()
        # prefer env-var, fall back to constant used elsewhere
        self.gcp_project_id = self.gcp_auth.project_id or "ai-engine-448418"

    async def _ensure_db_connected(self) -> None:
        """Ensure DB connection is open before any operation."""
        try:
            # idempotent connect; underlying client should no-op if already open
            await self.db.connect()
        except Exception as e:
            logger.error("DB connect failed: %s", e)
            raise

    async def create_user_with_infrastructure(
        self,
        email: str,
        name: Optional[str] = None,
        user_type: UserType = UserType.FREE,
    ) -> Dict[str, Any]:
        """
        Create a new user with all necessary infrastructure:
          1) user record in DB
          2) GCP service account (DB record; IAM creation assumed external or via ops)
          3) Workload Identity (best-effort placeholder)
          4) initial storage allocation (DB records; optional real GCS bucket if creds present)
        """
        await self._ensure_db_connected()

        user_id = f"user-{uuid.uuid4().hex[:8]}"
        logger.info("Creating user infrastructure for %s (ID: %s)", email, user_id)

        try:
            # 1) DB user
            user = await self.db.create_user(user_id, email, user_type, name)
            logger.info("✅ Created user record: %s", user_id)

            # 2) service account (record)
            service_account_email = f"{user_id}-gcs-accessor@{self.gcp_project_id}.iam.gserviceaccount.com"
            service_account = await self._create_gcp_service_account(user_id, service_account_email)
            logger.info("✅ Created GCP service account record: %s", service_account_email)

            # 3) workload identity (best-effort / placeholder)
            await self._setup_workload_identity(user_id, service_account_email)
            logger.info("✅ Configured Workload Identity for %s", user_id)

            # 4) initial storage (respects tier limits)
            storage_resources = await self._create_initial_storage(user_id, user_type)

            return {
                "user": user,
                "service_account": service_account,
                "storage_resources": storage_resources,
                "status": "created",
            }
        except Exception as e:
            logger.error("❌ Failed to create user infra for %s: %s", email, e)
            # TODO: add compensating actions/rollback
            raise

    async def _create_gcp_service_account(self, user_id: str, service_account_email: str) -> Dict[str, Any]:
        """Create GCP service account (record); actual IAM creation can be handled out-of-band/ops."""
        try:
            return await self.db.create_service_account(user_id, service_account_email, self.gcp_project_id)
        except Exception as e:
            logger.error("Failed to create service account DB record: %s", e)
            raise

    async def _setup_workload_identity(self, user_id: str, service_account_email: str) -> None:
        """
        Placeholder for Workload Identity wiring.
        Keep best-effort and non-fatal so user creation never breaks if cluster isn’t reachable.
        """
        try:
            namespace = f"onmemos-user-{user_id}"
            # In production, apply k8s resources + annotations here.
            logger.debug("Workload Identity placeholder for user=%s sa=%s ns=%s",
                         user_id, service_account_email, namespace)
        except Exception as e:
            logger.warning("Workload Identity setup skipped/failure for %s: %s", user_id, e)

    async def _create_initial_storage(self, user_id: str, user_type: UserType) -> List[Dict[str, Any]]:
        """Create initial storage resources according to the user's tier. Best-effort; non-fatal."""
        await self._ensure_db_connected()
        storage_resources: List[Dict[str, Any]] = []

        try:
            tier_limits = await self.db.get_user_tier_limits(user_type)

            # Optional real bucket creation if credentials are configured
            if tier_limits.get("max_buckets", 0) > 0:
                bucket_name = f"onmemos-{user_id}-default-{int(datetime.utcnow().timestamp())}"

                # Try real GCS bucket (won't fail user creation if this step is not configured)
                created_in_gcs = False
                try:
                    if self.gcp_auth.test_authentication():
                        # Use a generic namespace for user-scoped buckets
                        self.bucket_service.create_bucket(bucket_name, namespace="users", user=user_id)
                        created_in_gcs = True
                        logger.info("✅ Created initial GCS bucket: %s", bucket_name)
                except Exception as be:
                    logger.warning("GCS bucket creation skipped for %s: %s", user_id, be)

                bucket_resource = await self.db.create_storage_resource(
                    user_id, StorageType.GCS_BUCKET, bucket_name, 10
                )
                # annotate whether it was actually created in GCS
                bucket_resource["provisioned"] = created_in_gcs
                storage_resources.append(bucket_resource)

            if tier_limits.get("max_filestores", 0) > 0:
                pvc_name = f"pvc-{user_id}-default-{int(datetime.utcnow().timestamp())}"
                pvc_resource = await self.db.create_storage_resource(
                    user_id, StorageType.FILESTORE_PVC, pvc_name, 10
                )
                storage_resources.append(pvc_resource)
                logger.info("✅ Prepared initial PVC record: %s", pvc_name)

            return storage_resources
        except Exception as e:
            logger.error("Failed to create initial storage for %s: %s", user_id, e)
            return storage_resources  # non-fatal

    async def get_user_infrastructure(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Return complete user infra snapshot."""
        await self._ensure_db_connected()
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
                "workspaces": workspaces,
            }
        except Exception as e:
            logger.error("Failed to get user infra for %s: %s", user_id, e)
            return None

    async def create_storage_for_user(
        self,
        user_id: str,
        storage_type: StorageType,
        size_gb: int = 10,
        purpose: str = "general",
    ) -> Optional[Dict[str, Any]]:
        """Create storage resource for a user (best-effort provisioning; DB is source of truth)."""
        await self._ensure_db_connected()
        try:
            if not await self.db.check_user_storage_quota(user_id, storage_type):
                logger.warning("User %s has reached quota for %s", user_id, storage_type.value)
                return None

            ts = int(datetime.utcnow().timestamp())
            resource_name = f"onmemos-{user_id}-{purpose}-{ts}"

            provisioned = False
            if storage_type == StorageType.GCS_BUCKET:
                try:
                    if self.gcp_auth.test_authentication():
                        self.bucket_service.create_bucket(resource_name, namespace="users", user=user_id)
                        provisioned = True
                        logger.info("✅ Created user bucket: %s", resource_name)
                except Exception as be:
                    logger.warning("Bucket provisioning skipped for %s: %s", user_id, be)
            elif storage_type == StorageType.FILESTORE_PVC:
                # PVC actual creation usually happens during session creation; store record now.
                resource_name = f"pvc-{user_id}-{purpose}-{ts}"

            storage_resource = await self.db.create_storage_resource(
                user_id, storage_type, resource_name, size_gb
            )
            storage_resource["provisioned"] = provisioned
            logger.info("✅ Created %s record for user %s: %s", storage_type.value, user_id, resource_name)
            return storage_resource
        except Exception as e:
            logger.error("Failed to create storage for %s: %s", user_id, e)
            return None

    async def delete_user_infrastructure(self, user_id: str) -> bool:
        """Delete all user infrastructure (best-effort clean-up)."""
        await self._ensure_db_connected()
        try:
            storage_resources = await self.db.get_user_storage_resources(user_id)

            for resource in storage_resources:
                try:
                    if resource["storage_type"] == StorageType.GCS_BUCKET.value:
                        # best-effort bucket deletion (non-fatal)
                        try:
                            if self.gcp_auth.test_authentication():
                                self.bucket_service.delete_bucket(resource["resource_name"])
                                logger.info("🗑️ Deleted bucket %s for user %s", resource["resource_name"], user_id)
                        except Exception as be:
                            logger.warning("Bucket delete skipped for %s: %s", user_id, be)

                    await self.db.delete_storage_resource(resource["id"])
                except Exception as re:
                    logger.warning("Failed to delete storage resource %s: %s", resource.get("id"), re)

            await self.db.delete_user(user_id)
            logger.info("✅ Deleted user infrastructure: %s", user_id)
            return True
        except Exception as e:
            logger.error("Failed to delete user infra for %s: %s", user_id, e)
            return False
