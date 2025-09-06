"""
User Management Models for OnMemOS v3
"""

from enum import Enum
from typing import List, Optional, Dict, Any, ClassVar
from pydantic import BaseModel, Field
from datetime import datetime
import re


# -----------------------------
# Core enums & mappings
# -----------------------------

class UserType(str, Enum):
    """User types with different workspace entitlements"""
    FREE = "free"               # Free user: 1 workspace
    PRO = "pro"                 # Pro user: up to 5 workspaces
    ENTERPRISE = "enterprise"   # Enterprise user: up to 20 workspaces
    ADMIN = "admin"             # Admin user: unlimited workspaces


class WorkspaceStatus(str, Enum):
    """Workspace status"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class WorkspaceResourcePackage(str, Enum):
    """Resource packages available for workspaces"""
    # Free tier packages
    FREE_MICRO = "free_micro"       # Free micro workspace

    # Development packages
    DEV_MICRO = "dev_micro"         # Micro development environment
    DEV_SMALL = "dev_small"         # Small development environment
    DEV_MEDIUM = "dev_medium"       # Medium development environment
    DEV_LARGE = "dev_large"         # Large development environment

    # Data Science packages
    DS_SMALL = "ds_small"           # Small data science (CPU only)
    DS_MEDIUM = "ds_medium"         # Medium data science (CPU only)
    DS_LARGE = "ds_large"           # Large data science (CPU only)

    # Machine Learning packages
    ML_T4_SMALL = "ml_t4_small"     # Small ML with T4 GPU
    ML_T4_MEDIUM = "ml_t4_medium"   # Medium ML with T4 GPU
    ML_T4_LARGE = "ml_t4_large"     # Large ML with T4 GPU
    ML_A100_SMALL = "ml_a100_small" # Small ML with A100 GPU
    ML_A100_MEDIUM = "ml_a100_medium" # Medium ML with A100 GPU
    ML_A100_LARGE = "ml_a100_large" # Large ML with A100 GPU
    ML_H100_SMALL = "ml_h100_small" # Small ML with H100 GPU
    ML_H100_MEDIUM = "ml_h100_medium" # Medium ML with H100 GPU
    ML_H100_LARGE = "ml_h100_large" # Large ML with H100 GPU

    # Compute packages
    COMPUTE_SMALL = "compute_small"     # Small compute
    COMPUTE_MEDIUM = "compute_medium"   # Medium compute
    COMPUTE_LARGE = "compute_large"     # Large compute
    COMPUTE_XLARGE = "compute_xlarge"   # Extra large compute


class WorkspaceImageMapping:
    """Maps workspace resource packages to appropriate container images"""

    # Mapping from workspace packages to image types
    PACKAGE_IMAGE_MAP: ClassVar[Dict[WorkspaceResourcePackage, str]] = {
        # Free tier - basic images
        WorkspaceResourcePackage.FREE_MICRO: "alpine_basic",

        # Development packages - enhanced images
        WorkspaceResourcePackage.DEV_MICRO: "alpine_basic",
        WorkspaceResourcePackage.DEV_SMALL: "ubuntu_pro",
        WorkspaceResourcePackage.DEV_MEDIUM: "python_pro",
        WorkspaceResourcePackage.DEV_LARGE: "python_pro",

        # Data Science packages - Python-focused
        WorkspaceResourcePackage.DS_SMALL: "python_pro",
        WorkspaceResourcePackage.DS_MEDIUM: "python_enterprise",
        WorkspaceResourcePackage.DS_LARGE: "jupyter_enterprise",

        # Machine Learning packages - ML-optimized images
        WorkspaceResourcePackage.ML_T4_SMALL: "python_enterprise",
        WorkspaceResourcePackage.ML_T4_MEDIUM: "python_enterprise",
        WorkspaceResourcePackage.ML_T4_LARGE: "jupyter_enterprise",
        WorkspaceResourcePackage.ML_A100_SMALL: "cuda_enterprise",
        WorkspaceResourcePackage.ML_A100_MEDIUM: "cuda_enterprise",
        WorkspaceResourcePackage.ML_A100_LARGE: "cuda_enterprise",
        WorkspaceResourcePackage.ML_H100_SMALL: "cuda_enterprise",
        WorkspaceResourcePackage.ML_H100_MEDIUM: "cuda_enterprise",
        WorkspaceResourcePackage.ML_H100_LARGE: "cuda_enterprise",

        # Compute packages - general purpose
        WorkspaceResourcePackage.COMPUTE_SMALL: "ubuntu_pro",
        WorkspaceResourcePackage.COMPUTE_MEDIUM: "python_pro",
        WorkspaceResourcePackage.COMPUTE_LARGE: "python_enterprise",
        WorkspaceResourcePackage.COMPUTE_XLARGE: "python_enterprise",
    }

    @classmethod
    def get_image_type_for_package(cls, package: WorkspaceResourcePackage) -> str:
        """Get the appropriate image type for a workspace resource package"""
        return cls.PACKAGE_IMAGE_MAP.get(package, "alpine_basic")

    @classmethod
    def get_allowed_images_for_user_type(cls, user_type: 'UserType') -> List[str]:
        """Get allowed image types for a user type"""
        if user_type == UserType.FREE:
            return ["alpine_basic", "python_basic"]
        elif user_type == UserType.PRO:
            return ["alpine_basic", "python_basic", "ubuntu_pro", "python_pro", "nodejs_pro", "go_pro", "rust_pro"]
        elif user_type == UserType.ENTERPRISE:
            return ["alpine_basic", "python_basic", "ubuntu_pro", "python_pro", "nodejs_pro", "go_pro", "rust_pro",
                    "python_enterprise", "jupyter_enterprise", "cuda_enterprise", "java_enterprise"]
        elif user_type == UserType.ADMIN:
            return ["alpine_basic", "python_basic", "ubuntu_pro", "python_pro", "nodejs_pro", "go_pro", "rust_pro",
                    "python_enterprise", "jupyter_enterprise", "cuda_enterprise", "java_enterprise", "custom"]
        else:
            return ["alpine_basic"]


# -----------------------------
# Data models
# -----------------------------

class WorkspaceEntitlement(BaseModel):
    """Workspace entitlements for each user type"""
    max_workspaces: int = Field(description="Maximum number of workspaces")
    allowed_packages: List[WorkspaceResourcePackage] = Field(description="Allowed resource packages")
    can_share_workspaces: bool = Field(description="Can share workspaces with other users")
    can_cross_namespace: bool = Field(description="Can access workspaces across namespaces")


class WorkspaceProfile(BaseModel):
    """Workspace profile with resource configuration"""
    workspace_id: str = Field(description="Unique workspace identifier")
    user_id: str = Field(description="Owner user identifier")
    name: str = Field(description="Workspace name")
    description: Optional[str] = Field(None, description="Workspace description")
    resource_package: WorkspaceResourcePackage = Field(description="Resource package for this workspace")
    status: WorkspaceStatus = Field(default=WorkspaceStatus.ACTIVE, description="Workspace status")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: Optional[datetime] = Field(None, description="Last activity timestamp")

    # Resource usage tracking (per workspace)
    current_sessions: int = Field(default=0, description="Number of active sessions")
    current_storage_gb: float = Field(default=0.0, description="Current storage usage in GB")
    current_buckets: List[str] = Field(default_factory=list, description="List of bucket names")
    current_pvcs: List[str] = Field(default_factory=list, description="List of PVC names")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional workspace metadata")


class UserProfile(BaseModel):
    """User profile with workspace entitlements"""
    user_id: str = Field(description="Unique user identifier")
    user_type: UserType = Field(description="User type determining entitlements")
    email: Optional[str] = Field(None, description="User email")
    name: Optional[str] = Field(None, description="User display name")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: Optional[datetime] = Field(None, description="Last activity timestamp")

    # Workspace management
    workspaces: List[WorkspaceProfile] = Field(default_factory=list, description="User's workspaces")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional user metadata")


class WorkspaceStorageRequest(BaseModel):
    """Workspace's storage request for session creation"""
    workspace_id: str = Field(description="Workspace identifier")
    user_id: str = Field(description="User identifier")
    namespace: str = Field(description="Session namespace")
    session_id: str = Field(description="Session identifier")

    # Storage configuration
    request_bucket: bool = Field(False, description="Request GCS bucket")
    request_persistent_storage: bool = Field(False, description="Request persistent storage")

    # Storage specifications
    bucket_name: Optional[str] = Field(None, description="Specific bucket name (optional)")
    bucket_size_gb: Optional[int] = Field(None, description="Bucket size in GB")
    persistent_storage_size_gb: Optional[int] = Field(10, description="Persistent storage size in GB")
    mount_path: str = Field("/workspace", description="Mount path for storage")

    # Advanced options
    storage_class: Optional[str] = Field("standard-rwo", description="Storage class for persistent volumes")
    bucket_location: Optional[str] = Field("us-central1", description="GCS bucket location")
    shared_access: Optional[List[str]] = Field(None, description="List of user IDs with shared access")


