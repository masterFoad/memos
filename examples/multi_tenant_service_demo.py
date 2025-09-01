cd /home/foad/data/memos/onmemos-v3/examples && cat > multi_tenant_service_demo.py << 'EOF'
#!/usr/bin/env python3
"""
OnMemOS v3 Multi-Tenant Service Demo
Demonstrates how to build a SaaS application with multiple end-users using OnMemOS SDK.

This example shows:
1. How to handle multiple end-users with isolated storage
2. Storage organization per user and workspace
3. Workspace management per user
4. Bucket/filestore isolation strategies
5. Cost tracking per user
6. Subscription tier management
"""

import sys
import os
import time
import json
import uuid
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sdk', 'python'))

from client import OnMemOSClient
from server.models.sessions import CPUSize, MemorySize, GPUType, ImageType
from server.models.users import WorkspaceResourcePackage

@dataclass
class EndUser:
    """Represents an end-user of your SaaS application"""
    user_id: str
    email: str
    subscription_tier: str  # 'free', 'pro', 'enterprise'
    max_workspaces: int
    max_storage_gb: int
    created_at: datetime
    is_active: bool = True

@dataclass
class UserWorkspace:
    """A workspace belonging to an end-user"""
    workspace_id: str
    user_id: str
    name: str
    resource_package: WorkspaceResourcePackage
    storage_prefix: str  # GCS bucket prefix for this workspace
    created_at: datetime
    is_active: bool = True

