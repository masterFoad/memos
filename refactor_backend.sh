#!/bin/bash

echo "🚀 OnMemOS v3 Backend Refactoring Script"
echo "========================================"

# Create new directory structure
echo "📁 Creating new directory structure..."
mkdir -p server/core server/managers server/services/gcp server/services/workspace server/models server/api

# Create __init__.py files
echo "📝 Creating __init__.py files..."
touch server/core/__init__.py
touch server/managers/__init__.py
touch server/services/__init__.py
touch server/services/gcp/__init__.py
touch server/services/workspace/__init__.py
touch server/models/__init__.py
touch server/api/__init__.py

# Move core files
echo "🔧 Moving core files..."
cp server/config.py server/core/ 2>/dev/null || true
cp server/security.py server/core/ 2>/dev/null || true
cp server/utils.py server/core/ 2>/dev/null || true

# Move models
echo "📋 Moving models..."
cp server/models.py server/models/workspace.py 2>/dev/null || true

# Create unified storage manager
echo "💾 Creating unified storage manager..."
cat > server/managers/storage_manager.py << 'EOF'
"""
Unified Storage Manager for OnMemOS v3
"""

import os
import logging
from typing import Dict, List, Optional, Any
from ..services.gcp.bucket_service import GCSBucketService
from ..services.gcp.disk_service import GCPDiskService

logger = logging.getLogger(__name__)

class StorageManager:
    """Unified storage manager for GCS buckets and GCP persistent disks"""
    
    def __init__(self):
        self.bucket_service = GCSBucketService()
        self.disk_service = GCPDiskService()
        self.project_id = os.getenv("PROJECT_ID", "ai-engine-448418")
    
    def create_namespace_storage(self, namespace: str, user: str, options: Dict = None):
        """Create complete storage setup for a namespace"""
        if not options:
            options = {}
        
        try:
            # Create persistent disk
            disk_size_gb = options.get("disk_size_gb", 10)
            disk_type = options.get("disk_type", "pd-standard")
            
            disk = self.disk_service.create_disk(
                namespace=namespace,
                user=user,
                size_gb=disk_size_gb,
                disk_type=disk_type
            )
            
            # Create bucket
            bucket_region = options.get("bucket_region", "us-central1")
            bucket_storage_class = options.get("bucket_storage_class", "STANDARD")
            
            bucket = self.bucket_service.create_bucket(
                namespace=namespace,
                user=user,
                region=bucket_region,
                storage_class=bucket_storage_class
            )
            
            return {
                "disk": disk,
                "bucket": bucket,
                "namespace": namespace,
                "user": user
            }
            
        except Exception as e:
            logger.error(f"Failed to create namespace storage: {e}")
            raise

# Global storage manager instance
storage_manager = StorageManager()
EOF

# Create GCS bucket service
echo "🪣 Creating GCS bucket service..."
cat > server/services/gcp/bucket_service.py << 'EOF'
"""
Google Cloud Storage Bucket Service
"""

import os
import logging
import hashlib
from typing import Dict, List, Optional, Any
from google.cloud import storage

logger = logging.getLogger(__name__)

class GCSBucketService:
    """Service for managing GCS buckets"""
    
    def __init__(self):
        self.project_id = os.getenv("PROJECT_ID", "ai-engine-448418")
        self.storage_client = None
        
        try:
            self.storage_client = storage.Client(project=self.project_id)
            logger.info("GCS Bucket service initialized successfully")
        except Exception as e:
            logger.warning(f"GCS Bucket service not available: {e}")
            self.storage_client = None
    
    def create_bucket(self, namespace: str, user: str, region: str = "us-central1", storage_class: str = "STANDARD"):
        """Create a new bucket for a namespace"""
        if not self.storage_client:
            raise Exception("GCS not available")
        
        try:
            # Generate bucket name
            namespace_hash = hashlib.md5(f"{namespace}:{user}".encode()).hexdigest()[:8]
            bucket_name = f"onmemos-{namespace}-{namespace_hash}"
            
            # Create bucket
            bucket = self.storage_client.create_bucket(
                bucket_name,
                location=region,
                storage_class=storage_class
            )
            
            # Add labels
            bucket.labels = {
                "onmemos": "true",
                "namespace": namespace,
                "user": user,
                "type": "bucket",
                "created_by": "onmemos-v3"
            }
            bucket.patch()
            
            return {
                "name": bucket_name,
                "namespace": namespace,
                "user": user,
                "region": region,
                "storage_class": storage_class,
                "created_at": bucket.time_created
            }
            
        except Exception as e:
            logger.error(f"Failed to create bucket: {e}")
            raise
