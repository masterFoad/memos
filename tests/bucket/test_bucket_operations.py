#!/usr/bin/env python3
"""
Bucket Operations Test Suite
Tests bucket creation, mounting, and operations
"""

import pytest
import tempfile
import os
import time
import json
from pathlib import Path

# Add project root to path
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from sdk.python.client import OnMemOSClient as OnMemClient
from sdk.python.models import CreateWorkspace, BucketMountConfig
from tests.unit.test_utils import get_test_client

class TestBucketOperations:
    """Test bucket operations and mounting"""
    
    @pytest.fixture
    def client(self):
        """Create test client with proper authentication"""
        return get_test_client()
    
    @pytest.fixture
    def test_bucket_name(self):
        """Generate test bucket name"""
        return f"test-bucket-{int(time.time())}"
    
    def test_create_bucket(self, client, test_bucket_name):
        """Test bucket creation"""
        print(f"🧪 Testing bucket creation: {test_bucket_name}")
        
        # Create bucket
        result = client.create_bucket(
            bucket_name=test_bucket_name,
            namespace="test-namespace",
            user="test-user"
        )
        
        assert result["name"] is not None
        assert test_bucket_name in result["name"]
        print(f"   ✅ Bucket created: {result['name']}")
    
    def test_list_buckets(self, client):
        """Test bucket listing"""
        print("🧪 Testing bucket listing")
        
        buckets = client.list_buckets("test-namespace", "test-user")
        
        assert isinstance(buckets, list)
        print(f"   ✅ Found {len(buckets)} buckets")
        
        for bucket in buckets:
            print(f"   📦 Bucket: {bucket['name']}")
    
    def test_workspace_with_bucket_mount(self, client, test_bucket_name):
        """Test workspace creation with bucket mount"""
        print(f"🧪 Testing workspace with bucket mount: {test_bucket_name}")
        
        # Create bucket first
        client.create_bucket(test_bucket_name, "test-namespace", "test-user")
        
        # Create workspace with bucket mount
        bucket_mounts = [{
            "bucket_name": test_bucket_name,
            "mount_path": "/bucket",
            "prefix": "workspace/",
            "read_only": False
        }]
        
        workspace = client.create_workspace_with_buckets(
            template="python",
            namespace="test-namespace",
            user="test-user",
            bucket_mounts=bucket_mounts,
            bucket_prefix="workspace/"
        )
        
        assert workspace["id"] is not None
        assert workspace["bucket_mounts"] == bucket_mounts
        print(f"   ✅ Workspace created with bucket mount: {workspace['id']}")
        
        # Test bucket operations in workspace
        result = client.run_python(workspace["id"], {
            "code": """
import os
print("Bucket mount test:")
print(f"Bucket directory exists: {os.path.exists('/bucket')}")
print(f"Bucket contents: {os.listdir('/bucket') if os.path.exists('/bucket') else 'N/A'}")
""",
            "timeout": 10.0
        })
        
        print(f"   📄 Bucket test output: {result.get('stdout', '')}")
        
        # Cleanup
        client.delete(workspace["id"])
    
    def test_bucket_file_operations(self, client, test_bucket_name):
        """Test file operations in buckets"""
        print(f"🧪 Testing bucket file operations: {test_bucket_name}")
        
        # Create bucket
        client.create_bucket(test_bucket_name, "test-namespace", "test-user")
        
        # Create test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("Hello from bucket test!")
            test_file = f.name
        
        try:
            # Upload to bucket
            upload_result = client.upload_to_bucket(
                bucket_name=test_bucket_name,
                local_path=test_file,
                remote_path="test/hello.txt"
            )
            
            assert upload_result["ok"] == True
            print(f"   ✅ File uploaded to bucket")
            
            # Download from bucket
            download_path = f"{test_file}.downloaded"
            client.download_from_bucket(
                bucket_name=test_bucket_name,
                remote_path="test/hello.txt",
                local_path=download_path
            )
            
            with open(download_path, 'r') as f:
                content = f.read()
            
            assert content == "Hello from bucket test!"
            print(f"   ✅ File downloaded from bucket")
            
            # Cleanup
            os.unlink(download_path)
            
        finally:
            os.unlink(test_file)
    
    def test_bucket_operations(self, client, test_bucket_name):
        """Test bucket operations (list, etc.)"""
        print(f"🧪 Testing bucket operations: {test_bucket_name}")
        
        # Create bucket
        client.create_bucket(test_bucket_name, "test-namespace", "test-user")
        
        # List bucket contents
        result = client.bucket_operation(
            bucket_name=test_bucket_name,
            operation="list",
            recursive=True
        )
        
        assert result["success"] == True
        print(f"   ✅ Bucket listing successful")
        print(f"   📦 Objects: {len(result['data']['objects'])}")

    def test_elegant_bucket_functions(self, client, test_bucket_name):
        """Test elegant bucket helper functions"""
        print(f"🧪 Testing elegant bucket functions: {test_bucket_name}")
        
        # Test mount_bucket helper
        mount_config = client.mount_bucket(
            bucket_name=test_bucket_name,
            mount_path="/data",
            prefix="workspace/",
            read_only=False
        )
        
        assert mount_config["bucket_name"] == test_bucket_name
        assert mount_config["mount_path"] == "/data"
        assert mount_config["prefix"] == "workspace/"
        assert mount_config["read_only"] == False
        print(f"   ✅ Mount config created: {mount_config}")
        
        # Test create_workspace_with_mounted_bucket
        workspace = client.create_workspace_with_mounted_bucket(
            template="python",
            namespace="test-namespace",
            user="test-user",
            bucket_name=test_bucket_name,
            mount_path="/data",
            prefix="workspace/"
        )
        
        assert workspace["id"] is not None
        assert len(workspace["bucket_mounts"]) == 1
        print(f"   ✅ Workspace with mounted bucket created: {workspace['id']}")
        
        # Test bucket mount functionality
        mount_test = client.test_bucket_mount(workspace["id"], "/data")
        print(f"   📄 Mount test result: {mount_test.get('stdout', '')}")
        
        # Test file operations
        file_ops = client.bucket_file_operations(workspace["id"], "/data")
        print(f"   📄 File operations result: {file_ops.get('stdout', '')}")
        
        # Cleanup
        client.delete(workspace["id"])

    def test_multiple_bucket_mounts(self, client):
        """Test workspace with multiple bucket mounts"""
        print("🧪 Testing multiple bucket mounts")
        
        # Create multiple buckets
        bucket1_name = f"test-bucket1-{int(time.time())}"
        bucket2_name = f"test-bucket2-{int(time.time())}"
        
        client.create_bucket(bucket1_name, "test-namespace", "test-user")
        client.create_bucket(bucket2_name, "test-namespace", "test-user")
        
        # Create workspace with multiple bucket mounts
        bucket_mounts = [
            {
                "bucket_name": bucket1_name,
                "mount_path": "/data1",
                "prefix": "workspace1/",
                "read_only": False
            },
            {
                "bucket_name": bucket2_name,
                "mount_path": "/data2",
                "prefix": "workspace2/",
                "read_only": True
            }
        ]
        
        workspace = client.create_workspace_with_buckets(
            template="python",
            namespace="test-namespace",
            user="test-user",
            bucket_mounts=bucket_mounts
        )
        
        assert workspace["id"] is not None
        assert len(workspace["bucket_mounts"]) == 2
        print(f"   ✅ Workspace with multiple bucket mounts created: {workspace['id']}")
        
        # Test both mounts
        test_code = """
import os
import json

mounts = ["/data1", "/data2"]
results = {}

for mount in mounts:
    results[mount] = {
        "exists": os.path.exists(mount),
        "contents": os.listdir(mount) if os.path.exists(mount) else []
    }

print(json.dumps(results))
"""
        
        result = client.run_python(workspace["id"], {"code": test_code, "timeout": 10.0})
        print(f"   📄 Multiple mounts test: {result.get('stdout', '')}")
        
        # Cleanup
        client.delete(workspace["id"])

    def test_bucket_prefix_isolation(self, client, test_bucket_name):
        """Test bucket prefix isolation"""
        print(f"🧪 Testing bucket prefix isolation: {test_bucket_name}")
        
        # Create bucket
        client.create_bucket(test_bucket_name, "test-namespace", "test-user")
        
        # Create workspace with prefix isolation
        workspace = client.create_workspace_with_mounted_bucket(
            template="python",
            namespace="test-namespace",
            user="test-user",
            bucket_name=test_bucket_name,
            mount_path="/bucket",
            prefix="user1/",
            read_only=False
        )
        
        # Test prefix isolation
        test_code = """
import os
import json

# Test that we can only see our prefix
bucket_path = "/bucket"
contents = os.listdir(bucket_path) if os.path.exists(bucket_path) else []

# Create file in our prefix
test_file = os.path.join(bucket_path, "user1", "test.txt")
os.makedirs(os.path.dirname(test_file), exist_ok=True)
with open(test_file, 'w') as f:
    f.write("User1 data")

result = {
    "bucket_contents": contents,
    "user1_file_created": os.path.exists(test_file),
    "user1_file_content": open(test_file, 'r').read() if os.path.exists(test_file) else None
}

print(json.dumps(result))
"""
        
        result = client.run_python(workspace["id"], {"code": test_code, "timeout": 10.0})
        print(f"   📄 Prefix isolation test: {result.get('stdout', '')}")
        
        # Cleanup
        client.delete(workspace["id"])

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