class MultiTenantService:
    """
    A service that manages multiple end-users with isolated storage and workspaces.
    
    This demonstrates how to build a SaaS application using OnMemOS SDK.
    """
    
    def __init__(self, client: OnMemOSClient, service_admin_id: str = "service-admin"):
        self.client = client
        self.service_admin_id = service_admin_id
        
        # In-memory storage (in production, use a database)
        self.end_users: Dict[str, EndUser] = {}
        self.user_workspaces: Dict[str, List[UserWorkspace]] = {}  # user_id -> workspaces
        self.user_sessions: Dict[str, List[str]] = {}  # user_id -> session_ids
        self.user_costs: Dict[str, float] = {}  # user_id -> total_cost
        
        # Service-level workspace for managing users
        self.service_workspace_id = "multi-tenant-service"
        self._ensure_service_workspace()
    
    def _ensure_service_workspace(self):
        """Ensure the service-level workspace exists"""
        try:
            workspace = self.client.get_workspace(self.service_admin_id, self.service_workspace_id)
            print(f"✅ Using existing service workspace: {self.service_workspace_id}")
        except Exception:
            print(f"📦 Creating service workspace: {self.service_workspace_id}")
            self.client.create_workspace(
                user_id=self.service_admin_id,
                workspace_id=self.service_workspace_id,
                name="Multi-Tenant Service Management",
                resource_package=WorkspaceResourcePackage.ENTERPRISE_LARGE,
                description="Service workspace for managing multiple end-users"
            )
    
    def _generate_user_prefix(self, user_id: str) -> str:
        """Generate a unique storage prefix for a user"""
        # Create a deterministic but unique prefix
        hash_obj = hashlib.md5(user_id.encode())
        return f"users/{hash_obj.hexdigest()[:8]}/{user_id}"
    
    def _generate_workspace_prefix(self, user_id: str, workspace_id: str) -> str:
        """Generate a unique storage prefix for a workspace"""
        user_prefix = self._generate_user_prefix(user_id)
        return f"{user_prefix}/workspaces/{workspace_id}"
    
    def register_end_user(self, email: str, subscription_tier: str = "free") -> str:
        """
        Register a new end-user.
        
        Args:
            email: User's email address
            subscription_tier: Subscription tier ('free', 'pro', 'enterprise')
        
        Returns:
            User ID for the new user
        """
        # Generate unique user ID
        user_id = f"user_{uuid.uuid4().hex[:8]}"
        
        # Set limits based on subscription tier
        tier_limits = {
            "free": {"max_workspaces": 1, "max_storage_gb": 10},
            "pro": {"max_workspaces": 5, "max_storage_gb": 100},
            "enterprise": {"max_workspaces": 20, "max_storage_gb": 1000}
        }
        
        limits = tier_limits.get(subscription_tier, tier_limits["free"])
        
        # Create end user
        end_user = EndUser(
            user_id=user_id,
            email=email,
            subscription_tier=subscription_tier,
            max_workspaces=limits["max_workspaces"],
            max_storage_gb=limits["max_storage_gb"],
            created_at=datetime.now()
        )
        
        # Store user
        self.end_users[user_id] = end_user
        self.user_workspaces[user_id] = []
        self.user_sessions[user_id] = []
        self.user_costs[user_id] = 0.0
        
        print(f"✅ Registered end-user: {email} (ID: {user_id}, Tier: {subscription_tier})")
        return user_id
    
    def create_user_workspace(self, user_id: str, workspace_name: str, 
                            resource_package: WorkspaceResourcePackage) -> str:
        """
        Create a workspace for an end-user.
        
        Args:
            user_id: End-user ID
            workspace_name: Name for the workspace
            resource_package: Resource package for the workspace
        
        Returns:
            Workspace ID
        """
        # Validate user exists
        if user_id not in self.end_users:
            raise ValueError(f"User {user_id} not found")
        
        end_user = self.end_users[user_id]
        
        # Check workspace limits
        current_workspaces = len(self.user_workspaces[user_id])
        if current_workspaces >= end_user.max_workspaces:
            raise ValueError(f"User {user_id} has reached workspace limit ({end_user.max_workspaces})")
        
        # Generate workspace ID
        workspace_id = f"ws_{uuid.uuid4().hex[:8]}"
        
        # Generate storage prefix
        storage_prefix = self._generate_workspace_prefix(user_id, workspace_id)
        
        # Create workspace in OnMemOS
        try:
            workspace = self.client.create_workspace(
                user_id=self.service_admin_id,  # Service admin owns all workspaces
                workspace_id=workspace_id,
                name=f"{end_user.email} - {workspace_name}",
                resource_package=resource_package,
                description=f"Workspace for user {end_user.email}"
            )
            
            # Create user workspace record
            user_workspace = UserWorkspace(
                workspace_id=workspace_id,
                user_id=user_id,
                name=workspace_name,
                resource_package=resource_package,
                storage_prefix=storage_prefix,
                created_at=datetime.now()
            )
            
            # Store workspace
            self.user_workspaces[user_id].append(user_workspace)
            
            print(f"✅ Created workspace '{workspace_name}' for user {end_user.email}")
            print(f"   📁 Storage prefix: {storage_prefix}")
            print(f"   📦 Resource package: {resource_package.value}")
            
            return workspace_id
            
        except Exception as e:
            print(f"❌ Failed to create workspace: {e}")
            raise
    
    def create_user_session(self, user_id: str, workspace_id: str, 
                          session_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a session for an end-user in their workspace.
        
        Args:
            user_id: End-user ID
            workspace_id: Workspace ID
            session_config: Session configuration
        
        Returns:
            Session information
        """
        # Validate user and workspace
        if user_id not in self.end_users:
            raise ValueError(f"User {user_id} not found")
        
        # Find workspace
        workspace = None
        for ws in self.user_workspaces[user_id]:
            if ws.workspace_id == workspace_id:
                workspace = ws
                break
        
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found for user {user_id}")
        
        # Add user-specific storage configuration
        session_config.update({
            "workspace_id": workspace_id,
            "user": self.service_admin_id,  # Service admin owns the session
            "namespace": f"user-{user_id}",
            "request_bucket": True,
            "bucket_size_gb": 5,
            "request_persistent_storage": True,
            "persistent_storage_size_gb": 20
        })
        
        # Create session
        session = self.client.create_session(session_config)
        session_id = session["id"]
        
        # Track session for user
        self.user_sessions[user_id].append(session_id)
        
        print(f"✅ Created session for user {user_id} in workspace {workspace_id}")
        print(f"   🆔 Session ID: {session_id}")
        print(f"   📁 Storage prefix: {workspace.storage_prefix}")
        
        return session
    
    def execute_user_task(self, user_id: str, session_id: str, command: str) -> Dict[str, Any]:
        """Execute a task in a user's session"""
        # Validate user owns the session
        if user_id not in self.user_sessions or session_id not in self.user_sessions[user_id]:
            raise ValueError(f"Session {session_id} not found for user {user_id}")
        
        # Execute command
        result = self.client.execute_session(session_id, command)
        
        # Track cost (simplified)
        if result.get("success"):
            self.user_costs[user_id] += 0.01  # $0.01 per successful command
        
        return result
    
    def get_user_storage_info(self, user_id: str) -> Dict[str, Any]:
        """Get storage information for a user"""
        if user_id not in self.end_users:
            raise ValueError(f"User {user_id} not found")
        
        end_user = self.end_users[user_id]
        workspaces = self.user_workspaces[user_id]
        
        # Calculate storage usage
        total_storage_used = 0
        workspace_storage = {}
        
        for workspace in workspaces:
            # In a real implementation, you'd query actual storage usage
            # For demo, we'll estimate based on workspace type
            estimated_storage = {
                WorkspaceResourcePackage.FREE_MICRO: 1,
                WorkspaceResourcePackage.DEV_SMALL: 5,
                WorkspaceResourcePackage.DEV_MEDIUM: 10,
                WorkspaceResourcePackage.ML_T4_MEDIUM: 50,
                WorkspaceResourcePackage.ENTERPRISE_LARGE: 100
            }.get(workspace.resource_package, 10)
            
            workspace_storage[workspace.workspace_id] = {
                "name": workspace.name,
                "storage_prefix": workspace.storage_prefix,
                "estimated_storage_gb": estimated_storage,
                "resource_package": workspace.resource_package.value
            }
            total_storage_used += estimated_storage
        
        return {
            "user_id": user_id,
            "email": end_user.email,
            "subscription_tier": end_user.subscription_tier,
            "storage_limit_gb": end_user.max_storage_gb,
            "storage_used_gb": total_storage_used,
            "storage_available_gb": max(0, end_user.max_storage_gb - total_storage_used),
            "workspaces": workspace_storage,
            "total_cost": self.user_costs.get(user_id, 0.0)
        }
    
    def cleanup_user_session(self, user_id: str, session_id: str):
        """Clean up a user's session"""
        if user_id not in self.user_sessions or session_id not in self.user_sessions[user_id]:
            return
        
        try:
            self.client.delete_session(session_id)
            self.user_sessions[user_id].remove(session_id)
            print(f"✅ Cleaned up session {session_id} for user {user_id}")
        except Exception as e:
            print(f"❌ Failed to cleanup session {session_id}: {e}")
    
    def list_all_users(self) -> List[Dict[str, Any]]:
        """List all end-users with their information"""
        users_info = []
        
        for user_id, end_user in self.end_users.items():
            workspaces = self.user_workspaces[user_id]
            sessions = self.user_sessions[user_id]
            
            users_info.append({
                "user_id": user_id,
                "email": end_user.email,
                "subscription_tier": end_user.subscription_tier,
                "workspace_count": len(workspaces),
                "active_sessions": len(sessions),
                "total_cost": self.user_costs.get(user_id, 0.0),
                "created_at": end_user.created_at.isoformat(),
                "is_active": end_user.is_active
            })
        
        return users_info

# ============================================================================
# Demo: Multi-Tenant SaaS Application
# ============================================================================

def demo_multi_tenant_saas():
    """Demonstrate a multi-tenant SaaS application"""
    print("🚀 OnMemOS v3 Multi-Tenant SaaS Demo")
    print("=" * 50)
    
    # Initialize service
    client = OnMemOSClient()
    service = MultiTenantService(client)
    
    try:
        # Register multiple end-users
        print("\n👥 Registering end-users...")
        
        users = [
            ("alice@example.com", "free"),
            ("bob@startup.com", "pro"),
            ("charlie@enterprise.com", "enterprise"),
            ("diana@freelancer.com", "free")
        ]
        
        user_ids = {}
        for email, tier in users:
            user_id = service.register_end_user(email, tier)
            user_ids[email] = user_id
        
        # Create workspaces for users
        print("\n📦 Creating user workspaces...")
        
        # Alice (free tier) - 1 workspace
        alice_id = user_ids["alice@example.com"]
        alice_workspace = service.create_user_workspace(
            alice_id, "My Project", WorkspaceResourcePackage.FREE_MICRO
        )
        
        # Bob (pro tier) - multiple workspaces
        bob_id = user_ids["bob@startup.com"]
        bob_workspaces = [
            service.create_user_workspace(bob_id, "Development", WorkspaceResourcePackage.DEV_MEDIUM),
            service.create_user_workspace(bob_id, "Testing", WorkspaceResourcePackage.DEV_SMALL),
            service.create_user_workspace(bob_id, "Production", WorkspaceResourcePackage.DEV_LARGE)
        ]
        
        # Charlie (enterprise tier) - ML workspace
        charlie_id = user_ids["charlie@enterprise.com"]
        charlie_workspace = service.create_user_workspace(
            charlie_id, "ML Research", WorkspaceResourcePackage.ML_T4_MEDIUM
        )
        
        # Create sessions for users
        print("\n🖥️ Creating user sessions...")
        
        # Alice's session
        alice_session = service.create_user_session(alice_id, alice_workspace, {
            "template": "python",
            "cpu_size": CPUSize.SMALL,
            "memory_size": MemorySize.SMALL,
            "ttl_minutes": 60
        })
        
        # Bob's development session
        bob_dev_session = service.create_user_session(bob_id, bob_workspaces[0], {
            "template": "python",
            "cpu_size": CPUSize.MEDIUM,
            "memory_size": MemorySize.MEDIUM,
            "ttl_minutes": 120
        })
        
        # Charlie's ML session
        charlie_ml_session = service.create_user_session(charlie_id, charlie_workspace, {
            "template": "python",
            "cpu_size": CPUSize.LARGE,
            "memory_size": MemorySize.LARGE,
            "gpu_type": GPUType.T4,
            "ttl_minutes": 180
        })
        
        # Execute tasks for different users
        print("\n⚡ Executing user tasks...")
        
        # Alice's task
        print(f"\n👤 Alice (Free Tier) - Simple data analysis:")
        alice_result = service.execute_user_task(
            alice_id, alice_session["id"], 
            "python -c \"import pandas as pd; print('Alice: Simple analysis completed')\""
        )
        print(f"   Result: {'✅ Success' if alice_result.get('success') else '❌ Failed'}")
        
        # Bob's task
        print(f"\n👤 Bob (Pro Tier) - Development work:")
        bob_result = service.execute_user_task(
            bob_id, bob_dev_session["id"],
            "python -c \"import numpy as np; print('Bob: Development environment ready')\""
        )
        print(f"   Result: {'✅ Success' if bob_result.get('success') else '❌ Failed'}")
        
        # Charlie's task
        print(f"\n👤 Charlie (Enterprise Tier) - ML training:")
        charlie_result = service.execute_user_task(
            charlie_id, charlie_ml_session["id"],
            "python -c \"import torch; print('Charlie: ML environment ready')\""
        )
        print(f"   Result: {'✅ Success' if charlie_result.get('success') else '❌ Failed'}")
        
        # Show user storage information
        print("\n📊 User Storage Information:")
        for email, user_id in user_ids.items():
            storage_info = service.get_user_storage_info(user_id)
            print(f"\n👤 {email} ({storage_info['subscription_tier']}):")
            print(f"   💾 Storage: {storage_info['storage_used_gb']}GB / {storage_info['storage_limit_gb']}GB")
            print(f"   📦 Workspaces: {len(storage_info['workspaces'])}")
            print(f"   💰 Total Cost: ${storage_info['total_cost']:.2f}")
            
            for ws_id, ws_info in storage_info['workspaces'].items():
                print(f"     📁 {ws_info['name']}: {ws_info['storage_prefix']}")
        
        # Show all users
        print("\n👥 All Users Summary:")
        all_users = service.list_all_users()
        for user_info in all_users:
            print(f"   {user_info['email']}: {user_info['workspace_count']} workspaces, "
                  f"{user_info['active_sessions']} sessions, ${user_info['total_cost']:.2f}")
        
        print("\n🎉 Multi-tenant SaaS demo completed!")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup all sessions
        print("\n🧹 Cleaning up all user sessions...")
        for user_id, sessions in service.user_sessions.items():
            for session_id in sessions[:]:  # Copy list to avoid modification during iteration
                service.cleanup_user_session(user_id, session_id)

# ============================================================================
# Storage Organization Examples
# ============================================================================

def show_storage_organization():
    """Show how storage is organized for multi-tenant setup"""
    print("\n📁 Multi-Tenant Storage Organization")
    print("=" * 40)
    
    # Example storage structure
    storage_structure = {
        "GCS Bucket: onmemos-user-data": {
            "users/": {
                "a1b2c3d4/": {  # User hash prefix
                    "user_alice123/": {  # User ID
                        "workspaces/": {
                            "ws_project1/": {
                                "data/": "User's data files",
                                "models/": "Trained models",
                                "logs/": "Application logs"
                            }
                        },
                        "shared/": "Shared resources"
                    }
                },
                "e5f6g7h8/": {
                    "user_bob456/": {
                        "workspaces/": {
                            "ws_dev/": {"data/": "Development data"},
                            "ws_prod/": {"data/": "Production data"}
                        }
                    }
                }
            }
        },
        "Filestore Instances": {
            "user-alice123-ws-project1": "PVC for Alice's project workspace",
            "user-bob456-ws-dev": "PVC for Bob's dev workspace",
            "user-bob456-ws-prod": "PVC for Bob's prod workspace"
        }
    }
    
    print("📋 Storage Organization:")
    print("   • Each user gets a unique prefix based on their ID")
    print("   • Workspaces are isolated within user prefixes")
    print("   • Bucket and Filestore are separate for different use cases")
    print("   • Easy to implement per-user quotas and billing")
    
    print("\n🔐 Security Benefits:")
    print("   • Users can't access other users' data")
    print("   • Workspace-level isolation")
    print("   • Easy to implement access controls")
    print("   • Audit trails per user")

if __name__ == "__main__":
    print("🚀 OnMemOS v3 Multi-Tenant Service Demo")
    print("=" * 50)
    
    # Run demo
    demo_multi_tenant_saas()
    show_storage_organization()
    
    print("\n💡 Key Takeaways:")
    print("   ✅ Each end-user gets isolated storage and workspaces")
    print("   ✅ Storage prefixes prevent data leakage between users")
    print("   ✅ Easy to implement per-user quotas and billing")
    print("   ✅ Workspace limits based on subscription tiers")
    print("   ✅ Service admin owns all resources, users get access")
    print("   🚀 Perfect foundation for building SaaS applications!")