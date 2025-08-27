#!/usr/bin/env python3
"""
Cloud Run WebSocket Shell Service for OnMemOS v3
===============================================
WebSocket-based interactive shell for Cloud Run workspaces with slash commands
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse

from server.services.cloudrun.cloudrun_service import cloudrun_service
from server.core.security import verify_api_key

logger = logging.getLogger(__name__)

class CloudRunShellManager:
    """Manages Cloud Run shell WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.workspace_sessions: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, workspace_id: str, api_key: str):
        """Connect to Cloud Run workspace shell"""
        await websocket.accept()
        self.active_connections[workspace_id] = websocket
        
        # Initialize workspace session
        self.workspace_sessions[workspace_id] = {
            "workspace_id": workspace_id,
            "api_key": api_key,
            "current_directory": "/workspace/work",
            "history": []
        }
        
        logger.info(f"🔗 WebSocket connected to Cloud Run workspace: {workspace_id}")
        
        # Send welcome message
        await websocket.send_text(json.dumps({
            "type": "welcome",
            "message": f"🚀 Connected to Cloud Run workspace: {workspace_id}",
            "workspace_id": workspace_id,
            "current_directory": "/workspace/work"
        }))
    
    def disconnect(self, workspace_id: str):
        """Disconnect from Cloud Run workspace shell"""
        if workspace_id in self.active_connections:
            del self.active_connections[workspace_id]
        if workspace_id in self.workspace_sessions:
            del self.workspace_sessions[workspace_id]
        
        logger.info(f"🔌 WebSocket disconnected from Cloud Run workspace: {workspace_id}")
    
    async def send_message(self, workspace_id: str, message: Dict[str, Any]):
        """Send message to specific workspace"""
        if workspace_id in self.active_connections:
            await self.active_connections[workspace_id].send_text(json.dumps(message))
    
    async def handle_slash_command(self, workspace_id: str, command: str) -> Dict[str, Any]:
        """Handle slash commands for Cloud Run workspace management"""
        try:
            parts = command.split()
            cmd = parts[0].lower()
            
            if cmd == "/help":
                return {
                    "type": "help",
                    "message": """
🎯 Cloud Run Workspace Slash Commands:
=====================================

📁 Navigation:
  /pwd                    - Show current directory
  /cd <path>             - Change directory
  /ls [path]             - List files and directories
  /tree [path]           - Show directory tree

💾 Storage:
  /buckets               - List mounted GCS buckets
  /persist               - Show persistent storage info
  /upload <local> <remote> - Upload file to bucket
  /download <remote> <local> - Download file from bucket

🔧 Workspace:
  /info                  - Show workspace information
  /status                - Show workspace status
  /restart               - Restart workspace
  /cleanup               - Clean up temporary files

📊 System:
  /ps                    - Show running processes
  /df                    - Show disk usage
  /top                   - Show system resources
  /env                   - Show environment variables

❓ Help:
  /help                  - Show this help message
  /clear                 - Clear terminal
  /exit                  - Disconnect from workspace
"""
                }
            
            elif cmd == "/info":
                workspace = cloudrun_service.get_workspace(workspace_id)
                if workspace:
                    return {
                        "type": "info",
                        "message": f"""
📋 Workspace Information:
========================
ID: {workspace['id']}
Namespace: {workspace['namespace']}
User: {workspace['user']}
Status: {workspace['status']}
Service URL: {workspace['service_url']}
"""
                    }
                else:
                    return {"type": "error", "message": "❌ Workspace not found"}
            
            elif cmd == "/status":
                workspace = cloudrun_service.get_workspace(workspace_id)
                if workspace:
                    return {
                        "type": "status",
                        "message": f"✅ Workspace {workspace_id} is {workspace['status']}"
                    }
                else:
                    return {"type": "error", "message": "❌ Workspace not found"}
            
            elif cmd == "/pwd":
                result = cloudrun_service.execute_in_workspace(workspace_id, "pwd")
                if result["success"]:
                    return {
                        "type": "command_result",
                        "command": "pwd",
                        "stdout": result["stdout"].strip(),
                        "stderr": result["stderr"]
                    }
                else:
                    return {"type": "error", "message": f"❌ Failed to get current directory: {result['stderr']}"}
            
            elif cmd == "/cd" and len(parts) > 1:
                path = parts[1]
                result = cloudrun_service.execute_in_workspace(workspace_id, f"cd {path} && pwd")
                if result["success"]:
                    new_dir = result["stdout"].strip()
                    self.workspace_sessions[workspace_id]["current_directory"] = new_dir
                    return {
                        "type": "command_result",
                        "command": f"cd {path}",
                        "stdout": f"Changed directory to: {new_dir}",
                        "stderr": result["stderr"]
                    }
                else:
                    return {"type": "error", "message": f"❌ Failed to change directory: {result['stderr']}"}
            
            elif cmd == "/ls":
                path = parts[1] if len(parts) > 1 else "."
                result = cloudrun_service.execute_in_workspace(workspace_id, f"ls -la {path}")
                if result["success"]:
                    return {
                        "type": "command_result",
                        "command": f"ls -la {path}",
                        "stdout": result["stdout"],
                        "stderr": result["stderr"]
                    }
                else:
                    return {"type": "error", "message": f"❌ Failed to list directory: {result['stderr']}"}
            
            elif cmd == "/buckets":
                result = cloudrun_service.execute_in_workspace(workspace_id, "ls -la /workspace/buckets")
                if result["success"]:
                    return {
                        "type": "command_result",
                        "command": "ls -la /workspace/buckets",
                        "stdout": result["stdout"],
                        "stderr": result["stderr"]
                    }
                else:
                    return {"type": "error", "message": f"❌ Failed to list buckets: {result['stderr']}"}
            
            elif cmd == "/persist":
                result = cloudrun_service.execute_in_workspace(workspace_id, "ls -la /workspace/persist")
                if result["success"]:
                    return {
                        "type": "command_result",
                        "command": "ls -la /workspace/persist",
                        "stdout": result["stdout"],
                        "stderr": result["stderr"]
                    }
                else:
                    return {"type": "error", "message": f"❌ Failed to list persistent storage: {result['stderr']}"}
            
            elif cmd == "/ps":
                result = cloudrun_service.execute_in_workspace(workspace_id, "ps aux")
                if result["success"]:
                    return {
                        "type": "command_result",
                        "command": "ps aux",
                        "stdout": result["stdout"],
                        "stderr": result["stderr"]
                    }
                else:
                    return {"type": "error", "message": f"❌ Failed to show processes: {result['stderr']}"}
            
            elif cmd == "/df":
                result = cloudrun_service.execute_in_workspace(workspace_id, "df -h")
                if result["success"]:
                    return {
                        "type": "command_result",
                        "command": "df -h",
                        "stdout": result["stdout"],
                        "stderr": result["stderr"]
                    }
                else:
                    return {"type": "error", "message": f"❌ Failed to show disk usage: {result['stderr']}"}
            
            elif cmd == "/env":
                result = cloudrun_service.execute_in_workspace(workspace_id, "env | sort")
                if result["success"]:
                    return {
                        "type": "command_result",
                        "command": "env | sort",
                        "stdout": result["stdout"],
                        "stderr": result["stderr"]
                    }
                else:
                    return {"type": "error", "message": f"❌ Failed to show environment: {result['stderr']}"}
            
            elif cmd == "/clear":
                return {
                    "type": "clear",
                    "message": "Terminal cleared"
                }
            
            elif cmd == "/exit":
                return {
                    "type": "exit",
                    "message": "Disconnecting from workspace..."
                }
            
            else:
                return {
                    "type": "error",
                    "message": f"❌ Unknown slash command: {cmd}. Type /help for available commands."
                }
                
        except Exception as e:
            logger.error(f"Error handling slash command in workspace {workspace_id}: {e}")
            return {"type": "error", "message": f"❌ Error executing slash command: {str(e)}"}
    
    async def handle_command(self, workspace_id: str, command: str) -> Dict[str, Any]:
        """Handle regular shell command in Cloud Run workspace"""
        try:
            # Check if it's a slash command
            if command.startswith("/"):
                return await self.handle_slash_command(workspace_id, command)
            
            # Execute regular command with longer timeout
            result = cloudrun_service.execute_in_workspace(workspace_id, command, timeout=300)
            
            return {
                "type": "command_result",
                "command": command,
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "returncode": result["returncode"],
                "success": result["success"]
            }
            
        except Exception as e:
            logger.error(f"Error executing command in workspace {workspace_id}: {e}")
            return {"type": "error", "message": f"❌ Error executing command: {str(e)}"}

