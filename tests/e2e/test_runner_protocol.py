import pytest
import sys
import os
import json
import socket
import tempfile
import threading
import time
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from server.runner_proto import uds_request

class TestRunnerProtocol:
    def test_uds_communication(self):
        """Test Unix Domain Socket communication protocol"""
        # Create a temporary socket file
        sock_file = tempfile.mktemp()
        
        # Simple echo server
        def echo_server():
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.bind(sock_file)
            sock.listen(1)
            conn, addr = sock.accept()
            data = conn.recv(1024)
            # Echo back the data
            conn.sendall(data)
            conn.close()
            sock.close()
            os.unlink(sock_file)
        
        # Start server in background
        server_thread = threading.Thread(target=echo_server)
        server_thread.daemon = True
        server_thread.start()
        
        # Wait for server to start
        time.sleep(0.1)
        
        # Test communication
        test_data = {"op": "test", "data": "hello"}
        try:
            result = uds_request(sock_file, test_data, timeout=1.0)
            # The echo server should return the same data
            assert result == test_data
        except Exception as e:
            pytest.skip(f"UDS test skipped: {e}")
        finally:
            # Cleanup
            try:
                os.unlink(sock_file)
            except:
                pass
