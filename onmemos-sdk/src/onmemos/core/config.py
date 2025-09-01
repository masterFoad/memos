"""
Configuration management for OnMemOS SDK
Includes auto API key detection from .env files
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, validator

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


@dataclass(frozen=True)
class RetryConfig:
    """Retry configuration for HTTP requests"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


class ClientConfig(BaseModel):
    """Client configuration"""
    base_url: str = Field("https://api.onmemos.com", description="API base URL")
    timeout: float = Field(30.0, description="Request timeout in seconds")
    retry_config: RetryConfig = Field(default_factory=RetryConfig, description="Retry configuration")
    user_agent: str = Field("onmemos-sdk/0.1.0", description="User agent string")
    max_connections: int = Field(100, description="Maximum HTTP connections")
    connection_timeout: float = Field(10.0, description="Connection timeout")
    
    class Config:
        use_enum_values = True
        validate_assignment = True


class ConfigManager:
    """Configuration file manager with auto API key detection"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path or "~/.onmemos/config.yaml").expanduser()
        self._load_env_vars()
    
    def _load_env_vars(self) -> None:
        """Load environment variables from .env files"""
        # Try to load from current directory
        current_dir = Path.cwd()
        env_files = [
            current_dir / ".env",
            current_dir / ".env.local",
            current_dir / ".env.development",
            current_dir / ".env.production",
            Path.home() / ".onmemos" / ".env",
        ]
        
        for env_file in env_files:
            if env_file.exists() and load_dotenv:
                load_dotenv(env_file)
                break
    
    def get_api_key(self) -> Optional[str]:
        """Get API key with auto-detection priority"""
        # Priority order for API key detection
        sources = [
            ("ONMEMOS_API_KEY", "Environment variable"),
            ("ONMEMOS_PASSPORT", "Environment variable (legacy)"),
            ("API_KEY", "Environment variable (generic)"),
        ]
        
        for env_var, source in sources:
            api_key = os.getenv(env_var)
            if api_key:
                return api_key
        
        return None
    
    def get_base_url(self) -> str:
        """Get base URL with environment override"""
        return os.getenv("ONMEMOS_BASE_URL", "https://api.onmemos.com")
    
    def get_timeout(self) -> float:
        """Get timeout with environment override"""
        try:
            return float(os.getenv("ONMEMOS_TIMEOUT", "30.0"))
        except ValueError:
            return 30.0
    
    def get_profile_config(self, profile_name: str = "default") -> ClientConfig:
        """Get configuration for specific profile"""
        # For now, return default config with env overrides
        # TODO: Implement YAML config file loading
        return ClientConfig(
            base_url=self.get_base_url(),
            timeout=self.get_timeout(),
            retry_config=RetryConfig(),
            user_agent="onmemos-sdk/0.1.0",
            max_connections=100,
            connection_timeout=10.0
        )
    
    def save_config(self, config: ClientConfig, profile_name: str = "default") -> None:
        """Save configuration to file"""
        # TODO: Implement YAML config file saving
        pass
    
    def list_profiles(self) -> list[str]:
        """List available configuration profiles"""
        # TODO: Implement profile listing from config file
        return ["default"]
    
    def create_profile(self, profile_name: str, config: ClientConfig) -> None:
        """Create new configuration profile"""
        # TODO: Implement profile creation
        pass
    
    def delete_profile(self, profile_name: str) -> None:
        """Delete configuration profile"""
        # TODO: Implement profile deletion
        pass


# Global configuration manager instance
config_manager = ConfigManager()


def get_default_config() -> ClientConfig:
    """Get default configuration with environment overrides"""
    return config_manager.get_profile_config("default")


def get_api_key() -> Optional[str]:
    """Get API key with auto-detection"""
    return config_manager.get_api_key()


def get_base_url() -> str:
    """Get base URL with environment override"""
    return config_manager.get_base_url()


def get_timeout() -> float:
    """Get timeout with environment override"""
    return config_manager.get_timeout()
