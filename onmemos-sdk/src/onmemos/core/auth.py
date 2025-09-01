"""
Authentication manager for OnMemOS SDK
"""

from typing import Dict, Optional
from ..core.exceptions import AuthenticationError


class AuthManager:
    """Manages authentication for API requests"""
    
    def __init__(self, api_key: str):
        if not api_key:
            raise AuthenticationError("API key is required")
        self.api_key = api_key
    
    async def get_headers(self) -> Dict[str, str]:
        """Get authentication headers for requests"""
        return {
            "X-API-Key": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def validate_api_key(self) -> bool:
        """Validate API key format"""
        if not self.api_key or len(self.api_key) < 10:
            return False
        return True
    
    def get_api_key_info(self) -> Dict[str, str]:
        """Get API key information (masked)"""
        if len(self.api_key) <= 8:
            return {
                "api_key": "***",
                "length": len(self.api_key),
                "masked": "***"
            }
        
        return {
            "api_key": f"{self.api_key[:8]}...",
            "length": len(self.api_key),
            "masked": f"{self.api_key[:8]}...{self.api_key[-4:]}"
        }
    
    def refresh_token(self) -> None:
        """Refresh authentication token (not needed for API key auth)"""
        # API key auth doesn't require token refresh
        pass
    
    def is_expired(self) -> bool:
        """Check if authentication is expired (not applicable for API key auth)"""
        # API key auth doesn't expire
        return False