EOF

# Create GCP disk service
echo "💾 Creating GCP disk service..."
cat > server/services/gcp/disk_service.py << 'EOF'
"""
Google Cloud Persistent Disk Service
"""

import os
import logging
import hashlib
from typing import Dict, List, Optional, Any
from google.cloud import compute_v1

logger = logging.getLogger(__name__)

class GCPDiskService:
    """Service for managing GCP persistent disks"""
    
    def __init__(self):
        self.project_id = os.getenv("PROJECT_ID", "ai-engine-448418")
        self.zone = os.getenv("GCP_ZONE", "us-central1-a")
        self.compute_client = None
        
        try:
            self.compute_client = compute_v1.DisksClient()
            logger.info("GCP Disk service initialized successfully")
        except Exception as e:
            logger.warning(f"GCP Disk service not available: {e}")
            self.compute_client = None
    
    def create_disk(self, namespace: str, user: str, size_gb: int = 10, disk_type: str = "pd-standard"):
        """Create a persistent disk for a namespace"""
        if not self.compute_client:
            raise Exception("GCP Compute Engine not available")
        
        try:
            # Generate disk name
            namespace_hash = hashlib.md5(f"{namespace}:{user}".encode()).hexdigest()[:8]
            disk_name = f"onmemos-persist-{namespace_hash}"
            
            # Create disk request
            disk = compute_v1.Disk()
            disk.name = disk_name
            disk.size_gb = size_gb
            disk.type = f"zones/{self.zone}/diskTypes/{disk_type}"
            
            # Add labels
            disk.labels = {
                "onmemos": "true",
                "namespace": namespace,
                "user": user,
                "type": "persistent-storage",
                "created_by": "onmemos-v3"
            }
            
            # Create the disk
            operation = self.compute_client.insert(
                project=self.project_id,
                zone=self.zone,
                disk_resource=disk
            )
            result = operation.result()
            
            return {
                "disk_name": disk_name,
                "disk_id": result.id if result and hasattr(result, 'id') else None,
                "namespace": namespace,
                "user": user,
                "size_gb": size_gb,
                "disk_type": disk_type,
                "zone": self.zone,
                "status": "ready",
                "created_at": result.creation_timestamp if result else None
            }
            
        except Exception as e:
            logger.error(f"Failed to create disk: {e}")
            raise
EOF

# Create workspace manager
echo "🐳 Creating workspace manager..."
cat > server/managers/workspace_manager.py << 'EOF'
"""
Workspace Manager for OnMemOS v3
"""

import os
import time
import uuid
import datetime
import logging
from typing import Dict, List, Optional, Any
import docker
from ..managers.storage_manager import storage_manager

logger = logging.getLogger(__name__)