class WorkspaceStorageAllocation(BaseModel):
    """Allocated storage resources for a workspace session"""
    workspace_id: str = Field(description="Workspace identifier")
    user_id: str = Field(description="User identifier")
    session_id: str = Field(description="Session identifier")
    namespace: str = Field(description="Session namespace")

    # Allocated resources
    bucket_name: Optional[str] = Field(None, description="Allocated bucket name")
    persistent_volume_name: Optional[str] = Field(None, description="Allocated PVC name")
    storage_size_gb: float = Field(0.0, description="Total allocated storage size")

    # Allocation metadata
    allocated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(None, description="When allocation expires")
    is_shared: bool = Field(False, description="Whether storage is shared with other users")


# -----------------------------
# Entitlements
# -----------------------------

USER_ENTITLEMENTS: Dict[UserType, WorkspaceEntitlement] = {
    UserType.FREE: WorkspaceEntitlement(
        max_workspaces=1,
        allowed_packages=[
            WorkspaceResourcePackage.FREE_MICRO,
            WorkspaceResourcePackage.DEV_MICRO,
            WorkspaceResourcePackage.DEV_SMALL,
        ],
        can_share_workspaces=False,
        can_cross_namespace=False,
    ),
    UserType.PRO: WorkspaceEntitlement(
        max_workspaces=5,
        allowed_packages=[
            WorkspaceResourcePackage.DEV_MICRO,
            WorkspaceResourcePackage.DEV_SMALL,
            WorkspaceResourcePackage.DEV_MEDIUM,
            WorkspaceResourcePackage.DEV_LARGE,
            WorkspaceResourcePackage.DS_SMALL,
            WorkspaceResourcePackage.DS_MEDIUM,
            WorkspaceResourcePackage.ML_T4_SMALL,
            WorkspaceResourcePackage.ML_T4_MEDIUM,
            WorkspaceResourcePackage.COMPUTE_SMALL,
            WorkspaceResourcePackage.COMPUTE_MEDIUM,
        ],
        can_share_workspaces=True,
        can_cross_namespace=True,
    ),
    UserType.ENTERPRISE: WorkspaceEntitlement(
        max_workspaces=20,
        allowed_packages=[
            WorkspaceResourcePackage.DEV_MICRO,
            WorkspaceResourcePackage.DEV_SMALL,
            WorkspaceResourcePackage.DEV_MEDIUM,
            WorkspaceResourcePackage.DEV_LARGE,
            WorkspaceResourcePackage.DS_SMALL,
            WorkspaceResourcePackage.DS_MEDIUM,
            WorkspaceResourcePackage.DS_LARGE,
            WorkspaceResourcePackage.ML_T4_SMALL,
            WorkspaceResourcePackage.ML_T4_MEDIUM,
            WorkspaceResourcePackage.ML_T4_LARGE,
            WorkspaceResourcePackage.ML_A100_SMALL,
            WorkspaceResourcePackage.ML_A100_MEDIUM,
            WorkspaceResourcePackage.ML_A100_LARGE,
            WorkspaceResourcePackage.ML_H100_SMALL,
            WorkspaceResourcePackage.ML_H100_MEDIUM,
            WorkspaceResourcePackage.ML_H100_LARGE,
            WorkspaceResourcePackage.COMPUTE_SMALL,
            WorkspaceResourcePackage.COMPUTE_MEDIUM,
            WorkspaceResourcePackage.COMPUTE_LARGE,
            WorkspaceResourcePackage.COMPUTE_XLARGE,
        ],
        can_share_workspaces=True,
        can_cross_namespace=True,
    ),
    UserType.ADMIN: WorkspaceEntitlement(
        max_workspaces=1000,
        allowed_packages=list(WorkspaceResourcePackage),  # All packages
        can_share_workspaces=True,
        can_cross_namespace=True,
    ),
}


