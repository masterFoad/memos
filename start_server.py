#!/usr/bin/env python3
"""
OnMemOS v3 Server Startup Script

This script:
1. Loads environment variables from .env file
2. Sets up Google Cloud authentication
3. Starts the OnMemOS v3 server with proper configuration

Usage:
    python start_server.py
    python start_server.py --dev
    python start_server.py --test
"""

import os
import sys
import subprocess
from pathlib import Path
import argparse

def load_env_file():
    """Load environment variables from .env file"""
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found")
        print("   Copy env.example to .env and configure it")
        print("   Or run: python gcloud_auth.py --create-service-account")
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

def setup_gcloud_auth():
    """Set up Google Cloud authentication"""
    print("🔐 Setting up Google Cloud authentication...")
    
    try:
        # Check if GOOGLE_APPLICATION_CREDENTIALS is set
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path and os.path.exists(creds_path):
            print(f"✅ Using service account credentials: {creds_path}")
        else:
            print("⚠️  GOOGLE_APPLICATION_CREDENTIALS not set or file not found")
        
        # Test GCP authentication
        print("🧪 Testing Google Cloud authentication...")
        
        # Test basic GCP access
        result = subprocess.run(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ No active GCP authentication found")
            return False
        
        active_account = result.stdout.strip()
        if active_account:
            print(f"✅ Active account: {active_account}")
        else:
            print("❌ No active GCP account found")
            return False
        
        # Test GCS access
        result = subprocess.run(["gsutil", "ls"], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Cannot access GCS - check permissions")
            return False
        
        # Count accessible buckets
        buckets_result = subprocess.run(["gsutil", "ls"], capture_output=True, text=True)
        bucket_count = len([line for line in buckets_result.stdout.split('\n') if line.strip()])
        print(f"✅ GCS access successful - {bucket_count} buckets accessible")
        
        # Test Compute Engine access
        result = subprocess.run(["gcloud", "compute", "instances", "list", "--limit=1"], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("⚠️  Cannot access Compute Engine - some features may not work")
        else:
            print("✅ Compute Engine access successful")
        
        print("✅ Google Cloud authentication successful!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing Google Cloud authentication: {e}")
        return False

def start_server(dev_mode=False, test_mode=False):
    """Start the OnMemOS v3 server"""
    print("🚀 Starting OnMemOS v3 server...")
    
    # Set up environment
    if not load_env_file():
        return False
    
    # Set up Google Cloud authentication
    if not setup_gcloud_auth():
        print("⚠️  Google Cloud authentication not configured")
        print("   Server will start but cloud features may not work")
    
    # Set server mode
    if test_mode:
        os.environ["ONMEMOS_TEST_MODE"] = "true"
        print("🧪 Starting in TEST MODE")
    elif dev_mode:
        os.environ["DEBUG"] = "true"
        print("🔧 Starting in DEVELOPMENT MODE")
    else:
        print("🏭 Starting in PRODUCTION MODE")
    
    # Get configuration
    config_file = os.getenv("ONMEMOS_CONFIG", "ops/config.yaml")
    host = os.getenv("ONMEMOS_HOST", "127.0.0.1")
    port = os.getenv("ONMEMOS_PORT", "8080")
    
    print(f"📁 Config file: {config_file}")
    print(f"🌐 Server: http://{host}:{port}")
    
    # Start the server
    try:
        cmd = [
            "uvicorn", "server.app:app",
            "--host", host,
            "--port", port,
            "--log-level", "info"
        ]
        
        if dev_mode:
            cmd.append("--reload")
            cmd.extend(["--log-level", "debug"])
        
        print(f"🔄 Running: {' '.join(cmd)}")
        subprocess.run(cmd)
    
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return False
    
    return True

def main():
    parser = argparse.ArgumentParser(description="OnMemOS v3 Server Startup")
    parser.add_argument("--dev", action="store_true", 
                       help="Start in development mode with hot reload")
    parser.add_argument("--test", action="store_true", 
                       help="Start in test mode with mocks")
    parser.add_argument("--setup", action="store_true", 
                       help="Set up Google Cloud authentication only")
    
    args = parser.parse_args()
    
    if args.setup:
        setup_gcloud_auth()
        return
    
    start_server(dev_mode=args.dev, test_mode=args.test)

if __name__ == "__main__":
    main()
