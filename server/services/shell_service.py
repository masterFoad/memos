"""
Shell Service - WebSocket-based interactive shell with billing integration
"""

import asyncio
import json
import logging
import shlex
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from fastapi import WebSocket, WebSocketDisconnect

from server.core.logging import get_logger
from server.database.factory import get_database_client
from server.services.billing_service import BillingService

logger = get_logger("shell")

@dataclass
class ShellMessage:
    """Shell message structure"""
    type: str  # 'command', 'output', 'error', 'info'
    content: str
    timestamp: str
    session_id: Optional[str] = None

@dataclass
class ShellCommand:
    """Shell command definition"""
    name: str
    description: str
    handler: callable

class ShellService:
    """WebSocket-based interactive shell service with billing integration"""
    
    def __init__(self, workspace_manager):
        self.workspace_manager = workspace_manager
        self.active_sessions: Dict[str, 'ShellSession'] = {}
        self.commands: Dict[str, ShellCommand] = {}
        self.db = None
        self.billing_service = None
        
        # Shell session limits
        self.max_session_duration_hours = 8.0  # 8 hours max
        self.max_idle_time_minutes = 30.0      # 30 minutes idle timeout
        self.check_interval_seconds = 60       # Check every minute
        
        self._register_default_commands()
    
    async def _ensure_connected(self):
        """Ensure database and billing service are connected"""
        if self.db is None:
            self.db = get_database_client()
            await self.db.connect()
        if self.billing_service is None:
            self.billing_service = BillingService()
    
    def _register_default_commands(self):
        """Register default shell commands"""
        self.register_command(ShellCommand(
            name="help",
            description="Show available commands",
            handler=self._cmd_help
        ))
        
        self.register_command(ShellCommand(
            name="status",
            description="Show session status and billing info",
            handler=self._cmd_status
        ))
        
        self.register_command(ShellCommand(
            name="credits",
            description="Show current credit balance",
            handler=self._cmd_credits
        ))
        
        self.register_command(ShellCommand(
            name="exit",
            description="Exit shell session",
            handler=self._cmd_exit
        ))
    
    def register_command(self, command: ShellCommand):
        """Register a new shell command"""
        self.commands[f"/{command.name}"] = command
        logger.info(f"Registered shell command: /{command.name}")
    
    async def create_session(self, workspace_id: str, websocket: WebSocket) -> 'ShellSession':
        """Create a new shell session with billing integration"""
        await self._ensure_connected()
        
        session = ShellSession(workspace_id, websocket, self)
        self.active_sessions[session.session_id] = session
        
        # Start billing for shell session
        try:
            billing_info = await self.billing_service.start_session_billing(
                session.session_id, 
                session.user_id, 
                "shell"  # Special tier for shell sessions
            )
            session.billing_start_time = datetime.now()
            logger.info(f"Started shell session billing: {session.session_id}")
        except Exception as e:
            logger.error(f"Failed to start shell session billing: {e}")
        
        return session
    
    async def _cmd_help(self, session: 'ShellSession', args: List[str]):
        """Show available commands"""
        help_text = """
🔧 Available Commands:
====================
"""
        for cmd_name, cmd in self.commands.items():
            help_text += f"{cmd_name:<15} - {cmd.description}\n"
        
        help_text += """
💡 Regular shell commands work normally
🔍 Type /status to see session info
💰 Type /credits to check balance
"""
        await session.send_message(help_text)
    
    async def _cmd_status(self, session: 'ShellSession', args: List[str]):
        """Show session status and billing info"""
        try:
            # Get session duration
            duration = datetime.now() - session.billing_start_time
            hours = duration.total_seconds() / 3600.0
            
            # Get billing info
            billing_info = await self.db.get_session_billing_info(session.session_id)
            current_cost = billing_info.get('total_cost', 0) if billing_info else 0
            
            # Get user credits
            user_credits = await self.db.get_user_credits(session.user_id)
            
            status_text = f"""
📊 Session Status:
=================
🏠 Workspace: {session.workspace_id}
⏱️  Duration: {hours:.2f} hours
💰 Current Cost: ${current_cost:.4f}
💳 Credits: ${user_credits:.2f}
🆔 Session ID: {session.session_id}
"""
            await session.send_message(status_text)
            
        except Exception as e:
            await session.send_message(f"❌ Error getting status: {e}")
    
    async def _cmd_credits(self, session: 'ShellSession', args: List[str]):
        """Show current credit balance"""
        try:
            user_credits = await self.db.get_user_credits(session.user_id)
            await session.send_message(f"💳 Current Credits: ${user_credits:.2f}")
        except Exception as e:
            await session.send_message(f"❌ Error getting credits: {e}")
    
    async def _cmd_exit(self, session: 'ShellSession', args: List[str]):
        """Exit shell session"""
        await session.send_message("👋 Goodbye!")
        await session.close()

