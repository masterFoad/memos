#!/usr/bin/env python3
"""
Cloud Run API Endpoints for OnMemOS v3
=====================================
API endpoints for Cloud Run-based workspace management
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from server.core.security import require_api_key
from server.services.cloudrun.cloudrun_service import cloudrun_service
from server.models.sessions import CreateSessionRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/cloudrun", tags=["cloudrun"])


@router.post("/workspaces")
async def create_cloudrun_workspace(
    workspace: CreateSessionRequest,
    _api_key: str = Depends(require_api_key),  # verify API key; value unused
):
    """
    Create a Cloud Run workspace.
    """
    try:
        result = cloudrun_service.create_workspace(
            template="python",  # default template for Cloud Run
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
        logger.exception("create_cloudrun_workspace failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/workspaces")
async def list_cloudrun_workspaces(
    namespace: Optional[str] = Query(None),
    user: Optional[str] = Query(None),
    _api_key: str = Depends(require_api_key),
):
    """
    List Cloud Run workspaces (optionally filter by namespace/user).
    """
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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/workspaces/{workspace_id}")
async def get_cloudrun_workspace(
    workspace_id: str,
    _api_key: str = Depends(require_api_key),
):
    """
    Get a single Cloud Run workspace by ID.
    """
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
    _api_key: str = Depends(require_api_key),
):
    """
    Delete a Cloud Run workspace by ID.
    """
    ok = cloudrun_service.delete_workspace(workspace_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"message": "Workspace deleted successfully"}


@router.post("/workspaces/{workspace_id}/execute")
async def execute_in_cloudrun_workspace(
    workspace_id: str,
    command: str = Query(..., description="Shell command to execute"),
    timeout: int = Query(120, description="Timeout seconds"),
    _api_key: str = Depends(require_api_key),
):
    """
    Execute a shell command in the Cloud Run workspace.
    Returns job submission info; poll with your jobs status endpoint/util.
    """
    try:
        res = cloudrun_service.execute_in_workspace(workspace_id, command, timeout)
        return {"workspace_id": workspace_id, **res, "command": command}
    except Exception as e:
        logger.exception("execute_in_cloudrun_workspace failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/workspaces/{workspace_id}/runsh")
async def run_shell_in_cloudrun_workspace(
    workspace_id: str,
    command: str = Query(..., description="Shell command to execute"),
    _api_key: str = Depends(require_api_key),
):
    """
    Convenience wrapper over /execute for shell commands.
    """
    return await execute_in_cloudrun_workspace(
        workspace_id=workspace_id,
        command=command,
        timeout=120,
    )


@router.post("/workspaces/{workspace_id}/runpython")
async def run_python_in_cloudrun_workspace(
    workspace_id: str,
    code: str = Query(..., description="Python code to execute"),
    _api_key: str = Depends(require_api_key),
):
    """
    Run inline Python code inside the Cloud Run workspace using a here-doc.
    """
    cmd = f"python3 - <<'PY'\n{code}\nPY"
    return await execute_in_cloudrun_workspace(
        workspace_id=workspace_id,
        command=cmd,
        timeout=180,
    )
