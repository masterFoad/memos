import pytest
import sys
import os
import time
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from server.utils import human_to_bytes, safe_join

class TestUtilsPerformance:
    def test_human_to_bytes_performance(self):
        """Test performance of human_to_bytes function"""
        start_time = time.time()
        
        # Run many conversions
        for _ in range(10000):
            human_to_bytes("1k")
            human_to_bytes("1m")
            human_to_bytes("1g")
            human_to_bytes("512")
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete in reasonable time (less than 1 second)
        assert duration < 1.0, f"Performance test failed: {duration:.3f}s for 40k operations"

    def test_safe_join_performance(self):
        """Test performance of safe_join function"""
        start_time = time.time()
        
        # Run many path joins
        for i in range(10000):
            safe_join("/tmp/test", f"file_{i}.txt")
            safe_join("/tmp/test", f"subdir_{i}", "file.txt")
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete in reasonable time (less than 1 second)
        assert duration < 1.0, f"Performance test failed: {duration:.3f}s for 20k operations"
