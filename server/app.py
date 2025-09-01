"""
OnMemOS v3 - Main Application with Cloud Run Integration
"""

from fastapi import FastAPI, WebSocket, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
import datetime
import os
import sys
import time
from typing import List, Optional, Dict, Any
from server.core.config import load_settings
from server.core.logging import setup_logging, get_logger, get_api_logger
from server.core.security import require_api_key, require_namespace
from server.managers.workspace_manager import workspace_manager
from server.managers.storage_manager import storage_manager
from server.services.shell_service import get_shell_service
from server.services.session_monitor import session_monitor

# Import Cloud Run services
from server.api.cloudrun import router as cloudrun_router
from server.api.sessions import router as sessions_router
from server.api.gke import router as gke_router
from server.api.gke_websocket import router as gke_websocket_router
from server.api.billing import router as billing_router
from server.api.templates import router as templates_router
from server.api.cost_estimation import router as cost_estimation_router
from server.websockets.cloudrun_shell import cloudrun_shell_websocket

# Setup logging
setup_logging(
    log_level="INFO",
    log_dir="./logs",
    enable_file_logging=True,
    enable_console_logging=True
)

logger = get_logger(__name__)

app = FastAPI(title="OnMemOS v3", version="3.0.0")
settings = load_settings()

def setup_application_default_credentials():
    """Set up application default credentials using service account key file"""
    try:
        import os
        
        # Check if environment variable is already set
        if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            key_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if os.path.exists(key_file):
                logger.info(f"✅ Using existing GOOGLE_APPLICATION_CREDENTIALS: {key_file}")
                return True
            else:
                logger.warning(f"Service account key file not found: {key_file}")
        
        # Fallback to local file
        key_file = "./service-account-key.json"
        if os.path.exists(key_file):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_file
            logger.info(f"✅ Set GOOGLE_APPLICATION_CREDENTIALS to: {key_file}")
            return True
        else:
            logger.warning(f"Service account key file not found: {key_file}")
            return False
        
    except Exception as e:
        logger.warning(f"Failed to set up application default credentials: {e}")
        return False

