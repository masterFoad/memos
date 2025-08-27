import pytest
import sys
import os
import tempfile
import yaml
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from server.config import Settings, ServerCfg, RuntimeCfg, StorageCfg

class TestConfig:
    def test_default_settings(self):
        """Test default configuration values"""
        settings = Settings(
            server=ServerCfg(),
            runtime=RuntimeCfg(),
            storage=StorageCfg(),
            workspaces={"default_ttl_minutes": 180, "enforce_net_profile": False},
            pools=[]
        )
        
        assert settings.server.bind == "127.0.0.1"
        assert settings.server.port == 8080
        assert settings.runtime.engine == "docker"
        assert settings.storage.persist_root == "/opt/onmemos/persist"
        assert settings.storage.cas_root == "/opt/onmemos/cas"

    def test_custom_settings(self):
        """Test custom configuration values"""
        settings = Settings(
            server=ServerCfg(
                bind="0.0.0.0",
                port=9000,
                base_url="https://custom.example.com",
                jwt_secret="custom-secret"
            ),
            runtime=RuntimeCfg(
                engine="docker",
                default_network="host"
            ),
            storage=StorageCfg(
                persist_root="/custom/persist",
                cas_root="/custom/cas"
            ),
            workspaces={"default_ttl_minutes": 240, "enforce_net_profile": True},
            pools=[]
        )
        
        assert settings.server.bind == "0.0.0.0"
        assert settings.server.port == 9000
        assert settings.server.base_url == "https://custom.example.com"
        assert settings.server.jwt_secret == "custom-secret"
        assert settings.runtime.default_network == "host"
        assert settings.storage.persist_root == "/custom/persist"
        assert settings.storage.cas_root == "/custom/cas"

    def test_security_config(self):
        """Test security configuration"""
        from server.config import SecurityCfg
        
        sec = SecurityCfg(
            no_new_privileges=True,
            drop_caps=["ALL"],
            seccomp_profile="/path/to/profile.json"
        )
        
        assert sec.no_new_privileges is True
        assert sec.drop_caps == ["ALL"]
        assert sec.seccomp_profile == "/path/to/profile.json"
