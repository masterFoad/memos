#!/usr/bin/env python3
"""
Cloud Run API Endpoints for OnMemOS v3
=====================================
API endpoints for Cloud Run-based workspace management
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
import logging

from server.core.security import require_api_key
from server.services.cloudrun.cloudrun_service import cloudrun_service
from server.models.sessions import CreateSessionRequest, SessionInfo
from fastapi import HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/cloudrun", tags=["cloudrun"])


@router.post("/workspaces")
async def create_cloudrun_workspace(
    workspace: CreateSessionRequest,
    api_key: str = Depends(require_api_key),
):
    try:
        result = cloudrun_service.create_workspace(
            template="python",  # Default template for Cloud Run
            namespace=workspace.namespace,
            user=workspace.user,
            ttl_minutes=workspace.ttl_minutes or 180,
            storage_options=workspace.storage_config.dict() if workspace.storage_config else None,
        )
        return {
            "id": result["id"],
            "template": "python",
            "namespace": result["namespace"],
            "user": result["user"],
            "status": result["status"],
            "service_url": result["service_url"],
            "bucket_name": result.get("bucket_name"),
            "filestore_instance": result.get("filestore_instance"),
            "created_at": result.get("created_at"),
            "ttl_minutes": result.get("ttl_minutes"),
        }
    except Exception as e:
        logger.exception("create_workspace failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workspaces")
async def list_cloudrun_workspaces(
    namespace: Optional[str] = Query(None),
    user: Optional[str] = Query(None),
    api_key: str = Depends(require_api_key),
):
    try:
        items = cloudrun_service.list_workspaces(namespace=namespace, user=user)
        return {
            "workspaces": [
                {
                    "id": ws["id"],
                    "template": "python",
                    "namespace": ws["namespace"],
                    "user": ws["user"],
                    "status": ws["status"],
                    "service_url": ws["service_url"],
                    "bucket_name": ws.get("bucket_name"),
                    "filestore_instance": None,
                    "created_at": None,
                    "ttl_minutes": None,
                }
                for ws in items
            ]
        }
    except Exception as e:
        logger.exception("list_cloudrun_workspaces failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workspaces/{workspace_id}")
async def get_cloudrun_workspace(
    workspace_id: str,
    api_key: str = Depends(require_api_key),
):
    ws = cloudrun_service.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {
        "id": ws["id"],
        "template": "python",
        "namespace": ws["namespace"],
        "user": ws["user"],
        "status": ws["status"],
        "service_url": ws["service_url"],
        "bucket_name": ws.get("bucket_name"),
        "filestore_instance": None,
        "created_at": None,
        "ttl_minutes": None,
    }


@router.delete("/workspaces/{workspace_id}")
async def delete_cloudrun_workspace(
    workspace_id: str,
    api_key: str = Depends(require_api_key),
):
    ok = cloudrun_service.delete_workspace(workspace_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"message": "Workspace deleted successfully"}


@router.post("/workspaces/{workspace_id}/execute")
async def execute_in_cloudrun_workspace(
    workspace_id: str,
    command: str = Query(..., description="Shell command to execute"),
    timeout: int = Query(120, description="Timeout seconds"),
    api_key: str = Depends(require_api_key),
):
    try:
        res = cloudrun_service.execute_in_workspace(workspace_id, command, timeout)
        return {"workspace_id": workspace_id, **res, "command": command}
    except Exception as e:
        logger.exception("cloudrun execute failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workspaces/{workspace_id}/runsh")
async def run_shell_in_cloudrun_workspace(
    workspace_id: str,
    command: str = Query(..., description="Shell command to execute"),
    api_key: str = Depends(require_api_key),
):
    return await execute_in_cloudrun_workspace(workspace_id, command, 120, api_key)


@router.post("/workspaces/{workspace_id}/runpython")
async def run_python_in_cloudrun_workspace(
    workspace_id: str,
    code: str = Query(..., description="Python code to execute"),
    api_key: str = Depends(require_api_key),
):
    # use here-doc to avoid quoting issues
    cmd = f"python3 - <<'PY'\n{code}\nPY"
    return await execute_in_cloudrun_workspace(workspace_id, cmd, 180, api_key)
