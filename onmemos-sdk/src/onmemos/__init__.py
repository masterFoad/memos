"""
OnMemOS v3 Python SDK
Official Python client library for OnMemOS cloud development environments
"""

__version__ = "0.1.0"
__author__ = "OnMemOS Team"
__email__ = "team@onmemos.com"

# Core client
from .core.client import OnMemOSClient, create_client, client, quick_session

# Convenience functions
from .core.client import list_my_sessions, get_session_info, estimate_template_cost

# Configuration
from .core.config import ClientConfig, get_default_config, get_api_key, get_base_url

# Models
from .models.base import (
    ResourceTier, StorageType, GPUType, ImageType, UserType, 
    SessionStatus, MountType, TemplateCategory, CostEstimate
)
from .models.sessions import (
    CreateSessionRequest, Session, SessionList, SessionUpdateRequest,
    SessionMetrics, SessionLogs
)
from .models.storage import (
    StorageConfig, AdditionalStorage, StorageType, StorageClass,
    create_persistent_storage_config, create_gcs_storage_config, create_multi_storage_config
)

# Services (for advanced usage)
from .services.sessions import SessionService
from .services.storage import StorageService
from .services.templates import TemplateService
from .services.shell import ShellService
from .services.cost_estimation import CostEstimationService

# Exceptions
from .core.exceptions import (
    OnMemOSError, AuthenticationError, ConfigurationError,
    SessionError, StorageError, TemplateError, ShellError
)

# Main exports
__all__ = [
    # Core client
    "OnMemOSClient",
    "create_client", 
    "client",
    "quick_session",
    
    # Convenience functions
    "list_my_sessions",
    "get_session_info", 
    "estimate_template_cost",
    
    # Configuration
    "ClientConfig",
    "get_default_config",
    "get_api_key",
    "get_base_url",
    
    # Models
    "ResourceTier",
    "StorageType", 
    "GPUType",
    "ImageType",
    "UserType",
    "SessionStatus",
    "MountType",
    "TemplateCategory",
    "CostEstimate",
    "CreateSessionRequest",
    "Session",
    "SessionList",
    "SessionUpdateRequest",
    "SessionMetrics",
    "SessionLogs",
    "StorageConfig",
    "AdditionalStorage",
    "StorageType",
    "StorageClass",
    "create_persistent_storage_config",
    "create_gcs_storage_config",
    "create_multi_storage_config",
    
    # Services
    "SessionService",
    "StorageService", 
    "TemplateService",
    "ShellService",
    "CostEstimationService",
    
    # Exceptions
    "OnMemOSError",
    "AuthenticationError",
    "ConfigurationError",
    "SessionError",
    "StorageError",
    "TemplateError",
    "ShellError",
]

# Version info
def get_version() -> str:
    """Get SDK version"""
    return __version__


def get_info() -> dict:
    """Get SDK information"""
    return {
        "name": "onmemos-sdk",
        "version": __version__,
        "author": __author__,
        "email": __email__,
        "description": "Official Python SDK for OnMemOS v3",
        "url": "https://github.com/onmemos/onmemos-sdk"
    }
