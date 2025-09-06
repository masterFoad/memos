# server/api/sessions.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, Body, Query
from typing import Dict, Any
import logging

from server.core.security import require_passport
from server.database.factory import get_database_client_async
from server.services.sessions.manager import sessions_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


@router.post("")
async def create_session(spec: Dict[str, Any] = Body(...), user: Dict = Depends(require_passport)):
    try:
        spec = dict(spec or {})
        spec["user"] = user["user_id"]
        ws_id = spec.get("workspace_id")
        if not ws_id:
            raise HTTPException(400, "workspace_id is required")
        db = await get_database_client_async()
        ws = await db.get_workspace(ws_id)
        if not ws or ws.get("user_id") != user["user_id"]:
            raise HTTPException(403, "workspace does not belong to the authenticated user")
        spec.setdefault("namespace", ws_id)
        info = await sessions_manager.create_session(spec)
        return {"session": info}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("create_session failed")
        raise HTTPException(500, str(e))


@router.get("")
async def list_sessions(user: Dict = Depends(require_passport)):
    """List only the caller's sessions"""
    try:
        all_s = await sessions_manager.list_sessions()
        mine = [s for s in all_s.get("sessions", []) if s.get("user") == user["user_id"]]
        return {"sessions": mine, "count": len(mine)}
    except Exception as e:
        logger.exception("list_sessions failed")
        raise HTTPException(500, str(e))


@router.get("/{sid}")
async def get_session(sid: str, user: Dict = Depends(require_passport)):
    s = await sessions_manager.get_session(sid)
    if not s or s.get("user") != user["user_id"]:
        raise HTTPException(404, "Session not found")
    return {"session": s}


@router.delete("/{sid}")
async def delete_session(sid: str, user: Dict = Depends(require_passport)):
    s = await sessions_manager.get_session(sid)
    if not s or s.get("user") != user["user_id"]:
        raise HTTPException(404, "Session not found")
    ok = await sessions_manager.delete_session(sid)
    if not ok:
        raise HTTPException(500, "Provider deletion failed")
    return {"deleted": True}


@router.post("/{sid}/execute")
def execute(
    sid: str,
    command: str = Query(..., description="shell command"),
    timeout: int = Query(120, ge=1, le=3600),
    async_execution: bool = Query(False),
    user: Dict = Depends(require_passport),
):
    s = sessions_manager._sessions.get(sid)  # use in-memory fast path for ownership check
    if not s or s.user != user["user_id"]:
        # fallback to async get
        import anyio
        async def _check():
            ss = await sessions_manager.get_session(sid)
            return ss and ss.get("user") == user["user_id"]
        ok = anyio.run(_check)
        if not ok:
            raise HTTPException(404, "Session not found")
    try:
        res = sessions_manager.execute(sid, command, timeout, async_execution)
        return {"session_id": sid, "command": command, **res}
    except NotImplementedError:
        raise HTTPException(400, "execute not supported for this session provider")
    except Exception as e:
        logger.exception("execute failed")
        raise HTTPException(500, str(e))


@router.get("/{sid}/jobs/{job_id}/status")
def get_job_status(sid: str, job_id: str, job_name: str, user: Dict = Depends(require_passport)):
    """Get the status of a job execution (owned session only)"""
    s = sessions_manager._sessions.get(sid)
    if not s or s.user != user["user_id"]:
        raise HTTPException(404, "Session not found")
    try:
        return sessions_manager.get_job_status(job_id, job_name, sid)
    except Exception as e:
        logger.exception("get_job_status failed")
        raise HTTPException(500, str(e))


@router.get("/{sid}/connect")
def connect_info(sid: str, user: Dict = Depends(require_passport)):
    s = sessions_manager._sessions.get(sid)
    if not s or s.user != user["user_id"]:
        raise HTTPException(404, "Session not found")
    info = sessions_manager.connect_info(sid)
    if not info:
        raise HTTPException(404, "Session not found")
    return info

import time, jwt
from server.core.config import load_settings
_settings = load_settings()

@router.post("/{sid}/ws-token")
async def mint_ws_token(sid: str, user: Dict = Depends(require_passport)):
    s = await sessions_manager.get_session(sid)
    if not s or s.get("user") != user["user_id"]:
        raise HTTPException(404, "Session not found")
    payload = {
        "sub": user["user_id"],
        "sid": sid,
        "exp": int(time.time()) + 300,
        "scope": "ws/shell",
    }
    token = jwt.encode(payload, _settings.server.jwt_secret, algorithm="HS256")
    return {"token": token, "expires_in": 300}
