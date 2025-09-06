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
from fastapi import WebSocket, WebSocketDisconnect

from server.services.cloudrun.cloudrun_service import cloudrun_service
from server.core.security import verify_passport

logger = logging.getLogger(__name__)


class CloudRunShellManager:
    """Manages Cloud Run shell WebSocket connections"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.workspace_sessions: Dict[str, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, workspace_id: str, api_key: str):
        """Connect to Cloud Run workspace shell (accept AFTER auth done upstream)"""
        await websocket.accept()
        self.active_connections[workspace_id] = websocket

        # Initialize workspace session
        self.workspace_sessions[workspace_id] = {
            "workspace_id": workspace_id,
            "api_key": api_key,
            "current_directory": "/workspace/work",
            "history": [],
        }

        logger.info("🔗 WebSocket connected to Cloud Run workspace: %s", workspace_id)

        # Send welcome message
        await websocket.send_text(
            json.dumps(
                {
                    "type": "welcome",
                    "message": f"🚀 Connected to Cloud Run workspace: {workspace_id}",
                    "workspace_id": workspace_id,
                    "current_directory": "/workspace/work",
                }
            )
        )

    def disconnect(self, workspace_id: str):
        """Disconnect from Cloud Run workspace shell"""
        if workspace_id in self.active_connections:
            del self.active_connections[workspace_id]
        if workspace_id in self.workspace_sessions:
            del self.workspace_sessions[workspace_id]

        logger.info("🔌 WebSocket disconnected from Cloud Run workspace: %s", workspace_id)

    async def send_message(self, workspace_id: str, message: Dict[str, Any]):
        """Send message to specific workspace"""
        if workspace_id in self.active_connections:
            await self.active_connections[workspace_id].send_text(json.dumps(message))

    # ---------------- internal helpers ----------------

    async def _run_and_wait(
        self,
        workspace_id: str,
        command: str,
        *,
        timeout: int = 300,
        poll_interval: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Submit a Cloud Run job for the command and poll until it completes,
        returning stdout/stderr to preserve shell IO semantics.
        """
        submit = cloudrun_service.execute_in_workspace(workspace_id, command, timeout=timeout)
        # execute_in_workspace returns submission metadata with execution_id
        execution_id = submit.get("execution_id")
        if not submit.get("success") or not execution_id:
            return {
                "type": "command_result",
                "command": command,
                "stdout": submit.get("stdout", ""),
                "stderr": submit.get("stderr", "Failed to submit job"),
                "returncode": submit.get("returncode", 1),
                "success": False,
            }

        # Poll for completion
        deadline = asyncio.get_event_loop().time() + timeout
        last_status = None
        while True:
            status = cloudrun_service.get_job_status(execution_id)
            last_status = status
            if status.get("status") in {"completed", "failed"}:
                break
            if asyncio.get_event_loop().time() >= deadline:
                return {
                    "type": "command_result",
                    "command": command,
                    "stdout": "",
                    "stderr": "Execution timed out while waiting for job completion",
                    "returncode": None,
                    "success": False,
                }
            await asyncio.sleep(poll_interval)

        # Completed or failed: surface logs/stdout
        success = last_status.get("success", False) and last_status.get("status") == "completed"
        return {
            "type": "command_result",
            "command": command,
            "stdout": last_status.get("stdout", ""),
            "stderr": last_status.get("stderr", ""),
            "returncode": last_status.get("returncode", 0 if success else 1),
            "success": success,
        }

    # ---------------- slash commands ----------------

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
""",
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
""",
                    }
                else:
                    return {"type": "error", "message": "❌ Workspace not found"}

            elif cmd == "/status":
                workspace = cloudrun_service.get_workspace(workspace_id)
                if workspace:
                    return {"type": "status", "message": f"✅ Workspace {workspace_id} is {workspace['status']}"}
                else:
                    return {"type": "error", "message": "❌ Workspace not found"}

            elif cmd == "/pwd":
                return await self._run_and_wait(workspace_id, "pwd")

            elif cmd == "/cd" and len(parts) > 1:
                path = parts[1]
                result = await self._run_and_wait(workspace_id, f"cd {path} && pwd")
                if result.get("success"):
                    new_dir = (result.get("stdout") or "").strip()
                    self.workspace_sessions[workspace_id]["current_directory"] = new_dir or self.workspace_sessions[workspace_id]["current_directory"]
                    result["stdout"] = f"Changed directory to: {self.workspace_sessions[workspace_id]['current_directory']}"
                return result

            elif cmd == "/ls":
                path = parts[1] if len(parts) > 1 else "."
                return await self._run_and_wait(workspace_id, f"ls -la {path}")

            elif cmd == "/buckets":
                return await self._run_and_wait(workspace_id, "ls -la /workspace/buckets")

            elif cmd == "/persist":
                return await self._run_and_wait(workspace_id, "ls -la /workspace/persist")

            elif cmd == "/ps":
                return await self._run_and_wait(workspace_id, "ps aux")

            elif cmd == "/df":
                return await self._run_and_wait(workspace_id, "df -h")

            elif cmd == "/env":
                return await self._run_and_wait(workspace_id, "env | sort")

            elif cmd == "/clear":
                return {"type": "clear", "message": "Terminal cleared"}

            elif cmd == "/exit":
                return {"type": "exit", "message": "Disconnecting from workspace..."}

            else:
                return {"type": "error", "message": f"❌ Unknown slash command: {cmd}. Type /help for available commands."}

        except Exception as e:
            logger.error("Error handling slash command in workspace %s: %s", workspace_id, e)
            return {"type": "error", "message": f"❌ Error executing slash command: {str(e)}"}

    async def handle_command(self, workspace_id: str, command: str) -> Dict[str, Any]:
        """Handle regular shell command in Cloud Run workspace"""
        try:
            if command.startswith("/"):
                return await self.handle_slash_command(workspace_id, command)

            # Regular command: run & wait for completion to return stdout/stderr
            return await self._run_and_wait(workspace_id, command, timeout=300)

        except Exception as e:
            logger.error("Error executing command in workspace %s: %s", workspace_id, e)
            return {"type": "error", "message": f"❌ Error executing command: {str(e)}"}


