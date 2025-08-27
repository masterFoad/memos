#!/usr/bin/env python3
"""
Cleanup utility for OnMemOS v3

This script helps clean up orphaned resources:
- Docker containers with ws_ prefix
- Temporary files
- Orphaned workspaces
"""

import subprocess
import os
import sys
import argparse

def run_command(cmd, capture_output=True):
    """Run a command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture_output, text=True)
        return result
    except Exception as e:
        print(f"❌ Error running command '{cmd}': {e}")
        return None

def cleanup_docker_containers():
    """Clean up Docker containers with ws_ prefix"""
    print("🐳 Cleaning up Docker containers...")
    
    # List containers with ws_ prefix
    result = run_command("docker ps -a --filter 'name=ws_' --format '{{.Names}}'")
    if not result or result.returncode != 0:
        print("❌ Failed to list containers")
        return
    
    containers = result.stdout.strip().split('\n') if result.stdout.strip() else []
    
    if not containers:
        print("✅ No containers to clean up")
        return
    
    print(f"📋 Found {len(containers)} containers to clean up:")
    for container in containers:
        if container:
            print(f"   🐳 {container}")
    
    # Stop containers
    print("🛑 Stopping containers...")
    result = run_command("docker stop $(docker ps -q --filter 'name=ws_')")
    if result and result.returncode == 0:
        print("✅ Containers stopped")
    else:
        print("⚠️ Some containers may not have stopped properly")
    
    # Remove containers
    print("🗑️ Removing containers...")
    result = run_command("docker rm $(docker ps -aq --filter 'name=ws_')")
    if result and result.returncode == 0:
        print("✅ Containers removed")
    else:
        print("⚠️ Some containers may not have been removed properly")
    
    # Verify cleanup
    result = run_command("docker ps -a --filter 'name=ws_' --format '{{.Names}}'")
    if result and result.returncode == 0:
        remaining = result.stdout.strip().split('\n') if result.stdout.strip() else []
        remaining = [c for c in remaining if c]  # Remove empty strings
        if remaining:
            print(f"⚠️ {len(remaining)} containers still remain:")
            for container in remaining:
                print(f"   🐳 {container}")
        else:
            print("✅ All ws_ containers cleaned up!")

def cleanup_temp_files():
    """Clean up temporary files"""
    print("📁 Cleaning up temporary files...")
    
    # Clean up /tmp/gcs-bucket-* directories
    result = run_command("find /tmp -name 'gcs-bucket-*' -type d 2>/dev/null")
    if result and result.returncode == 0 and result.stdout.strip():
        dirs = result.stdout.strip().split('\n')
        print(f"📋 Found {len(dirs)} temporary GCS directories:")
        for dir_path in dirs:
            if dir_path:
                print(f"   📁 {dir_path}")
        
        # Remove directories
        result = run_command("rm -rf /tmp/gcs-bucket-*")
        if result and result.returncode == 0:
            print("✅ Temporary GCS directories removed")
        else:
            print("⚠️ Some directories may not have been removed properly")
    else:
        print("✅ No temporary GCS directories found")
    
    # Clean up /tmp/mock-bucket-* directories
    result = run_command("find /tmp -name 'mock-bucket-*' -type d 2>/dev/null")
    if result and result.returncode == 0 and result.stdout.strip():
        dirs = result.stdout.strip().split('\n')
        print(f"📋 Found {len(dirs)} temporary mock directories:")
        for dir_path in dirs:
            if dir_path:
                print(f"   📁 {dir_path}")
        
        # Remove directories
        result = run_command("rm -rf /tmp/mock-bucket-*")
        if result and result.returncode == 0:
            print("✅ Temporary mock directories removed")
        else:
            print("⚠️ Some directories may not have been removed properly")
    else:
        print("✅ No temporary mock directories found")

def cleanup_orphaned_workspaces():
    """Clean up orphaned workspace directories"""
    print("🏗️ Cleaning up orphaned workspace directories...")
    
    # Check for workspace directories in /opt/onmemos/persist
    persist_root = "/opt/onmemos/persist"
    if os.path.exists(persist_root):
        result = run_command(f"find {persist_root} -name 'ws_*' -type d 2>/dev/null")
        if result and result.returncode == 0 and result.stdout.strip():
            dirs = result.stdout.strip().split('\n')
            print(f"📋 Found {len(dirs)} orphaned workspace directories:")
            for dir_path in dirs:
                if dir_path:
                    print(f"   🏗️ {dir_path}")
            
            # Remove directories (be careful!)
            print("⚠️ Removing orphaned workspace directories...")
            result = run_command(f"rm -rf {persist_root}/*/ws_*")
            if result and result.returncode == 0:
                print("✅ Orphaned workspace directories removed")
            else:
                print("⚠️ Some directories may not have been removed properly")
        else:
            print("✅ No orphaned workspace directories found")
    else:
        print("✅ Persist root directory not found")

def show_status():
    """Show current status of resources"""
    print("📊 Current Resource Status")
    print("=" * 40)
    
    # Docker containers
    result = run_command("docker ps -a --filter 'name=ws_' --format 'table {{.Names}}\t{{.Status}}\t{{.CreatedAt}}'")
    if result and result.returncode == 0:
        print("🐳 Docker Containers:")
        print(result.stdout)
    else:
        print("🐳 No ws_ containers found")
    
    # Temporary directories
    print("\n📁 Temporary Directories:")
    result = run_command("find /tmp -name '*bucket*' -type d 2>/dev/null | head -10")
    if result and result.returncode == 0 and result.stdout.strip():
        print(result.stdout)
    else:
        print("   No temporary bucket directories found")
    
    # Disk usage
    print("\n💾 Disk Usage:")
    result = run_command("df -h /tmp")
    if result and result.returncode == 0:
        print(result.stdout)

def main():
    parser = argparse.ArgumentParser(description="OnMemOS v3 Cleanup Utility")
    parser.add_argument("--containers", action="store_true", 
                       help="Clean up Docker containers")
    parser.add_argument("--temp-files", action="store_true", 
                       help="Clean up temporary files")
    parser.add_argument("--workspaces", action="store_true", 
                       help="Clean up orphaned workspace directories")
    parser.add_argument("--all", action="store_true", 
                       help="Clean up all resources")
    parser.add_argument("--status", action="store_true", 
                       help="Show current status")
    
    args = parser.parse_args()
    
    if not any([args.containers, args.temp_files, args.workspaces, args.all, args.status]):
        print("❌ No cleanup action specified")
        print("Use --help for options")
        sys.exit(1)
    
    print("🧹 OnMemOS v3 Cleanup Utility")
    print("=" * 40)
    
    if args.status:
        show_status()
        return
    
    if args.all or args.containers:
        cleanup_docker_containers()
        print()
    
    if args.all or args.temp_files:
        cleanup_temp_files()
        print()
    
    if args.all or args.workspaces:
        cleanup_orphaned_workspaces()
        print()
    
    print("✅ Cleanup completed!")

if __name__ == "__main__":
    main()
