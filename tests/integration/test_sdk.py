import pytest
import sys
import os
import tempfile
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from sdk.python.models import CreateWorkspace, ExecCode
from sdk.python.client import OnMemClient

class TestSDK:
    def test_create_workspace_model(self):
        """Test CreateWorkspace dataclass"""
        ws = CreateWorkspace(
            template="python",
            namespace="test-ns",
            user="test-user",
            ttl_minutes=120,
            env={"TEST": "value"}
        )
        assert ws.template == "python"
        assert ws.namespace == "test-ns"
        assert ws.user == "test-user"
        assert ws.ttl_minutes == 120
        assert ws.env == {"TEST": "value"}

    def test_exec_code_model(self):
        """Test ExecCode dataclass"""
        code = ExecCode(
            code="print('hello world')",
            env={"PYTHONPATH": "/tmp"},
            timeout=30.0
        )
        assert code.code == "print('hello world')"
        assert code.env == {"PYTHONPATH": "/tmp"}
        assert code.timeout == 30.0

    def test_client_initialization(self):
        """Test OnMemClient initialization"""
        client = OnMemClient("https://api.example.com", "test-token")
        assert client.base == "https://api.example.com"
        assert client.s.headers["Authorization"] == "Bearer test-token"

    def test_client_url_normalization(self):
        """Test URL normalization in client"""
        client = OnMemClient("https://api.example.com/", "test-token")
        assert client.base == "https://api.example.com"
        
        client = OnMemClient("https://api.example.com", "test-token")
        assert client.base == "https://api.example.com"
