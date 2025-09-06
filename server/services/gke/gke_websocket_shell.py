"""
GKE WebSocket Shell Service - Interactive shell for GKE pods
Based on imru_official implementation, adapted for OnMemOS v3
"""

import asyncio
import json
import os
import shlex
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect  # Correct exception for FastAPI
try:
    # Optional: tolerate environments that use websockets lib directly
    from websockets.exceptions import ConnectionClosed as WSConnectionClosed
except Exception:  # pragma: no cover
    WSConnectionClosed = tuple()  # harmless fallback

from server.core.logging import get_websocket_logger, get_gke_logger
from .gke_service import gke_service
from server.database.factory import get_database_client
from server.services.billing_service import BillingService

websocket_logger = get_websocket_logger()
gke_logger = get_gke_logger()

# Optional safety: cap per-message stdout size (default unlimited)
MAX_OUT_BYTES = int(os.getenv("GKE_SHELL_MAX_OUTPUT_BYTES", "0")) or None


class ShellCommandType(Enum):
    """Types of shell commands"""
    SYSTEM = "system"       # /help, /status, /clear, /env, /df, /credits
    WORKSPACE = "workspace" # /upload, /download, /list, /pwd, /ls
    FILE = "file"           # /cat, /edit, /rm
    PROCESS = "process"     # /ps, /kill, /top
    NETWORK = "network"     # /curl, /ping, /netstat
    CUSTOM = "custom"       # User-defined commands


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
    type: str  # "output", "error", "info", "warning", "success", "clear", "prompt"
    content: str
    timestamp: str
    command_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


def _clamp_text(s: str) -> str:
    """Optionally clamp large outputs to protect the websocket client."""
    if MAX_OUT_BYTES is None or s is None:
        return s
    if len(s.encode("utf-8", errors="ignore")) <= MAX_OUT_BYTES:
        return s
    # Trim by characters (approximate), then ensure byte bound
    approx = s[:MAX_OUT_BYTES]
    while len(approx.encode("utf-8", errors="ignore")) > MAX_OUT_BYTES and approx:
        approx = approx[:-1]
    return approx + "\n\n[output truncated]\n"


