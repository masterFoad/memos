"""
OnMemOS v3 - Main Application with Cloud Run Integration
"""

import datetime
import logging
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    HTTPException,
    Query,
    UploadFile,
    File,
)

from server.core.config import load_settings
from server.core.logging import setup_logging, get_logger
from server.core.security import require_api_key, require_namespace


from server.services.session_monitor import session_monitor

# Import Cloud Run services
from server.api.cloudrun import router as cloudrun_router
from server.api.sessions import router as sessions_router
from server.api.gke import router as gke_router
from server.api.gke_websocket import router as gke_websocket_router
from server.api.billing import router as billing_router
from server.api.templates import router as templates_router
from server.api.cost_estimation import router as cost_estimation_router
from server.api.admin import router as admin_router
from server.websockets.cloudrun_shell import cloudrun_shell_websocket

# Setup logging
setup_logging(
    log_level="INFO",
    log_dir="./logs",
    enable_file_logging=True,
    enable_console_logging=True,
)

# Configure Uvicorn to reduce WebSocket 403 spam
uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.setLevel(logging.WARNING)  # Reduce noisy INFO logs


# Create custom filter to hide WebSocket 403 errors
class WebSocketFilter(logging.Filter):
    def filter(self, record):
        # Hide WebSocket 403 connection rejections
        if hasattr(record, "msg") and isinstance(record.msg, str):
            if "WebSocket" in record.msg and "403" in record.msg:
                return False
            if "connection rejected (403 Forbidden)" in record.msg:
                return False
        return True


# Apply filter to uvicorn access logger
uvicorn_logger.addFilter(WebSocketFilter())

logger = get_logger(__name__)

app = FastAPI(title="OnMemOS v3", version="3.0.0")
settings = load_settings()


def setup_application_default_credentials():
    """Set up application default credentials using service account key file"""
    try:
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


