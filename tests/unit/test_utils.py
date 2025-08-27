#!/usr/bin/env python3
"""
Test utilities for OnMemOS v3
"""

import jwt
import datetime
import yaml
import os
from pathlib import Path

def load_test_config():
    """Load test configuration"""
    config_path = os.environ.get("ONMEMOS_CONFIG", "ops/config.yaml")
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def generate_test_token(namespace="test-namespace", user="test-user", expires_in=3600):
    """Generate a test JWT token for testing"""
    config = load_test_config()
    jwt_secret = config['server']['jwt_secret']
    
    now = datetime.datetime.utcnow()
    claims = {
        "sub": f"user:{user}",
        "namespace": namespace,
        "user": user,
        "iat": int(now.timestamp()),
        "exp": int((now + datetime.timedelta(seconds=expires_in)).timestamp())
    }
    
    return jwt.encode(claims, jwt_secret, algorithm="HS256")

def get_test_client():
    """Get a test client with proper authentication"""
    from sdk.python.client import OnMemOSClient
    token = generate_test_token()
    return OnMemOSClient("http://localhost:8080", token)

if __name__ == "__main__":
    # Generate a test token for manual testing
    token = generate_test_token()
    print(f"Test token: {token}")
    print(f"Use this token in your tests or API calls")
