"""
HTTP client with authentication and retry logic for OnMemOS SDK
"""

from typing import Optional, Dict, Any, Union
import aiohttp
import asyncio
import random
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

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
            headers={
                "User-Agent": "onmemos-sdk/0.1.0",
                "Accept": "application/json",
            },
            trust_env=True,  # honor proxies/env when present; harmless otherwise
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

    def _build_url(self, endpoint: str) -> str:
        """Build an absolute URL from base_url and endpoint (idempotent)."""
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        return f"{self.base_url}{endpoint}"

    def _parse_retry_after(self, value: Optional[str]) -> int:
        """
        Parse Retry-After header which may be:
        - Delta seconds (int or float string)
        - HTTP-date
        Returns seconds (int, >= 0). Defaults to 60 on parse failure.
        """
        if not value:
            return 60
        # seconds (or float seconds)?
        try:
            secs = int(float(value))
            return max(0, secs)
        except (ValueError, TypeError):
            pass
        # HTTP-date
        try:
            dt = parsedate_to_datetime(value)  # may be naive
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            delta = (dt - datetime.now(timezone.utc)).total_seconds()
            return max(0, int(delta))
        except Exception:
            return 60

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        if not self.is_connected:
            raise ConnectionError("Client not connected. Use async context manager.")

        url = self._build_url(endpoint)

        # Auth headers (copy to avoid mutating provider's dict)
        auth_headers = dict(await self.auth_manager.get_headers())

        # Handle custom timeout
        custom_timeout = kwargs.pop('timeout', None)
        if custom_timeout:
            kwargs['timeout'] = aiohttp.ClientTimeout(total=custom_timeout)
        else:
            kwargs['timeout'] = self.timeout

        # Merge headers: user-provided overrides auth/defaults
        merged_headers = {"Accept": "application/json", **auth_headers}
        if 'headers' in kwargs and kwargs['headers']:
            merged_headers.update(kwargs['headers'])
        kwargs['headers'] = merged_headers

        async with self._connection_semaphore:
            for attempt in range(self.retry_config.max_retries + 1):
                try:
                    async with self._session.request(method, url, **kwargs) as response:
                        return await self._handle_response(response)

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    # Only network/timeout errors are retried here (existing behavior)
                    if attempt == self.retry_config.max_retries:
                        raise ConnectionError(f"Request failed after {attempt + 1} attempts: {e}")

                    delay = self._calculate_retry_delay(attempt)
                    await asyncio.sleep(delay)

    async def _handle_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Handle HTTP response"""
        status = response.status

        # Rate limiting
        if status == 429:
            retry_after_s = self._parse_retry_after(response.headers.get("Retry-After"))
            raise RateLimitError(
                f"Rate limited. Retry after {retry_after_s} seconds",
                retry_after=retry_after_s
            )

        # Server errors
        if status >= 500:
            raise ServerError(f"Server error: {status}", status_code=status)

        # Client errors
        if status >= 400:
            # Try JSON error payload first
            try:
                error_data = await response.json()
                raise HTTPError(
                    f"Client error: {status} - {error_data}",
                    status_code=status
                )
            except Exception:
                # Fallback to text snippet to aid debugging
                try:
                    text = await response.text()
                    snippet = text[:512]
                    raise HTTPError(
                        f"Client error: {status} - {snippet}",
                        status_code=status
                    )
                except Exception:
                    raise HTTPError(f"Client error: {status}", status_code=status)

        # Success: prefer JSON, fallback to text (preserve old keys)
        # Try JSON regardless of header; many APIs send JSON without proper content-type.
        try:
            return await response.json()
        except Exception:
            try:
                text = await response.text()
            except Exception:
                # last resort: no body
                return {"status": "success", "status_code": status}

            return {
                "status": "success",
                "status_code": status,
                "content_type": response.headers.get("Content-Type"),
                "text": text,
            }

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff and jitter"""
        delay = min(
            self.retry_config.base_delay * (self.retry_config.exponential_base ** attempt),
            self.retry_config.max_delay
        )
        if self.retry_config.jitter:
            # multiplicative jitter in [0.5, 1.5]
            delay *= random.uniform(0.5, 1.5)
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
