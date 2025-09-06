"""
Admin (internal) API router
"""

from __future__ import annotations

import uuid
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from server.core.security import require_api_key
from server.database.factory import get_database_client
from server.models.users import UserType, WorkspaceResourcePackage
from server.services.identity.identity_provisioner import identity_provisioner


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/admin", tags=["admin"])


class CreateUserBody(BaseModel):
    email: str
    name: Optional[str] = None
    user_type: UserType = UserType.PRO


class CreatePassportBody(BaseModel):
    user_id: str
    name: str = Field(default="default")
    permissions: List[str] = Field(default_factory=list)


class AddCreditsBody(BaseModel):
    user_id: str
    amount: float = Field(gt=0)
    source: str = "admin_adjustment"
    description: Optional[str] = None


class CreateWorkspaceBody(BaseModel):
    user_id: str
    workspace_id: Optional[str] = None
    name: str
    resource_package: WorkspaceResourcePackage = WorkspaceResourcePackage.DEV_SMALL
    description: Optional[str] = None


@router.post("/users")
async def create_user(body: CreateUserBody, _: dict = Depends(require_api_key)):
    db = get_database_client()
    ok = await db.connect()
    if not ok:
        raise HTTPException(500, "database connection failed")
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    user = await db.create_user(user_id, body.email, body.user_type, body.name)
    if not user:
        raise HTTPException(500, "failed to create user")
    return {"user": user}


@router.post("/passports")
async def create_passport(body: CreatePassportBody, _: dict = Depends(require_api_key)):
    db = get_database_client()
    await db.connect()
    passport = await db.create_passport(body.user_id, body.name, body.permissions)
    if not passport:
        raise HTTPException(500, "failed to create passport")
    return {
        "passport_id": passport.get("passport_id"),
        "passport_key": passport.get("passport_key"),
        "user_id": passport.get("user_id"),
        "name": passport.get("name"),
        "permissions": passport.get("permissions", []),
        "created_at": passport.get("created_at"),
    }


@router.post("/credits/add")
async def add_credits(body: AddCreditsBody, _: dict = Depends(require_api_key)):
    db = get_database_client()
    await db.connect()
    ok = await db.add_credits(body.user_id, body.amount, body.source, body.description)
    if not ok:
        raise HTTPException(500, "failed to add credits")
    return {"ok": True}


@router.post("/workspaces")
async def create_workspace(body: CreateWorkspaceBody, _: dict = Depends(require_api_key)):
    db = get_database_client()
    await db.connect()
    ws_id = body.workspace_id or f"ws-{body.user_id}-{uuid.uuid4().hex[:6]}"
    ws = await db.create_workspace(
        user_id=body.user_id,
        workspace_id=ws_id,
        name=body.name,
        resource_package=body.resource_package.value,
        description=body.description,
    )
    if not ws:
        raise HTTPException(500, "failed to create workspace")
    return {"workspace": ws}


class EnsureIdentityBody(BaseModel):
    project: str
    region: str
    cluster: str
    workspace_id: str
    bucket: Optional[str] = None


@router.post("/workspaces/ensure-identity")
async def ensure_workspace_identity(body: EnsureIdentityBody, _: dict = Depends(require_api_key)):
    try:
        result = await identity_provisioner.ensure_workspace_identity(
            project=body.project,
            region=body.region,
            cluster=body.cluster,
            workspace_id=body.workspace_id,
            bucket=body.bucket,
        )
        return {"identity": result}
    except Exception as e:
        logger.error(f"ensure-identity failed: {e}")
        raise HTTPException(500, f"ensure-identity failed: {e}")