# -----------------------------
# Helpers (naming safety)
# -----------------------------

def _slugify(value: str, *, max_len: int, allow_dot: bool = False) -> str:
    """
    Lowercase, keep alphanumerics and '-', optionally '.', collapse repeats,
    trim to max_len, and trim leading/trailing separators.
    """
    v = value.lower()
    allowed = r"[^a-z0-9\-\.]" if allow_dot else r"[^a-z0-9\-]"
    v = re.sub(allowed, "-", v)
    v = re.sub(r"-{2,}", "-", v).strip("-")
    if not allow_dot:
        v = v.replace(".", "-")
    return v[:max_len].strip("-")


def _safe_gcs_bucket_name(*parts: str) -> str:
    """
    Build a GCS-compliant bucket name (3–63 chars, lowercase, digits, '-', '.', no underscores).
    We avoid dots to keep TLS wildcard hassles; stick to dashes.
    Ensures it doesn't start/end with '-' and collapses length safely.
    """
    base = "-".join(_slugify(p, max_len=40) for p in parts if p)
    # Enforce length; keep prefix/suffix balance
    if len(base) > 63:
        base = base[:63]
    base = base.strip("-")
    # GCS requires 3–63 chars; add fallback if too short
    if len(base) < 3:
        base = (base + "-onm").ljust(3, "x")
    return base


