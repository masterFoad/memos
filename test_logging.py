#!/usr/bin/env python3
"""
Test script for OnMemOS v3 logging system
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

from server.core.logging import setup_logging, get_logger, get_gke_logger, get_cloudrun_logger, get_storage_logger, get_websocket_logger, get_api_logger

def test_logging():
    """Test the logging system"""
    
    # Setup logging
    setup_logging(
        log_level="DEBUG",
        log_dir="./logs",
        enable_file_logging=True,
        enable_console_logging=True
    )
    
    # Get different loggers
    main_logger = get_logger("test")
    gke_logger = get_gke_logger()
    cloudrun_logger = get_cloudrun_logger()
    storage_logger = get_storage_logger()
    websocket_logger = get_websocket_logger()
    api_logger = get_api_logger()
    
    # Test different log levels
    main_logger.debug("🔍 Debug message from main logger")
    main_logger.info("ℹ️ Info message from main logger")
    main_logger.warning("⚠️ Warning message from main logger")
    main_logger.error("❌ Error message from main logger")
    
    # Test service-specific loggers
    gke_logger.info("🚀 GKE service log message")
    cloudrun_logger.info("☁️ Cloud Run service log message")
    storage_logger.info("💾 Storage service log message")
    websocket_logger.info("🔌 WebSocket service log message")
    api_logger.info("🌐 API service log message")
    
    # Test error logging
    try:
        raise ValueError("Test exception for logging")
    except Exception as e:
        main_logger.error(f"Caught exception: {e}", exc_info=True)
    
    print("✅ Logging test completed! Check the ./logs directory for log files.")

if __name__ == "__main__":
    test_logging()
