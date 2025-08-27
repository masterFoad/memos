import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from server.models import (
    CreateWorkspaceRequest, WorkspaceInfo, ExecPyRequest, 
    ExecShRequest, SnapshotMeta, ShareRequest
)

class TestModels:
    def test_create_workspace_request(self):
        """Test CreateWorkspaceRequest model"""
        req = CreateWorkspaceRequest(
            template="python",
            namespace="test-ns",
            user="test-user",
            ttl_minutes=120,
            env={"TEST": "value"}
        )
        assert req.template == "python"
        assert req.namespace == "test-ns"
        assert req.user == "test-user"
        assert req.ttl_minutes == 120
        assert req.env == {"TEST": "value"}

    def test_workspace_info(self):
        """Test WorkspaceInfo model"""
        info = WorkspaceInfo(
            id="ws_abc123",
            template="python",
            namespace="test-ns",
            user="test-user",
            shell_ws="/v1/workspaces/ws_abc123/shell",
            expires_at="2024-01-01T00:00:00Z"
        )
        assert info.id == "ws_abc123"
        assert info.template == "python"
        assert info.shell_ws == "/v1/workspaces/ws_abc123/shell"

    def test_exec_py_request(self):
        """Test ExecPyRequest model"""
        req = ExecPyRequest(
            code="print('hello')",
            env={"PYTHONPATH": "/tmp"},
            timeout=15.0
        )
        assert req.code == "print('hello')"
        assert req.env == {"PYTHONPATH": "/tmp"}
        assert req.timeout == 15.0

    def test_exec_sh_request(self):
        """Test ExecShRequest model"""
        req = ExecShRequest(
            cmd="ls -la",
            stdin="input data",
            env={"PATH": "/usr/bin"},
            timeout=10.0
        )
        assert req.cmd == "ls -la"
        assert req.stdin == "input data"
        assert req.env == {"PATH": "/usr/bin"}
        assert req.timeout == 10.0

    def test_snapshot_meta(self):
        """Test SnapshotMeta model"""
        meta = SnapshotMeta(
            id="sha256:abc123",
            template="python",
            created_at="2024-01-01T00:00:00Z",
            bytes=1024,
            files=5,
            base_image="onmemos/python-runner:3.11",
            comment="test snapshot"
        )
        assert meta.id == "sha256:abc123"
        assert meta.template == "python"
        assert meta.bytes == 1024
        assert meta.files == 5
        assert meta.comment == "test snapshot"