# Global Cloud Run shell manager
cloudrun_shell_manager = CloudRunShellManager()


def get_passport_from_websocket(websocket: WebSocket) -> Optional[str]:
    """Get passport from WebSocket query parameters (no validation here)."""
    return websocket.query_params.get("passport")


async def cloudrun_shell_websocket(websocket: WebSocket, workspace_id: str):
    """WebSocket endpoint for Cloud Run shell"""
    # ---- Authenticate BEFORE accept ----
    passport = get_passport_from_websocket(websocket)
    if not passport:
        await websocket.close(code=1008, reason="passport required")
        return
    try:
        user_info = await verify_passport(x_api_key=passport)
    except Exception as e:
        logger.info("WebSocket auth failed for workspace %s: %s", workspace_id, e)
        await websocket.close(code=1008, reason="Invalid passport")
        return

    try:
        # Accept and connect
        await cloudrun_shell_manager.connect(websocket, workspace_id, user_info.get("passport_key", ""))

        # Handle messages
        while True:
            try:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    message = {"type": "command", "command": data}

                msg_type = message.get("type")
                if msg_type == "command":
                    command = message.get("command", "")
                    result = await cloudrun_shell_manager.handle_command(workspace_id, command)
                    await websocket.send_text(json.dumps(result))
                    if result.get("type") == "exit":
                        break

                elif msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

                else:
                    await websocket.send_text(json.dumps({"type": "error", "message": f"Unknown message type: {msg_type}"}))

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error("Error handling WebSocket message: %s", e)
                try:
                    await websocket.send_text(json.dumps({"type": "error", "message": f"❌ Error: {str(e)}"}))
                except Exception:
                    break

    finally:
        # Cleanup (safe even if not connected)
        cloudrun_shell_manager.disconnect(workspace_id)
