#!/usr/bin/env python3
"""
Google Cloud Authentication Utility for OnMemOS v3

This utility handles Google Cloud authentication using multiple methods:
1. Service Account Key File
2. Application Default Credentials
3. Direct Service Account Key JSON
4. gcloud CLI authentication

Usage:
    python gcloud_auth.py --setup
    python gcloud_auth.py --test
    python gcloud_auth.py --create-service-account
"""

import os
import sys
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple
import argparse

def setup_gcloud_auth() -> bool:
    """Set up Google Cloud authentication using the best available method"""
    print("🔐 Setting up Google Cloud Authentication...")
    
    # Check if we're already authenticated
    if test_gcloud_auth():
        print("✅ Google Cloud authentication already configured!")
        return True
    
    # Method 1: Check for service account key file
    if setup_service_account_key():
        return True
    
    # Method 2: Check for direct service account key in environment
    if setup_direct_service_account():
        return True
    
    # Method 3: Use gcloud CLI authentication
    if setup_gcloud_cli_auth():
        return True
    
    print("❌ Failed to set up Google Cloud authentication")
    print("   Please check the documentation for manual setup instructions")
    return False

def setup_service_account_key() -> bool:
    """Set up authentication using service account key file"""
    print("🔑 Checking for service account key file...")
    
    # Check environment variable
    key_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if key_file and os.path.exists(key_file):
        print(f"✅ Found service account key file: {key_file}")
        return True
    
    # Check common locations
    common_locations = [
        "./service-account-key.json",
        "./gcp-key.json",
        "./google-cloud-key.json",
        "~/.gcp/service-account-key.json",
        "/etc/gcp/service-account-key.json"
    ]
    
    for location in common_locations:
        expanded_path = os.path.expanduser(location)
        if os.path.exists(expanded_path):
            print(f"✅ Found service account key file: {expanded_path}")
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = expanded_path
            return True
    
    print("   No service account key file found")
    return False

def setup_direct_service_account() -> bool:
    """Set up authentication using direct service account key in environment"""
    print("🔑 Checking for direct service account key...")
    
    key_json = os.getenv("GOOGLE_CLOUD_KEYFILE_JSON")
    if key_json:
        try:
            # Validate JSON
            json.loads(key_json)
            print("✅ Found valid service account key in environment")
            return True
        except json.JSONDecodeError:
            print("   Invalid JSON in GOOGLE_CLOUD_KEYFILE_JSON")
            return False
    
    print("   No direct service account key found")
    return False