def test_gcp_authentication():
    """Test GCP authentication and services with comprehensive permission checks"""
    try:
        import subprocess
        from google.cloud import storage
        from google.cloud.exceptions import Forbidden
        
        # Test basic GCP access
        result = subprocess.run(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            return False, "No active GCP authentication found"
        
        account = result.stdout.strip()
        logger.info(f"🔐 Authenticated as: {account}")
        
        # Set up application default credentials
        if not setup_application_default_credentials():
            logger.warning("⚠️ Could not set up application default credentials")
        
        # Test GCS access with detailed permission checks
        try:
            # Use gcloud credentials directly
            from google.auth import default
            from google.auth.transport.requests import Request
            
            credentials, project = default()
            client = storage.Client(credentials=credentials, project=project)
            buckets = list(client.list_buckets(max_results=1))
            logger.info("✅ GCS bucket listing permission: OK")
        except Forbidden as e:
            return False, f"GCS bucket listing permission denied: {e}"
        except Exception as e:
            return False, f"GCS access failed: {e}"
        
        # Test GCS bucket creation permission
        test_bucket_name = f"onmemos-test-{int(time.time())}"
        try:
            bucket = client.bucket(test_bucket_name)
            bucket.create(location="us-central1")
            logger.info("✅ GCS bucket creation permission: OK")
            
            # Clean up test bucket
            bucket.delete()
            logger.info("✅ GCS bucket deletion permission: OK")
        except Forbidden as e:
            return False, f"GCS bucket creation/deletion permission denied: {e}"
        except Exception as e:
            return False, f"GCS bucket operations failed: {e}"
        
        # Test Compute Engine access
        result = subprocess.run(["gcloud", "compute", "instances", "list", "--limit=1"], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("⚠️ Cannot access Compute Engine - some features may not work")
        else:
            logger.info("✅ Compute Engine access: OK")
        
        # Test GKE Autopilot access
        try:
            # Test GKE clusters list
            result = subprocess.run(["gcloud", "container", "clusters", "list", "--format=value(name,location)"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                clusters = result.stdout.strip().split('\n') if result.stdout.strip() else []
                logger.info(f"✅ GKE clusters access: OK ({len(clusters)} clusters found)")
                
                # Test kubectl access if clusters exist
                if clusters:
                    result = subprocess.run(["kubectl", "get", "nodes", "--no-headers"], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        logger.info("✅ GKE kubectl access: OK")
                    else:
                        logger.warning("⚠️ GKE kubectl access failed - check cluster configuration")
                else:
                    logger.info("ℹ️ No GKE clusters found - this is normal for new projects")
            else:
                logger.warning("⚠️ Cannot access GKE clusters - check permissions")
                
        except Exception as e:
            logger.warning(f"⚠️ GKE access test failed: {e}")
        
        # Test GKE Autopilot specific permissions
        try:
            # Test if we can create GKE Autopilot clusters
            result = subprocess.run(["gcloud", "container", "clusters", "create-auto", "--help"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("✅ GKE Autopilot cluster creation permission: OK")
            else:
                logger.warning("⚠️ GKE Autopilot cluster creation permission: Check")
        except Exception as e:
            logger.warning(f"⚠️ GKE Autopilot permission test failed: {e}")
        
        logger.info("✅ All GCP permissions verified successfully")
        return True, "GCP authentication and permissions successful"
        
    except Exception as e:
        return False, f"GCP authentication failed: {e}"

@app.on_event("startup")
async def startup_event():
    """Startup event - Test GCP authentication and start session monitor"""
    logger.info("🚀 Starting OnMemOS v3...")
    
    # Test GCP authentication
    logger.info("🔐 Testing GCP authentication...")
    success, message = test_gcp_authentication()
    if success:
        logger.info(f"✅ {message}")
    else:
        logger.warning(f"⚠️ {message}")
        logger.warning("Some features may not work without proper GCP authentication")
    
    # Start session monitoring
    try:
        await session_monitor.start_monitoring()
        logger.info("✅ Session monitor started")
    except Exception as e:
        logger.error(f"❌ Failed to start session monitor: {e}")

@app.get("/")
def root(_=Depends(require_api_key)):
    """Root endpoint - provides API information"""
    return {
        "service": "OnMemOS v3",
        "description": "In-memory operating system with real GCP integration",
        "version": "3.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "workspaces": "/v1/workspaces (DEPRECATED - use /v1/cloudrun/workspaces)",
            "cloudrun_workspaces": "/v1/cloudrun/workspaces",
            "storage": "/v1/storage",
            "shell": "/v1/workspaces/{id}/shell (DEPRECATED - use /v1/cloudrun/workspaces/{id}/shell)",
            "cloudrun_shell": "/v1/cloudrun/workspaces/{id}/shell",
            "buckets": "/v1/buckets",
            "disks": "/v1/disks"
        },
        "documentation": "API requires authentication via X-API-Key header",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

@app.get("/health")
def health_check():
    """Health check endpoint with GCP status"""
    gcp_status, gcp_message = test_gcp_authentication()
    
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "version": "3.0.0",
        "services": {
            "server": "running",
            "workspaces": len(workspace_manager.workspaces),
            "storage": "available",
            "gcp": "connected" if gcp_status else "disconnected"
        },
        "gcp": {
            "status": "connected" if gcp_status else "disconnected",
            "message": gcp_message
        }
    }

# Workspace endpoints
@app.post("/v1/workspaces")
def create_workspace(template: str = Query(...), namespace: str = Query(...), 
                    user: str = Query(...), ttl_minutes: int = Query(180),
                    storage_options: dict = None, _=Depends(require_api_key)):
    """Create a new workspace with real GCP storage"""
    try:
        logger.info(f"Creating workspace: template={template}, namespace={namespace}, user={user}")
        return workspace_manager.create_workspace(template, namespace, user, ttl_minutes, storage_options)
    except Exception as e:
        logger.error(f"Failed to create workspace: {e}")
        raise HTTPException(500, f"Failed to create workspace: {str(e)}")

@app.get("/v1/workspaces")
def list_workspaces(namespace: Optional[str] = Query(None), 
                   user: Optional[str] = Query(None), _=Depends(require_api_key)):
    """List workspaces"""
    return workspace_manager.list_workspaces(namespace, user)

@app.delete("/v1/workspaces/{workspace_id}")
def delete_workspace(workspace_id: str, _=Depends(require_api_key)):
    """Delete a workspace"""
    success = workspace_manager.delete_workspace(workspace_id)
    if not success:
        raise HTTPException(404, "Workspace not found")
    return {"ok": True}

@app.get("/v1/workspaces/{workspace_id}")
def get_workspace(workspace_id: str, _=Depends(require_api_key)):
    """Get workspace information"""
    workspace = workspace_manager.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    return workspace

# Storage endpoints
@app.post("/v1/storage/namespaces/{namespace}/setup")
def setup_namespace_storage(namespace: str, user: str = Query(...), 
                          options: dict = None, _=Depends(require_api_key)):
    """Setup storage for a namespace"""
    try:
        return storage_manager.create_namespace_storage(namespace, user, options or {})
    except Exception as e:
        raise HTTPException(500, f"Failed to setup storage: {str(e)}")

@app.get("/v1/storage/namespaces/{namespace}")
def list_namespace_storage(namespace: str, _=Depends(require_api_key)):
    """List storage resources for a namespace"""
    try:
        return storage_manager.list_namespace_storage(namespace)
    except Exception as e:
        raise HTTPException(500, f"Failed to list storage: {str(e)}")

@app.delete("/v1/storage/namespaces/{namespace}")
def delete_namespace_storage(namespace: str, user: str = Query(...), _=Depends(require_api_key)):
    """Delete storage resources for a namespace"""
    try:
        success = storage_manager.delete_namespace_storage(namespace, user)
        return {"ok": success}
    except Exception as e:
        raise HTTPException(500, f"Failed to delete storage: {str(e)}")

# Bucket endpoints
@app.post("/v1/buckets")
def create_bucket(bucket_name: str = Query(...), namespace: str = Query(...), 
                 user: str = Query(...), _=Depends(require_api_key)):
    """Create a GCS bucket"""
    try:
        return storage_manager.bucket_service.create_bucket(bucket_name, namespace, user)
    except Exception as e:
        raise HTTPException(500, f"Failed to create bucket: {str(e)}")

@app.get("/v1/buckets")
def list_buckets(namespace: str = Query(...), _=Depends(require_api_key)):
    """List buckets in namespace"""
    try:
        return storage_manager.bucket_service.list_buckets_in_namespace(namespace)
    except Exception as e:
        raise HTTPException(500, f"Failed to list buckets: {str(e)}")

@app.delete("/v1/buckets/{bucket_name}")
def delete_bucket(bucket_name: str, _=Depends(require_api_key)):
    """Delete a bucket"""
    try:
        success = storage_manager.bucket_service.delete_bucket(bucket_name)
        return {"ok": success}
    except Exception as e:
        raise HTTPException(500, f"Failed to delete bucket: {str(e)}")

# Disk endpoints
@app.post("/v1/disks")
def create_persistent_disk(disk_name: str = Query(...), namespace: str = Query(...), 
                          user: str = Query(...), size_gb: int = Query(10), _=Depends(require_api_key)):
    """Create a GCP persistent disk"""
    try:
        return storage_manager.disk_service.create_disk(disk_name, namespace, user, size_gb)
    except Exception as e:
        raise HTTPException(500, f"Failed to create disk: {str(e)}")

@app.get("/v1/disks")
def list_persistent_disks(namespace: str = Query(...), _=Depends(require_api_key)):
    """List persistent disks in namespace"""
    try:
        return storage_manager.disk_service.list_disks_in_namespace(namespace)
    except Exception as e:
        raise HTTPException(500, f"Failed to list disks: {str(e)}")

@app.delete("/v1/disks/{disk_name}")
def delete_persistent_disk(disk_name: str, _=Depends(require_api_key)):
    """Delete a persistent disk"""
    try:
        success = storage_manager.disk_service.delete_disk(disk_name)
        return {"ok": success}
    except Exception as e:
        raise HTTPException(500, f"Failed to delete disk: {str(e)}")

# ============================================================================
# Persistent Storage Endpoints
# ============================================================================

from fastapi import UploadFile, File

@app.post("/v1/fs/persist/upload")
async def upload_persist(namespace: str = Query(...), user: str = Query(...), 
                        dst: str = Query(""), file: UploadFile = File(...), 
                        _=Depends(require_namespace)):
    """Upload a file to persistent storage"""
    try:
        # Create storage directory
        root = f"{settings.storage.persist_root}/{namespace}/{user}"
        os.makedirs(root, exist_ok=True)
        
        # Determine filename
        if dst:
            filename = dst
        else:
            filename = file.filename
        
        out_path = os.path.join(root, filename)
        
        # Check if path already exists and is a directory
        if os.path.exists(out_path) and os.path.isdir(out_path):
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "Path conflict",
                    "message": f"Path '{out_path}' already exists as a directory",
                    "suggestion": "Use a different filename or remove the existing directory",
                    "path": out_path
                }
            )
        
        # Read and write file
        data = await file.read()
        with open(out_path, "wb") as f:
            f.write(data)
        
        return {"ok": True, "bytes": len(data), "path": out_path}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Upload failed",
                "message": f"Failed to upload file to persistent storage: {str(e)}",
                "suggestion": "Check file permissions and available disk space",
                "namespace": namespace,
                "user": user,
                "filename": dst or (file.filename if file else "unknown")
            }
        )

@app.get("/v1/fs/persist/download")
def download_persist(namespace: str = Query(...), user: str = Query(...), 
                    path: str = Query(...), _=Depends(require_namespace)):
    """Download a file from persistent storage"""
    try:
        from fastapi.responses import FileResponse
        
        file_path = os.path.join(settings.storage.persist_root, namespace, user, path)
        
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "File not found",
                    "message": f"File '{path}' not found in persistent storage",
                    "namespace": namespace,
                    "user": user,
                    "path": path
                }
            )
        
        if os.path.isdir(file_path):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Path is directory",
                    "message": f"Path '{path}' is a directory, not a file",
                    "namespace": namespace,
                    "user": user,
                    "path": path
                }
            )
        
        return FileResponse(file_path, filename=os.path.basename(path))
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Download failed",
                "message": f"Failed to download file from persistent storage: {str(e)}",
                "namespace": namespace,
                "user": user,
                "path": path
            }
        )

