from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import os, yaml, pathlib

class SecurityCfg(BaseModel):
    no_new_privileges: bool = True
    drop_caps: List[str] = ["ALL"]
    seccomp_profile: Optional[str] = None

class RuntimeCfg(BaseModel):
    engine: str = "docker"
    default_network: str = "bridge"
    security: SecurityCfg = SecurityCfg()

class StorageCfg(BaseModel):
    persist_root: str = "/opt/onmemos/persist"
    cas_root: str = "/opt/onmemos/cas"

class BucketCfg(BaseModel):
    """Bucket storage configuration"""
    enabled: bool = True
    provider: str = "gcs"  # "gcs", "s3", "azure"
    default_region: str = "us-central1"
    default_storage_class: str = "STANDARD"
    mount_base_path: str = "/bucket"
    # GCS specific settings
    gcs_project_id: Optional[str] = None
    gcs_key_file: Optional[str] = None
    # S3 specific settings
    s3_endpoint: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None

class WorkspaceCfg(BaseModel):
    default_ttl_minutes: int = 180
    enforce_net_profile: bool = False
    # New bucket-related settings
    default_bucket_prefix: str = "workspace"
    enable_bucket_mounts: bool = True
    max_bucket_mounts_per_workspace: int = 5

class PoolCfg(BaseModel):
    template: str
    warm_size: int = 2
    max_size: int = 8

class LimitsUser(BaseModel):
    max_live_workspaces: int = 4
    cpu_quota: float = 4.0
    mem_limit: str = "8g"
    persist_quota_gb: int = 20
    # New bucket limits
    max_buckets_per_user: int = 10
    bucket_quota_gb: int = 100

class LimitsCfg(BaseModel):
    per_user: LimitsUser = LimitsUser()

class ServerCfg(BaseModel):
    bind: str = "127.0.0.1"
    port: int = 8080
    base_url: str = "https://dev.example.tld"
    jwt_secret: str = "change-me"

class Settings(BaseModel):
    server: ServerCfg
    runtime: RuntimeCfg
    storage: StorageCfg
    workspaces: WorkspaceCfg
    buckets: BucketCfg = BucketCfg()  # New bucket configuration
    pools: List[PoolCfg]
    limits: LimitsCfg = LimitsCfg()

def load_settings() -> Settings:
    # Get config path from environment or use default
    config_path = os.environ.get("ONMEMOS_CONFIG", "ops/config.yaml")
    
    # If it's a relative path, make it relative to the project root
    if not os.path.isabs(config_path):
        # Get the project root (parent of server directory)
        current_dir = pathlib.Path(__file__).parent
        project_root = current_dir.parent.parent
        config_path = project_root / config_path
    
    data = yaml.safe_load(pathlib.Path(config_path).read_text())
    return Settings(**data)
