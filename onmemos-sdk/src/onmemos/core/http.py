"""
HTTP client with authentication and retry logic for OnMemOS SDK
"""

from typing import Optional, Dict, Any, Union
import aiohttp
import asyncio
from pydantic import BaseModel

from .auth import AuthManager
from .config import RetryConfig
from .exceptions import HTTPError, RateLimitError, ServerError, TimeoutError, ConnectionError


class HTTPClient:
    """HTTP client with authentication and retry logic"""
    
    def __init__(
        self,
        base_url: str,
        auth_manager: AuthManager,
        timeout: float = 30.0,
        retry_config: Optional[RetryConfig] = None
    ):
        self.base_url = base_url.rstrip('/')
        self.auth_manager = auth_manager
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.retry_config = retry_config or RetryConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._connection_semaphore = asyncio.Semaphore(100)
    
    async def __aenter__(self):
        """Async context manager entry"""
        self._session = aiohttp.ClientSession(
            timeout=self.timeout,
            headers={"User-Agent": "onmemos-sdk/0.1.0"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._session:
            await self._session.close()
            self._session = None
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self._session is not None and not self._session.closed
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        if not self.is_connected:
            raise ConnectionError("Client not connected. Use async context manager.")
        
        url = f"{self.base_url}{endpoint}"
        headers = await self.auth_manager.get_headers()
        
        # Merge headers
        if 'headers' in kwargs:
            headers.update(kwargs['headers'])
        kwargs['headers'] = headers
        
        async with self._connection_semaphore:
            for attempt in range(self.retry_config.max_retries + 1):
                try:
                    async with self._session.request(method, url, **kwargs) as response:
                        return await self._handle_response(response)
                        
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    if attempt == self.retry_config.max_retries:
                        raise ConnectionError(f"Request failed after {attempt + 1} attempts: {e}")
                    
                    delay = self._calculate_retry_delay(attempt)
                    await asyncio.sleep(delay)
    
    async def _handle_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Handle HTTP response"""
        if response.status == 429:
            retry_after = response.headers.get("Retry-After", 60)
            raise RateLimitError(f"Rate limited. Retry after {retry_after} seconds", retry_after=int(retry_after))
        
        if response.status >= 500:
            raise ServerError(f"Server error: {response.status}", status_code=response.status)
        
        if response.status >= 400:
            try:
                error_data = await response.json()
                raise HTTPError(f"Client error: {response.status} - {error_data}", status_code=response.status)
            except:
                raise HTTPError(f"Client error: {response.status}", status_code=response.status)
        
        try:
            return await response.json()
        except:
            return {"status": "success", "status_code": response.status}
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff and jitter"""
        delay = min(
            self.retry_config.base_delay * (self.retry_config.exponential_base ** attempt),
            self.retry_config.max_delay
        )
        
        if self.retry_config.jitter:
            delay *= (0.5 + asyncio.get_event_loop().time() % 1)
        
        return delay
    
    # HTTP method wrappers
    async def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """GET request"""
        return await self._make_request("GET", endpoint, **kwargs)
    
    async def post(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """POST request"""
        return await self._make_request("POST", endpoint, **kwargs)
    
    async def put(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """PUT request"""
        return await self._make_request("PUT", endpoint, **kwargs)
    
    async def delete(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """DELETE request"""
        return await self._make_request("DELETE", endpoint, **kwargs)
    
    async def patch(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """PATCH request"""
        return await self._make_request("PATCH", endpoint, **kwargs)