class GKEShellSession:
    """Individual WebSocket session for GKE interactive shell with billing integration"""
    
    def __init__(self, websocket: WebSocket, session_id: str, 
                 k8s_ns: str, pod_name: str, shell_service: 'GKEShellService',
                 user_id: str = None):
        self.websocket = websocket
        self.session_id = session_id
        self.k8s_ns = k8s_ns
        self.pod_name = pod_name
        self.shell_service = shell_service
        self.user_id = user_id
        self.is_running = False
        self.command_history: List[str] = []
        self.max_history = 100
        
        # Session metadata
        self.created_at = datetime.now(timezone.utc)
        self.last_activity = self.created_at
        self.command_count = 0
        
        # Billing integration
        self.billing_start_time = None
        self.db = None
        self.billing_service = None
    
    async def run(self):
        """Main session loop with billing integration"""
        self.is_running = True
        
        try:
            # Initialize billing services
            await self._init_billing()
            
            # Quiet mode?
            quiet = False
            try:
                if hasattr(self.websocket, 'query_params'):
                    quiet = self.websocket.query_params.get('quiet', '0') == '1'
            except Exception:
                pass
            
            if not quiet:
                await self.send_response(ShellResponse(
                    type="info",
                    content="🚀 Welcome to OnMemOS GKE Interactive Shell!\nType /help for available commands.",
                    timestamp=datetime.now(timezone.utc).isoformat()
                ))
                
                if self.user_id:
                    await self._send_billing_info()
                
                await self._send_prompt()
            
            # Main message loop
            while True:
                try:
                    message = await self.websocket.receive_text()
                    await self._handle_message(message)
                except (WebSocketDisconnect, WSConnectionClosed):
                    websocket_logger.info(f"WebSocket disconnected for session {self.session_id}")
                    break
                except Exception as e:
                    websocket_logger.error(f"Error receiving message: {e}")
                    break
                
        except (WebSocketDisconnect, WSConnectionClosed):
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
        
        # Slash command?
        if command.startswith('/'):
            await self._handle_slash_command(command)
        else:
            await self._handle_shell_command(command)
    
    async def _handle_slash_command(self, command: str):
        """Handle slash commands"""
        try:
            parts = shlex.split(command)
            cmd_name = parts[0]
            args = parts[1:] if len(parts) > 1 else []
            
            if cmd_name in self.shell_service.commands:
                cmd = self.shell_service.commands[cmd_name]
                response = await cmd.handler(self, args)
                # Clamp outputs if needed
                if response and response.content:
                    response.content = _clamp_text(response.content)
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
        """Handle regular shell commands with credit checking"""
        try:
            if not await self._check_credits():
                await self.close()
                return
            
            result = gke_service.exec_in_workspace(
                workspace_id=self.session_id,
                k8s_ns=self.k8s_ns,
                pod=self.pod_name,
                command=command,
                timeout=120
            )
            
            if result["success"]:
                out = _clamp_text(result.get("stdout", ""))
                await self.send_response(ShellResponse(
                    type="output",
                    content=out,
                    timestamp=datetime.now(timezone.utc).isoformat()
                ))
                
                if result.get("stderr"):
                    await self.send_response(ShellResponse(
                        type="warning",
                        content=_clamp_text(f"stderr: {result['stderr']}"),
                        timestamp=datetime.now(timezone.utc).isoformat()
                    ))
            else:
                await self.send_response(ShellResponse(
                    type="error",
                    content=_clamp_text(f"Command failed (rc={result['returncode']}): {result.get('stderr','')}"),
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
    
    async def _init_billing(self):
        """Initialize billing services and start session billing"""
        try:
            if self.user_id:
                self.db = get_database_client()
                await self.db.connect()
                self.billing_service = BillingService()
                
                await self.billing_service.start_session_billing(
                    self.session_id, 
                    self.user_id, 
                    "gke_shell"  # Special tier for GKE shell sessions
                )
                self.billing_start_time = datetime.now(timezone.utc)
                websocket_logger.info(f"Started GKE shell billing: {self.session_id} for user {self.user_id}")
        except Exception as e:
            websocket_logger.error(f"Failed to initialize billing for session {self.session_id}: {e}")
    
    async def _check_credits(self) -> bool:
        """Check if user has sufficient credits"""
        try:
            if self.user_id and self.db:
                current_credits = await self.db.get_user_credits(self.user_id)
                if current_credits <= 0:
                    await self.send_response(ShellResponse(
                        type="error",
                        content="💳 Insufficient credits. Session will be terminated.",
                        timestamp=datetime.now(timezone.utc).isoformat()
                    ))
                    return False
            return True
        except Exception as e:
            websocket_logger.error(f"Error checking credits: {e}")
            return True  # Allow continuation on error
    
    async def _send_billing_info(self):
        """Send current billing information"""
        try:
            if self.user_id and self.db:
                current_credits = await self.db.get_user_credits(self.user_id)
                await self.send_response(ShellResponse(
                    type="info",
                    content=f"💳 Current Credits: ${current_credits:.2f}",
                    timestamp=datetime.now(timezone.utc).isoformat()
                ))
        except Exception as e:
            websocket_logger.error(f"Error sending billing info: {e}")
    
    async def _handle_ping(self):
        """Handle ping message"""
        await self.websocket.send_text(json.dumps({
            "type": "pong",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))
    
    async def _handle_resize(self, cols: int, rows: int):
        """Handle terminal resize (best-effort; may be no-tty)"""
        try:
            gke_service.exec_in_workspace(
                workspace_id=self.session_id,
                k8s_ns=self.k8s_ns,
                pod=self.pod_name,
                command=f"stty cols {int(cols)} rows {int(rows)}",
                timeout=30
            )
        except Exception as e:
            websocket_logger.debug(f"Resize ignored (no TTY or stty): {e}")
    
    async def _send_prompt(self):
        """Send shell prompt"""
        try:
            pwd_result = gke_service.exec_in_workspace(
                workspace_id=self.session_id,
                k8s_ns=self.k8s_ns,
                pod=self.pod_name,
                command="pwd",
                timeout=30
            )
            user_result = gke_service.exec_in_workspace(
                workspace_id=self.session_id,
                k8s_ns=self.k8s_ns,
                pod=self.pod_name,
                command="whoami",
                timeout=30
            )
            if pwd_result.get("success") and user_result.get("success"):
                pwd = (pwd_result.get("stdout") or "").strip()
                user = (user_result.get("stdout") or "").strip()
                prompt = f"{user or 'root'}@{self.pod_name}:{pwd or '/'}$ "
            else:
                prompt = f"root@{self.pod_name}:/$ "
        except Exception:
            prompt = f"root@{self.pod_name}:/$ "
        
        await self.send_response(ShellResponse(
            type="prompt",
            content=prompt,
            timestamp=datetime.now(timezone.utc).isoformat()
        ))
    
    async def close(self):
        """Close session and cleanup billing"""
        self.is_running = False
        
        try:
            if self.billing_service and self.session_id:
                final_billing = await self.billing_service.stop_session_billing(self.session_id)
                if final_billing:
                    total_cost = final_billing.get('total_cost', 0)
                    total_hours = final_billing.get('total_hours', 0)
                    websocket_logger.info(
                        f"GKE shell session {self.session_id} billing completed: {total_hours:.2f} hours = ${total_cost:.4f}"
                    )
                    if total_cost > 0 and self.user_id and self.db:
                        await self.db.deduct_credits(
                            self.user_id, 
                            total_cost, 
                            f"GKE shell session {self.session_id} runtime",
                            session_id=self.session_id
                        )
                        websocket_logger.info(
                            f"Deducted ${total_cost:.4f} from user {self.user_id} for GKE shell session {self.session_id}"
                        )
        except Exception as e:
            websocket_logger.error(f"Failed to cleanup billing for GKE shell session {self.session_id}: {e}")
        
        # Close WebSocket connection
        try:
            await self.websocket.close()
        except Exception as e:
            websocket_logger.error(f"Error closing WebSocket: {e}")
    
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
            # DB disconnect (avoid leaks)
            if self.db:
                try:
                    await self.db.disconnect()
                except Exception as e:
                    websocket_logger.debug(f"DB disconnect warning: {e}")
                finally:
                    self.db = None
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
        self.register_command(ShellCommand(
            name="help", description="Show available commands", usage="/help [category]",
            category=ShellCommandType.SYSTEM, handler=self._cmd_help
        ))
        self.register_command(ShellCommand(
            name="status", description="Show workspace status", usage="/status",
            category=ShellCommandType.SYSTEM, handler=self._cmd_status
        ))
        self.register_command(ShellCommand(
            name="credits", description="Show current credit balance", usage="/credits",
            category=ShellCommandType.SYSTEM, handler=self._cmd_credits
        ))
        self.register_command(ShellCommand(
            name="clear", description="Clear terminal", usage="/clear",
            category=ShellCommandType.SYSTEM, handler=self._cmd_clear
        ))
        # Workspace
        self.register_command(ShellCommand(
            name="list", description="List workspace files", usage="/list [path]",
            category=ShellCommandType.WORKSPACE, handler=self._cmd_list
        ))
        self.register_command(ShellCommand(
            name="pwd", description="Show current directory", usage="/pwd",
            category=ShellCommandType.WORKSPACE, handler=self._cmd_pwd
        ))
        self.register_command(ShellCommand(
            name="ls", description="List directory contents", usage="/ls [path]",
            category=ShellCommandType.WORKSPACE, handler=self._cmd_ls
        ))
        # File
        self.register_command(ShellCommand(
            name="cat", description="Display file contents", usage="/cat <file_path>",
            category=ShellCommandType.FILE, handler=self._cmd_cat
        ))
        self.register_command(ShellCommand(
            name="rm", description="Remove file or directory", usage="/rm <path>",
            category=ShellCommandType.FILE, handler=self._cmd_rm
        ))
        # Process
        self.register_command(ShellCommand(
            name="ps", description="List running processes", usage="/ps",
            category=ShellCommandType.PROCESS, handler=self._cmd_ps
        ))
        self.register_command(ShellCommand(
            name="kill", description="Kill process", usage="/kill <pid>",
            category=ShellCommandType.PROCESS, handler=self._cmd_kill
        ))
        # Network
        self.register_command(ShellCommand(
            name="curl", description="Make HTTP request", usage="/curl <url> [options]",
            category=ShellCommandType.NETWORK, handler=self._cmd_curl
        ))
        self.register_command(ShellCommand(
            name="ping", description="Ping host", usage="/ping <host>",
            category=ShellCommandType.NETWORK, handler=self._cmd_ping
        ))
        # Env/system
        self.register_command(ShellCommand(
            name="env", description="Show environment variables", usage="/env",
            category=ShellCommandType.SYSTEM, handler=self._cmd_env
        ))
        self.register_command(ShellCommand(
            name="df", description="Show disk usage", usage="/df",
            category=ShellCommandType.SYSTEM, handler=self._cmd_df
        ))
    
    def register_command(self, command: ShellCommand):
        """Register a new slash command"""
        self.commands[f"/{command.name}"] = command
        gke_logger.info(f"Registered GKE command: /{command.name}")
    
    async def handle_websocket(self, websocket: WebSocket, session_id: str, k8s_ns: str, pod_name: str, user_id: str = None):
        """Handle WebSocket connection for interactive shell with billing integration"""
        try:
            # Normalize k8s namespace using the actual service prefix
            try:
                ns_prefix = getattr(gke_service, "namespace_prefix", "onmemos")
                if not k8s_ns.startswith(f"{ns_prefix}-"):
                    k8s_ns = f"{ns_prefix}-{k8s_ns}"
            except Exception:
                pass
            
            session = GKEShellSession(websocket, session_id, k8s_ns, pod_name, self, user_id)
            self.active_sessions[session_id] = session
            
            websocket_logger.info(
                f"GKE shell session started: {session_id} for pod {pod_name} in {k8s_ns} (user: {user_id})"
            )
            
            await session.run()
        except Exception as e:
            websocket_logger.error(f"GKE shell session error: {e}")
        finally:
            if session_id in self.active_sessions:
                try:
                    await self.active_sessions[session_id].cleanup()
                except Exception as e:
                    websocket_logger.debug(f"Cleanup warning for session {session_id}: {e}")
                del self.active_sessions[session_id]
    
    # ------------------ Command handlers ------------------ #

    async def _cmd_help(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /help command"""
        if args:
            raw = args[0]
            # Accept either enum name or value, any case
            try:
                category_enum = ShellCommandType[raw.upper()]
            except KeyError:
                try:
                    category_enum = ShellCommandType(raw.lower())
                except ValueError:
                    return ShellResponse("error", f"Unknown category: {raw}", datetime.now(timezone.utc).isoformat())
            commands = [cmd for cmd in self.commands.values() if cmd.category == category_enum]
        else:
            commands = list(self.commands.values())
        
        help_lines = ["📚 Available Commands:\n"]
        for cmd in commands:
            help_lines.append(f"🔹 {cmd.name}: {cmd.description}")
            help_lines.append(f"   Usage: {cmd.usage}\n")
        return ShellResponse("info", "\n".join(help_lines), datetime.now(timezone.utc).isoformat())
    
    async def _cmd_status(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /status command"""
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id,
                k8s_ns=session.k8s_ns,
                pod=session.pod_name,
                command="echo 'Pod is running'",
                timeout=30
            )
            status_text = (
                "📊 GKE Pod Status:\n"
                f"🔹 Session ID: {session.session_id}\n"
                f"🔹 Namespace: {session.k8s_ns}\n"
                f"🔹 Pod: {session.pod_name}\n"
                f"🔹 Status: {'Running' if result.get('success') else 'Error'}\n"
                f"🔹 Connected: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                f"🔹 Commands executed: {session.command_count}\n"
            )
            return ShellResponse("info", status_text, datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"Failed to get status: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_credits(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /credits command"""
        try:
            if session.user_id and session.db:
                current_credits = await session.db.get_user_credits(session.user_id)
                credits_text = (
                    "💳 Credit Balance:\n"
                    f"🔹 User: {session.user_id}\n"
                    f"🔹 Current Credits: ${current_credits:.2f}\n"
                    f"🔹 Session ID: {session.session_id}\n"
                )
                if session.billing_start_time:
                    duration = datetime.now(timezone.utc) - session.billing_start_time
                    hours = duration.total_seconds() / 3600.0
                    credits_text += f"🔹 Session Duration: {hours:.2f} hours\n"
                return ShellResponse("info", credits_text, datetime.now(timezone.utc).isoformat())
            else:
                return ShellResponse("warning", "Billing not available for this session", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"Failed to get credits: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_clear(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /clear command"""
        return ShellResponse("clear", "", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_list(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /list command"""
        path = args[0] if args else "/workspace"
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id, k8s_ns=session.k8s_ns, pod=session.pod_name,
                command=f"ls -la {shlex.quote(path)}", timeout=60
            )
            if result.get("success"):
                return ShellResponse("output", _clamp_text(result.get("stdout", "")), datetime.now(timezone.utc).isoformat())
            return ShellResponse("error", f"List failed: {result.get('stderr','')}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"List failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_pwd(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /pwd command"""
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id, k8s_ns=session.k8s_ns, pod=session.pod_name,
                command="pwd", timeout=30
            )
            if result.get("success"):
                return ShellResponse("output", result.get("stdout",""), datetime.now(timezone.utc).isoformat())
            return ShellResponse("error", f"PWD failed: {result.get('stderr','')}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"PWD failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_ls(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /ls command"""
        path = args[0] if args else "."
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id, k8s_ns=session.k8s_ns, pod=session.pod_name,
                command=f"ls -la {shlex.quote(path)}", timeout=60
            )
            if result.get("success"):
                return ShellResponse("output", _clamp_text(result.get("stdout","")), datetime.now(timezone.utc).isoformat())
            return ShellResponse("error", f"LS failed: {result.get('stderr','')}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"LS failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_cat(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /cat command"""
        if len(args) < 1:
            return ShellResponse("error", "Usage: /cat <file_path>", datetime.now(timezone.utc).isoformat())
        file_path = args[0]
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id, k8s_ns=session.k8s_ns, pod=session.pod_name,
                command=f"cat {shlex.quote(file_path)}", timeout=60
            )
            if result.get("success"):
                return ShellResponse("output", _clamp_text(result.get("stdout","")), datetime.now(timezone.utc).isoformat())
            return ShellResponse("error", f"Cat failed: {result.get('stderr','')}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"Cat failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_rm(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /rm command"""
        if len(args) < 1:
            return ShellResponse("error", "Usage: /rm <path>", datetime.now(timezone.utc).isoformat())
        path = args[0]
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id, k8s_ns=session.k8s_ns, pod=session.pod_name,
                command=f"rm -rf {shlex.quote(path)}", timeout=60
            )
            if result.get("success"):
                return ShellResponse("success", f"🗑️ Removed {path}", datetime.now(timezone.utc).isoformat())
            return ShellResponse("error", f"Remove failed: {result.get('stderr','')}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"Remove failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_ps(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /ps command"""
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id, k8s_ns=session.k8s_ns, pod=session.pod_name,
                command="ps aux", timeout=60
            )
            if result.get("success"):
                return ShellResponse("output", _clamp_text(result.get("stdout","")), datetime.now(timezone.utc).isoformat())
            return ShellResponse("error", f"PS failed: {result.get('stderr','')}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"PS failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_kill(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /kill command"""
        if len(args) < 1:
            return ShellResponse("error", "Usage: /kill <pid>", datetime.now(timezone.utc).isoformat())
        pid = args[0]
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id, k8s_ns=session.k8s_ns, pod=session.pod_name,
                command=f"kill {shlex.quote(pid)}", timeout=30
            )
            if result.get("success"):
                return ShellResponse("success", f"💀 Killed process {pid}", datetime.now(timezone.utc).isoformat())
            return ShellResponse("error", f"Kill failed: {result.get('stderr','')}", datetime.now(timezone.utc).isoformat())
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
                workspace_id=session.session_id, k8s_ns=session.k8s_ns, pod=session.pod_name,
                command=f"curl {options} {shlex.quote(url)}", timeout=120
            )
            if result.get("success"):
                return ShellResponse("output", _clamp_text(result.get("stdout","")), datetime.now(timezone.utc).isoformat())
            return ShellResponse("error", f"Curl failed: {result.get('stderr','')}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"Curl failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_ping(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /ping command"""
        if len(args) < 1:
            return ShellResponse("error", "Usage: /ping <host>", datetime.now(timezone.utc).isoformat())
        host = args[0]
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id, k8s_ns=session.k8s_ns, pod=session.pod_name,
                command=f"ping -c 3 {shlex.quote(host)}", timeout=60
            )
            if result.get("success"):
                return ShellResponse("output", _clamp_text(result.get("stdout","")), datetime.now(timezone.utc).isoformat())
            return ShellResponse("error", f"Ping failed: {result.get('stderr','')}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"Ping failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_env(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /env command"""
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id, k8s_ns=session.k8s_ns, pod=session.pod_name,
                command="env | sort", timeout=60
            )
            if result.get("success"):
                return ShellResponse("output", _clamp_text(result.get("stdout","")), datetime.now(timezone.utc).isoformat())
            return ShellResponse("error", f"ENV failed: {result.get('stderr','')}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"ENV failed: {str(e)}", datetime.now(timezone.utc).isoformat())
    
    async def _cmd_df(self, session: GKEShellSession, args: List[str]) -> ShellResponse:
        """Handle /df command"""
        try:
            result = gke_service.exec_in_workspace(
                workspace_id=session.session_id, k8s_ns=session.k8s_ns, pod=session.pod_name,
                command="df -h", timeout=60
            )
            if result.get("success"):
                return ShellResponse("output", _clamp_text(result.get("stdout","")), datetime.now(timezone.utc).isoformat())
            return ShellResponse("error", f"DF failed: {result.get('stderr','')}", datetime.now(timezone.utc).isoformat())
        except Exception as e:
            return ShellResponse("error", f"DF failed: {str(e)}", datetime.now(timezone.utc).isoformat())


# Global instance
gke_shell_service = GKEShellService()