def test_gcp_authentication(do_mutating_tests: bool = True):
    """
    Test GCP authentication and services with comprehensive permission checks.

    Args:
        do_mutating_tests: If True, perform bucket create/delete tests.
                           Set to False for lightweight health checks.
    """
    try:
        import subprocess
        from google.cloud import storage
        from google.cloud.exceptions import Forbidden

        # Test basic gcloud auth
        try:
            result = subprocess.run(
                ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return False, "gcloud CLI not found on PATH"

        if result.returncode != 0:
            return False, "No active GCP authentication found"

        account = result.stdout.strip()
        logger.info(f"🔐 Authenticated as: {account}")

        # Set up application default credentials
        if not setup_application_default_credentials():
            logger.warning("⚠️ Could not set up application default credentials")

        # Test GCS access with detailed permission checks
        try:
            from google.auth import default

            credentials, project = default()
            client = storage.Client(credentials=credentials, project=project)
            _ = list(client.list_buckets(max_results=1))
            logger.info("✅ GCS bucket listing permission: OK")
        except Forbidden as e:
            return False, f"GCS bucket listing permission denied: {e}"
        except Exception as e:
            return False, f"GCS access failed: {e}"

        # Optional mutating tests (skip for health checks)
        if do_mutating_tests:
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

        # Test Compute Engine access (non-fatal)
        result = subprocess.run(
            ["gcloud", "compute", "instances", "list", "--limit=1"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.warning("⚠️ Cannot access Compute Engine - some features may not work")
        else:
            logger.info("✅ Compute Engine access: OK")

        # Test GKE access (non-fatal)
        try:
            result = subprocess.run(
                ["gcloud", "container", "clusters", "list", "--format=value(name,location)"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                clusters = result.stdout.strip().split("\n") if result.stdout.strip() else []
                logger.info(f"✅ GKE clusters access: OK ({len(clusters)} clusters found)")

                # Test kubectl access if clusters exist
                if clusters:
                    result = subprocess.run(
                        ["kubectl", "get", "nodes", "--no-headers"],
                        capture_output=True,
                        text=True,
                    )
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

        # Test GKE Autopilot permission (help page presence; non-fatal)
        try:
            result = subprocess.run(
                ["gcloud", "container", "clusters", "create-auto", "--help"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                logger.info("✅ GKE Autopilot cluster creation permission: OK")
            else:
                logger.warning("⚠️ GKE Autopilot cluster creation permission: Check")
        except Exception as e:
            logger.warning(f"⚠️ GKE Autopilot permission test failed: {e}")

        logger.info("✅ GCP authentication and permission checks complete")
        return True, "GCP authentication and permissions successful"

    except Exception as e:
        return False, f"GCP authentication failed: {e}"


def _safe_join(base_dir: Path, *parts: str) -> Path:
    """
    Safely join paths and ensure the result stays within base_dir.
    Raises HTTPException on path traversal attempts.
    """
    # Normalize and resolve
    base_dir = base_dir.resolve()
    # Disallow absolute user parts; build relative path only
    target = base_dir.joinpath(*parts).resolve()
    try:
        # Python 3.9+: Path.is_relative_to
        if not target.is_relative_to(base_dir):
            raise ValueError("Path escapes base directory")
    except AttributeError:
        # Fallback for older versions
        base_str = str(base_dir)
        target_str = str(target)
        if not (target_str == base_str or target_str.startswith(base_str + os.sep)):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid path",
                    "message": "Resolved path escapes base directory",
                    "path": str(target),
                },
            )
    return target


@app.on_event("startup")
async def startup_event():
    """Startup event - Test GCP authentication and start session monitor"""
    logger.info("🚀 Starting OnMemOS v3...")

    # Test GCP authentication (full check, including mutating tests)
    logger.info("🔐 Testing GCP authentication...")
    success, message = test_gcp_authentication(do_mutating_tests=True)
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
            "disks": "/v1/disks",
        },
        "documentation": "API requires authentication via X-API-Key header",
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }


@app.get("/health")
def health_check():
    """Health check endpoint with lightweight GCP status (non-mutating)"""
    gcp_status, gcp_message = test_gcp_authentication(do_mutating_tests=False)

    return {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "version": "3.0.0",
        "services": {
            "server": "running",
            "workspaces": len(workspace_manager.workspaces),
            "storage": "available",
            "gcp": "connected" if gcp_status else "disconnected",
        },
        "gcp": {"status": "connected" if gcp_status else "disconnected", "message": gcp_message},
    }


# Workspace endpoints
@app.post("/v1/workspaces")
def create_workspace(
    template: str = Query(...),
    namespace: str = Query(...),
    user: str = Query(...),
    ttl_minutes: int = Query(180),
    storage_options: dict = None,
    _=Depends(require_api_key),
):
    """Create a new workspace with real GCP storage"""
    try:
        logger.info(f"Creating workspace: template={template}, namespace={namespace}, user={user}")
        return workspace_manager.create_workspace(
            template, namespace, user, ttl_minutes, storage_options
        )
    except Exception as e:
        logger.error(f"Failed to create workspace: {e}")
        raise HTTPException(500, f"Failed to create workspace: {str(e)}")


@app.get("/v1/workspaces")
def list_workspaces(
    namespace: Optional[str] = Query(None), user: Optional[str] = Query(None), _=Depends(require_api_key)
):
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
def setup_namespace_storage(
    namespace: str,
    user: str = Query(...),
    options: dict = None,
    _=Depends(require_api_key),
):
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
def create_bucket(
    bucket_name: str = Query(...), namespace: str = Query(...), user: str = Query(...), _=Depends(require_api_key)
):
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
def create_persistent_disk(
    disk_name: str = Query(...),
    namespace: str = Query(...),
    user: str = Query(...),
    size_gb: int = Query(10),
    _=Depends(require_api_key),
):
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


@app.post("/v1/fs/persist/upload")
async def upload_persist(
    namespace: str = Query(...),
    user: str = Query(...),
    dst: str = Query(""),
    file: UploadFile = File(...),
    _=Depends(require_namespace),
):
    """Upload a file to persistent storage"""
    try:
        # Base storage directory for this namespace/user
        base = Path(settings.storage.persist_root) / namespace / user
        base.mkdir(parents=True, exist_ok=True)

        # Determine filename (disallow empty or directory-only names)
        filename = dst or (file.filename if file else "")
        if not filename or filename.endswith(("/", "\\")):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid filename",
                    "message": "Filename cannot be empty or a directory",
                    "suggestion": "Provide a valid filename in 'dst' or upload a file with a name",
                },
            )

        # Compute safe output path (prevents path traversal)
        out_path = _safe_join(base, filename)

        # If the path exists and is a directory, return a conflict
        if out_path.exists() and out_path.is_dir():
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "Path conflict",
                    "message": f"Path '{out_path}' already exists as a directory",
                    "suggestion": "Use a different filename or remove the existing directory",
                    "path": str(out_path),
                },
            )

        # Ensure parent directories exist (if dst included subdirs)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Read and write file
        data = await file.read()
        with open(out_path, "wb") as f:
            f.write(data)

        return {"ok": True, "bytes": len(data), "path": str(out_path)}

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
                "filename": dst or (file.filename if file else "unknown"),
            },
        )


