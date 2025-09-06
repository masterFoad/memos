"""
Main client for OnMemOS v3 API
Includes auto API key detection and context manager support
"""

from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
import aiohttp

from ..core.config import ClientConfig, get_api_key, get_base_url, get_timeout
from ..core.auth import AuthManager
from ..core.http import HTTPClient
from ..core.exceptions import OnMemOSError, AuthenticationError, ConfigurationError
from ..services.sessions import SessionService
from ..services.storage import StorageService
from ..services.templates import TemplateService
from ..services.shell import ShellService
from ..services.cost_estimation import CostEstimationService


class OnMemOSClient:
    """Main client for OnMemOS v3 API"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        config: Optional[ClientConfig] = None
    ):
        # Auto-detect API key if not provided
        self.api_key = api_key or get_api_key()
        if not self.api_key:
            raise ConfigurationError(
                "No API key provided. Set ONMEMOS_API_KEY environment variable "
                "or pass api_key parameter to OnMemOSClient constructor."
            )
        
        # Use provided config or auto-detect
        self.config = config or ClientConfig(
            base_url=base_url or get_base_url(),
            timeout=get_timeout()
        )
        
        # Initialize authentication and HTTP client
        self.auth_manager = AuthManager(self.api_key)
        self.http_client = HTTPClient(
            base_url=self.config.base_url,
            auth_manager=self.auth_manager,
            timeout=self.config.timeout,
            retry_config=self.config.retry_config
        )
        
        # Initialize services
        self.sessions = SessionService(self.http_client)
        self.storage = StorageService(self.http_client)
        self.templates = TemplateService(self.http_client)
        self.shell = ShellService(self.http_client)
        self.cost_estimation = CostEstimationService(self.http_client)
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.http_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.http_client.__aexit__(exc_type, exc_val, exc_tb)
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self.http_client.is_connected
    
    @property
    def api_info(self) -> Dict[str, Any]:
        """Get API information"""
        return {
            "base_url": self.config.base_url,
            "timeout": self.config.timeout,
            "user_agent": self.config.user_agent,
            "api_key": f"{self.api_key[:8]}..." if self.api_key else None
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        try:
            return await self.http_client.get("/health")
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def get_api_info(self) -> Dict[str, Any]:
        """Get API information"""
        try:
            return await self.http_client.get("/info")
        except Exception as e:
            return {"error": str(e)}
    
    async def test_connection(self) -> bool:
        """Test connection to OnMemOS API"""
        try:
            health = await self.health_check()
            return health.get("status") == "healthy"
        except Exception:
            return False
    
    def get_shell_url(self, session_id: str, k8s_ns: str, pod_name: str) -> str:
        """Get WebSocket shell URL for a session"""
        base = self.config.base_url.rstrip('/')
        return f"{base}/v1/gke/shell/{session_id}?k8s_ns={k8s_ns}&pod={pod_name}"
    
    def get_session_url(self, session_id: str) -> str:
        """Get session management URL"""
        base = self.config.base_url.rstrip('/')
        return f"{base}/v1/sessions/{session_id}"
    
    def get_storage_url(self, session_id: str) -> str:
        """Get storage management URL for a session"""
        base = self.config.base_url.rstrip('/')
        return f"{base}/v1/sessions/{session_id}/storage"


# Factory function for easy client creation
def create_client(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    config: Optional[ClientConfig] = None
) -> OnMemOSClient:
    """Create OnMemOS client with auto-detection"""
    return OnMemOSClient(api_key=api_key, base_url=base_url, config=config)


# Context manager for easy usage
@asynccontextmanager
async def client(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    config: Optional[ClientConfig] = None
):
    """Context manager for OnMemOS client"""
    async with OnMemOSClient(api_key=api_key, base_url=base_url, config=config) as client:
        yield client


# Convenience function for quick operations
async def quick_session(
    template_id: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    **kwargs
):
    """Quick session creation with auto-cleanup"""
    async with client(api_key=api_key, base_url=base_url) as sdk_client:
        # Create session request
        from ..models.sessions import CreateSessionRequest, ResourceTier
        
        session_request = CreateSessionRequest(
            template=template_id,
            namespace=kwargs.get('namespace', 'sdk-demo'),
            user=kwargs.get('user', 'sdk-test-user'),
            workspace_id=kwargs.get('workspace_id', '5e3f6ebb-6656-4301-be47-5436646ba44e'),
            template_id=template_id,
            resource_tier=kwargs.get('resource_tier', ResourceTier.MEDIUM),
            ttl_minutes=kwargs.get('ttl_minutes', 60)
        )
        
        # Create session
        session = await sdk_client.sessions.create_session(session_request)
        
        try:
            # Wait for session to be ready
            await sdk_client.sessions.wait_for_ready(session.session_id)
            
            # Return session info
            return {
                "session_id": session.session_id,
                "shell_url": sdk_client.get_shell_url(
                    session.session_id,
                    session.k8s_namespace or "default",
                    session.pod_name or "unknown"
                ),
                "session_url": sdk_client.get_session_url(session.session_id),
                "storage_url": sdk_client.get_storage_url(session.session_id),
                "status": session.status
            }
        
        except Exception as e:
            # Cleanup on error
            try:
                await sdk_client.sessions.delete_session(session.session_id)
            except:
                pass
            raise e


# Example usage functions
async def list_my_sessions(api_key: Optional[str] = None) -> list:
    """List user's sessions"""
    async with client(api_key=api_key) as sdk_client:
        sessions = await sdk_client.sessions.list_sessions()
        return [s.dict() for s in sessions.sessions]


async def get_session_info(session_id: str, api_key: Optional[str] = None) -> dict:
    """Get session information"""
    async with client(api_key=api_key) as sdk_client:
        session = await sdk_client.sessions.get_session(session_id)
        return session.dict()


async def estimate_template_cost(template_id: str, duration_hours: float = 1.0, api_key: Optional[str] = None) -> dict:
    """Estimate cost for a template"""
    async with client(api_key=api_key) as sdk_client:
        estimate = await sdk_client.cost_estimation.estimate_template_cost(template_id, duration_hours)
        return estimate.dict()
