"""
GKE API endpoints
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Query, Depends

from server.core.security import require_api_key
from server.services.sessions.gke_provider import gke_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/gke", tags=["gke"])


@router.post("/sessions/{session_id}/execute")
def execute_in_session(
    session_id: str,
    command: str = Query(..., description="Shell command to execute"),
    timeout: int = Query(120, description="Timeout seconds"),
    async_execution: bool = Query(False, description="Run asynchronously as a job"),
    _api_key: str = Depends(require_api_key),
):
    """Execute a command in a GKE session"""
    try:
        result = gke_provider.execute(session_id, command, timeout, async_execution)
        return result
    except Exception as e:
        logger.error("execute failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}/status")
def get_job_status(
    job_id: str,
    job_name: str = Query(..., description="Kubernetes Job name"),
    session_id: str = Query(..., description="Session ID that submitted the job"),
    _api_key: str = Depends(require_api_key),
):
    """Get the status of a GKE job execution"""
    try:
        result = gke_provider.get_job_status(job_id, job_name, session_id)
        return result
    except Exception as e:
        logger.error("get_job_status failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