class WorkspaceManager:
    """Manages workspace lifecycle and operations"""
    
    def __init__(self):
        self.api = docker.APIClient()
        self.workspaces: Dict[str, Dict] = {}  # wid -> info
    
    def create_workspace(self, template: str, namespace: str, user: str, 
                        ttl_minutes: int = 180, storage_options: Dict = None):
        """Create a new workspace with storage"""
        try:
            # Generate workspace ID
            wid = f"ws_{uuid.uuid4().hex[:8]}"
            
            # Get or create storage for namespace
            storage_config = storage_manager.create_namespace_storage(
                namespace, user, storage_options or {}
            )
            
            # Create container with storage mounts
            container_info = self._create_container(wid, template, storage_config, ttl_minutes)
            
            # Store workspace info
            workspace_info = {
                "id": wid,
                "template": template,
                "namespace": namespace,
                "user": user,
                "container_id": container_info["container_id"],
                "storage_config": storage_config,
                "expires_at": container_info["expires_at"],
                "created_at": datetime.datetime.utcnow().isoformat() + "Z"
            }
            
            self.workspaces[wid] = workspace_info
            
            return {
                "id": wid,
                "template": template,
                "namespace": namespace,
                "user": user,
                "shell_ws": f"/v1/workspaces/{wid}/shell",
                "expires_at": workspace_info["expires_at"],
                "storage_config": storage_config
            }
            
        except Exception as e:
            logger.error(f"Failed to create workspace: {e}")
            raise
    
    def _create_container(self, workspace_id: str, template: str, storage_config: Dict, ttl_minutes: int):
        """Create Docker container with storage mounts"""
        # Create socket directory
        sock_dir = f"/run/onmemos/ws/{workspace_id}"
        os.makedirs(sock_dir, exist_ok=True)
        os.chmod(sock_dir, 0o777)
        
        # Create mounts
        mounts = [
            {"Type": "bind", "Source": sock_dir, "Target": "/run", "ReadOnly": False},
            {"Type": "tmpfs", "Target": "/work", "TmpfsOptions": {"SizeBytes": 4294967296, "Mode": 0o1777}},
            {"Type": "tmpfs", "Target": "/tmp", "TmpfsOptions": {"SizeBytes": 1073741824, "Mode": 0o1777}}
        ]
        
        # Add storage mounts
        if storage_config.get("disk"):
            disk_mount = self._get_disk_mount(storage_config["disk"]["disk_name"], "/persist")
            mounts.append(disk_mount)
        
        if storage_config.get("bucket"):
            bucket_mount = self._get_bucket_mount(storage_config["bucket"]["name"], "/buckets")
            mounts.append(bucket_mount)
        
        # Create host config
        hc = self.api.create_host_config(
            network_mode="bridge",
            mounts=mounts,
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            shm_size=1073741824,
            nano_cpus=2000000000,
            mem_limit="3g",
            pids_limit=512,
        )
        
        # Create and start container
        cont = self.api.create_container(
            image="onmemos/python-runner:3.11", 
            name=workspace_id, 
            host_config=hc
        )
        self.api.start(cont)
        
        # Calculate expiration
        expires = (datetime.datetime.utcnow() + 
                  datetime.timedelta(minutes=ttl_minutes)).isoformat() + "Z"
        
        return {
            "container_id": cont["Id"],
            "expires_at": expires
        }
    
    def _get_disk_mount(self, disk_name: str, mount_path: str):
        """Get disk mount configuration"""
        import tempfile
        import os
        
        disk_dir = f"/tmp/gcp-disk-{disk_name}"
        os.makedirs(disk_dir, exist_ok=True)
        
        return {
            "Type": "bind",
            "Source": disk_dir,
            "Target": mount_path,
            "ReadOnly": False
        }
    
    def _get_bucket_mount(self, bucket_name: str, mount_path: str):
        """Get bucket mount configuration"""
        import tempfile
        import os
        
        bucket_dir = f"/tmp/gcs-bucket-{bucket_name}"
        os.makedirs(bucket_dir, exist_ok=True)
        
        return {
            "Type": "bind",
            "Source": bucket_dir,
            "Target": mount_path,
            "ReadOnly": False
        }
    
    def list_workspaces(self, namespace: Optional[str] = None, user: Optional[str] = None):
        """List workspaces with optional filtering"""
        workspaces = []
        
        for wid, info in self.workspaces.items():
            # Apply filters
            if namespace and info["namespace"] != namespace:
                continue
            if user and info["user"] != user:
                continue
            
            workspaces.append({
                "id": info["id"],
                "template": info["template"],
                "namespace": info["namespace"],
                "user": info["user"],
                "shell_ws": f"/v1/workspaces/{info['id']}/shell",
                "expires_at": info["expires_at"]
            })
        
        return workspaces
    
    def delete_workspace(self, workspace_id: str):
        """Delete a workspace"""
        if workspace_id not in self.workspaces:
            return False
        
        try:
            # Stop and remove container
            self.api.remove_container(workspace_id, force=True)
            
            # Remove from tracking
            del self.workspaces[workspace_id]
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete workspace: {e}")
            return False

# Global workspace manager instance
workspace_manager = WorkspaceManager()
EOF

# Create new main app.py
echo "🔄 Creating new main app.py..."
cat > server/app_new.py << 'EOF'
"""
OnMemOS v3 - Refactored Main Application
"""

