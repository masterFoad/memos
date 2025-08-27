"""
Interactive Shell Service - WebSocket-based workspace shell with slash commands
"""
import asyncio
import json
import logging
import subprocess
import threading
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from fastapi import WebSocket
import os

logger = logging.getLogger(__name__)

@dataclass
class SlashCommand:
    """Slash command definition"""
    name: str
    description: str
    usage: str
    handler: Callable

class ShellService:
    """WebSocket-based interactive shell service with slash commands"""
    
    def __init__(self, workspace_manager):
        self.workspace_manager = workspace_manager
        self.active_sessions: Dict[str, 'ShellSession'] = {}
        self.slash_commands = self._register_slash_commands()
        
    def _register_slash_commands(self) -> Dict[str, SlashCommand]:
        """Register default slash commands"""
        commands = {}
        
        commands["help"] = SlashCommand(
            name="help",
            description="Show available slash commands",
            usage="/help [command]",
            handler=self._cmd_help
        )
        
        commands["status"] = SlashCommand(
            name="status",
            description="Show workspace status and resources",
            usage="/status",
            handler=self._cmd_status
        )
        
        commands["files"] = SlashCommand(
            name="files",
            description="List files in current directory",
            usage="/files [path]",
            handler=self._cmd_files
        )
        
        commands["upload"] = SlashCommand(
            name="upload",
            description="Upload file to bucket",
            usage="/upload <local_path> <bucket_path>",
            handler=self._cmd_upload
        )
        
        commands["download"] = SlashCommand(
            name="download",
            description="Download file from bucket",
            usage="/download <bucket_path> <local_path>",
            handler=self._cmd_download
        )
        
        commands["persist"] = SlashCommand(
            name="persist",
            description="Show persistent storage info",
            usage="/persist",
            handler=self._cmd_persist
        )
        
        commands["buckets"] = SlashCommand(
            name="buckets",
            description="List and manage buckets",
            usage="/buckets [list|info|create]",
            handler=self._cmd_buckets
        )
        
        commands["python"] = SlashCommand(
            name="python",
            description="Run Python code",
            usage="/python <code>",
            handler=self._cmd_python
        )
        
        commands["disks"] = SlashCommand(
            name="disks",
            description="List and manage persistent disks",
            usage="/disks [list|info]",
            handler=self._cmd_disks
        )
        
        commands["debug"] = SlashCommand(
            name="debug",
            description="Show debug information",
            usage="/debug",
            handler=self._cmd_debug
        )
        
        commands["clear"] = SlashCommand(
            name="clear",
            description="Clear terminal",
            usage="/clear",
            handler=self._cmd_clear
        )
        
        commands["exit"] = SlashCommand(
            name="exit",
            description="Exit shell session",
            usage="/exit",
            handler=self._cmd_exit
        )
        
        return commands
    
    def get_command_help(self, command_name: str = None) -> str:
        """Get help for commands"""
        if command_name:
            if command_name in self.slash_commands:
                cmd = self.slash_commands[command_name]
                return f"📖 {cmd.name}: {cmd.description}\n   Usage: {cmd.usage}"
            else:
                return f"❌ Unknown command: {command_name}"
        
        help_text = "🔧 Available Slash Commands:\n"
        help_text += "=" * 40 + "\n"
        
        for cmd in self.slash_commands.values():
            help_text += f"• /{cmd.name:<12} - {cmd.description}\n"
        
        help_text += "\n💡 Type /help <command> for detailed usage"
        return help_text
    
    async def create_session(self, workspace_id: str, websocket: WebSocket) -> 'ShellSession':
        """Create a new shell session"""
        session = ShellSession(workspace_id, websocket, self)
        self.active_sessions[workspace_id] = session
        return session
    
    def remove_session(self, workspace_id: str):
        """Remove a shell session"""
        if workspace_id in self.active_sessions:
            del self.active_sessions[workspace_id]
    
    # Slash command handlers
    async def _cmd_help(self, session: 'ShellSession', args: List[str]):
        """Handle /help command"""
        command = args[0] if args else None
        help_text = self.get_command_help(command)
        await session.send_message(help_text)
    
    async def _cmd_status(self, session: 'ShellSession', args: List[str]):
        """Handle /status command"""
        workspace = self.workspace_manager.get_workspace(session.workspace_id)
        if not workspace:
            await session.send_message("❌ Workspace not found")
            return
        
        status_text = f"🏠 Workspace Status: {session.workspace_id}\n"
        status_text += "=" * 40 + "\n"
        status_text += f"📦 Template: {workspace.get('template', 'unknown')}\n"
        status_text += f"📁 Namespace: {workspace.get('namespace', 'unknown')}\n"
        status_text += f"👤 User: {workspace.get('user', 'unknown')}\n"
        status_text += f"⏰ Created: {time.ctime(workspace.get('created_at', 0))}\n"
        status_text += f"🔄 Status: {workspace.get('status', 'unknown')}\n"
        
        if workspace.get('bucket'):
            bucket = workspace['bucket']
            status_text += f"🪣 Bucket: {bucket.get('bucket_name', 'unknown')}\n"
            status_text += f"   📍 Mount: {bucket.get('mount_path', 'unknown')}\n"
        
        if workspace.get('disk'):
            disk = workspace['disk']
            status_text += f"💾 Disk: {disk.get('disk_name', 'unknown')}\n"
            status_text += f"   📏 Size: {disk.get('size_gb', 'unknown')} GB\n"
            status_text += f"   📍 Mount: {disk.get('mount_path', 'unknown')}\n"
        
        await session.send_message(status_text)
    
    async def _cmd_files(self, session: 'ShellSession', args: List[str]):
        """Handle /files command"""
        path = args[0] if args else "."
        
        try:
            result = session.execute_command(f"ls -la {path}")
            if result['success']:
                await session.send_message(f"📁 Files in {path}:\n{result['stdout']}")
            else:
                await session.send_message(f"❌ Error listing files: {result['stderr']}")
        except Exception as e:
            await session.send_message(f"❌ Error: {e}")
    
    async def _cmd_upload(self, session: 'ShellSession', args: List[str]):
        """Handle /upload command"""
        if len(args) < 2:
            await session.send_message("❌ Usage: /upload <local_path> <bucket_path>")
            return
        
        local_path, bucket_path = args[0], args[1]
        workspace = self.workspace_manager.get_workspace(session.workspace_id)
        
        if not workspace or not workspace.get('bucket'):
            await session.send_message("❌ No bucket available for upload")
            return
        
        bucket_name = workspace['bucket']['bucket_name']
        
        try:
            # Use gsutil to upload
            cmd = f"gsutil cp {local_path} gs://{bucket_name}/{bucket_path}"
            result = session.execute_command(cmd)
            
            if result['success']:
                await session.send_message(f"✅ Uploaded {local_path} to gs://{bucket_name}/{bucket_path}")
            else:
                await session.send_message(f"❌ Upload failed: {result['stderr']}")
        except Exception as e:
            await session.send_message(f"❌ Error: {e}")
    
    async def _cmd_download(self, session: 'ShellSession', args: List[str]):
        """Handle /download command"""
        if len(args) < 2:
            await session.send_message("❌ Usage: /download <bucket_path> <local_path>")
            return
        
        bucket_path, local_path = args[0], args[1]
        workspace = self.workspace_manager.get_workspace(session.workspace_id)
        
        if not workspace or not workspace.get('bucket'):
            await session.send_message("❌ No bucket available for download")
            return
        
        bucket_name = workspace['bucket']['bucket_name']
        
        try:
            # Use gsutil to download
            cmd = f"gsutil cp gs://{bucket_name}/{bucket_path} {local_path}"
            result = session.execute_command(cmd)
            
            if result['success']:
                await session.send_message(f"✅ Downloaded gs://{bucket_name}/{bucket_path} to {local_path}")
            else:
                await session.send_message(f"❌ Download failed: {result['stderr']}")
        except Exception as e:
            await session.send_message(f"❌ Error: {e}")
    
    async def _cmd_persist(self, session: 'ShellSession', args: List[str]):
        """Handle /persist command"""
        workspace = self.workspace_manager.get_workspace(session.workspace_id)
        
        if not workspace or not workspace.get('disk'):
            await session.send_message("❌ No persistent disk available")
            return
        
        disk = workspace['disk']
        mount_path = disk.get('mount_path', '/persist')
        
        try:
            result = session.execute_command(f"df -h {mount_path}")
            if result['success']:
                await session.send_message(f"💾 Persistent Storage:\n{result['stdout']}")
            else:
                await session.send_message(f"❌ Error checking persistent storage: {result['stderr']}")
        except Exception as e:
            await session.send_message(f"❌ Error: {e}")
    
    async def _cmd_buckets(self, session: 'ShellSession', args: List[str]):
        """Handle /buckets command"""
        action = args[0] if args else "list"
        workspace = self.workspace_manager.get_workspace(session.workspace_id)
        
        if not workspace:
            await session.send_message("❌ Workspace not found")
            return
        
        if action == "list":
            try:
                buckets = self.workspace_manager.bucket_service.list_buckets_in_namespace(
                    workspace['namespace']
                )
                if buckets:
                    bucket_text = "🪣 Available Buckets:\n"
                    for bucket in buckets:
                        bucket_text += f"• {bucket['bucket_name']} ({bucket.get('location', 'unknown')})\n"
                    await session.send_message(bucket_text)
                else:
                    await session.send_message("📭 No buckets found")
            except Exception as e:
                await session.send_message(f"❌ Error listing buckets: {e}")
        
        elif action == "info" and workspace.get('bucket'):
            bucket = workspace['bucket']
            info_text = f"🪣 Current Bucket Info:\n"
            info_text += f"   Name: {bucket.get('bucket_name', 'unknown')}\n"
            info_text += f"   Location: {bucket.get('location', 'unknown')}\n"
            info_text += f"   Mount: {bucket.get('mount_path', 'unknown')}\n"
            info_text += f"   URL: {bucket.get('url', 'unknown')}\n"
            await session.send_message(info_text)
        
        else:
            await session.send_message("❌ Usage: /buckets [list|info]")
    
    async def _cmd_python(self, session: 'ShellSession', args: List[str]):
        """Handle /python command"""
        if not args:
            await session.send_message("❌ Usage: /python <code>")
            return
        
        code = " ".join(args)
        
        try:
            result = session.execute_command(f"python -c '{code}'")
            if result['success']:
                if result['stdout']:
                    await session.send_message(f"🐍 Python Output:\n{result['stdout']}")
                else:
                    await session.send_message("✅ Python code executed successfully")
            else:
                await session.send_message(f"❌ Python Error:\n{result['stderr']}")
        except Exception as e:
            await session.send_message(f"❌ Error: {e}")
    
    async def _cmd_disks(self, session: 'ShellSession', args: List[str]):
        """Handle /disks command"""
        action = args[0] if args else "list"
        workspace = self.workspace_manager.get_workspace(session.workspace_id)
        
        if not workspace:
            await session.send_message("❌ Workspace not found")
            return
        
        if action == "list":
            try:
                disks = self.workspace_manager.disk_service.list_disks_in_namespace(
                    workspace['namespace']
                )
                if disks:
                    disk_text = "💾 Available Disks:\n"
                    for disk in disks:
                        disk_text += f"• {disk['disk_name']} ({disk.get('size_gb', 'unknown')} GB)\n"
                    await session.send_message(disk_text)
                else:
                    await session.send_message("📭 No disks found")
            except Exception as e:
                await session.send_message(f"❌ Error listing disks: {e}")
        
        elif action == "info" and workspace.get('disk'):
            disk = workspace['disk']
            info_text = f"💾 Current Disk Info:\n"
            info_text += f"   Name: {disk.get('disk_name', 'unknown')}\n"
            info_text += f"   Size: {disk.get('size_gb', 'unknown')} GB\n"
            info_text += f"   Zone: {disk.get('zone', 'unknown')}\n"
            info_text += f"   Mount: {disk.get('mount_path', 'unknown')}\n"
            await session.send_message(info_text)
        
        else:
            await session.send_message("❌ Usage: /disks [list|info]")
    
    async def _cmd_debug(self, session: 'ShellSession', args: List[str]):
        """Handle /debug command"""
        workspace = self.workspace_manager.get_workspace(session.workspace_id)
        
        debug_text = "🐛 Debug Information:\n"
        debug_text += "=" * 30 + "\n"
        debug_text += f"Session ID: {session.workspace_id}\n"
        debug_text += f"Workspace exists: {workspace is not None}\n"
        debug_text += f"Active sessions: {len(self.active_sessions)}\n"
        
        if workspace:
            debug_text += f"Container ID: {workspace.get('container_id', 'unknown')}\n"
            debug_text += f"Status: {workspace.get('status', 'unknown')}\n"
        
        await session.send_message(debug_text)
    
    async def _cmd_clear(self, session: 'ShellSession', args: List[str]):
        """Handle /clear command"""
        await session.send_message("\033[2J\033[H")  # Clear screen
    
    async def _cmd_exit(self, session: 'ShellSession', args: List[str]):
        """Handle /exit command"""
        await session.send_message("👋 Goodbye!")
        await session.close()