# Global Cloud Run shell manager
cloudrun_shell_manager = CloudRunShellManager()

def get_api_key_from_websocket(websocket: WebSocket) -> str:
    """Get API key from WebSocket query parameters"""
    query_params = websocket.query_params
    api_key = query_params.get("api_key")
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    return api_key

async def cloudrun_shell_websocket(websocket: WebSocket, workspace_id: str):
    """WebSocket endpoint for Cloud Run shell"""
    try:
        # Get API key from query parameters
        api_key = get_api_key_from_websocket(websocket)
        
        # Connect to workspace
        await cloudrun_shell_manager.connect(websocket, workspace_id, api_key)
        
        # Handle messages
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message["type"] == "command":
                    command = message["command"]
                    
                    # Handle command
                    result = await cloudrun_shell_manager.handle_command(workspace_id, command)
                    
                    # Send result back
                    await websocket.send_text(json.dumps(result))
                    
                    # Handle exit command
                    if result["type"] == "exit":
                        break
                
                elif message["type"] == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"❌ Error: {str(e)}"
                }))
    
    except Exception as e:
        logger.error(f"WebSocket error for workspace {workspace_id}: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"❌ Connection error: {str(e)}"
        }))
    
    finally:
        # Cleanup
        cloudrun_shell_manager.disconnect(workspace_id)
