"""
OnMemOS v3 - Centralized Logging Configuration
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Log levels
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        # Add color to levelname
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
        
        return super().format(record)

class StructuredFormatter(logging.Formatter):
    """Structured formatter for JSON-like log output"""
    
    def format(self, record):
        # Create structured log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        return str(log_entry)

def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[str] = None,
    enable_file_logging: bool = True,
    enable_console_logging: bool = True,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """
    Setup comprehensive logging for OnMemOS v3
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (defaults to ./logs)
        enable_file_logging: Whether to log to files
        enable_console_logging: Whether to log to console
        max_file_size: Maximum size of log files before rotation
        backup_count: Number of backup log files to keep
    """
    
    # Create log directory if needed
    if log_dir is None:
        log_dir = Path.cwd() / "logs"
    else:
        log_dir = Path(log_dir)
    
    log_dir.mkdir(exist_ok=True)
    
    # Get log level
    level = LOG_LEVELS.get(log_level.upper(), logging.INFO)
    
    # Clear existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    
    # Console handler with colors
    if enable_console_logging:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        
        console_formatter = ColoredFormatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # File handlers
    if enable_file_logging:
        # Main application log
        app_log_file = log_dir / "onmemos.log"
        app_handler = logging.handlers.RotatingFileHandler(
            app_log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        app_handler.setLevel(level)
        
        app_formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        app_handler.setFormatter(app_formatter)
        root_logger.addHandler(app_handler)
        
        # Error log (only errors and critical)
        error_log_file = log_dir / "onmemos-error.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(app_formatter)
        root_logger.addHandler(error_handler)
        
        # WebSocket specific log
        websocket_log_file = log_dir / "websocket.log"
        websocket_handler = logging.handlers.RotatingFileHandler(
            websocket_log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        websocket_handler.setLevel(level)
        websocket_handler.setFormatter(app_formatter)
        
        # Create websocket logger
        websocket_logger = logging.getLogger("websocket")
        websocket_logger.addHandler(websocket_handler)
        websocket_logger.setLevel(level)
        
        # GKE specific log
        gke_log_file = log_dir / "gke.log"
        gke_handler = logging.handlers.RotatingFileHandler(
            gke_log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        gke_handler.setLevel(level)
        gke_handler.setFormatter(app_formatter)
        
        # Create GKE logger
        gke_logger = logging.getLogger("gke")
        gke_logger.addHandler(gke_handler)
        gke_logger.setLevel(level)
        
        # Cloud Run specific log
        cloudrun_log_file = log_dir / "cloudrun.log"
        cloudrun_handler = logging.handlers.RotatingFileHandler(
            cloudrun_log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        cloudrun_handler.setLevel(level)
        cloudrun_handler.setFormatter(app_formatter)
        
        # Create Cloud Run logger
        cloudrun_logger = logging.getLogger("cloudrun")
        cloudrun_logger.addHandler(cloudrun_handler)
        cloudrun_logger.setLevel(level)
        
        # Storage specific log
        storage_log_file = log_dir / "storage.log"
        storage_handler = logging.handlers.RotatingFileHandler(
            storage_log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        storage_handler.setLevel(level)
        storage_handler.setFormatter(app_formatter)
        
        # Create storage logger
        storage_logger = logging.getLogger("storage")
        storage_logger.addHandler(storage_handler)
        storage_logger.setLevel(level)
    
    # Set specific loggers to avoid duplicate messages
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info("🚀 OnMemOS v3 logging system initialized")
    logger.info(f"📁 Log directory: {log_dir}")
    logger.info(f"📊 Log level: {log_level}")
    logger.info(f"📝 File logging: {'enabled' if enable_file_logging else 'disabled'}")
    logger.info(f"🖥️ Console logging: {'enabled' if enable_console_logging else 'disabled'}")

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name"""
    return logging.getLogger(name)

def log_execution_time(logger: logging.Logger):
    """Decorator to log function execution time"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.info(f"✅ {func.__name__} completed in {execution_time:.2f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"❌ {func.__name__} failed after {execution_time:.2f}s: {str(e)}")
                raise
        return wrapper
    return decorator

def log_async_execution_time(logger: logging.Logger):
    """Decorator to log async function execution time"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.info(f"✅ {func.__name__} completed in {execution_time:.2f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"❌ {func.__name__} failed after {execution_time:.2f}s: {str(e)}")
                raise
        return wrapper
    return decorator

# Convenience functions for common loggers
def get_gke_logger() -> logging.Logger:
    """Get GKE-specific logger"""
    return logging.getLogger("gke")

def get_cloudrun_logger() -> logging.Logger:
    """Get Cloud Run-specific logger"""
    return logging.getLogger("cloudrun")

def get_storage_logger() -> logging.Logger:
    """Get storage-specific logger"""
    return logging.getLogger("storage")

def get_websocket_logger() -> logging.Logger:
    """Get WebSocket-specific logger"""
    return logging.getLogger("websocket")

def get_api_logger() -> logging.Logger:
    """Get API-specific logger"""
    return logging.getLogger("api")