@app.get("/v1/fs/persist/list")
def list_persist(namespace: str = Query(...), user: str = Query(...), 
                _=Depends(require_namespace)):
    """List files in persistent storage"""
    try:
        import pathlib
        
        storage_dir = os.path.join(settings.storage.persist_root, namespace, user)
        
        if not os.path.exists(storage_dir):
            return {"files": [], "total": 0, "namespace": namespace, "user": user}
        
        files = []
        total_size = 0
        
        for item in pathlib.Path(storage_dir).iterdir():
            if item.is_file():
                stat = item.stat()
                files.append({
                    "name": item.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "path": str(item.relative_to(storage_dir))
                })
                total_size += stat.st_size
        
        return {
            "files": files,
            "total": len(files),
            "total_size": total_size,
            "namespace": namespace,
            "user": user
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "List failed",
                "message": f"Failed to list files in persistent storage: {str(e)}",
                "namespace": namespace,
                "user": user
            }
        )

# Include routers
app.include_router(cloudrun_router)
app.include_router(sessions_router)
app.include_router(gke_router)
app.include_router(gke_websocket_router)
app.include_router(billing_router)
app.include_router(templates_router)
app.include_router(cost_estimation_router)

# Startup event - Start session monitor
@app.on_event("startup")
async def startup_event():
    """Start session monitoring on app startup"""
    try:
        await session_monitor.start_monitoring()
        logger.info("✅ Session monitor started")
    except Exception as e:
        logger.error(f"❌ Failed to start session monitor: {e}")

