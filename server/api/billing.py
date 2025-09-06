# server/api/billing.py
from __future__ import annotations

import logging
from typing import Dict

from fastapi import APIRouter, HTTPException, Depends, Query

from server.core.security import require_passport
from server.database.factory import get_database_client_async
from server.services.billing_service import BillingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/billing", tags=["billing"])


@router.get("/credits")
async def get_user_credits(user_info: Dict = Depends(require_passport)):
    """Get current user's credit balance."""
    try:
        db = await get_database_client_async()
        credits = await db.get_user_credits(user_info["user_id"])
        return {
            "user_id": user_info["user_id"],
            "credits": float(round(credits, 2)),
            "currency": "USD",
        }
    except Exception as e:
        logger.exception("get_user_credits failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_credit_history(
    user_info: Dict = Depends(require_passport),
    limit: int = Query(50, ge=1, le=100),
):
    """Get user's credit transaction history."""
    try:
        db = await get_database_client_async()
        history = await db.get_credit_history(user_info["user_id"])
        # Trim on the application side to avoid changing DB interface
        trimmed = history[:limit]
        return {
            "user_id": user_info["user_id"],
            "transactions": trimmed,
            "total_transactions": len(history),
        }
    except Exception as e:
        logger.exception("get_credit_history failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/purchase")
async def purchase_credits(
    amount_usd: float = Query(..., gt=0, description="Amount in USD to purchase"),
    user_info: Dict = Depends(require_passport),
):
    """Purchase credits for the user."""
    try:
        billing_service = BillingService()
        result = await billing_service.purchase_credits(user_info["user_id"], amount_usd)
        return result
    except Exception as e:
        logger.exception("purchase_credits failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def get_session_billing_history(
    user_info: Dict = Depends(require_passport),
    limit: int = Query(50, ge=1, le=100),
):
    """Get user's session billing history."""
    try:
        db = await get_database_client_async()

        # Fetch sessions that belong to the user via workspaces
        sessions = await db._execute_query(  # noqa: SLF001 (using internal helper intentionally)
            """
            SELECT s.* FROM sessions s
            JOIN workspaces w ON s.workspace_id = w.workspace_id
            WHERE w.user_id = ?
            ORDER BY s.created_at DESC
            LIMIT ?
            """,
            (user_info["user_id"], limit),
        )

        session_billing = []
        for session in sessions:
            billing_info = await db.get_session_billing_info(session["session_id"])
            if billing_info:
                session_billing.append(
                    {
                        "session_id": session["session_id"],
                        "created_at": session["created_at"],
                        "status": billing_info.get("status", "unknown"),
                        "total_hours": float(billing_info.get("total_hours", 0) or 0),
                        "total_cost": float(round(billing_info.get("total_cost", 0) or 0.0, 4)),
                        "hourly_rate": float(round(billing_info.get("hourly_rate", 0) or 0.0, 4)),
                    }
                )

        return {
            "user_id": user_info["user_id"],
            "sessions": session_billing,
            "total_sessions": len(session_billing),
        }
    except Exception as e:
        logger.exception("get_session_billing_history failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/estimate")
async def estimate_session_cost(
    resource_tier: str = Query(..., description="Resource tier (small, medium, large)"),
    duration_hours: float = Query(1.0, gt=0, description="Estimated duration in hours"),
    user_info: Dict = Depends(require_passport),
):
    """
    Estimate cost for a session.

    Note: We currently base price on user_type (consistent with session providers).
    `resource_tier` is accepted for client display/filtering, not pricing.
    """
    try:
        user_type = user_info["user_type"]

        # Keep rates consistent with providers:
        # free: 0.05, pro: 0.075, enterprise: 0.01, admin: 0.0
        hourly_rate = 0.075  # default (treat unknowns as PRO)
        if user_type == "free":
            hourly_rate = 0.05
        elif user_type == "enterprise":
            hourly_rate = 0.01
        elif user_type == "admin":
            hourly_rate = 0.0

        estimated_cost = float(round(hourly_rate * duration_hours, 4))

        return {
            "user_id": user_info["user_id"],
            "user_type": user_type,
            "resource_tier": resource_tier,
            "duration_hours": float(duration_hours),
            "hourly_rate": float(hourly_rate),
            "estimated_cost": estimated_cost,
            "currency": "USD",
        }
    except Exception as e:
        logger.exception("estimate_session_cost failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_billing_summary(user_info: Dict = Depends(require_passport)):
    """Get comprehensive billing summary for the user."""
    try:
        db = await get_database_client_async()

        # Current credits
        current_credits = float(round(await db.get_user_credits(user_info["user_id"]), 2))

        # Credit history and totals
        credit_history = await db.get_credit_history(user_info["user_id"])
        total_added = float(round(sum(t["amount"] for t in credit_history if t["amount"] > 0), 2))
        total_used = float(round(-sum(t["amount"] for t in credit_history if t["amount"] < 0), 2))
        # total_spent should reflect amounts used (not inferred as added - balance)
        total_spent = total_used

        # Recent sessions (by workspace ownership)
        recent_sessions = await db._execute_query(  # noqa: SLF001
            """
            SELECT s.* FROM sessions s
            JOIN workspaces w ON s.workspace_id = w.workspace_id
            WHERE w.user_id = ?
            ORDER BY s.created_at DESC
            LIMIT 10
            """,
            (user_info["user_id"],),
        )

        # Aggregate session costs (completed sessions only will have totals)
        total_session_cost = 0.0
        for session in recent_sessions:
            billing_info = await db.get_session_billing_info(session["session_id"])
            if billing_info:
                total_session_cost += float(billing_info.get("total_cost", 0) or 0.0)
        total_session_cost = float(round(total_session_cost, 4))

        return {
            "user_id": user_info["user_id"],
            "user_type": user_info["user_type"],
            "current_balance": current_credits,
            "credits_added": total_added,
            "credits_used": total_used,
            "total_spent": total_spent,
            "transaction_count": len(credit_history),
            "recent_sessions": len(recent_sessions),
            "total_session_cost": total_session_cost,
        }
    except Exception as e:
        logger.exception("get_billing_summary failed")
        raise HTTPException(status_code=500, detail=str(e))