class ShellSession:
    """Individual shell session for a workspace with billing integration"""
    
    def __init__(self, workspace_id: str, websocket: WebSocket, shell_service: ShellService):
        self.workspace_id = workspace_id
        self.websocket = websocket
        self.shell_service = shell_service
        self.workspace_manager = shell_service.workspace_manager
        self.session_id = f"shell_{workspace_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.user_id = None  # Will be set when workspace is loaded
        self.running = False
        self.container_process = None
        self.billing_start_time = None
        self.last_activity = datetime.now()
        self.monitor_task = None
        
        # Session limits
        self.max_duration_hours = 8.0
        self.max_idle_minutes = 30.0
    
    async def start(self):
        """Start the shell session with monitoring"""
        self.running = True
        
        # Get user ID from workspace
        try:
            workspace = self.workspace_manager.get_workspace(self.workspace_id)
            if workspace:
                self.user_id = workspace.get('user_id', 'unknown')
        except Exception as e:
            logger.error(f"Error getting workspace info: {e}")
            self.user_id = 'unknown'
        
        # Send welcome message
        welcome_msg = f"""
🚀 OnMemOS v3 Interactive Shell
===============================
🏠 Workspace: {self.workspace_id}
👤 User: {self.user_id}
💡 Type /help for available commands
🔧 Type /exit to quit
⏰ Session limit: {self.max_duration_hours} hours
================================
"""
        await self.send_message(welcome_msg)
        
        # Start session monitoring
        self.monitor_task = asyncio.create_task(self._monitor_session())
        
        # Start container shell process
        await self._start_container_shell()
        
        # Handle WebSocket messages
        try:
            while self.running:
                try:
                    message = await self.websocket.receive_text()
                    self.last_activity = datetime.now()
                    await self._handle_input(message)
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
                    break
        finally:
            await self.stop()
    
    async def _monitor_session(self):
        """Monitor session for timeouts and limits"""
        while self.running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Check session duration
                if self.billing_start_time:
                    duration = datetime.now() - self.billing_start_time
                    if duration.total_seconds() / 3600.0 > self.max_duration_hours:
                        await self.send_message("⏰ Session duration limit reached. Closing session...")
                        await self.close()
                        break
                
                # Check idle time
                idle_time = datetime.now() - self.last_activity
                if idle_time.total_seconds() / 60.0 > self.max_idle_minutes:
                    await self.send_message("😴 Session idle timeout. Closing session...")
                    await self.close()
                    break
                
                # Check user credits
                if self.user_id and self.user_id != 'unknown':
                    try:
                        user_credits = await self.shell_service.db.get_user_credits(self.user_id)
                        if user_credits <= 0:
                            await self.send_message("💳 Insufficient credits. Closing session...")
                            await self.close()
                            break
                    except Exception as e:
                        logger.error(f"Error checking credits: {e}")
                
            except Exception as e:
                logger.error(f"Error in session monitor: {e}")
    
    async def _start_container_shell(self):
        """Start the container shell process"""
        # TODO: Implement container shell process
        # This would start a shell process in the workspace container
        logger.info(f"Starting container shell for workspace {self.workspace_id}")
    
    async def _handle_input(self, message: str):
        """Handle user input"""
        try:
            # Check for slash commands
            if message.startswith('/'):
                await self._handle_slash_command(message)
            else:
                await self._handle_shell_command(message)
        except Exception as e:
            await self.send_message(f"❌ Error: {e}")
    
    async def _handle_slash_command(self, command: str):
        """Handle slash commands"""
        parts = command.split(' ', 1)
        cmd_name = parts[0]
        args = parts[1].split() if len(parts) > 1 else []
        
        if cmd_name in self.shell_service.commands:
            cmd = self.shell_service.commands[cmd_name]
            await cmd.handler(self, args)
        else:
            await self.send_message(f"❌ Unknown command: {cmd_name}. Type /help for available commands.")
    
    async def _handle_shell_command(self, command: str):
        """Handle regular shell commands"""
        # TODO: Implement shell command execution
        # This would execute the command in the container
        await self.send_message(f"🔧 Executing: {command}")
        await self.send_message("📝 Command output would appear here...")
    
    async def send_message(self, message: str):
        """Send a message to the WebSocket"""
        try:
            shell_msg = ShellMessage(
                type="output",
                content=message,
                timestamp=datetime.now().isoformat(),
                session_id=self.session_id
            )
            await self.websocket.send_text(json.dumps(shell_msg.__dict__))
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    async def stop(self):
        """Stop the shell session"""
        self.running = False
        
        # Cancel monitoring task
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        # Stop billing
        if self.session_id:
            try:
                await self.shell_service.billing_service.stop_session_billing(self.session_id)
                logger.info(f"Stopped billing for shell session: {self.session_id}")
            except Exception as e:
                logger.error(f"Error stopping shell session billing: {e}")
        
        # Remove from active sessions
        if self.session_id in self.shell_service.active_sessions:
            del self.shell_service.active_sessions[self.session_id]
        
        logger.info(f"Shell session stopped: {self.session_id}")
    
    async def close(self):
        """Close the WebSocket connection"""
        try:
            await self.websocket.close()
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")
        finally:
            await self.stop()

# Global shell service instance
def get_shell_service(workspace_manager):
    """Get the global shell service instance"""
    return ShellService(workspace_manager)
