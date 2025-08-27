#!/usr/bin/env python3
"""
Namespace Manager for OnMemOS v3

This utility helps manage namespaces:
- List namespaces and their contents
- Show persistent storage usage
- List bucket contents
- Clean up unused namespaces
- Backup namespace data
"""

import os
import json
import argparse
import subprocess
from pathlib import Path
from sdk.python.client import OnMemOSClient as OnMemClient
from tests.unit.test_utils import generate_test_token

class NamespaceManager:
    """Manages OnMemOS v3 namespaces"""
    
    def __init__(self, client: OnMemClient):
        self.client = client
        self.persist_root = "/opt/onmemos/persist"
    
    def list_namespaces(self):
        """List all namespaces and their users"""
        print("📁 Available Namespaces")
        print("=" * 50)
        
        if not os.path.exists(self.persist_root):
            print("❌ Persistent storage root not found")
            return []
        
        namespaces = []
        for namespace_dir in os.listdir(self.persist_root):
            namespace_path = os.path.join(self.persist_root, namespace_dir)
            if os.path.isdir(namespace_path):
                users = []
                for user_dir in os.listdir(namespace_path):
                    user_path = os.path.join(namespace_path, user_dir)
                    if os.path.isdir(user_path):
                        users.append(user_dir)
                
                namespaces.append({
                    "namespace": namespace_dir,
                    "users": users,
                    "path": namespace_path
                })
        
        for ns in namespaces:
            print(f"📁 {ns['namespace']}")
            for user in ns['users']:
                print(f"   👤 {user}")
        
        return namespaces
    
    def show_namespace_details(self, namespace: str, user: str = None):
        """Show detailed information about a namespace"""
        print(f"📋 Namespace Details: {namespace}")
        print("=" * 50)
        
        namespace_path = os.path.join(self.persist_root, namespace)
        if not os.path.exists(namespace_path):
            print(f"❌ Namespace '{namespace}' not found")
            return
        
        # Show users in namespace
        users = [d for d in os.listdir(namespace_path) 
                if os.path.isdir(os.path.join(namespace_path, d))]
        
        print(f"👥 Users in namespace: {', '.join(users)}")
        
        if user:
            self._show_user_details(namespace, user)
        else:
            # Show details for all users
            for user in users:
                print(f"\n--- User: {user} ---")
                self._show_user_details(namespace, user)
    
    def _show_user_details(self, namespace: str, user: str):
        """Show details for a specific user in a namespace"""
        user_path = os.path.join(self.persist_root, namespace, user)
        
        if not os.path.exists(user_path):
            print(f"❌ User '{user}' not found in namespace '{namespace}'")
            return
        
        # Calculate storage usage
        total_size = 0
        file_count = 0
        
        for root, dirs, files in os.walk(user_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    total_size += os.path.getsize(file_path)
                    file_count += 1
                except OSError:
                    pass
        
        print(f"📊 Storage Usage:")
        print(f"   📁 Files: {file_count}")
        print(f"   💾 Size: {self._format_size(total_size)}")
        print(f"   🗂️ Path: {user_path}")
        
        # List files
        print(f"📄 Files:")
        for root, dirs, files in os.walk(user_path):
            rel_root = os.path.relpath(root, user_path)
            if rel_root == ".":
                rel_root = ""
            
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    size = os.path.getsize(file_path)
                    rel_path = os.path.join(rel_root, file) if rel_root else file
                    print(f"   📄 {rel_path} ({self._format_size(size)})")
                except OSError:
                    pass
    
    def list_buckets_for_namespace(self, namespace: str, user: str):
        """List buckets associated with a namespace/user"""
        print(f"☁️ Buckets for {namespace}/{user}")
        print("=" * 50)
        
        try:
            buckets = self.client.list_buckets(namespace, user)
            
            if not buckets:
                print("📭 No buckets found")
                return
            
            for bucket in buckets:
                bucket_name = bucket.get("name", "unknown")
                print(f"📦 {bucket_name}")
                
                # Try to list bucket contents
                try:
                    contents = self.client.bucket_operation(bucket_name, "list", prefix=f"{namespace}/")
                    if contents.get("success"):
                        objects = contents.get("data", {}).get("objects", [])
                        if objects:
                            print(f"   📄 Files: {len(objects)}")
                            for obj in objects[:5]:  # Show first 5
                                print(f"      📄 {obj}")
                            if len(objects) > 5:
                                print(f"      ... and {len(objects) - 5} more")
                        else:
                            print("   📭 No files")
                except Exception as e:
                    print(f"   ⚠️ Error listing contents: {e}")
        
        except Exception as e:
            print(f"❌ Error listing buckets: {e}")
    
    def backup_namespace(self, namespace: str, user: str, backup_path: str):
        """Backup a namespace to a local directory"""
        print(f"💾 Backing up namespace: {namespace}/{user}")
        print("=" * 50)
        
        source_path = os.path.join(self.persist_root, namespace, user)
        if not os.path.exists(source_path):
            print(f"❌ Namespace path not found: {source_path}")
            return False
        
        # Create backup directory
        backup_dir = os.path.join(backup_path, f"{namespace}_{user}_backup")
        os.makedirs(backup_dir, exist_ok=True)
        
        # Create metadata
        metadata = {
            "namespace": namespace,
            "user": user,
            "backup_timestamp": self._get_timestamp(),
            "source_path": source_path,
            "backup_path": backup_dir
        }
        
        with open(os.path.join(backup_dir, "backup_metadata.json"), "w") as f:
            json.dump(metadata, f, indent=2)
        
        # Copy files
        try:
            result = subprocess.run([
                "cp", "-r", source_path, backup_dir
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Backup completed: {backup_dir}")
                return True
            else:
                print(f"❌ Backup failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Backup error: {e}")
            return False
    
    def cleanup_namespace(self, namespace: str, user: str, dry_run: bool = True):
        """Clean up a namespace (remove old files, etc.)"""
        print(f"🧹 Cleaning up namespace: {namespace}/{user}")
        print("=" * 50)
        
        user_path = os.path.join(self.persist_root, namespace, user)
        if not os.path.exists(user_path):
            print(f"❌ Namespace path not found: {user_path}")
            return
        
        # Find old files (older than 30 days)
        old_files = []
        total_size = 0
        
        for root, dirs, files in os.walk(user_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    stat = os.stat(file_path)
                    age_days = (time.time() - stat.st_mtime) / (24 * 3600)
                    
                    if age_days > 30:
                        old_files.append({
                            "path": file_path,
                            "size": stat.st_size,
                            "age_days": age_days
                        })
                        total_size += stat.st_size
                except OSError:
                    pass
        
        if not old_files:
            print("✅ No old files found to clean up")
            return
        
        print(f"📋 Found {len(old_files)} old files ({self._format_size(total_size)})")
        
        if dry_run:
            print("🔍 Dry run - would delete:")
            for file_info in old_files[:10]:  # Show first 10
                rel_path = os.path.relpath(file_info["path"], user_path)
                print(f"   🗑️ {rel_path} ({self._format_size(file_info['size'])}, {file_info['age_days']:.1f} days old)")
            if len(old_files) > 10:
                print(f"   ... and {len(old_files) - 10} more")
        else:
            print("🗑️ Deleting old files...")
            deleted_count = 0
            deleted_size = 0
            
            for file_info in old_files:
                try:
                    os.remove(file_info["path"])
                    deleted_count += 1
                    deleted_size += file_info["size"]
                except OSError as e:
                    print(f"⚠️ Failed to delete {file_info['path']}: {e}")
            
            print(f"✅ Deleted {deleted_count} files ({self._format_size(deleted_size)})")
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def _get_timestamp(self) -> str:
        """Get current timestamp string"""
        from datetime import datetime
        return datetime.now().isoformat()

def main():
    parser = argparse.ArgumentParser(description="OnMemOS v3 Namespace Manager")
    parser.add_argument("--list", action="store_true", 
                       help="List all namespaces")
    parser.add_argument("--show", metavar="NAMESPACE", 
                       help="Show details for a namespace")
    parser.add_argument("--user", metavar="USER", 
                       help="User to show details for (with --show)")
    parser.add_argument("--buckets", metavar="NAMESPACE", 
                       help="List buckets for a namespace")
    parser.add_argument("--backup", metavar="NAMESPACE", 
                       help="Backup a namespace")
    parser.add_argument("--backup-user", metavar="USER", 
                       help="User to backup (with --backup)")
    parser.add_argument("--backup-path", metavar="PATH", default="./backups",
                       help="Backup directory path")
    parser.add_argument("--cleanup", metavar="NAMESPACE", 
                       help="Clean up old files in a namespace")
    parser.add_argument("--cleanup-user", metavar="USER", 
                       help="User to clean up (with --cleanup)")
    parser.add_argument("--execute", action="store_true", 
                       help="Execute cleanup (default is dry run)")
    
    args = parser.parse_args()
    
    if not any([args.list, args.show, args.buckets, args.backup, args.cleanup]):
        print("❌ No action specified")
        print("Use --help for options")
        return
    
    # Initialize client
    token = generate_test_token()
    client = OnMemClient("http://localhost:8080", token)
    manager = NamespaceManager(client)
    
    print("🏗️ OnMemOS v3 Namespace Manager")
    print("=" * 50)
    
    if args.list:
        manager.list_namespaces()
    
    if args.show:
        manager.show_namespace_details(args.show, args.user)
    
    if args.buckets:
        if not args.user:
            print("❌ --user required with --buckets")
            return
        manager.list_buckets_for_namespace(args.buckets, args.user)
    
    if args.backup:
        if not args.backup_user:
            print("❌ --backup-user required with --backup")
            return
        manager.backup_namespace(args.backup, args.backup_user, args.backup_path)
    
    if args.cleanup:
        if not args.cleanup_user:
            print("❌ --cleanup-user required with --cleanup")
            return
        manager.cleanup_namespace(args.cleanup, args.cleanup_user, not args.execute)

if __name__ == "__main__":
    main()
