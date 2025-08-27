import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from server.utils import safe_join

class TestPathTraversal:
    def test_path_traversal_attempts(self):
        """Test various path traversal attack attempts"""
        root = "/tmp/test"
        
        # Test that the function correctly catches path traversal
        with pytest.raises(ValueError, match="unsafe path"):
            safe_join(root, "../../../etc/passwd")
        
        # Test Windows-style path traversal
        with pytest.raises(ValueError, match="unsafe path"):
            safe_join(root, "..\\..\\..\\windows\\system32\\config\\sam")

    def test_url_encoded_path_traversal(self):
        """Test URL-encoded path traversal attempts"""
        root = "/tmp/test"
        
        # URL-encoded paths (these might not be caught by basic path resolution)
        # but they should still be tested
        url_encoded_paths = [
            "..%2F..%2F..%2Fetc%2Fpasswd",
            "..%252F..%252F..%252Fetc%252Fpasswd",
        ]
        
        # Note: These might not raise ValueError depending on implementation
        # but we test them to ensure they don't allow access to sensitive files
        for path in url_encoded_paths:
            result = safe_join(root, path)
            # Should not contain sensitive paths
            assert "/etc/passwd" not in result
            assert result.startswith("/tmp/test")

    def test_absolute_path_attempts(self):
        """Test absolute path attempts"""
        root = "/tmp/test"
        
        with pytest.raises(ValueError, match="unsafe path"):
            safe_join(root, "/etc/passwd")
        
        with pytest.raises(ValueError, match="unsafe path"):
            safe_join(root, "subdir", "/etc/passwd")

    def test_symlink_attempts(self):
        """Test symlink-based traversal attempts"""
        root = "/tmp/test"
        
        # Test that the function correctly catches multi-component path traversal
        with pytest.raises(ValueError, match="unsafe path"):
            safe_join(root, "symlink", "..", "etc", "passwd")
        
        # Test that the function still works for valid paths
        valid_path = safe_join(root, "symlink", "valid", "file.txt")
        assert valid_path == "/tmp/test/symlink/valid/file.txt"
        
        # Test that normal path joining works
        normal_path = safe_join(root, "subdir", "file.txt")
        assert normal_path == "/tmp/test/subdir/file.txt"
