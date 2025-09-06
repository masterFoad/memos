"""
Session models for OnMemOS SDK
"""

from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime

from .base import OnMemOSModel, ResourceTier, StorageType, GPUType, ImageType, SessionStatus, SessionProvider
from .storage import StorageConfig


class CreateSessionRequest(OnMemOSModel):
    """Request model for creating a session"""
    # Required fields for server compatibility
    template: str = Field(..., description="Template name")
    namespace: str = Field(..., description="Namespace for the session")
    user: str = Field(..., description="User creating the session")
    workspace_id: str = Field(..., description="Workspace ID")
    
    # Provider selection
    provider: SessionProvider = Field(SessionProvider.AUTO, description="Session provider")
    
    # Optional fields
    template_id: Optional[str] = Field(None, description="Template ID to use")
    resource_tier: ResourceTier = Field(ResourceTier.MEDIUM, description="Resource allocation")
    storage_type: StorageType = Field(StorageType.EPHEMERAL, description="Storage type")
    storage_size_gb: int = Field(0, ge=0, description="Storage size in GB")
    gpu_type: GPUType = Field(GPUType.NONE, description="GPU configuration")
    image_type: ImageType = Field(ImageType.ALPINE_BASIC, description="Container image type")
    ttl_minutes: int = Field(60, ge=1, le=1440, description="Session TTL in minutes")
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    labels: Dict[str, str] = Field(default_factory=dict, description="Session labels")
    
    # Provider selection flags (these determine which provider gets chosen)
    long_lived: bool = Field(False, description="Force long-lived provider (GKE) - for sessions >1 hour")
    needs_ssh: bool = Field(False, description="Requires SSH/WebSocket access - forces GKE provider")
    expected_duration_minutes: Optional[int] = Field(None, description="Expected session duration - >60min forces GKE")
    
    # Storage configuration (matches server implementation)
    storage_config: Optional[Union[StorageConfig, Dict[str, Any]]] = Field(None, description="Storage configuration")
    request_bucket: bool = Field(False, description="Request GCS bucket")
    bucket_size_gb: Optional[int] = Field(None, ge=1, description="Bucket size in GB")
    request_persistent_storage: bool = Field(False, description="Request persistent storage")
    persistent_storage_size_gb: Optional[int] = Field(None, ge=1, description="Persistent storage size")
    
    @validator('storage_size_gb')
    def validate_storage_size(cls, v, values):
        """Validate storage size based on storage type"""
        storage_type = values.get('storage_type')
        if storage_type != StorageType.EPHEMERAL and v <= 0:
            raise ValueError(f"Storage size must be > 0 for {storage_type}")
        return v
    
    @validator('ttl_minutes')
    def validate_ttl(cls, v):
        """Validate TTL range"""
        if v < 1 or v > 1440:
            raise ValueError("TTL must be between 1 and 1440 minutes")
        return v


class Session(OnMemOSModel):
    """Session model - matches server response"""
    # Core fields from server response
    id: str = Field(..., description="Unique session identifier")
    provider: str = Field(..., description="Session provider (gke, cloud_run, etc.)")
    namespace: str = Field(..., description="Namespace for the session")
    user: str = Field(..., description="User who created the session")
    workspace_id: str = Field(..., description="Associated workspace ID")
    status: str = Field(..., description="Current session status")
    url: Optional[str] = Field(None, description="Session URL")
    websocket: Optional[str] = Field(None, description="WebSocket endpoint")
    ssh: Optional[bool] = Field(False, description="SSH enabled")
    
    # Optional fields that may be null
    user_type: Optional[str] = Field(None, description="User type")
    storage_allocation: Optional[Dict[str, Any]] = Field(None, description="Storage allocation")
    storage_config: Optional[Dict[str, Any]] = Field(None, description="Storage configuration")
    resource_tier: Optional[str] = Field(None, description="Resource allocation tier")
    resource_package: Optional[str] = Field(None, description="Resource package")
    resource_spec: Optional[Dict[str, Any]] = Field(None, description="Resource specification")
    image_spec: Optional[Dict[str, Any]] = Field(None, description="Image specification")
    gpu_spec: Optional[Dict[str, Any]] = Field(None, description="GPU specification")
    created_at: Optional[Union[float, str, datetime]] = Field(None, description="Creation timestamp (float) or datetime string")
    expires_at: Optional[Union[float, str, datetime]] = Field(None, description="Expiration timestamp (float) or datetime string")
    
    # Provider-specific fields
    k8s_namespace: Optional[str] = Field(None, description="Kubernetes namespace")
    pod_name: Optional[str] = Field(None, description="Pod name")
    service_name: Optional[str] = Field(None, description="Service name")
    job_name: Optional[str] = Field(None, description="Job name")
    
    # Storage status
    storage_status: Dict[str, Any] = Field(default_factory=dict, description="Storage status")
    
    # Details object
    details: Optional[Dict[str, Any]] = Field(None, description="Session details")
    
    # Computed properties
    @property
    def session_id(self) -> str:
        """Alias for id field"""
        return self.id
    
    @property
    def user_id(self) -> str:
        """Alias for user field"""
        return self.user
    
    @property
    def is_active(self) -> bool:
        """Check if session is currently active"""
        return self.status in [SessionStatus.CREATING, SessionStatus.RUNNING, SessionStatus.PAUSED]
    
    @property
    def duration_minutes(self) -> int:
        """Calculate session duration in minutes"""
        if not self.started_at:
            return 0
        end_time = self.stopped_at or datetime.utcnow()
        return int((end_time - self.started_at).total_seconds() / 60)
    
    @property
    def remaining_minutes(self) -> int:
        """Calculate remaining time in minutes"""
        if not self.started_at:
            return self.ttl_minutes
        elapsed = self.duration_minutes
        return max(0, self.ttl_minutes - elapsed)
    
    @property
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return self.remaining_minutes <= 0
    
    @property
    def estimated_total_cost(self) -> float:
        """Estimate total cost based on duration and hourly rate"""
        hours = self.duration_minutes / 60.0
        return hours * self.cost_per_hour
    
    @validator('created_at', 'expires_at', pre=True)
    def convert_datetime_to_timestamp(cls, v):
        """Convert datetime strings to timestamps if needed"""
        if v is None:
            return v
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, str):
            try:
                # Try to parse ISO format datetime string
                dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
                return dt.timestamp()
            except ValueError:
                # If parsing fails, return as-is
                return v
        if isinstance(v, datetime):
            return v.timestamp()
        return v