class ShellSession:
    """Individual shell session for a workspace"""
    
    def __init__(self, workspace_id: str, websocket: WebSocket, shell_service: ShellService):
        self.workspace_id = workspace_id
        self.websocket = websocket
        self.shell_service = shell_service
        self.workspace_manager = shell_service.workspace_manager
        self.running = False
        self.container_process = None
    
    async def start(self):
        """Start the shell session"""
        self.running = True
        
        # Send welcome message
        welcome_msg = f"""
🚀 OnMemOS v3 Interactive Shell
===============================
🏠 Workspace: {self.workspace_id}
💡 Type /help for available commands
🔧 Type /exit to quit
================================
"""
        await self.send_message(welcome_msg)
        
        # Start container shell process
        await self._start_container_shell()
        
        # Handle WebSocket messages
        try:
            while self.running:
                try:
                    message = await self.websocket.receive_text()
                    await self._handle_input(message)
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
                    break
        finally:
            await self.stop()
    
    async def _start_container_shell(self):
        """Start the container shell process"""
        try:
            workspace = self.workspace_manager.get_workspace(self.workspace_id)
            if not workspace or not workspace.get('container_id'):
                await self.send_message("❌ Container not available")
                return
            
            container_id = workspace['container_id']
            
            # Start interactive shell in container
            cmd = ["docker", "exec", "-i", container_id, "/bin/bash"]
            self.container_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # Start output reader thread
            threading.Thread(target=self._read_output, daemon=True).start()
            
        except Exception as e:
            await self.send_message(f"❌ Failed to start container shell: {e}")
    
    def _read_output(self):
        """Read output from container process"""
        try:
            while self.running and self.container_process:
                line = self.container_process.stdout.readline()
                if line:
                    asyncio.create_task(self.send_message(line))
                else:
                    break
        except Exception as e:
            logger.error(f"Error reading container output: {e}")
    
    async def _handle_input(self, input_line: str):
        """Handle user input"""
        line = input_line.strip()
        
        if not line:
            return
        
        # Check if it's a slash command
        if line.startswith('/'):
            await self._handle_slash_command(line)
        else:
            # Send to container shell
            await self._send_to_container(line)
    
    async def _handle_slash_command(self, input_line: str):
        """Handle slash commands"""
        try:
            parts = input_line.split()
            if not parts:
                return
            
            cmd_name = parts[0][1:]  # Remove the slash
            args = parts[1:] if len(parts) > 1 else []
            
            if cmd_name in self.shell_service.slash_commands:
                cmd = self.shell_service.slash_commands[cmd_name]
                await cmd.handler(self, args)
            else:
                await self.send_message(f"❌ Unknown command: /{cmd_name}\nType /help for available commands")
        
        except Exception as e:
            await self.send_message(f"❌ Error executing command: {e}")
    
    async def _send_to_container(self, command: str):
        """Send command to container shell"""
        try:
            if self.container_process and self.container_process.poll() is None:
                self.container_process.stdin.write(command + '\n')
                self.container_process.stdin.flush()
            else:
                await self.send_message("❌ Container shell not available")
        except Exception as e:
            await self.send_message(f"❌ Error sending to container: {e}")
    
    def execute_command(self, command: str) -> Dict[str, Any]:
        """Execute a command in the container"""
        try:
            workspace = self.workspace_manager.get_workspace(self.workspace_id)
            if not workspace or not workspace.get('container_id'):
                return {"success": False, "error": "Container not available"}
            
            container_id = workspace['container_id']
            result = subprocess.run(
                ["docker", "exec", container_id, "sh", "-c", command],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def send_message(self, message: str):
        """Send message to WebSocket"""
        try:
            await self.websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    async def stop(self):
        """Stop the shell session"""
        self.running = False
        
        if self.container_process:
            try:
                self.container_process.terminate()
                self.container_process.wait(timeout=5)
            except:
                self.container_process.kill()
        
        self.shell_service.remove_session(self.workspace_id)
    
    async def close(self):
        """Close the WebSocket connection"""
        try:
            await self.websocket.close()
        except:
            pass

# Global shell service instance
shell_service = None

def get_shell_service(workspace_manager) -> ShellService:
    """Get or create shell service instance"""
    global shell_service
    if shell_service is None:
        shell_service = ShellService(workspace_manager)
    return shell_service
