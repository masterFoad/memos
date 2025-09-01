"""
Shell service for OnMemOS SDK
"""

from typing import Optional, Dict, Any
from ..core.http import HTTPClient
from ..core.exceptions import ShellError


class ShellService:
    """Shell access service"""
    
    def __init__(self, http_client: HTTPClient):
        self.http_client = http_client
    
    async def get_connection_info(self, session_id: str) -> Dict[str, Any]:
        """Get shell connection information"""
        try:
            response = await self.http_client.get(f"/v1/sessions/{session_id}/shell")
            return response
        except Exception as e:
            raise ShellError(f"Failed to get shell info: {e}")
    
    async def execute_command(
        self,
        session_id: str,
        command: str,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Execute command in session shell"""
        try:
            response = await self.http_client.post(
                f"/v1/sessions/{session_id}/shell/execute",
                json={"command": command, "timeout": timeout}
            )
            return response
        except Exception as e:
            raise ShellError(f"Failed to execute command: {e}")
    
    async def get_shell_status(self, session_id: str) -> Dict[str, Any]:
        """Get shell status"""
        try:
            response = await self.http_client.get(f"/v1/sessions/{session_id}/shell/status")
            return response
        except Exception as e:
            raise ShellError(f"Failed to get shell status: {e}")
