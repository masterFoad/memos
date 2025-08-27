#!/usr/bin/env python3
"""
Setup persistent storage directories with proper permissions
"""

import os
import sys
import subprocess

def setup_persistent_storage():
    """Setup persistent storage directories with proper permissions"""
    print("🔧 Setting up Persistent Storage")
    print("=" * 50)
    
    # Configuration
    persist_root = "/opt/onmemos/persist"
    namespace = "data-science-demo"
    user = "researcher-123"
    
    print(f"📁 Persist Root: {persist_root}")
    print(f"📁 Namespace: {namespace}")
    print(f"👤 User: {user}")
    
    # Create the full path
    full_path = os.path.join(persist_root, namespace, user)
    print(f"🔗 Full Path: {full_path}")
    
    try:
        # Create directories
        print("📂 Creating directories...")
        os.makedirs(full_path, exist_ok=True)
        print(f"✅ Created directory: {full_path}")
        
        # Set permissions to be writable by the container
        print("🔐 Setting permissions...")
        subprocess.run(["chmod", "-R", "777", full_path], check=True)
        print(f"✅ Set permissions on: {full_path}")
        
        # Create a test file to verify
        test_file = os.path.join(full_path, "test.txt")
        with open(test_file, 'w') as f:
            f.write("Persistent storage test file\n")
        print(f"✅ Created test file: {test_file}")
        
        # List contents
        contents = os.listdir(full_path)
        print(f"📋 Directory contents: {contents}")
        
        # Check permissions
        stat_info = os.stat(full_path)
        print(f"🔐 Directory permissions: {oct(stat_info.st_mode)}")
        print(f"👤 Owner: {stat_info.st_uid}")
        print(f"👥 Group: {stat_info.st_gid}")
        
        print("✅ Persistent storage setup completed!")
        
    except Exception as e:
        print(f"❌ Failed to setup persistent storage: {e}")
        return False
    
    return True

if __name__ == "__main__":
    setup_persistent_storage()
