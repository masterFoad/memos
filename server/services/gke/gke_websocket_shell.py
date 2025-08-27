"""
GKE WebSocket Shell Service - Interactive shell for GKE pods
Based on imru_official implementation, adapted for OnMemOS v3
"""

import asyncio
import json
import shlex
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from fastapi import WebSocket
from websockets.exceptions import ConnectionClosed

from server.core.logging import get_websocket_logger, get_gke_logger
from .gke_service import gke_service

websocket_logger = get_websocket_logger()
gke_logger = get_gke_logger()

class ShellCommandType(Enum):
    """Types of shell commands"""
    SYSTEM = "system"      # /help, /status, /clear
    WORKSPACE = "workspace"  # /upload, /download, /list
    FILE = "file"          # /cat, /edit, /rm
    PROCESS = "process"    # /ps, /kill, /top
    NETWORK = "network"    # /curl, /ping, /netstat
    CUSTOM = "custom"      # User-defined commands

@dataclass
class ShellCommand:
    """Shell command definition"""
    name: str
    description: str
    usage: str
    category: ShellCommandType
    handler: Callable
    requires_auth: bool = True
    admin_only: bool = False

@dataclass
class ShellResponse:
    """Standardized shell response"""
    type: str  # "output", "error", "info", "warning", "success"
    content: str
    timestamp: str
    command_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class GKEShellSession:
    """Individual WebSocket session for GKE interactive shell"""
    
    def __init__(self, websocket: WebSocket, session_id: str, 
                 k8s_ns: str, pod_name: str, shell_service: 'GKEShellService'):
        self.websocket = websocket
        self.session_id = session_id
        self.k8s_ns = k8s_ns
        self.pod_name = pod_name
        self.shell_service = shell_service
        self.is_running = False
        self.command_history: List[str] = []
        self.max_history = 100
        
        # Session metadata
        self.created_at = datetime.now(timezone.utc)
        self.last_activity = self.created_at
        self.command_count = 0
    
    async def run(self):
        """Main session loop"""
        self.is_running = True
        
        try:
            # Check if we should be quiet (for testing)
            quiet = False
            try:
                # Try to get quiet parameter from query string
                if hasattr(self.websocket, 'query_params'):
                    quiet = self.websocket.query_params.get('quiet', '0') == '1'
            except:
                pass
            
            if not quiet:
                # Send welcome message
                await self.send_response(ShellResponse(
                    type="info",
                    content="🚀 Welcome to OnMemOS GKE Interactive Shell!\nType /help for available commands.",
                    timestamp=datetime.now(timezone.utc).isoformat()
                ))
                
                # Send prompt
                await self._send_prompt()
            
            # Main message loop
            while True:
                try:
                    message = await self.websocket.receive_text()
                    await self._handle_message(message)
                except ConnectionClosed as e:
                    # Normal WebSocket closure - not an error
                    if e.code == 1000:
                        websocket_logger.debug(f"WebSocket connection closed normally: {e}")
                    else:
                        websocket_logger.info(f"WebSocket connection closed with code {e.code}: {e}")
                    break
                except Exception as e:
                    websocket_logger.error(f"Error receiving message: {e}")
                    break
                
        except ConnectionClosed:
            websocket_logger.info(f"WebSocket connection closed for session {self.session_id}")
        except Exception as e:
            websocket_logger.error(f"Session error: {e}")
            await self.send_response(ShellResponse(
                type="error",
                content=f"Session error: {str(e)}",
                timestamp=datetime.now(timezone.utc).isoformat()
            ))
        finally:
            self.is_running = False
            await self.cleanup()
    
    async def _handle_message(self, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            message_type = data.get("type", "command")
            
            if message_type == "command":
                await self._handle_command(data.get("command", ""))
            elif message_type == "ping":
                await self._handle_ping()
            elif message_type == "resize":
                await self._handle_resize(data.get("cols", 80), data.get("rows", 24))
            else:
                await self.send_response(ShellResponse(
                    type="error",
                    content=f"Unknown message type: {message_type}",
                    timestamp=datetime.now(timezone.utc).isoformat()
                ))
                
        except json.JSONDecodeError:
            # Treat as raw command
            await self._handle_command(message)
        except Exception as e:
            websocket_logger.error(f"Message handling error: {str(e)}")
            await self.send_response(ShellResponse(
                type="error",
                content=f"Message handling error: {str(e)}",
                timestamp=datetime.now(timezone.utc).isoformat()
            ))
    
    async def _handle_command(self, command: str):
        """Handle shell command"""
        if not command.strip():
            await self._send_prompt()
            return
        
        self.command_count += 1
        self.last_activity = datetime.now(timezone.utc)
        
        # Add to history
        self.command_history.append(command)
        if len(self.command_history) > self.max_history:
            self.command_history.pop(0)
        
        # Check if it's a slash command
        if command.startswith('/'):
            await self._handle_slash_command(command)
        else:
            await self._handle_shell_command(command)
    
    async def _handle_slash_command(self, command: str):
        """Handle slash commands"""
        try:
            # Parse command
            parts = shlex.split(command)
            cmd_name = parts[0]
            args = parts[1:] if len(parts) > 1 else []
            
            # Find command handler
            if cmd_name in self.shell_service.commands:
                cmd = self.shell_service.commands[cmd_name]
                
                # Execute command
                response = await cmd.handler(self, args)
                await self.send_response(response)
                
            else:
                await self.send_response(ShellResponse(
                    type="error",
                    content=f"Unknown command: {cmd_name}. Type /help for available commands.",
                    timestamp=datetime.now(timezone.utc).isoformat()
                ))
                
        except Exception as e:
            websocket_logger.error(f"Command error: {str(e)}")
            await self.send_response(ShellResponse(
                type="error",
                content=f"Command error: {str(e)}",
                timestamp=datetime.now(timezone.utc).isoformat()
            ))
        
        await self._send_prompt()
    
    async def _handle_shell_command(self, command: str):
        """Handle regular shell commands"""
        try:
            # Execute command in pod using gke_service
            result = gke_service.exec_in_workspace(
                workspace_id=self.session_id,
                k8s_ns=self.k8s_ns,
                pod=self.pod_name,
                command=command,
                timeout=120
            )
            
            if result["success"]:
                await self.send_response(ShellResponse(
                    type="output",
                    content=result["stdout"],
                    timestamp=datetime.now(timezone.utc).isoformat()
                ))
                
                if result["stderr"]:
                    await self.send_response(ShellResponse(
                        type="warning",
                        content=f"stderr: {result['stderr']}",
                        timestamp=datetime.now(timezone.utc).isoformat()
                    ))
            else:
                await self.send_response(ShellResponse(
                    type="error",
                    content=f"Command failed (rc={result['returncode']}): {result['stderr']}",
                    timestamp=datetime.now(timezone.utc).isoformat()
                ))
            
        except Exception as e:
            gke_logger.error(f"Command execution failed: {str(e)}")
            await self.send_response(ShellResponse(
                type="error",
                content=f"Command execution failed: {str(e)}",
                timestamp=datetime.now(timezone.utc).isoformat()
            ))
        
        await self._send_prompt()
    
    async def _handle_ping(self):
        """Handle ping message"""
        await self.websocket.send_text(json.dumps({
            "type": "pong",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))
    
    async def _handle_resize(self, cols: int, rows: int):
        """Handle terminal resize"""
        try:
            # Set terminal size in pod
            gke_service.exec_in_workspace(
                workspace_id=self.session_id,
                k8s_ns=self.k8s_ns,
                pod=self.pod_name,
                command=f"stty cols {cols} rows {rows}",
                timeout=30
            )
        except Exception as e:
            websocket_logger.warning(f"Failed to resize terminal: {e}")
    
    async def _send_prompt(self):
        """Send shell prompt"""
        try:
            # Get current working directory
            pwd_result = gke_service.exec_in_workspace(
                workspace_id=self.session_id,
                k8s_ns=self.k8s_ns,
                pod=self.pod_name,
                command="pwd",
                timeout=30
            )
            
            # Get username
            user_result = gke_service.exec_in_workspace(
                workspace_id=self.session_id,
                k8s_ns=self.k8s_ns,
                pod=self.pod_name,
                command="whoami",
                timeout=30
            )
            
            if pwd_result["success"] and user_result["success"]:
                pwd = pwd_result["stdout"].strip()
                user = user_result["stdout"].strip()
                prompt = f"{user}@{self.pod_name}:{pwd}$ "
            else:
                prompt = f"root@{self.pod_name}:/$ "
            
        except Exception as e:
            # Fallback prompt
            prompt = f"root@{self.pod_name}:/$ "
        
        await self.send_response(ShellResponse(
            type="prompt",
            content=prompt,
            timestamp=datetime.now(timezone.utc).isoformat()
        ))
    
    async def send_response(self, response: ShellResponse):
        """Send response to client"""
        try:
            message = {
                "type": response.type,
                "content": response.content,
                "timestamp": response.timestamp,
                "session_id": self.session_id
            }
            
            if response.command_id:
                message["command_id"] = response.command_id
            
            if response.metadata:
                message["metadata"] = response.metadata
            
            await self.websocket.send_text(json.dumps(message))
            
        except Exception as e:
            websocket_logger.error(f"Failed to send response: {e}")
    
    async def cleanup(self):
        """Clean up session resources"""
        try:
            # Keep pod running for now
            pass
        except Exception as e:
            websocket_logger.error(f"Cleanup error: {e}")
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get session information"""
        return {
            "session_id": self.session_id,
            "k8s_ns": self.k8s_ns,
            "pod_name": self.pod_name,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "command_count": self.command_count,
            "is_running": self.is_running
        }

class GKEShellService:
    """WebSocket-based interactive shell service for GKE"""
    
    def __init__(self):
        self.active_sessions: Dict[str, GKEShellSession] = {}
        self.commands: Dict[str, ShellCommand] = {}
        self._register_default_commands()
    
    def _register_default_commands(self):
        """Register default slash commands"""
        
        # System commands
        self.register_command(ShellCommand(
            name="help",
            description="Show available commands",
            usage="/help [category]",
            category=ShellCommandType.SYSTEM,
            handler=self._cmd_help
        ))
        
        self.register_command(ShellCommand(
            name="status",
            description="Show workspace status",
            usage="/status",
            category=ShellCommandType.SYSTEM,
            handler=self._cmd_status
        ))
        
        self.register_command(ShellCommand(
            name="clear",
            description="Clear terminal",
            usage="/clear",
            category=ShellCommandType.SYSTEM,
            handler=self._cmd_clear
        ))
        
        # Workspace commands
        self.register_command(ShellCommand(
            name="list",
            description="List workspace files",
            usage="/list [path]",
            category=ShellCommandType.WORKSPACE,
            handler=self._cmd_list
        ))
        
        self.register_command(ShellCommand(
            name="pwd",
            description="Show current directory",
            usage="/pwd",
            category=ShellCommandType.WORKSPACE,
            handler=self._cmd_pwd
        ))
        
        self.register_command(ShellCommand(
            name="ls",
            description="List directory contents",
            usage="/ls [path]",
            category=ShellCommandType.WORKSPACE,
            handler=self._cmd_ls
        ))
        
        # File commands
        self.register_command(ShellCommand(
            name="cat",
            description="Display file contents",
            usage="/cat <file_path>",
            category=ShellCommandType.FILE,
            handler=self._cmd_cat
        ))
        
        self.register_command(ShellCommand(
            name="rm",
            description="Remove file or directory",
            usage="/rm <path>",
            category=ShellCommandType.FILE,
            handler=self._cmd_rm
        ))
        
        # Process commands
        self.register_command(ShellCommand(
            name="ps",
            description="List running processes",
            usage="/ps",
            category=ShellCommandType.PROCESS,
            handler=self._cmd_ps
        ))
        
        self.register_command(ShellCommand(
            name="kill",
            description="Kill process",
            usage="/kill <pid>",
            category=ShellCommandType.PROCESS,
            handler=self._cmd_kill
        ))
        
        # Network commands
        self.register_command(ShellCommand(
            name="curl",
            description="Make HTTP request",
            usage="/curl <url> [options]",
            category=ShellCommandType.NETWORK,
            handler=self._cmd_curl
        ))
        
        self.register_command(ShellCommand(
            name="ping",
            description="Ping host",
            usage="/ping <host>",
            category=ShellCommandType.NETWORK,
            handler=self._cmd_ping
        ))
        
        # Environment commands
        self.register_command(ShellCommand(
            name="env",
            description="Show environment variables",
            usage="/env",
            category=ShellCommandType.SYSTEM,
            handler=self._cmd_env
        ))
        
        self.register_command(ShellCommand(
            name="df",
            description="Show disk usage",
            usage="/df",
            category=ShellCommandType.SYSTEM,
            handler=self._cmd_df
        ))
    
    def register_command(self, command: ShellCommand):
        """Register a new slash command"""
        self.commands[f"/{command.name}"] = command
        gke_logger.info(f"Registered GKE command: /{command.name}")
    
    async def handle_websocket(self, websocket: WebSocket, session_id: str, k8s_ns: str, pod_name: str):
        """Handle WebSocket connection for interactive shell"""
        
        try:
            # Normalize k8s namespace to include the prefix
            try:
                ns_prefix = "onmemos"
                if not k8s_ns.startswith(f"{ns_prefix}-"):
                    k8s_ns = f"{ns_prefix}-{k8s_ns}"
            except Exception:
                pass
            
            # Create shell session
            session = GKEShellSession(websocket, session_id, k8s_ns, pod_name, self)
            self.active_sessions[session_id] = session
            
            websocket_logger.info(f"GKE shell session started: {session_id} for pod {pod_name} in {k8s_ns}")
            
            # Handle shell interaction
            await session.run()
            
        except Exception as e:
            websocket_logger.error(f"GKE shell session error: {e}")
        finally:
            if session_id in self.active_sessions:
                await self.active_sessions[session_id].cleanup()
                del self.active_sessions[session_id]
    
    # Command handlers
    async def _cmd_help(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /help command"""
        if args:
            category = args[0].upper()
            try:
                category_enum = ShellCommandType(category)
                commands = [cmd for cmd in self.commands.values() if cmd.category == category_enum]
            except ValueError:
                return ShellResponse("error", f"Unknown category: {category}", datetime.now(timezone.utc).isoformat())
        else:
            commands = list(self.commands.values())
        
        help_text = "📚 Available Commands:\n\n"
        for cmd in commands:
            help_text += f"🔹 {cmd.name}: {cmd.description}\n"
            help_text += f"   Usage: {cmd.usage}\n\n"
        
        return ShellResponse("info", help_text, datetime.now(timezone.utc).isoformat())
    
    async def _cmd_status(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /status command"""
        try:
            # Get pod status
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id,
                k8s_ns=session.k8s_ns,
                pod=session.pod_name,
                command="echo 'Pod is running'",
                timeout=30
            )
            
            status_text = f"📊 GKE Pod Status:\n"
            status_text += f"🔹 Session ID: {session.session_id}\n"
            status_text += f"🔹 Namespace: {session.k8s_ns}\n"
            status_text += f"🔹 Pod: {session.pod_name}\n"
            status_text += f"🔹 Status: {'Running' if result['success'] else 'Error'}\n"
            status_text += f"🔹 Connected: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            status_text += f"🔹 Commands executed: {session.command_count}\n"
            
            return ShellResponse("info", status_text, datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"Failed to get status: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_clear(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /clear command"""
        return ShellResponse("clear", "", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_list(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /list command"""
        path = args[0] if args else "/workspace"
        
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id,
                k8s_ns=session.k8s_ns,
                pod=session.pod_name,
                command=f"ls -la {shlex.quote(path)}",
                timeout=60
            )
            
            if result["success"]:
                return ShellResponse("output", result["stdout"], datetime.now(timezone.utc).isoformat())
            else:
                return ShellResponse("error", f"List failed: {result['stderr']}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"List failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_pwd(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /pwd command"""
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id,
                k8s_ns=session.k8s_ns,
                pod=session.pod_name,
                command="pwd",
                timeout=30
            )
            
            if result["success"]:
                return ShellResponse("output", result["stdout"], datetime.now(timezone.utc).isoformat())
            else:
                return ShellResponse("error", f"PWD failed: {result['stderr']}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"PWD failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_ls(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /ls command"""
        path = args[0] if args else "."
        
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id,
                k8s_ns=session.k8s_ns,
                pod=session.pod_name,
                command=f"ls -la {shlex.quote(path)}",
                timeout=60
            )
            
            if result["success"]:
                return ShellResponse("output", result["stdout"], datetime.now(timezone.utc).isoformat())
            else:
                return ShellResponse("error", f"LS failed: {result['stderr']}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"LS failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_cat(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /cat command"""
        if len(args) < 1:
            return ShellResponse("error", "Usage: /cat <file_path>", datetime.now(timezone.utc).isoformat())
        
        file_path = args[0]
        
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id,
                k8s_ns=session.k8s_ns,
                pod=session.pod_name,
                command=f"cat {shlex.quote(file_path)}",
                timeout=60
            )
            
            if result["success"]:
                return ShellResponse("output", result["stdout"], datetime.now(timezone.utc).isoformat())
            else:
                return ShellResponse("error", f"Cat failed: {result['stderr']}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"Cat failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_rm(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /rm command"""
        if len(args) < 1:
            return ShellResponse("error", "Usage: /rm <path>", datetime.now(timezone.utc).isoformat())
        
        path = args[0]
        
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id,
                k8s_ns=session.k8s_ns,
                pod=session.pod_name,
                command=f"rm -rf {shlex.quote(path)}",
                timeout=60
            )
            
            if result["success"]:
                return ShellResponse("success", f"🗑️ Removed {path}", datetime.now(timezone.utc).isoformat())
            else:
                return ShellResponse("error", f"Remove failed: {result['stderr']}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"Remove failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_ps(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /ps command"""
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id,
                k8s_ns=session.k8s_ns,
                pod=session.pod_name,
                command="ps aux",
                timeout=60
            )
            
            if result["success"]:
                return ShellResponse("output", result["stdout"], datetime.now(timezone.utc).isoformat())
            else:
                return ShellResponse("error", f"PS failed: {result['stderr']}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"PS failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_kill(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /kill command"""
        if len(args) < 1:
            return ShellResponse("error", "Usage: /kill <pid>", datetime.now(timezone.utc).isoformat())
        
        pid = args[0]
        
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id,
                k8s_ns=session.k8s_ns,
                pod=session.pod_name,
                command=f"kill {shlex.quote(pid)}",
                timeout=30
            )
            
            if result["success"]:
                return ShellResponse("success", f"💀 Killed process {pid}", datetime.now(timezone.utc).isoformat())
            else:
                return ShellResponse("error", f"Kill failed: {result['stderr']}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"Kill failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_curl(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /curl command"""
        if len(args) < 1:
            return ShellResponse("error", "Usage: /curl <url> [options]", datetime.now(timezone.utc).isoformat())
        
        url = args[0]
        options = " ".join(args[1:]) if len(args) > 1 else ""
        
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id,
                k8s_ns=session.k8s_ns,
                pod=session.pod_name,
                command=f"curl {options} {shlex.quote(url)}",
                timeout=120
            )
            
            if result["success"]:
                return ShellResponse("output", result["stdout"], datetime.now(timezone.utc).isoformat())
            else:
                return ShellResponse("error", f"Curl failed: {result['stderr']}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"Curl failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_ping(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /ping command"""
        if len(args) < 1:
            return ShellResponse("error", "Usage: /ping <host>", datetime.now(timezone.utc).isoformat())
        
        host = args[0]
        
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id,
                k8s_ns=session.k8s_ns,
                pod=session.pod_name,
                command=f"ping -c 3 {shlex.quote(host)}",
                timeout=60
            )
            
            if result["success"]:
                return ShellResponse("output", result["stdout"], datetime.now(timezone.utc).isoformat())
            else:
                return ShellResponse("error", f"Ping failed: {result['stderr']}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"Ping failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_env(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /env command"""
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id,
                k8s_ns=session.k8s_ns,
                pod=session.pod_name,
                command="env | sort",
                timeout=60
            )
            
            if result["success"]:
                return ShellResponse("output", result["stdout"], datetime.now(timezone.utc).isoformat())
            else:
                return ShellResponse("error", f"ENV failed: {result['stderr']}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"ENV failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_df(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /df command"""
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id,
                k8s_ns=session.k8s_ns,
                pod=session.pod_name,
                command="df -h",
                timeout=60
            )
            
            if result["success"]:
                return ShellResponse("output", result["stdout"], datetime.now(timezone.utc).isoformat())
            else:
                return ShellResponse("error", f"DF failed: {result['stderr']}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"DF failed: {str(e)}", datetime.now(timezone.utc).isoformat())

# Global instance
gke_shell_service = GKEShellService()