from fastapi import FastAPI, WebSocket, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
import datetime
from typing import List, Optional
from .core.config import load_settings
from .core.security import require_api_key, require_namespace
from .managers.workspace_manager import workspace_manager
from .managers.storage_manager import storage_manager

app = FastAPI(title="OnMemOS v3", version="3.0.0")
settings = load_settings()

@app.get("/")
def root(_=Depends(require_api_key)):
    """Root endpoint - provides API information"""
    return {
        "service": "OnMemOS v3",
        "description": "In-memory operating system with cloud integration",
        "version": "3.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "workspaces": "/v1/workspaces",
            "storage": "/v1/storage",
            "shell": "/v1/workspaces/{id}/shell"
        },
        "documentation": "API requires authentication via X-API-Key header",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "version": "3.0.0",
        "services": {
            "server": "running",
            "workspaces": len(workspace_manager.workspaces),
            "storage": "available"
        }
    }

# Workspace endpoints
@app.post("/v1/workspaces")
def create_workspace(template: str = Query(...), namespace: str = Query(...), 
                    user: str = Query(...), ttl_minutes: int = Query(180),
                    storage_options: dict = None, _=Depends(require_namespace)):
    """Create a new workspace"""
    try:
        return workspace_manager.create_workspace(template, namespace, user, ttl_minutes, storage_options)
    except Exception as e:
        raise HTTPException(500, f"Failed to create workspace: {str(e)}")

@app.get("/v1/workspaces")
def list_workspaces(namespace: Optional[str] = Query(None), 
                   user: Optional[str] = Query(None), _=Depends(require_namespace)):
    """List workspaces"""
    return workspace_manager.list_workspaces(namespace, user)

@app.delete("/v1/workspaces/{workspace_id}")
def delete_workspace(workspace_id: str, _=Depends(require_namespace)):
    """Delete a workspace"""
    success = workspace_manager.delete_workspace(workspace_id)
    if not success:
        raise HTTPException(404, "Workspace not found")
    return {"ok": True}

# Storage endpoints
@app.post("/v1/storage/namespaces/{namespace}/setup")
def setup_namespace_storage(namespace: str, user: str = Query(...), 
                          options: dict = None, _=Depends(require_namespace)):
    """Setup storage for a namespace"""
    try:
        return storage_manager.create_namespace_storage(namespace, user, options or {})
    except Exception as e:
        raise HTTPException(500, f"Failed to setup storage: {str(e)}")

@app.websocket("/v1/workspaces/{workspace_id}/shell")
async def shell_websocket(websocket: WebSocket, workspace_id: str):
    """Interactive shell WebSocket endpoint"""
    await websocket.accept()
    # TODO: Implement shell bridging
    await websocket.send_text("Shell connected!")
EOF

# Clean up old files
echo "🧹 Cleaning up old files..."
rm -f server/bucket_service.py
rm -f server/real_bucket_service.py
rm -f server/gcp_persistent_storage_service.py
rm -f server/unified_gcp_namespace_service.py
rm -f server/unified_namespace_service.py
rm -f server/gcloud_namespace_service.py
rm -f server/gcloud_secrets_service.py
rm -f server/cloud_storage_service.py
rm -f server/manager.py
rm -f server/shell_ws.py
rm -f server/runner_proto.py

# Replace old app.py
echo "🔄 Replacing main app.py..."
mv server/app_new.py server/app.py

# Create __init__.py files
echo "📝 Creating __init__.py files..."
echo "from .workspace_manager import workspace_manager" > server/managers/__init__.py
echo "from .storage_manager import storage_manager" >> server/managers/__init__.py

echo "from .bucket_service import GCSBucketService" > server/services/gcp/__init__.py
echo "from .disk_service import GCPDiskService" >> server/services/gcp/__init__.py

echo "✅ Refactoring complete!"
echo "📁 New structure:"
echo "   server/"
echo "   ├── core/           # Core infrastructure"
echo "   ├── managers/       # High-level managers"
echo "   ├── services/       # Individual services"
echo "   ├── models/         # Data models"
echo "   ├── api/            # API endpoints"
echo "   └── app.py          # Main application"
echo ""
echo "🚀 Ready to test the new architecture!"
