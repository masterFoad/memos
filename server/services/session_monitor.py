"""
Session Monitor Service - Auto-kill sessions that exceed limits
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

from server.database.factory import get_database_client
from server.services.billing_service import BillingService
from server.services.sessions.manager import sessions_manager

logger = logging.getLogger(__name__)

@dataclass
class SessionLimit:
    """Session limits configuration"""
    max_duration_hours: float = 24.0  # Default 24 hours
    max_cost_usd: float = 100.0       # Default $100 max
    check_interval_minutes: int = 5   # Check every 5 minutes

class SessionMonitor:
    """Monitors active sessions and enforces limits"""
    
    def __init__(self):
        self.db = None
        self.billing_service = None
        self.running = False
        self.monitor_task = None
        self.limits = SessionLimit()
    
    async def _ensure_connected(self):
        """Ensure database and billing service are connected"""
        if self.db is None:
            self.db = get_database_client()
            await self.db.connect()
        if self.billing_service is None:
            self.billing_service = BillingService()
    
    async def start_monitoring(self):
        """Start the session monitoring loop"""
        if self.running:
            logger.warning("Session monitor is already running")
            return
        
        try:
            # Ensure database connection
            await self._ensure_connected()
            
            self.running = True
            self.monitor_task = asyncio.create_task(self._monitor_loop())
            logger.info("Session monitor started successfully")
        except Exception as e:
            logger.error(f"Failed to start session monitor: {e}")
            self.running = False
            raise
    
    async def stop_monitoring(self):
        """Stop the session monitoring loop"""
        self.running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Session monitor stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        await self._ensure_connected()
        
        while self.running:
            try:
                await self._check_all_sessions()
                await asyncio.sleep(self.limits.check_interval_minutes * 60)
            except Exception as e:
                logger.error(f"Error in session monitor loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def _check_all_sessions(self):
        """Check all active sessions for limit violations"""
        try:
            # Get all active sessions
            active_sessions = await self._get_active_sessions()
            
            for session in active_sessions:
                await self._check_session_limits(session)
                
        except Exception as e:
            logger.error(f"Error checking sessions: {e}")
    
    async def _get_active_sessions(self) -> List[Dict]:
        """Get all active sessions from database"""
        try:
            query = """
                SELECT s.*, w.user_id, sb.start_time, sb.hourly_rate
                FROM sessions s
                JOIN workspaces w ON s.workspace_id = w.workspace_id
                LEFT JOIN session_billing sb ON s.session_id = sb.session_id
                WHERE s.status = 'active' AND sb.status = 'active'
            """
            sessions = await self.db._execute_query(query)
            if sessions:
                logger.debug(f"Found {len(sessions)} active sessions to monitor")
            return sessions
        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return []
    
    async def _check_session_limits(self, session: Dict):
        """Check if a session exceeds limits and kill if necessary"""
        session_id = session["session_id"]
        user_id = session["user_id"]
        start_time = session["start_time"]
        hourly_rate = session["hourly_rate"]
        
        try:
            # Check duration limit
            if await self._check_duration_limit(session_id, start_time):
                await self._kill_session(session_id, user_id, "duration_limit_exceeded")
                return
            
            # Check cost limit
            if await self._check_cost_limit(session_id, start_time, hourly_rate):
                await self._kill_session(session_id, user_id, "cost_limit_exceeded")
                return
            
            # Check user credits
            if await self._check_credit_limit(user_id, session_id, start_time, hourly_rate):
                await self._kill_session(session_id, user_id, "insufficient_credits")
                return
                
        except Exception as e:
            logger.error(f"Error checking limits for session {session_id}: {e}")
    
    async def _check_duration_limit(self, session_id: str, start_time: datetime) -> bool:
        """Check if session exceeds maximum duration"""
        if not start_time:
            return False
        
        duration = datetime.now() - start_time
        max_duration = timedelta(hours=self.limits.max_duration_hours)
        
        if duration > max_duration:
            logger.warning(f"Session {session_id} exceeded duration limit: {duration} > {max_duration}")
            return True
        
        return False
    
    async def _check_cost_limit(self, session_id: str, start_time: datetime, hourly_rate: float) -> bool:
        """Check if session exceeds maximum cost"""
        if not start_time:
            return False
        
        duration = datetime.now() - start_time
        hours_used = duration.total_seconds() / 3600.0
        current_cost = hours_used * hourly_rate
        
        if current_cost > self.limits.max_cost_usd:
            logger.warning(f"Session {session_id} exceeded cost limit: ${current_cost:.2f} > ${self.limits.max_cost_usd}")
            return True
        
        return False
    
    async def _check_credit_limit(self, user_id: str, session_id: str, start_time: datetime, hourly_rate: float) -> bool:
        """Check if user has sufficient credits for continued usage"""
        try:
            # Get user's current credits
            current_credits = await self.db.get_user_credits(user_id)
            
            # Calculate cost for next hour
            if current_credits < hourly_rate:
                logger.warning(f"User {user_id} has insufficient credits for session {session_id}: ${current_credits:.2f} < ${hourly_rate:.2f}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking credit limit for user {user_id}: {e}")
            return False
    
    async def _kill_session(self, session_id: str, user_id: str, reason: str):
        """Kill a session and log the reason"""
        try:
            logger.warning(f"Killing session {session_id} for user {user_id}: {reason}")
            
            # Stop session billing and calculate final cost
            final_billing = await self.billing_service.stop_session_billing(session_id)
            
            # Delete the session
            success = await sessions_manager.delete_session(session_id)
            
            if success:
                logger.info(f"Successfully killed session {session_id}")
                
                # Send notification to user (if WebSocket is active)
                await self._notify_user_session_killed(user_id, session_id, reason)
            else:
                logger.error(f"Failed to kill session {session_id}")
                
        except Exception as e:
            logger.error(f"Error killing session {session_id}: {e}")
    
    async def _notify_user_session_killed(self, user_id: str, session_id: str, reason: str):
        """Notify user that their session was killed"""
        # TODO: Implement WebSocket notification
        # This would send a message to any active WebSocket connections for this user
        logger.info(f"User {user_id} session {session_id} killed: {reason}")

# Global session monitor instance
session_monitor = SessionMonitor()