"""
Core module for OnMemOS SDK
"""

from .client import OnMemOSClient, create_client, client, quick_session
from .config import ClientConfig, RetryConfig, get_default_config, get_api_key, get_base_url
from .auth import AuthManager
from .http import HTTPClient
from .exceptions import (
    OnMemOSError, AuthenticationError, ConfigurationError, ValidationError,
    SessionError, StorageError, TemplateError, ShellError, CostEstimationError,
    HTTPError, RateLimitError, ServerError, TimeoutError, ConnectionError,
    ResourceNotFoundError, InsufficientCreditsError, QuotaExceededError
)

__all__ = [
    "OnMemOSClient",
    "create_client",
    "client", 
    "quick_session",
    "ClientConfig",
    "RetryConfig",
    "get_default_config",
    "get_api_key",
    "get_base_url",
    "AuthManager",
    "HTTPClient",
    "OnMemOSError",
    "AuthenticationError",
    "ConfigurationError",
    "ValidationError",
    "SessionError",
    "StorageError",
    "TemplateError",
    "ShellError",
    "CostEstimationError",
    "HTTPError",
    "RateLimitError",
    "ServerError",
    "TimeoutError",
    "ConnectionError",
    "ResourceNotFoundError",
    "InsufficientCreditsError",
    "QuotaExceededError",
]
