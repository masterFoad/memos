#!/usr/bin/env python3
"""
OnMemOS v3 Session Client
========================
Unified client for all session backends:
- Cloud Run (Service + Jobs)
- GKE Autopilot (per-user Pod)
- Cloud Workstations (per-user WS)

Provides consistent interfaces across all backends with backend-specific optimizations.
"""

import time
import json
import asyncio
import websockets
from typing import Dict, Any, List, Optional, Union, ContextManager
from dataclasses import dataclass
from enum import Enum
from contextlib import contextmanager

from .client import OnMemOSClient

class SessionType(Enum):
    """Supported session backend types"""
    CLOUD_RUN = "cloud_run"
    GKE = "gke"
    WORKSTATIONS = "workstations"

@dataclass
class SessionConfig:
    """Configuration for session creation"""
    template: str = "python"
    namespace: str = "default"
    user: str = "default"
    ttl_minutes: int = 180
    storage_options: Optional[Dict[str, Any]] = None
    backend_specific_options: Optional[Dict[str, Any]] = None

@dataclass
class SessionInfo:
    """Information about a session"""
    id: str
    type: SessionType
    namespace: str
    user: str
    status: str
    url: Optional[str] = None
    websocket: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    created_at: Optional[float] = None
    ttl_minutes: Optional[int] = None

@dataclass
class CommandResult:
    """Result of command execution"""
    success: bool
    stdout: str
    stderr: str
    returncode: int
    execution_time: float
    backend_type: SessionType

