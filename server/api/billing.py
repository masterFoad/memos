# server/api/billing.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, Optional
import logging

from server.core.security import require_passport
from server.database.factory import get_database_client
from server.services.billing_service import BillingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/billing", tags=["billing"])


@router.get("/credits")
async def get_user_credits(user_info: Dict = Depends(require_passport)):
    """Get current user's credit balance"""
    try:
        db = get_database_client()
        await db.connect()
        
        credits = await db.get_user_credits(user_info["user_id"])
        return {
            "user_id": user_info["user_id"],
            "credits": credits,
            "currency": "USD"
        }
    except Exception as e:
        logger.exception("get_user_credits failed")
        raise HTTPException(500, str(e))


@router.get("/history")
async def get_credit_history(
    user_info: Dict = Depends(require_passport),
    limit: int = Query(50, ge=1, le=100)
):
    """Get user's credit transaction history"""
    try:
        db = get_database_client()
        await db.connect()
        
        history = await db.get_credit_history(user_info["user_id"])
        return {
            "user_id": user_info["user_id"],
            "transactions": history[:limit],
            "total_transactions": len(history)
        }
    except Exception as e:
        logger.exception("get_credit_history failed")
        raise HTTPException(500, str(e))


@router.post("/purchase")
async def purchase_credits(
    amount_usd: float = Query(..., gt=0, description="Amount in USD to purchase"),
    user_info: Dict = Depends(require_passport)
):
    """Purchase credits for the user"""
    try:
        billing_service = BillingService()
        result = await billing_service.purchase_credits(user_info["user_id"], amount_usd)
        return result
    except Exception as e:
        logger.exception("purchase_credits failed")
        raise HTTPException(500, str(e))


@router.get("/sessions")
async def get_session_billing_history(
    user_info: Dict = Depends(require_passport),
    limit: int = Query(50, ge=1, le=100)
):
    """Get user's session billing history"""
    try:
        db = get_database_client()
        await db.connect()
        
        # Get user's sessions (join through workspaces)
        sessions = await db._execute_query(
            """
            SELECT s.* FROM sessions s
            JOIN workspaces w ON s.workspace_id = w.workspace_id
            WHERE w.user_id = ? 
            ORDER BY s.created_at DESC LIMIT ?
            """,
            (user_info["user_id"], limit)
        )
        
        # Get billing info for each session
        session_billing = []
        for session in sessions:
            billing_info = await db.get_session_billing_info(session["session_id"])
            if billing_info:
                session_billing.append({
                    "session_id": session["session_id"],
                    "created_at": session["created_at"],
                    "status": billing_info.get("status", "unknown"),
                    "total_hours": billing_info.get("total_hours", 0),
                    "total_cost": billing_info.get("total_cost", 0),
                    "hourly_rate": billing_info.get("hourly_rate", 0)
                })
        
        return {
            "user_id": user_info["user_id"],
            "sessions": session_billing,
            "total_sessions": len(session_billing)
        }
    except Exception as e:
        logger.exception("get_session_billing_history failed")
        raise HTTPException(500, str(e))


@router.get("/estimate")
async def estimate_session_cost(
    resource_tier: str = Query(..., description="Resource tier (small, medium, large)"),
    duration_hours: float = Query(1.0, gt=0, description="Estimated duration in hours"),
    user_info: Dict = Depends(require_passport)
):
    """Estimate cost for a session"""
    try:
        # Get user's tier limits and pricing
        tier_limits = await get_database_client().get_user_tier_limits(user_info["user_id"])
        
        # Determine hourly rate based on user type
        user_type = user_info["user_type"]
        hourly_rate = 0.075  # Default PRO rate
        if user_type == "free":
            hourly_rate = 0.05
        elif user_type == "enterprise":
            hourly_rate = 0.01
        elif user_type == "admin":
            hourly_rate = 0.0
        
        estimated_cost = hourly_rate * duration_hours
        
        return {
            "user_id": user_info["user_id"],
            "user_type": user_type,
            "resource_tier": resource_tier,
            "duration_hours": duration_hours,
            "hourly_rate": hourly_rate,
            "estimated_cost": estimated_cost,
            "currency": "USD"
        }
    except Exception as e:
        logger.exception("estimate_session_cost failed")
        raise HTTPException(500, str(e))


@router.get("/summary")
async def get_billing_summary(user_info: Dict = Depends(require_passport)):
    """Get comprehensive billing summary for the user"""
    try:
        db = get_database_client()
        await db.connect()
        
        # Get current credits
        current_credits = await db.get_user_credits(user_info["user_id"])
        
        # Get credit history
        credit_history = await db.get_credit_history(user_info["user_id"])
        
        # Calculate totals
        total_added = sum(t["amount"] for t in credit_history if t["amount"] > 0)
        total_used = abs(sum(t["amount"] for t in credit_history if t["amount"] < 0))
        
        # Get recent sessions (join through workspaces)
        recent_sessions = await db._execute_query(
            """
            SELECT s.* FROM sessions s
            JOIN workspaces w ON s.workspace_id = w.workspace_id
            WHERE w.user_id = ? 
            ORDER BY s.created_at DESC LIMIT 10
            """,
            (user_info["user_id"],)
        )
        
        # Calculate session costs
        total_session_cost = 0
        for session in recent_sessions:
            billing_info = await db.get_session_billing_info(session["session_id"])
            if billing_info:
                total_session_cost += billing_info.get("total_cost", 0)
        
        return {
            "user_id": user_info["user_id"],
            "user_type": user_info["user_type"],
            "current_balance": current_credits,
            "credits_added": total_added,
            "credits_used": total_used,
            "total_spent": total_added - current_credits,
            "transaction_count": len(credit_history),
            "recent_sessions": len(recent_sessions),
            "total_session_cost": total_session_cost
        }
    except Exception as e:
        logger.exception("get_billing_summary failed")
        raise HTTPException(500, str(e))

