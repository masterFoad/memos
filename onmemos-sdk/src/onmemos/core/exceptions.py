"""
Custom exceptions for OnMemOS SDK
"""


class OnMemOSError(Exception):
    """Base exception for OnMemOS SDK"""
    
    def __init__(self, message: str, code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
    
    def __str__(self):
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


class AuthenticationError(OnMemOSError):
    """Authentication failed"""
    
    def __init__(self, message: str = "Authentication failed", details: dict = None):
        super().__init__(message, "AUTH_ERROR", details)


class ConfigurationError(OnMemOSError):
    """Configuration error"""
    
    def __init__(self, message: str = "Configuration error", details: dict = None):
        super().__init__(message, "CONFIG_ERROR", details)


class ValidationError(OnMemOSError):
    """Validation error"""
    
    def __init__(self, message: str = "Validation error", details: dict = None):
        super().__init__(message, "VALIDATION_ERROR", details)


class SessionError(OnMemOSError):
    """Session operation failed"""
    
    def __init__(self, message: str = "Session operation failed", details: dict = None):
        super().__init__(message, "SESSION_ERROR", details)


class StorageError(OnMemOSError):
    """Storage operation failed"""
    
    def __init__(self, message: str = "Storage operation failed", details: dict = None):
        super().__init__(message, "STORAGE_ERROR", details)


class TemplateError(OnMemOSError):
    """Template operation failed"""
    
    def __init__(self, message: str = "Template operation failed", details: dict = None):
        super().__init__(message, "TEMPLATE_ERROR", details)


class ShellError(OnMemOSError):
    """Shell operation failed"""
    
    def __init__(self, message: str = "Shell operation failed", details: dict = None):
        super().__init__(message, "SHELL_ERROR", details)


class CostEstimationError(OnMemOSError):
    """Cost estimation failed"""
    
    def __init__(self, message: str = "Cost estimation failed", details: dict = None):
        super().__init__(message, "COST_ESTIMATION_ERROR", details)


class HTTPError(OnMemOSError):
    """HTTP request failed"""
    
    def __init__(self, message: str = "HTTP request failed", status_code: int = None, details: dict = None):
        super().__init__(message, "HTTP_ERROR", details)
        self.status_code = status_code
    
    def __str__(self):
        if self.status_code:
            return f"[HTTP {self.status_code}] {self.message}"
        return super().__str__()


class RateLimitError(OnMemOSError):
    """Rate limit exceeded"""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = None, details: dict = None):
        super().__init__(message, "RATE_LIMIT_ERROR", details)
        self.retry_after = retry_after
    
    def __str__(self):
        if self.retry_after:
            return f"{self.message} (retry after {self.retry_after}s)"
        return super().__str__()


class ServerError(OnMemOSError):
    """Server error"""
    
    def __init__(self, message: str = "Server error", status_code: int = None, details: dict = None):
        super().__init__(message, "SERVER_ERROR", details)
        self.status_code = status_code
    
    def __str__(self):
        if self.status_code:
            return f"[Server {self.status_code}] {self.message}"
        return super().__str__()


class TimeoutError(OnMemOSError):
    """Request timeout"""
    
    def __init__(self, message: str = "Request timeout", timeout: float = None, details: dict = None):
        super().__init__(message, "TIMEOUT_ERROR", details)
        self.timeout = timeout
    
    def __str__(self):
        if self.timeout:
            return f"{self.message} (after {self.timeout}s)"
        return super().__str__()


class ConnectionError(OnMemOSError):
    """Connection error"""
    
    def __init__(self, message: str = "Connection error", details: dict = None):
        super().__init__(message, "CONNECTION_ERROR", details)


class ResourceNotFoundError(OnMemOSError):
    """Resource not found"""
    
    def __init__(self, resource_type: str = "Resource", resource_id: str = None, details: dict = None):
        message = f"{resource_type} not found"
        if resource_id:
            message += f": {resource_id}"
        super().__init__(message, "NOT_FOUND_ERROR", details)
        self.resource_type = resource_type
        self.resource_id = resource_id


class InsufficientCreditsError(OnMemOSError):
    """Insufficient credits"""
    
    def __init__(self, required: float = None, available: float = None, details: dict = None):
        message = "Insufficient credits"
        if required is not None and available is not None:
            message += f" (required: ${required:.2f}, available: ${available:.2f})"
        super().__init__(message, "INSUFFICIENT_CREDITS_ERROR", details)
        self.required = required
        self.available = available


class QuotaExceededError(OnMemOSError):
    """Quota exceeded"""
    
    def __init__(self, quota_type: str = "quota", limit: str = None, details: dict = None):
        message = f"{quota_type} exceeded"
        if limit:
            message += f" (limit: {limit})"
        super().__init__(message, "QUOTA_EXCEEDED_ERROR", details)
        self.quota_type = quota_type
        self.limit = limit
