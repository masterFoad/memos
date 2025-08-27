# server/api/sessions.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import logging

from server.core.security import require_api_key
from server.services.sessions.manager import sessions_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


@router.post("")
def create_session(payload: Dict[str, Any], _=Depends(require_api_key)):
    try:
        return sessions_manager.create_session(payload)
    except Exception as e:
        logger.exception("create_session failed")
        raise HTTPException(500, str(e))


@router.get("")
def list_sessions(_=Depends(require_api_key)):
    """List all active sessions"""
    try:
        return sessions_manager.list_sessions()
    except Exception as e:
        logger.exception("list_sessions failed")
        raise HTTPException(500, str(e))


@router.get("/{sid}")
def get_session(sid: str, _=Depends(require_api_key)):
    s = sessions_manager.get_session(sid)
    if not s:
        raise HTTPException(404, "Session not found")
    return s


@router.delete("/{sid}")
def delete_session(sid: str, _=Depends(require_api_key)):
    ok = sessions_manager.delete_session(sid)
    if not ok:
        raise HTTPException(404, "Session not found")
    return {"ok": True}


@router.post("/{sid}/execute")
def execute(sid: str, body: Dict[str, Any], _=Depends(require_api_key)):
    cmd = (body or {}).get("command")
    timeout = int((body or {}).get("timeout") or 120)
    async_execution = bool((body or {}).get("async_execution", False))
    if not cmd:
        raise HTTPException(400, "command required")
    try:
        return sessions_manager.execute(sid, cmd, timeout, async_execution)
    except NotImplementedError:
        raise HTTPException(400, "execute not supported for this session provider")
    except Exception as e:
        logger.exception("execute failed")
        raise HTTPException(500, str(e))


@router.get("/{sid}/jobs/{job_id}/status")
def get_job_status(sid: str, job_id: str, job_name: str, _=Depends(require_api_key)):
    """Get the status of a job execution"""
    try:
        return sessions_manager.get_job_status(job_id, job_name, sid)
    except Exception as e:
        logger.exception("get_job_status failed")
        raise HTTPException(500, str(e))


@router.get("/{sid}/connect")
def connect_info(sid: str, _=Depends(require_api_key)):
    info = sessions_manager.connect_info(sid)
    if not info:
        raise HTTPException(404, "Session not found")
    return info