def _safe_k8s_name(*parts: str) -> str:
    """K8s resource names: RFC 1123 label (<=253), lowercase alphanumeric and '-'."""
    base = "-".join(_slugify(p, max_len=100) for p in parts if p)
    return base[:253].strip("-")


# -----------------------------
# User Manager
# -----------------------------

class UserManager:
    """Manages user profiles and workspace entitlements (in-memory for server runtime)"""

    def __init__(self):
        self.users: Dict[str, UserProfile] = {}

    # ---- Users ----

    def create_user(
        self,
        user_id: str,
        user_type: UserType = UserType.FREE,
        email: Optional[str] = None,
        name: Optional[str] = None,
    ) -> UserProfile:
        """Create a new user profile"""
        if user_id in self.users:
            raise ValueError(f"User {user_id} already exists")

        user = UserProfile(user_id=user_id, user_type=user_type, email=email, name=name)
        self.users[user_id] = user
        return user

    def ensure_user(
        self,
        user_id: str,
        user_type: UserType = UserType.FREE,
        email: Optional[str] = None,
        name: Optional[str] = None,
    ) -> UserProfile:
        """Get existing or create a user profile."""
        u = self.get_user(user_id)
        return u or self.create_user(user_id, user_type, email, name)

    def get_user(self, user_id: str) -> Optional[UserProfile]:
        """Get user profile by ID"""
        return self.users.get(user_id)

    def get_user_entitlements(self, user_id: str) -> Optional[WorkspaceEntitlement]:
        """Get workspace entitlements for a user"""
        user = self.get_user(user_id)
        if not user:
            return None
        return USER_ENTITLEMENTS.get(user.user_type)

    def get_allowed_images_for_user(self, user_id: str) -> List[str]:
        user = self.get_user(user_id)
        if not user:
            return ["alpine_basic"]
        return WorkspaceImageMapping.get_allowed_images_for_user_type(user.user_type)

    # ---- Workspaces ----

    def can_create_workspace(self, user_id: str, resource_package: WorkspaceResourcePackage) -> bool:
        """Check if user can create a workspace with the specified resource package"""
        user = self.get_user(user_id)
        if not user:
            return False

        entitlements = USER_ENTITLEMENTS.get(user.user_type)
        if not entitlements:
            return False

        # Check workspace limit
        if len(user.workspaces) >= entitlements.max_workspaces:
            return False

        # Check if resource package is allowed
        if resource_package not in entitlements.allowed_packages:
            return False

        return True

    def create_workspace(
        self,
        user_id: str,
        workspace_id: str,
        name: str,
        resource_package: WorkspaceResourcePackage,
        description: Optional[str] = None,
    ) -> WorkspaceProfile:
        """Create a new workspace for a user"""
        if not self.can_create_workspace(user_id, resource_package):
            raise ValueError(f"User {user_id} cannot create workspace with package {resource_package}")

        user = self.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Uniqueness within the user's set
        for workspace in user.workspaces:
            if workspace.workspace_id == workspace_id:
                raise ValueError(f"Workspace {workspace_id} already exists")

        workspace = WorkspaceProfile(
            workspace_id=workspace_id,
            user_id=user_id,
            name=name,
            description=description,
            resource_package=resource_package,
        )

        user.workspaces.append(workspace)
        return workspace

    def list_workspaces(self, user_id: str) -> List[WorkspaceProfile]:
        """List all workspaces for a user"""
        u = self.get_user(user_id)
        return list(u.workspaces) if u else []

    def get_workspace(self, user_id: str, workspace_id: str) -> Optional[WorkspaceProfile]:
        """Get workspace by ID for a user"""
        user = self.get_user(user_id)
        if not user:
            return None

        for workspace in user.workspaces:
            if workspace.workspace_id == workspace_id:
                return workspace

        return None

    def delete_workspace(self, user_id: str, workspace_id: str) -> bool:
        """Delete a workspace"""
        user = self.get_user(user_id)
        if not user:
            return False

        for i, workspace in enumerate(user.workspaces):
            if workspace.workspace_id == workspace_id:
                workspace.status = WorkspaceStatus.DELETED
                user.workspaces.pop(i)
                return True

        return False

    # ---- Storage allocation (session-scoped) ----

    def can_allocate_storage(self, workspace_id: str, request: WorkspaceStorageRequest) -> bool:
        """Check if workspace can allocate requested storage.

        Currently permissive; hooks in place for future per-package limits.
        """
        workspace = self.get_workspace(request.user_id, workspace_id)
        if not workspace:
            return False

        # Example place to insert future constraints:
        #  - max buckets/pvcs per workspace by package
        #  - max total storage per workspace
        # For now, always allow when request is syntactically valid.
        if not request.request_bucket and not request.request_persistent_storage:
            return True

        # Quick sanity on sizes
        if request.bucket_size_gb is not None and request.bucket_size_gb < 0:
            return False
        if request.persistent_storage_size_gb is not None and request.persistent_storage_size_gb < 0:
            return False

        return True

    def allocate_storage(self, workspace_id: str, request: WorkspaceStorageRequest) -> WorkspaceStorageAllocation:
        """Allocate storage for a workspace session"""
        if not self.can_allocate_storage(workspace_id, request):
            raise ValueError(f"Workspace {workspace_id} cannot allocate requested storage")

        workspace = self.get_workspace(request.user_id, workspace_id)
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found")

        allocation = WorkspaceStorageAllocation(
            workspace_id=workspace_id,
            user_id=request.user_id,
            session_id=request.session_id,
            namespace=request.namespace,
        )

        # Generate resource names (sanitized for providers)
        timestamp = int(datetime.utcnow().timestamp())

        if request.request_bucket:
            # Respect provided name if present, otherwise build a safe global name
            bucket_name = request.bucket_name or _safe_gcs_bucket_name(
                "onmemos",
                workspace_id,
                request.namespace,
                str(timestamp),
            )
            allocation.bucket_name = bucket_name
            workspace.current_buckets.append(bucket_name)

        if request.request_persistent_storage:
            pvc_name = _safe_k8s_name("pvc", workspace_id, request.namespace, str(timestamp))
            allocation.persistent_volume_name = pvc_name
            workspace.current_pvcs.append(pvc_name)

        # Update storage usage
        allocation.storage_size_gb = float((request.bucket_size_gb or 0) + (request.persistent_storage_size_gb or 0))
        workspace.current_storage_gb += allocation.storage_size_gb

        return allocation

    def deallocate_storage(self, workspace_id: str, allocation: WorkspaceStorageAllocation):
        """Deallocate storage when session ends"""
        workspace = self.get_workspace(allocation.user_id, workspace_id)
        if not workspace:
            return

        # Remove from current usage
        if allocation.bucket_name and allocation.bucket_name in workspace.current_buckets:
            workspace.current_buckets.remove(allocation.bucket_name)

        if allocation.persistent_volume_name and allocation.persistent_volume_name in workspace.current_pvcs:
            workspace.current_pvcs.remove(allocation.persistent_volume_name)

        # Update storage usage (never below zero)
        workspace.current_storage_gb -= allocation.storage_size_gb
        workspace.current_storage_gb = max(0.0, workspace.current_storage_gb)


# Global user manager instance
user_manager = UserManager()
