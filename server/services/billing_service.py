"""
Billing Service for OnMemOS v3
Handles payment calculations, session billing, and credit management
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import math

from ..database.factory import get_database_client
from ..database.base import UserType, StorageType, BillingType, PaymentStatus

logger = logging.getLogger(__name__)

class BillingService:
    """Service for handling billing and payment calculations"""
    
    def __init__(self):
        self.db = get_database_client()
    
    async def calculate_session_cost(self, user_id: str, session_duration_hours: float, 
                                   resource_tier: str = "small") -> float:
        """Calculate the cost for a session based on duration and resource tier"""
        try:
            # Get user's tier and hourly rate
            user = await self.db.get_user(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            tier_limits = await self.db.get_user_tier_limits(UserType(user["user_type"]))
            hourly_rate = tier_limits.get("hourly_rate", 0.05)  # Default $0.05/hour
            
            # Calculate base cost
            base_cost = hourly_rate * session_duration_hours
            
            # Apply resource tier multipliers
            tier_multipliers = {
                "small": 1.0,
                "medium": 1.5,
                "large": 2.0,
                "gpu": 5.0  # GPU sessions cost 5x more
            }
            
            multiplier = tier_multipliers.get(resource_tier, 1.0)
            total_cost = base_cost * multiplier
            
            logger.info(f"Session cost calculation: {session_duration_hours}h * ${hourly_rate}/h * {multiplier}x = ${total_cost:.4f}")
            
            return round(total_cost, 4)
            
        except Exception as e:
            logger.error(f"Failed to calculate session cost: {e}")
            return 0.0
    
    async def calculate_storage_cost(self, storage_type: StorageType, size_gb: int, 
                                   duration_days: int = 30) -> float:
        """Calculate the cost for storage based on type, size, and duration"""
        try:
            # Get payment configuration
            payment_config = await self.db.get_payment_config()
            storage_pricing = payment_config.get("pricing", {}).get("storage_pricing", {})
            
            # Get monthly rates
            bucket_rate = storage_pricing.get("bucket_per_gb_monthly", 0.02)  # $0.02/GB/month
            filestore_rate = storage_pricing.get("filestore_per_gb_monthly", 0.17)  # $0.17/GB/month
            
            # Calculate monthly cost
            if storage_type == StorageType.GCS_BUCKET:
                monthly_cost = size_gb * bucket_rate
            elif storage_type == StorageType.FILESTORE_PVC:
                monthly_cost = size_gb * filestore_rate
            else:
                monthly_cost = 0.0
            
            # Calculate cost for the specified duration
            duration_months = duration_days / 30.0
            total_cost = monthly_cost * duration_months
            
            logger.info(f"Storage cost calculation: {size_gb}GB * ${monthly_cost:.4f}/month * {duration_months:.2f} months = ${total_cost:.4f}")
            
            return round(total_cost, 4)
            
        except Exception as e:
            logger.error(f"Failed to calculate storage cost: {e}")
            return 0.0
    
    async def start_session_billing(self, session_id: str, user_id: str, 
                                  resource_tier: str = "small") -> Dict[str, Any]:
        """Start billing for a session"""
        try:
            # Get user's hourly rate
            user = await self.db.get_user(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            tier_limits = await self.db.get_user_tier_limits(UserType(user["user_type"]))
            hourly_rate = tier_limits.get("hourly_rate", 0.05)
            
            # Apply resource tier multiplier
            tier_multipliers = {
                "small": 1.0,
                "medium": 1.5,
                "large": 2.0,
                "gpu": 5.0
            }
            
            adjusted_hourly_rate = hourly_rate * tier_multipliers.get(resource_tier, 1.0)
            
            # Start billing
            billing_info = await self.db.start_session_billing(session_id, user_id, adjusted_hourly_rate)
            
            logger.info(f"Started billing for session {session_id}: ${adjusted_hourly_rate:.4f}/hour")
            
            return billing_info
            
        except Exception as e:
            logger.error(f"Failed to start session billing: {e}")
            raise
    
    async def stop_session_billing(self, session_id: str) -> Dict[str, Any]:
        """Stop billing for a session and calculate final cost"""
        try:
            # Get billing info
            billing_info = await self.db.get_session_billing_info(session_id)
            if not billing_info or billing_info["status"] != "active":
                raise ValueError(f"No active billing found for session {session_id}")
            
            # Calculate session duration
            start_time = billing_info["start_time"]
            end_time = datetime.now()
            duration = end_time - start_time
            total_hours = duration.total_seconds() / 3600.0
            
            # Stop billing and calculate cost
            await self.db.stop_session_billing(session_id, total_hours)
            
            # Get updated billing info
            updated_billing = await self.db.get_session_billing_info(session_id)
            
            logger.info(f"Stopped billing for session {session_id}: {total_hours:.2f} hours = ${updated_billing['total_cost']:.4f}")
            
            return updated_billing
            
        except Exception as e:
            logger.error(f"Failed to stop session billing: {e}")
            raise
    
    async def purchase_credits(self, user_id: str, amount_usd: float, 
                             payment_method: str = "stripe") -> Dict[str, Any]:
        """Purchase credits for a user"""
        try:
            # Get payment configuration
            payment_config = await self.db.get_payment_config()
            credit_config = payment_config.get("pricing", {}).get("credit_purchase", {})
            
            min_amount = credit_config.get("min_amount", 10.0)
            bonus_percent = credit_config.get("bonus_percent", 0)
            
            # Validate minimum amount
            if amount_usd < min_amount:
                raise ValueError(f"Minimum credit purchase amount is ${min_amount}")
            
            # Calculate credits (1 USD = 1 credit + bonus)
            base_credits = amount_usd
            bonus_credits = base_credits * (bonus_percent / 100.0)
            total_credits = base_credits + bonus_credits
            
            # Create transaction record
            transaction = await self.db.create_transaction(
                user_id, amount_usd, BillingType.CREDIT_PURCHASE,
                f"Credit purchase: ${amount_usd} ({total_credits:.2f} credits)",
                {
                    "payment_method": payment_method,
                    "base_credits": base_credits,
                    "bonus_credits": bonus_credits,
                    "total_credits": total_credits,
                    "bonus_percent": bonus_percent
                }
            )
            
            # Add credits to user account
            await self.db.add_credits(
                user_id, total_credits, "credit_purchase",
                f"Purchased ${amount_usd} worth of credits"
            )
            
            logger.info(f"Credit purchase for user {user_id}: ${amount_usd} = {total_credits:.2f} credits")
            
            return {
                "transaction_id": transaction["transaction_id"],
                "amount_usd": amount_usd,
                "total_credits": total_credits,
                "bonus_credits": bonus_credits,
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"Failed to purchase credits: {e}")
            raise
    
    async def check_user_credit_balance(self, user_id: str, required_amount: float) -> bool:
        """Check if user has sufficient credits for an operation"""
        try:
            current_credits = await self.db.get_user_credits(user_id)
            return current_credits >= required_amount
            
        except Exception as e:
            logger.error(f"Failed to check credit balance: {e}")
            return False
    
    async def get_user_billing_summary(self, user_id: str, 
                                     start_date: datetime = None, 
                                     end_date: datetime = None) -> Dict[str, Any]:
        """Get comprehensive billing summary for a user"""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now()
            
            # Get user info
            user = await self.db.get_user(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Get credit transactions
            credit_history = await self.db.get_credit_history(user_id, start_date, end_date)
            
            # Get billing transactions
            billing_transactions = await self.db.get_user_transactions(user_id, start_date, end_date)
            
            # Get usage statistics
            usage_stats = await self.db.get_user_usage(user_id, start_date, end_date)
            
            # Calculate totals
            total_credits_added = sum(t["amount"] for t in credit_history if t["transaction_type"] == "credit")
            total_credits_used = sum(t["amount"] for t in credit_history if t["transaction_type"] == "debit")
            current_balance = await self.db.get_user_credits(user_id)
            
            # Calculate costs by type
            costs_by_type = {}
            for transaction in billing_transactions:
                billing_type = transaction["billing_type"]
                if billing_type not in costs_by_type:
                    costs_by_type[billing_type] = 0.0
                costs_by_type[billing_type] += transaction["amount"]
            
            return {
                "user_id": user_id,
                "user_type": user["user_type"],
                "current_balance": current_balance,
                "period": {
                    "start": start_date,
                    "end": end_date
                },
                "credits": {
                    "total_added": total_credits_added,
                    "total_used": total_credits_used,
                    "net_change": total_credits_added - total_credits_used,
                    "current_balance": current_balance
                },
                "costs_by_type": costs_by_type,
                "total_spent": sum(costs_by_type.values()),
                "transaction_count": len(billing_transactions),
                "usage_stats": usage_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get billing summary: {e}")
            raise
    
    async def process_storage_creation_billing(self, user_id: str, storage_type: StorageType, 
                                             size_gb: int, duration_days: int = 30) -> Dict[str, Any]:
        """Process billing for storage creation"""
        try:
            # Calculate storage cost
            storage_cost = await self.calculate_storage_cost(storage_type, size_gb, duration_days)
            
            # Check if user has enough credits
            if not await self.check_user_credit_balance(user_id, storage_cost):
                raise ValueError(f"Insufficient credits. Required: ${storage_cost}")
            
            # Create transaction record
            transaction = await self.db.create_transaction(
                user_id, storage_cost, BillingType.STORAGE_CCREATION,
                f"Storage creation: {storage_type.value} ({size_gb}GB for {duration_days} days)",
                {
                    "storage_type": storage_type.value,
                    "size_gb": size_gb,
                    "duration_days": duration_days
                }
            )
            
            # Deduct credits
            await self.db.deduct_credits(
                user_id, storage_cost, f"Storage creation: {storage_type.value}",
                storage_resource_id=transaction["id"]
            )
            
            logger.info(f"Storage creation billing for user {user_id}: ${storage_cost}")
            
            return {
                "transaction_id": transaction["id"],
                "storage_type": storage_type.value,
                "size_gb": size_gb,
                "cost": storage_cost,
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"Failed to process storage creation billing: {e}")
            raise
    
    async def get_pricing_info(self) -> Dict[str, Any]:
        """Get current pricing information"""
        try:
            payment_config = await self.db.get_payment_config()
            
            # Get tier limits for hourly rates
            tier_limits = {}
            for user_type in UserType:
                limits = await self.db.get_user_tier_limits(user_type)
                tier_limits[user_type.value] = {
                    "hourly_rate": limits.get("hourly_rate", 0.05),
                    "credit_bonus": limits.get("credit_bonus", 0.0),
                    "max_buckets": limits.get("max_buckets", 1),
                    "max_filestores": limits.get("max_filestores", 1),
                    "max_total_storage_gb": limits.get("max_total_storage_gb", 50)
                }
            
            return {
                "pricing": payment_config.get("pricing", {}),
                "billing": payment_config.get("billing", {}),
                "limits": payment_config.get("limits", {}),
                "tier_limits": tier_limits
            }
            
        except Exception as e:
            logger.error(f"Failed to get pricing info: {e}")
            raise
    
    async def refund_transaction(self, transaction_id: str, reason: str) -> bool:
        """Refund a transaction"""
        try:
            # Get transaction details
            # Note: This would need to be implemented in the database interface
            # For now, we'll just update the status
            
            await self.db.update_transaction_status(transaction_id, PaymentStatus.REFUNDED)
            
            logger.info(f"Refunded transaction {transaction_id}: {reason}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to refund transaction: {e}")
            return False
