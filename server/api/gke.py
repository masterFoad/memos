"""
GKE API endpoints
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any

from server.services.sessions.gke_provider import gke_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/gke", tags=["gke"])


@router.post("/sessions/{session_id}/execute")
def execute_in_session(session_id: str, command: str, timeout: int = 120, async_execution: bool = False):
    """Execute a command in a GKE session"""
    try:
        result = gke_provider.execute(session_id, command, timeout, async_execution)
        return result
    except Exception as e:
        logger.error("execute failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}/status")
def get_job_status(job_id: str, job_name: str, session_id: str):
    """Get the status of a GKE job execution"""
    try:
        result = gke_provider.get_job_status(job_id, job_name, session_id)
        return result
    except Exception as e:
        logger.error("get_job_status failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
