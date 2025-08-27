#!/usr/bin/env python3
"""
Interactive Shell Script
========================
Provides an actual interactive shell inside the Docker container
"""

import sys
import os
import asyncio
import websockets
import json
import threading
import time
# Add the project root to the path
project_root = os.path.join(os.path.dirname(__file__))
sys.path.append(project_root)

from sdk.python.client import OnMemClient
# Import test_utils from the correct location
sys.path.append(os.path.join(project_root, 'tests', 'unit'))
from test_utils import generate_test_token

class InteractiveShell:
    def __init__(self, workspace_id, websocket_url):
        self.workspace_id = workspace_id
        self.websocket_url = websocket_url
        self.running = False
        
    async def connect_and_run(self):
        """Connect to the WebSocket and run interactive shell"""
        try:
            async with websockets.connect(self.websocket_url) as websocket:
                print(f"🔗 Connected to workspace {self.workspace_id}")
                print("🐳 You are now inside the Docker container!")
                print("💾 Persistent storage is mounted at /persist")
                print("🔧 Type 'exit' to leave the container")
                print("=" * 50)
                
                self.running = True
                
                # Start input thread
                input_thread = threading.Thread(target=self.input_loop, args=(websocket,))
                input_thread.daemon = True
                input_thread.start()
                
                # Handle incoming messages
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        if data.get("type") == "output":
                            print(data.get("data", ""), end="")
                        elif data.get("type") == "error":
                            print(f"❌ Error: {data.get('data', '')}")
                        elif data.get("type") == "exit":
                            print(f"\n🔚 Shell exited with code: {data.get('code', 0)}")
                            break
                    except json.JSONDecodeError:
                        print(f"Raw message: {message}")
                        
        except Exception as e:
            print(f"❌ WebSocket connection failed: {e}")
        finally:
            self.running = False
    
    def input_loop(self, websocket):
        """Handle user input in a separate thread"""
        try:
            while self.running:
                try:
                    command = input()
                    if command.lower() in ['exit', 'quit']:
                        # Send exit command
                        asyncio.run(websocket.send(json.dumps({"type": "exit"})))
                        break
                    else:
                        # Send command to shell
                        asyncio.run(websocket.send(json.dumps({"type": "input", "data": command + "\n"})))
                except EOFError:
                    break
                except KeyboardInterrupt:
                    print("\n🛑 Interrupted by user")
                    break
        except Exception as e:
            print(f"❌ Input loop error: {e}")

def create_interactive_session():
    """Create and launch an interactive shell session"""
    print("🔧 Creating Interactive Shell Session")
    print("=" * 50)
    
    # Initialize client
    token = generate_test_token()
    client = OnMemClient('http://localhost:8080', token)
    
    namespace = "data-science-demo"
    user = "researcher-123"
    
    print(f"📁 Namespace: {namespace}")
    print(f"👤 User: {user}")
    
    try:
        # Create workspace
        print("\n🚀 Creating workspace...")
        workspace = client.create_workspace_with_buckets(
            template="python",
            namespace=namespace,
            user=user,
            ttl_minutes=60  # 1 hour for debugging
        )
        
        workspace_id = workspace['id']
        print(f"✅ Created workspace: {workspace_id}")
        
        # Get WebSocket URL
        base_url = client.base.replace('http://', 'ws://')
        websocket_url = f"{base_url}/v1/workspaces/{workspace_id}/shell"
        
        print(f"🔗 WebSocket URL: {websocket_url}")
        print(f"⏰ Expires at: {workspace.get('expires_at', 'Unknown')}")
        
        # Create interactive shell
        shell = InteractiveShell(workspace_id, websocket_url)
        
        print("\n🎯 Starting interactive shell...")
        print("Connecting to container...")
        
        # Run the interactive shell
        asyncio.run(shell.connect_and_run())
        
        print("\n🧹 Cleaning up workspace...")
        client.delete_workspace(workspace_id)
        print("✅ Workspace cleaned up")
        
    except Exception as e:
        print(f"❌ Failed to create interactive session: {e}")
        return None

if __name__ == "__main__":
    create_interactive_session()