# Shutdown event - Stop session monitor
@app.on_event("shutdown")
async def shutdown_event():
    """Stop session monitoring on app shutdown"""
    try:
        await session_monitor.stop_monitoring()
        logger.info("✅ Session monitor stopped")
    except Exception as e:
        logger.error(f"❌ Failed to stop session monitor: {e}")

# Workspace execution endpoints (DEPRECATED - use Cloud Run endpoints)
@app.post("/v1/workspaces/{workspace_id}/runpy")
def run_python(workspace_id: str, code: dict, _=Depends(require_api_key)):
    """Run Python code in workspace (DEPRECATED - use /v1/cloudrun/workspaces/{id}/runpython)"""
    try:
        return workspace_manager.execute_in_workspace(workspace_id, f"python -c '{code['code']}'")
    except Exception as e:
        raise HTTPException(500, f"Failed to run Python: {str(e)}")

@app.post("/v1/workspaces/{workspace_id}/runsh")
def run_shell(workspace_id: str, command: dict, _=Depends(require_api_key)):
    """Run shell command in workspace (DEPRECATED - use /v1/cloudrun/workspaces/{id}/execute)"""
    try:
        return workspace_manager.execute_in_workspace(workspace_id, command['command'])
    except Exception as e:
        raise HTTPException(500, f"Failed to run shell: {str(e)}")

@app.websocket("/v1/workspaces/{workspace_id}/shell")
async def shell_websocket(websocket: WebSocket, workspace_id: str):
    """Interactive shell WebSocket endpoint with slash commands (DEPRECATED - use /v1/cloudrun/workspaces/{id}/shell)"""
    await websocket.accept()
    
    try:
        # Get shell service
        shell_service = get_shell_service(workspace_manager)
        
        # Create shell session
        session = await shell_service.create_session(workspace_id, websocket)
        
        # Start the session
        await session.start()
        
    except Exception as e:
        logger.error(f"Shell session error: {e}")
        try:
            await websocket.send_text(f"❌ Error: {e}")
        except:
            pass

# Cloud Run WebSocket shell endpoint
@app.websocket("/v1/cloudrun/workspaces/{workspace_id}/shell")
async def cloudrun_shell_websocket_endpoint(websocket: WebSocket, workspace_id: str):
    """Interactive Cloud Run shell WebSocket endpoint with slash commands"""
    await cloudrun_shell_websocket(websocket, workspace_id)