@app.get("/v1/fs/persist/download")
def download_persist(
    namespace: str = Query(...),
    user: str = Query(...),
    path: str = Query(...),
    _=Depends(require_namespace),
):
    """Download a file from persistent storage"""
    try:
        from fastapi.responses import FileResponse

        base = Path(settings.storage.persist_root) / namespace / user
        file_path = _safe_join(base, path)

        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "File not found",
                    "message": f"File '{path}' not found in persistent storage",
                    "namespace": namespace,
                    "user": user,
                    "path": path,
                },
            )

        if file_path.is_dir():
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Path is directory",
                    "message": f"Path '{path}' is a directory, not a file",
                    "namespace": namespace,
                    "user": user,
                    "path": path,
                },
            )

        return FileResponse(str(file_path), filename=file_path.name)

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
                "path": path,
            },
        )


@app.get("/v1/fs/persist/list")
def list_persist(namespace: str = Query(...), user: str = Query(...), _=Depends(require_namespace)):
    """List files in persistent storage"""
    try:
        storage_dir = Path(settings.storage.persist_root) / namespace / user

        if not storage_dir.exists():
            return {"files": [], "total": 0, "namespace": namespace, "user": user}

        files = []
        total_size = 0

        for item in storage_dir.iterdir():
            if item.is_file():
                stat = item.stat()
                files.append(
                    {
                        "name": item.name,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "path": str(item.relative_to(storage_dir)),
                    }
                )
                total_size += stat.st_size

        return {
            "files": files,
            "total": len(files),
            "total_size": total_size,
            "namespace": namespace,
            "user": user,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "List failed",
                "message": f"Failed to list files in persistent storage: {str(e)}",
                "namespace": namespace,
                "user": user,
            },
        )


# Include routers
app.include_router(cloudrun_router)
app.include_router(sessions_router)
app.include_router(gke_router)
app.include_router(gke_websocket_router)
app.include_router(billing_router)
app.include_router(templates_router)
app.include_router(cost_estimation_router)
app.include_router(admin_router)

# Import and include storage API
from .api.storage import router as storage_router
app.include_router(storage_router)


# Shutdown event - Stop session monitor
@app.on_event("shutdown")
async def shutdown_event():
    """Stop session monitoring on app shutdown"""
    try:
        await session_monitor.stop_monitoring()
        logger.info("✅ Session monitor stopped")
    except Exception as e:
        logger.error(f"❌ Failed to stop session monitor: {e}")





# Root WebSocket handler for unauthorized connections (prevents spam)
@app.websocket("/")
async def root_websocket_handler(websocket: WebSocket):
    """Handle unauthorized WebSocket connections to root path"""
    # Check for API key in query parameters BEFORE accepting
    api_key = websocket.query_params.get("api_key")
    if not api_key:
        # Silently reject connection without logging (reduces spam)
        # These are usually browser dev tools or monitoring tools
        await websocket.close(code=1008, reason="API key required")
        return

    # If we have an API key, accept and then validate
    await websocket.accept()

    try:
        # Send helpful message for authenticated but misrouted connections
        await websocket.send_json(
            {
                "error": "No service available at root path",
                "message": "Use specific WebSocket endpoints like /v1/cloudrun/workspaces/{workspace_id}/shell or /v1/gke/shell/{session_id}",
                "available_endpoints": [
                    "/v1/cloudrun/workspaces/{workspace_id}/shell",
                    "/v1/gke/shell/{session_id}",
                ],
            }
        )
        await websocket.close(code=1000, reason="No service at root path")
    except Exception as e:
        # Only log unexpected errors, not routine rejections
        logger.debug(f"WebSocket handler error: {e}")
        await websocket.close(code=1011, reason="Internal error")


# Cloud Run WebSocket shell endpoint
@app.websocket("/v1/cloudrun/workspaces/{workspace_id}/shell")
async def cloudrun_shell_websocket_endpoint(websocket: WebSocket, workspace_id: str):
    """Interactive Cloud Run shell WebSocket endpoint with slash commands"""
    await cloudrun_shell_websocket(websocket, workspace_id)
