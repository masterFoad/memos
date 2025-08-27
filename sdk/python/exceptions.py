"""
Custom exceptions for OnMemOS v3 SDK

Provides user-friendly error messages with actionable suggestions.
"""

class OnMemOSError(Exception):
    """Base exception for OnMemOS SDK errors"""
    
    def __init__(self, message: str, suggestion: str = None, details: dict = None):
        self.message = message
        self.suggestion = suggestion or "Please check your request and try again"
        self.details = details or {}
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        msg = f"❌ {self.message}"
        if self.suggestion:
            msg += f"\n💡 Suggestion: {self.suggestion}"
        return msg

class NamespaceError(OnMemOSError):
    """Exception for namespace-related errors"""
    pass

class StorageError(OnMemOSError):
    """Exception for storage-related errors"""
    pass

class WorkspaceError(OnMemOSError):
    """Exception for workspace-related errors"""
    pass

class BucketError(OnMemOSError):
    """Exception for bucket-related errors"""
    pass

class AuthenticationError(OnMemOSError):
    """Exception for authentication-related errors"""
    pass

class ValidationError(OnMemOSError):
    """Exception for validation errors"""
    pass

def handle_http_error(e, operation: str = "operation") -> OnMemOSError:
    """Convert HTTP errors to user-friendly OnMemOS exceptions"""
    try:
        error_detail = e.response.json() if e.response.headers.get('content-type', '').startswith('application/json') else {}
        detail = error_detail.get('detail', {})
        
        if isinstance(detail, dict):
            error_msg = detail.get('message', str(e))
            suggestion = detail.get('suggestion', f'Check your request and try again')
            
            # Determine exception type based on error
            error_type = detail.get('error', '').lower()
            if 'namespace' in error_type or 'namespace' in error_msg.lower():
                return NamespaceError(error_msg, suggestion, detail)
            elif 'storage' in error_type or 'file' in error_msg.lower() or 'upload' in error_msg.lower() or 'download' in error_msg.lower():
                return StorageError(error_msg, suggestion, detail)
            elif 'workspace' in error_type or 'workspace' in error_msg.lower():
                return WorkspaceError(error_msg, suggestion, detail)
            elif 'bucket' in error_type or 'bucket' in error_msg.lower():
                return BucketError(error_msg, suggestion, detail)
            elif 'auth' in error_type or 'unauthorized' in error_msg.lower():
                return AuthenticationError(error_msg, suggestion, detail)
            elif 'validation' in error_type or 'invalid' in error_msg.lower():
                return ValidationError(error_msg, suggestion, detail)
            else:
                return OnMemOSError(error_msg, suggestion, detail)
        else:
            return OnMemOSError(str(e), f"Check your request and try again")
            
    except Exception:
        return OnMemOSError(str(e), f"Check your request and try again")
