"""
Session Monitor Service - Auto-kill sessions that exceed limits
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from server.database.factory import get_database_client
from server.services.billing_service import BillingService
from server.services.sessions.manager import sessions_manager

logger = logging.getLogger(__name__)

@dataclass
class SessionLimit:
    """Session limits configuration - ONLY for truly stale/problematic sessions"""
    max_duration_hours: float = 48.0      # Very generous 48 hours (2 days)
    max_cost_usd: float = 500.0           # Very generous $500 max
    check_interval_minutes: int = 30      # Check every 30 minutes (less aggressive)
    min_session_age_minutes: int = 60     # Don't touch sessions younger than 1 hour
    grace_period_minutes: int = 15        # Grace period before killing


class SessionMonitor:
    """Monitors active sessions and enforces limits"""

    def __init__(self):
        self.db = None
        self.billing_service = None
        self.running = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.limits = SessionLimit()

    # ---------------- internals ---------------- #

    async def _ensure_connected(self):
        """Ensure database and billing service are connected"""
        if self.db is None:
            self.db = get_database_client()
            await self.db.connect()
        if self.billing_service is None:
            self.billing_service = BillingService()

    def _now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def _as_utc(self, dt_like: Any) -> Optional[datetime]:
        """Coerce DB value (str | datetime | None) to aware UTC datetime."""
        if dt_like is None:
            return None
        if isinstance(dt_like, datetime):
            if dt_like.tzinfo is None:
                # assume UTC if naive
                return dt_like.replace(tzinfo=timezone.utc)
            return dt_like.astimezone(timezone.utc)
        # try parse string (ISO)
        try:
            # Python handles Z-less ISO; add UTC if naive
            parsed = datetime.fromisoformat(str(dt_like).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            return None

    def _to_float(self, val: Any, default: float = 0.0) -> float:
        try:
            f = float(val)
            if f != f or f is None:  # NaN check
                return default
            return f
        except Exception:
            return default

    # ---------------- lifecycle ---------------- #

    async def start_monitoring(self):
        """Start the session monitoring loop"""
        if self.running:
            logger.warning("Session monitor is already running")
            return

        try:
            await self._ensure_connected()
            self.running = True
            # if a previous task exists but finished, replace it
            if self.monitor_task and self.monitor_task.done():
                self.monitor_task = None
            self.monitor_task = asyncio.create_task(self._monitor_loop(), name="session-monitor-loop")
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
            finally:
                self.monitor_task = None
        logger.info("Session monitor stopped")

    # ---------------- main loop ---------------- #

    async def _monitor_loop(self):
        """Main monitoring loop"""
        await self._ensure_connected()

        interval = max(1, int(self.limits.check_interval_minutes)) * 60
        while self.running:
            try:
                await self._check_all_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session monitor loop: {e}")
                # fall through to sleep
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break

    async def _check_all_sessions(self):
        """Check all active sessions for limit violations"""
        try:
            active_sessions = await self._get_active_sessions()
            for session in active_sessions:
                # Each session checked sequentially to avoid stampedes
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
                WHERE s.status = 'active' AND (sb.status = 'active' OR sb.status IS NULL)
            """
            sessions = await self.db._execute_query(query)
            if sessions:
                logger.debug(f"Found {len(sessions)} active sessions to monitor")
            return sessions or []
        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return []

    async def _check_session_limits(self, session: Dict):
        """Check if a session is truly stale/problematic and needs cleanup"""
        session_id = session.get("session_id")
        user_id = session.get("user_id")
        start_time = self._as_utc(session.get("start_time"))
        hourly_rate = self._to_float(session.get("hourly_rate"), default=0.05)

        if not session_id or not user_id:
            return  # skip malformed rows

        try:
            # 1) Too young? (avoid touching fresh sessions)
            if not await self._is_session_old_enough(session_id, start_time):
                logger.debug(f"⏳ Session {session_id} is too young to monitor, skipping")
                return

            # 2) Orphaned? (not running in any provider)
            if not await self._is_session_actually_running(session_id):
                logger.warning(f"👻 Session {session_id} is orphaned (not running in any provider), cleaning up")
                await self._kill_session(session_id, user_id, "orphaned_session")
                return

            # 3) Extreme duration
            if await self._check_extreme_duration_limit(session_id, start_time):
                await self._kill_session(session_id, user_id, "extreme_duration_exceeded")
                return

            # 4) Extreme cost
            if await self._check_extreme_cost_limit(session_id, start_time, hourly_rate):
                await self._kill_session(session_id, user_id, "extreme_cost_exceeded")
                return

            # 5) ZERO credits (or critically low)
            if await self._check_zero_credits(user_id, session_id):
                await self._kill_session(session_id, user_id, "zero_credits")
                return

        except Exception as e:
            logger.error(f"Error checking limits for session {session_id}: {e}")

    # ---------------- checks ---------------- #

    async def _is_session_old_enough(self, session_id: str, start_time: Optional[datetime]) -> bool:
        """Check if session is old enough to be monitored (avoid touching fresh sessions)"""
        if not start_time:
            return False
        age = self._now_utc() - start_time
        return age >= timedelta(minutes=self.limits.min_session_age_minutes)

    async def _is_session_actually_running(self, session_id: str) -> bool:
        """Check if session actually exists in any provider (detect orphaned sessions)"""
        try:
            # sessions_manager.get_session returns a dict or None
            session_info = await sessions_manager.get_session(session_id)
            return session_info is not None
        except Exception as e:
            logger.error(f"Error checking if session {session_id} is running: {e}")
            # Assume running if we can't check to avoid accidental kills
            return True

    async def _check_extreme_duration_limit(self, session_id: str, start_time: Optional[datetime]) -> bool:
        """Check if session exceeds EXTREME duration (48+ hours)"""
        if not start_time:
            return False
        duration = self._now_utc() - start_time
        max_duration = timedelta(hours=self.limits.max_duration_hours)
        if duration > max_duration:
            logger.warning(f"🚨 Session {session_id} exceeded EXTREME duration limit: {duration} > {max_duration}")
            return True
        return False

    async def _check_extreme_cost_limit(self, session_id: str, start_time: Optional[datetime], hourly_rate: float) -> bool:
        """Check if session exceeds EXTREME cost ($500+)"""
        if not start_time:
            return False
        hours_used = (self._now_utc() - start_time).total_seconds() / 3600.0
        # defend against garbage rates
        hourly_rate = max(0.0, min(hourly_rate, 1000.0))
        current_cost = hours_used * hourly_rate
        if current_cost > self.limits.max_cost_usd:
            logger.warning(f"🚨 Session {session_id} exceeded EXTREME cost limit: ${current_cost:.2f} > ${self.limits.max_cost_usd}")
            return True
        return False

    async def _check_zero_credits(self, user_id: str, session_id: str) -> bool:
        """Check if user has ZERO credits with intelligent warning system"""
        try:
            current_credits = self._to_float(await self.db.get_user_credits(user_id), default=0.0)

            # Get session hourly rate (fallback to conservative default)
            try:
                query = """
                    SELECT hourly_rate FROM session_billing
                    WHERE session_id = ? AND status = 'active'
                    LIMIT 1
                """
                billing_info = await self.db._execute_query(query, (session_id,))
                hourly_rate = self._to_float((billing_info or [{}])[0].get("hourly_rate"), default=0.05)
            except Exception:
                hourly_rate = 0.05

            if current_credits <= 0.0:
                logger.warning(f"🚨 User {user_id} has ZERO credits for session {session_id}: ${current_credits:.2f}")
                return True

            if current_credits < hourly_rate:
                logger.warning(f"⚠️  User {user_id} has LOW credits for session {session_id}: ${current_credits:.2f} < ${hourly_rate:.2f}/hour")
                # Only kill if critically low (<6 minutes left)
                if current_credits < (hourly_rate * 0.1):
                    logger.warning(f"🚨 User {user_id} credits CRITICALLY LOW: ${current_credits:.2f}")
                    return True
                else:
                    logger.info(f"💳 User {user_id} has low credits but still some time left: ${current_credits:.2f}")
                    return False

            logger.debug(f"💰 User {user_id} has sufficient credits: ${current_credits:.2f}")
            return False

        except Exception as e:
            logger.error(f"Error checking credits for user {user_id}: {e}")
            return False

    # ---------------- kill/notify ---------------- #

    async def _kill_session(self, session_id: str, user_id: str, reason: str):
        """Kill a session with EXTREME care and multiple safety checks"""
        try:
            logger.warning(f"🔪 Session Monitor: CONSIDERING killing session {session_id} for user {user_id}: {reason}")

            # Confirm still exists
            session_info = await sessions_manager.get_session(session_id)
            if not session_info:
                logger.info(f"⚠️  Session {session_id} no longer exists, ABORTING kill operation")
                return

            # Respect grace period for non-orphans
            if reason != "orphaned_session":
                created_at_val = (session_info.get("created_at") if isinstance(session_info, dict)
                                  else getattr(session_info, "created_at", None))
                created_at = self._as_utc(created_at_val)
                if created_at:
                    session_age = self._now_utc() - created_at
                    if session_age < timedelta(minutes=self.limits.grace_period_minutes):
                        logger.info(f"⚠️  Session {session_id} is too young ({session_age}), ABORTING kill")
                        return

            logger.warning(f"🚨 Session Monitor: PROCEEDING with kill for session {session_id}: {reason}")

            # Stop billing (best-effort)
            try:
                final_billing = await self.billing_service.stop_session_billing(session_id)
                logger.info(f"💰 Stopped billing for session {session_id}: {final_billing}")
            except Exception as e:
                logger.error(f"💰 Error stopping billing for session {session_id}: {e}")

            # Delete the session
            success = await sessions_manager.delete_session(session_id)

            if success:
                logger.warning(f"🔪 Successfully killed session {session_id} due to: {reason}")
                await self._notify_user_session_killed(user_id, session_id, reason)
            else:
                logger.error(f"❌ Failed to kill session {session_id}")

        except Exception as e:
            logger.error(f"💥 Error in kill operation for session {session_id}: {e}")
            import traceback
            logger.error(f"💥 TRACEBACK: {traceback.format_exc()}")

    async def _notify_user_session_killed(self, user_id: str, session_id: str, reason: str):
        """Notify user that their session was killed"""
        # TODO: Implement WebSocket notification hook
        logger.info(f"User {user_id} session {session_id} killed: {reason}")


# Global session monitor instance
session_monitor = SessionMonitor()