class SessionList(OnMemOSModel):
    """List of sessions with pagination"""
    sessions: List[Session] = Field(..., description="List of sessions")
    total: int = Field(..., description="Total number of sessions")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Sessions per page")
    has_next: bool = Field(..., description="Has next page")
    has_prev: bool = Field(..., description="Has previous page")
    
    @property
    def active_sessions(self) -> List[Session]:
        """Get only active sessions"""
        return [s for s in self.sessions if s.is_active]
    
    @property
    def stopped_sessions(self) -> List[Session]:
        """Get only stopped sessions"""
        return [s for s in self.sessions if not s.is_active]
    
    @property
    def total_cost(self) -> float:
        """Calculate total cost of all sessions"""
        return sum(s.total_cost for s in self.sessions)


class SessionUpdateRequest(OnMemOSModel):
    """Request model for updating a session"""
    ttl_minutes: Optional[int] = Field(None, ge=1, le=1440, description="New TTL in minutes")
    env_vars: Optional[Dict[str, str]] = Field(None, description="New environment variables")
    labels: Optional[Dict[str, str]] = Field(None, description="New labels")
    
    @validator('ttl_minutes')
    def validate_ttl(cls, v):
        """Validate TTL range"""
        if v is not None and (v < 1 or v > 1440):
            raise ValueError("TTL must be between 1 and 1440 minutes")
        return v


class SessionMetrics(OnMemOSModel):
    """Session performance metrics"""
    session_id: str = Field(..., description="Session identifier")
    cpu_usage_percent: float = Field(..., description="CPU usage percentage")
    memory_usage_mb: int = Field(..., description="Memory usage in MB")
    memory_limit_mb: int = Field(..., description="Memory limit in MB")
    disk_usage_gb: float = Field(..., description="Disk usage in GB")
    network_rx_mb: float = Field(..., description="Network received in MB")
    network_tx_mb: float = Field(..., description="Network transmitted in MB")
    gpu_usage_percent: Optional[float] = Field(None, description="GPU usage percentage")
    gpu_memory_mb: Optional[int] = Field(None, description="GPU memory usage in MB")
    timestamp: datetime = Field(..., description="Metrics timestamp")
    
    @property
    def memory_usage_percent(self) -> float:
        """Calculate memory usage percentage"""
        if self.memory_limit_mb == 0:
            return 0.0
        return (self.memory_usage_mb / self.memory_limit_mb) * 100
    
    @property
    def disk_usage_percent(self) -> float:
        """Calculate disk usage percentage (assuming 100GB default)"""
        default_disk_gb = 100.0
        return (self.disk_usage_gb / default_disk_gb) * 100


class SessionLogs(OnMemOSModel):
    """Session logs"""
    session_id: str = Field(..., description="Session identifier")
    logs: List[str] = Field(..., description="Log lines")
    total_lines: int = Field(..., description="Total number of log lines")
    start_line: int = Field(..., description="Starting line number")
    end_line: int = Field(..., description="Ending line number")
    has_more: bool = Field(..., description="Has more logs available")
    log_type: str = Field("stdout", description="Log type (stdout/stderr/system)")
    timestamp: datetime = Field(..., description="Log timestamp")