def setup_gcloud_cli_auth() -> bool:
    """Set up authentication using gcloud CLI"""
    print("🔑 Setting up gcloud CLI authentication...")
    
    try:
        # Check if gcloud is installed
        result = subprocess.run(["gcloud", "--version"], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("   gcloud CLI not found. Please install it first.")
            return False
        
        # Check if already authenticated
        result = subprocess.run(["gcloud", "auth", "list", "--filter=status:ACTIVE"], 
                              capture_output=True, text=True)
        if "ACTIVE" in result.stdout:
            print("✅ gcloud CLI already authenticated")
            return True
        
        # Set up application default credentials
        print("   Setting up application default credentials...")
        result = subprocess.run(["gcloud", "auth", "application-default", "login"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ gcloud CLI authentication successful")
            return True
        else:
            print(f"   gcloud authentication failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"   Error setting up gcloud CLI: {e}")
        return False

def test_gcloud_auth() -> bool:
    """Test Google Cloud authentication"""
    print("🧪 Testing Google Cloud authentication...")
    
    try:
        from google.cloud import storage
        
        # Try to create a storage client
        client = storage.Client()
        
        # Test if we can list buckets (this requires authentication)
        buckets = list(client.list_buckets(max_results=1))
        
        print("✅ Google Cloud authentication successful!")
        print(f"   Project: {client.project}")
        print(f"   Buckets accessible: {len(buckets)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Google Cloud authentication failed: {e}")
        return False

def create_service_account() -> bool:
    """Create a new service account for OnMemOS v3"""
    print("🔧 Creating service account for OnMemOS v3...")
    
    try:
        # Get project ID
        project_id = os.getenv("PROJECT_ID")
        if not project_id:
            print("❌ PROJECT_ID environment variable not set")
            return False
        
        service_account_name = "onmemos-v3-service"
        service_account_email = f"{service_account_name}@{project_id}.iam.gserviceaccount.com"
        
        # Check if service account already exists
        result = subprocess.run([
            "gcloud", "iam", "service-accounts", "describe", service_account_email,
            "--project", project_id
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Service account already exists: {service_account_email}")
        else:
            # Create service account
            print(f"   Creating service account: {service_account_name}")
            result = subprocess.run([
                "gcloud", "iam", "service-accounts", "create", service_account_name,
                "--display-name", "OnMemOS v3 Service Account",
                "--description", "Service account for OnMemOS v3 cloud operations",
                "--project", project_id
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"❌ Failed to create service account: {result.stderr}")
                return False
            
            print(f"✅ Service account created: {service_account_email}")
        
        # Grant necessary permissions
        print("   Granting permissions...")
        permissions = [
            "roles/storage.admin",  # Full access to Cloud Storage
            "roles/storage.objectAdmin",  # Object-level access
            "roles/storage.objectViewer",  # Read access
            "roles/logging.logWriter",  # Write logs
            "roles/monitoring.metricWriter"  # Write metrics
        ]
        
        for permission in permissions:
            result = subprocess.run([
                "gcloud", "projects", "add-iam-policy-binding", project_id,
                "--member", f"serviceAccount:{service_account_email}",
                "--role", permission
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"   ✅ Granted {permission}")
            else:
                print(f"   ⚠️ Failed to grant {permission}: {result.stderr}")
        
        # Create and download key
        print("   Creating service account key...")
        key_file = f"{service_account_name}-key.json"
        
        result = subprocess.run([
            "gcloud", "iam", "service-accounts", "keys", "create", key_file,
            "--iam-account", service_account_email,
            "--project", project_id
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Service account key created: {key_file}")
            print(f"   Set GOOGLE_APPLICATION_CREDENTIALS={os.path.abspath(key_file)}")
            
            # Update .env file if it exists
            update_env_file(key_file)
            
            return True
        else:
            print(f"❌ Failed to create service account key: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating service account: {e}")
        return False

def update_env_file(key_file: str):
    """Update .env file with the new key file path"""
    env_file = Path(".env")
    if env_file.exists():
        print("   Updating .env file...")
        
        # Read current .env file
        with open(env_file, 'r') as f:
            content = f.read()
        
        # Update GOOGLE_APPLICATION_CREDENTIALS
        lines = content.split('\n')
        updated_lines = []
        found = False
        
        for line in lines:
            if line.startswith("GOOGLE_APPLICATION_CREDENTIALS="):
                updated_lines.append(f"GOOGLE_APPLICATION_CREDENTIALS={os.path.abspath(key_file)}")
                found = True
            else:
                updated_lines.append(line)
        
        if not found:
            updated_lines.append(f"GOOGLE_APPLICATION_CREDENTIALS={os.path.abspath(key_file)}")
        
        # Write updated .env file
        with open(env_file, 'w') as f:
            f.write('\n'.join(updated_lines))
        
        print("   ✅ Updated .env file")

def load_env_file() -> bool:
    """Load environment variables from .env file"""
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found")
        print("   Copy env.example to .env and configure it")
        return False
    
    print("📄 Loading environment from .env file...")
    
    try:
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        
        print("✅ Environment variables loaded")
        return True
        
    except Exception as e:
        print(f"❌ Error loading .env file: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Google Cloud Authentication for OnMemOS v3")
    parser.add_argument("--setup", action="store_true", 
                       help="Set up Google Cloud authentication")
    parser.add_argument("--test", action="store_true", 
                       help="Test Google Cloud authentication")
    parser.add_argument("--create-service-account", action="store_true", 
                       help="Create a new service account for OnMemOS v3")
    parser.add_argument("--load-env", action="store_true", 
                       help="Load environment variables from .env file")
    
    args = parser.parse_args()
    
    if args.load_env:
        load_env_file()
    
    if args.setup:
        setup_gcloud_auth()
    
    if args.test:
        test_gcloud_auth()
    
    if args.create_service_account:
        create_service_account()
    
    if not any([args.setup, args.test, args.create_service_account, args.load_env]):
        parser.print_help()

if __name__ == "__main__":
    main()
