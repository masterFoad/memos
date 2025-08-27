#!/usr/bin/env python3
"""
OnMemOS v3 Interactive Shell Demo
=================================
Demonstrates the WebSocket-based interactive shell with slash commands
"""

import asyncio
import websockets
import json
import time
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from sdk.python.client import OnMemOSClient

class InteractiveShellDemo:
    """Demo class for interactive shell with slash commands"""
    
    def __init__(self, server_url: str = "ws://localhost:8080", api_key: str = "onmemos-internal-key-2024-secure"):
        self.server_url = server_url
        self.api_key = api_key
        self.client = OnMemOSClient(server_url.replace("ws://", "http://"), api_key)
        self.workspace_id = None
        self.websocket = None
    
    async def create_workspace(self):
        """Create a workspace for the demo"""
        print("🚀 Creating workspace for interactive shell demo...")
        
        try:
            workspace = self.client.create_workspace(
                template="python",
                namespace="demo",
                user="interactive-user",
                ttl_minutes=60
            )
            
            self.workspace_id = workspace['id']
            print(f"✅ Workspace created: {self.workspace_id}")
            print(f"📦 Template: {workspace.get('template', 'unknown')}")
            print(f"📁 Namespace: {workspace.get('namespace', 'unknown')}")
            print(f"👤 User: {workspace.get('user', 'unknown')}")
            
            if workspace.get('bucket'):
                bucket = workspace['bucket']
                print(f"🪣 Bucket: {bucket.get('bucket_name', 'unknown')}")
                print(f"   📍 Mount: {bucket.get('mount_path', 'unknown')}")
            
            if workspace.get('disk'):
                disk = workspace['disk']
                print(f"💾 Disk: {disk.get('disk_name', 'unknown')}")
                print(f"   📏 Size: {disk.get('size_gb', 'unknown')} GB")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to create workspace: {e}")
            return False
    
    async def connect_shell(self):
        """Connect to the WebSocket shell"""
        if not self.workspace_id:
            print("❌ No workspace created")
            return False
        
        websocket_url = f"{self.server_url}/v1/workspaces/{self.workspace_id}/shell"
        print(f"🔗 Connecting to shell: {websocket_url}")
        
        try:
            self.websocket = await websockets.connect(websocket_url)
            print("✅ Connected to interactive shell!")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to shell: {e}")
            return False
    
    async def run_demo_commands(self):
        """Run demo commands to showcase slash commands"""
        if not self.websocket:
            print("❌ Not connected to shell")
            return
        
        print("\n🎯 Running Interactive Shell Demo")
        print("=" * 50)
        
        # Demo commands to showcase features
        demo_commands = [
            "/help",
            "/status",
            "/files",
            "/python print('Hello from OnMemOS v3!')",
            "/buckets list",
            "/disks list",
            "/debug",
            "ls -la",
            "pwd",
            "echo 'Testing regular shell commands'",
            "/clear",
            "/help status",
            "/exit"
        ]
        
        for i, command in enumerate(demo_commands, 1):
            print(f"\n[{i}/{len(demo_commands)}] Executing: {command}")
            print("-" * 40)
            
            try:
                await self.websocket.send(command)
                
                # Wait for response
                response = await asyncio.wait_for(self.websocket.recv(), timeout=10.0)
                print(f"📄 Response:\n{response}")
                
                # Small delay between commands
                await asyncio.sleep(1)
                
            except asyncio.TimeoutError:
                print("⏰ Timeout waiting for response")
            except Exception as e:
                print(f"❌ Error: {e}")
                break
    
    async def interactive_mode(self):
        """Run in interactive mode for manual testing"""
        if not self.websocket:
            print("❌ Not connected to shell")
            return
        
        print("\n🎮 Interactive Mode")
        print("=" * 30)
        print("💡 Type commands to send to the shell")
        print("💡 Use slash commands like /help, /status, /files")
        print("💡 Type 'exit' to quit")
        print("=" * 30)
        
        try:
            while True:
                # Get user input
                user_input = input("onmemos> ")
                
                if user_input.lower() in ['exit', 'quit']:
                    break
                
                if not user_input.strip():
                    continue
                
                # Send command
                await self.websocket.send(user_input)
                
                # Wait for response
                try:
                    response = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
                    print(f"📄 {response}")
                except asyncio.TimeoutError:
                    print("⏰ No response received")
                except Exception as e:
                    print(f"❌ Error receiving response: {e}")
                    break
                    
        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user")
        except Exception as e:
            print(f"❌ Error in interactive mode: {e}")
    
    async def cleanup(self):
        """Clean up resources"""
        if self.websocket:
            try:
                await self.websocket.close()
                print("🔌 WebSocket connection closed")
            except:
                pass
        
        if self.workspace_id:
            try:
                self.client.delete_workspace(self.workspace_id)
                print("🧹 Workspace cleaned up")
            except Exception as e:
                print(f"⚠️ Failed to cleanup workspace: {e}")
    
    async def run_demo(self, interactive: bool = False):
        """Run the complete demo"""
        print("🚀 OnMemOS v3 Interactive Shell Demo")
        print("=" * 50)
        
        try:
            # Create workspace
            if not await self.create_workspace():
                return
            
            # Connect to shell
            if not await self.connect_shell():
                return
            
            # Run demo
            if interactive:
                await self.interactive_mode()
            else:
                await self.run_demo_commands()
            
        finally:
            await self.cleanup()

async def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="OnMemOS v3 Interactive Shell Demo")
    parser.add_argument("--server", default="ws://localhost:8080", help="Server WebSocket URL")
    parser.add_argument("--api-key", default="onmemos-internal-key-2024-secure", help="API key")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    
    args = parser.parse_args()
    
    demo = InteractiveShellDemo(args.server, args.api_key)
    await demo.run_demo(interactive=args.interactive)

if __name__ == "__main__":
    print("🎯 OnMemOS v3 Interactive Shell Demo")
    print("=" * 50)
    print("This demo showcases:")
    print("✅ Real GCP bucket and disk integration")
    print("✅ WebSocket-based interactive shell")
    print("✅ Slash commands for workspace management")
    print("✅ Container shell bridging")
    print("=" * 50)
    
    asyncio.run(main())