class SessionClient:
    """Unified client for all session backends"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8080", api_key: str = "onmemos-internal-key-2024-secure"):
        self.client = OnMemOSClient(base_url, api_key)
        self.sessions: Dict[str, SessionInfo] = {}
    
    def create_session(self, session_type: SessionType, config: SessionConfig) -> SessionInfo:
        """Create a session of the specified type"""
        if session_type == SessionType.CLOUD_RUN:
            return self._create_cloudrun_session(config)
        elif session_type == SessionType.GKE:
            return self._create_gke_session(config)
        elif session_type == SessionType.WORKSTATIONS:
            return self._create_workstation_session(config)
        else:
            raise ValueError(f"Unsupported session type: {session_type}")
    
    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Get session information"""
        if session_id in self.sessions:
            return self.sessions[session_id]
        
        # Try to get session from the unified sessions API first
        try:
            response = self.client._make_request("GET", f"/v1/sessions/{session_id}")
            session_data = response.json()
            
            # Determine session type from the response
            provider = session_data.get("provider", "cloud_run")
            if provider == "gke":
                session_type = SessionType.GKE
            elif provider == "workstations":
                session_type = SessionType.WORKSTATIONS
            else:
                session_type = SessionType.CLOUD_RUN
            
            return SessionInfo(
                id=session_data["id"],
                type=session_type,
                namespace=session_data["namespace"],
                user=session_data["user"],
                status=session_data["status"],
                url=session_data.get("url"),
                websocket=session_data.get("websocket"),
                details=session_data.get("details", {})
            )
        except Exception as e:
            print(f"DEBUG: Sessions API failed for {session_id}: {e}")
            pass
        
        # Fallback: Try to find session by ID across all backends
        for session_type in SessionType:
            try:
                if session_type == SessionType.CLOUD_RUN:
                    workspace = self.client.get_cloudrun_workspace(session_id)
                    if workspace:
                        return SessionInfo(
                            id=workspace["id"],
                            type=SessionType.CLOUD_RUN,
                            namespace=workspace["namespace"],
                            user=workspace["user"],
                            status=workspace["status"],
                            url=workspace.get("service_url"),
                            details=workspace
                        )
                # Add Workstations implementation here
            except Exception:
                continue
        
        return None
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        try:
            if session.type == SessionType.CLOUD_RUN:
                return self.client.delete_cloudrun_workspace(session_id)
            elif session.type == SessionType.GKE:
                return self._delete_gke_session(session_id)
            elif session.type == SessionType.WORKSTATIONS:
                return self._delete_workstation_session(session_id)
        except Exception:
            return False
        
        return True
    
    def execute_command(self, session_id: str, command: str, timeout: int = 60) -> CommandResult:
        """Execute a command in a session"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        start_time = time.time()
        
        try:
            if session.type == SessionType.CLOUD_RUN:
                result = self.client.execute_in_cloudrun_workspace(session_id, command, timeout)
            elif session.type == SessionType.GKE:
                result = self._execute_gke_command(session_id, command, timeout)
            elif session.type == SessionType.WORKSTATIONS:
                result = self._execute_workstation_command(session_id, command, timeout)
            
            execution_time = time.time() - start_time
            
            return CommandResult(
                success=result["success"],
                stdout=result["stdout"],
                stderr=result["stderr"],
                returncode=result["returncode"],
                execution_time=execution_time,
                backend_type=session.type
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return CommandResult(
                success=False,
                stdout="",
                stderr=str(e),
                returncode=-1,
                execution_time=execution_time,
                backend_type=session.type
            )
    
    def execute_python(self, session_id: str, code: str, timeout: int = 90) -> CommandResult:
        """Execute Python code in a session"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        start_time = time.time()
        
        try:
            if session.type == SessionType.CLOUD_RUN:
                result = self.client.run_python_in_cloudrun_workspace(session_id, code)
            elif session.type == SessionType.GKE:
                result = self._execute_gke_python(session_id, code, timeout)
            elif session.type == SessionType.WORKSTATIONS:
                result = self._execute_workstation_python(session_id, code, timeout)
            
            execution_time = time.time() - start_time
            
            return CommandResult(
                success=result["success"],
                stdout=result["stdout"],
                stderr=result["stderr"],
                returncode=result["returncode"],
                execution_time=execution_time,
                backend_type=session.type
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return CommandResult(
                success=False,
                stdout="",
                stderr=str(e),
                returncode=-1,
                execution_time=execution_time,
                backend_type=session.type
            )
    
    async def connect_websocket(self, session_id: str) -> 'WebSocketSession':
        """Connect to a session via WebSocket (for interactive use)"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        if session.type == SessionType.CLOUD_RUN:
            return await self._connect_cloudrun_websocket(session_id)
        elif session.type == SessionType.GKE:
            return await self._connect_gke_websocket(session_id)
        elif session.type == SessionType.WORKSTATIONS:
            return await self._connect_workstation_websocket(session_id)
        else:
            raise ValueError(f"WebSocket not supported for session type: {session.type}")
    
    def list_sessions(self, session_type: Optional[SessionType] = None, 
                     namespace: Optional[str] = None, user: Optional[str] = None) -> List[SessionInfo]:
        """List sessions with optional filtering"""
        sessions = []
        
        if session_type is None or session_type == SessionType.CLOUD_RUN:
            try:
                cloudrun_workspaces = self.client.list_cloudrun_workspaces(namespace, user)
                for ws in cloudrun_workspaces["workspaces"]:
                    sessions.append(SessionInfo(
                        id=ws["id"],
                        type=SessionType.CLOUD_RUN,
                        namespace=ws["namespace"],
                        user=ws["user"],
                        status=ws["status"],
                        url=ws.get("service_url"),
                        details=ws
                    ))
            except Exception:
                pass
        
        # Add GKE and Workstations implementations here
        
        return sessions
    
    @contextmanager
    def session(self, session_type: SessionType, config: SessionConfig) -> ContextManager[SessionInfo]:
        """Context manager for session lifecycle"""
        session = self.create_session(session_type, config)
        try:
            yield session
        finally:
            self.delete_session(session.id)
    
    # Backend-specific implementations
    
    def _create_cloudrun_session(self, config: SessionConfig) -> SessionInfo:
        """Create a Cloud Run session"""
        workspace = self.client.create_cloudrun_workspace(
            template=config.template,
            namespace=config.namespace,
            user=config.user,
            ttl_minutes=config.ttl_minutes,
            storage_options=config.storage_options or {}
        )
        
        session = SessionInfo(
            id=workspace["id"],
            type=SessionType.CLOUD_RUN,
            namespace=workspace["namespace"],
            user=workspace["user"],
            status=workspace["status"],
            url=workspace["service_url"],
            details=workspace,
            created_at=workspace.get("created_at"),
            ttl_minutes=workspace.get("ttl_minutes")
        )
        
        self.sessions[session.id] = session
        return session
    
    def _create_gke_session(self, config: SessionConfig) -> SessionInfo:
        """Create a GKE session (placeholder)"""
        raise NotImplementedError("GKE sessions not implemented yet")
    
    def _create_workstation_session(self, config: SessionConfig) -> SessionInfo:
        """Create a Cloud Workstation session (placeholder)"""
        raise NotImplementedError("Cloud Workstation sessions not implemented yet")
    
    def _delete_gke_session(self, session_id: str) -> bool:
        """Delete a GKE session (placeholder)"""
        raise NotImplementedError("GKE sessions not implemented yet")
    
    def _delete_workstation_session(self, session_id: str) -> bool:
        """Delete a Cloud Workstation session (placeholder)"""
        raise NotImplementedError("Cloud Workstation sessions not implemented yet")
    
    def _execute_gke_command(self, session_id: str, command: str, timeout: int) -> Dict[str, Any]:
        """Execute command in GKE session (placeholder)"""
        raise NotImplementedError("GKE sessions not implemented yet")
    
    def _execute_workstation_command(self, session_id: str, command: str, timeout: int) -> Dict[str, Any]:
        """Execute command in Workstation session (placeholder)"""
        raise NotImplementedError("Cloud Workstation sessions not implemented yet")
    
    def _execute_gke_python(self, session_id: str, code: str, timeout: int) -> Dict[str, Any]:
        """Execute Python in GKE session (placeholder)"""
        raise NotImplementedError("GKE sessions not implemented yet")
    
    def _execute_workstation_python(self, session_id: str, code: str, timeout: int) -> Dict[str, Any]:
        """Execute Python in Workstation session (placeholder)"""
        raise NotImplementedError("Cloud Workstation sessions not implemented yet")
    
    async def _connect_cloudrun_websocket(self, session_id: str) -> 'WebSocketSession':
        """Connect to Cloud Run WebSocket"""
        ws_url = f"ws://127.0.0.1:8080/v1/cloudrun/workspaces/{session_id}/shell?api_key={self.client.api_key}"
        websocket = await websockets.connect(ws_url)
        return WebSocketSession(websocket, SessionType.CLOUD_RUN)
    
    async def _connect_gke_websocket(self, session_id: str) -> 'WebSocketSession':
        """Connect to GKE WebSocket (placeholder)"""
        raise NotImplementedError("GKE WebSocket not implemented yet")
    
    async def _connect_workstation_websocket(self, session_id: str) -> 'WebSocketSession':
        """Connect to Workstation WebSocket (placeholder)"""
        raise NotImplementedError("Cloud Workstation WebSocket not implemented yet")

class WebSocketSession:
    """WebSocket session for interactive use"""
    
    def __init__(self, websocket, session_type: SessionType):
        self.websocket = websocket
        self.session_type = session_type
    
    async def send_command(self, command: str) -> Dict[str, Any]:
        """Send a command via WebSocket"""
        message = {
            "type": "command",
            "command": command
        }
        await self.websocket.send(json.dumps(message))
        
        response = await self.websocket.recv()
        return json.loads(response)
    
    async def send_slash_command(self, command: str) -> Dict[str, Any]:
        """Send a slash command via WebSocket"""
        message = {
            "type": "slash_command",
            "command": command
        }
        await self.websocket.send(json.dumps(message))
        
        response = await self.websocket.recv()
        return json.loads(response)
    
    async def close(self):
        """Close the WebSocket connection"""
        await self.websocket.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

# Convenience functions for common use cases

def create_cloudrun_session(template: str = "python", namespace: str = "default", 
                           user: str = "default", ttl_minutes: int = 180) -> SessionInfo:
    """Create a Cloud Run session with default settings"""
    client = SessionClient()
    config = SessionConfig(template=template, namespace=namespace, user=user, ttl_minutes=ttl_minutes)
    return client.create_session(SessionType.CLOUD_RUN, config)

def execute_in_session(session_id: str, command: str, timeout: int = 60) -> CommandResult:
    """Execute a command in any session type"""
    client = SessionClient()
    return client.execute_command(session_id, command, timeout)

def execute_python_in_session(session_id: str, code: str, timeout: int = 90) -> CommandResult:
    """Execute Python code in any session type"""
    client = SessionClient()
    return client.execute_python(session_id, code, timeout)

@contextmanager
def cloudrun_session(template: str = "python", namespace: str = "default", 
                    user: str = "default", ttl_minutes: int = 180) -> ContextManager[SessionInfo]:
    """Context manager for Cloud Run sessions"""
    client = SessionClient()
    config = SessionConfig(template=template, namespace=namespace, user=user, ttl_minutes=ttl_minutes)
    with client.session(SessionType.CLOUD_RUN, config) as session:
        yield session

# Example usage:
if __name__ == "__main__":
    # Example 1: Simple Cloud Run session
    with cloudrun_session(template="python", namespace="test", user="demo") as session:
        print(f"Created session: {session.id}")
        
        # Execute a command
        result = execute_in_session(session.id, "echo 'Hello from Cloud Run!'")
        print(f"Command result: {result.stdout}")
        
        # Execute Python code
        python_result = execute_python_in_session(session.id, """
import os
import sys
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Environment: {os.environ.get('WORKSPACE_ID', 'Not set')}")
""")
        print(f"Python result: {python_result.stdout}")
    
    # Example 2: Using the session client directly
    client = SessionClient()
    
    # Create a session
    config = SessionConfig(template="python", namespace="advanced", user="developer")
    session = client.create_session(SessionType.CLOUD_RUN, config)
    
    try:
        # Execute multiple commands
        commands = [
            "pwd",
            "ls -la",
            "python3 --version",
            "echo 'Session ID: $WORKSPACE_ID'"
        ]
        
        for cmd in commands:
            result = client.execute_command(session.id, cmd)
            print(f"Command: {cmd}")
            print(f"Result: {result.stdout}")
            print(f"Success: {result.success}")
            print("---")
    
    finally:
        # Clean up
        client.delete_session(session.id)
    
    # Example 3: WebSocket interactive session
    async def interactive_example():
        client = SessionClient()
        config = SessionConfig(template="python", namespace="interactive", user="user")
        session = client.create_session(SessionType.CLOUD_RUN, config)
        
        try:
            async with client.connect_websocket(session.id) as ws:
                # Send a command
                response = await ws.send_command("echo 'Interactive session!'")
                print(f"WebSocket response: {response}")
                
                # Send a slash command
                slash_response = await ws.send_slash_command("/help")
                print(f"Slash command response: {slash_response}")
        
        finally:
            client.delete_session(session.id)
    
    # Run the async example
    asyncio.run(interactive_example())
