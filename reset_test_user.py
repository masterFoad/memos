#!/usr/bin/env python3
"""
Reset test user for OnMemOS v3
Creates a pro user with a development workspace
"""

import sys
import os

# Add the server directory to the path so we can import the models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

from server.models.users import user_manager, UserType, WorkspaceResourcePackage

def reset_test_user():
    """Reset the test user to a pro user with a development workspace"""
    user_id = "tester"
    
    # Create or update the user as PRO
    try:
        user = user_manager.get_user(user_id)
        if user:
            print(f"User {user_id} already exists, updating to PRO type...")
            user.user_type = UserType.PRO
        else:
            print(f"Creating new PRO user: {user_id}")
            user = user_manager.create_user(
                user_id=user_id,
                user_type=UserType.PRO,
                name=f"Test User {user_id}"
            )
        
        # Create a development workspace for the user
        workspace_id = "test-workspace"
        workspace_name = "Test Development Workspace"
        
        # Check if workspace already exists
        existing_workspace = user_manager.get_workspace(user_id, workspace_id)
        if existing_workspace:
            print(f"Workspace {workspace_id} already exists for user {user_id}")
        else:
            print(f"Creating development workspace: {workspace_id}")
            workspace = user_manager.create_workspace(
                user_id=user_id,
                workspace_id=workspace_id,
                name=workspace_name,
                resource_package=WorkspaceResourcePackage.DEV_MEDIUM,
                description="Test workspace for development and experimentation"
            )
            print(f"Created workspace: {workspace.name} with package {workspace.resource_package}")
        
        # Print user and workspace information
        print(f"\nUser {user_id} (Type: {user.user_type}):")
        print(f"  Workspaces: {len(user.workspaces)}")
        for workspace in user.workspaces:
            print(f"    - {workspace.workspace_id}: {workspace.name} ({workspace.resource_package})")
        
        # Print entitlements
        entitlements = user_manager.get_user_entitlements(user_id)
        if entitlements:
            print(f"\nUser Entitlements:")
            print(f"  Max Workspaces: {entitlements.max_workspaces}")
            print(f"  Can Share Workspaces: {entitlements.can_share_workspaces}")
            print(f"  Can Cross Namespace: {entitlements.can_cross_namespace}")
            print(f"  Allowed Packages: {len(entitlements.allowed_packages)}")
            for package in entitlements.allowed_packages:
                print(f"    - {package}")
        
        print(f"\nTest user '{user_id}' reset successfully!")
        return True
        
    except Exception as e:
        print(f"Error resetting test user: {e}")
        return False

if __name__ == "__main__":
    success = reset_test_user()
    sys.exit(0 if success else 1)
