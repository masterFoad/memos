"""
SQLite Database Client for OnMemOS v3 Development
Production-ready SQLite implementation for development environment
"""

import aiosqlite
import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import json

from .base import (
    CompleteDatabaseInterface,
    UserType,
    StorageType,
    PaymentStatus,
    BillingType
)

logger = logging.getLogger(__name__)

class SQLiteTempClient(CompleteDatabaseInterface):
    """
    SQLite database client for development environment
    Implements all database interfaces with production-ready features
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize SQLite client
        
        Args:
            db_path: Path to SQLite database file. If None, uses default location
        """
        if db_path is None:
            # Default to project directory
            project_dir = Path(__file__).parent.parent.parent
            db_path = project_dir / "data" / "onmemos_dev.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        
        logger.info(f"SQLite client initialized with database: {self.db_path}")
    
    async def connect(self) -> bool:
        """Connect to SQLite database and initialize tables"""
        try:
            async with self._lock:
                self._connection = await aiosqlite.connect(str(self.db_path))
                self._connection.row_factory = aiosqlite.Row
                
                # Initialize database schema
                await self._create_tables()
                
                logger.info(f"Connected to SQLite database: {self.db_path}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to connect to SQLite database: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from SQLite database"""
        try:
            async with self._lock:
                if self._connection:
                    await self._connection.close()
                    self._connection = None
                    logger.info("Disconnected from SQLite database")
                return True
        except Exception as e:
            logger.error(f"Error disconnecting from SQLite database: {e}")
            return False
    
    async def _create_tables(self):
        """Create all database tables with proper constraints"""
        tables = [
            # Users table
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                user_type TEXT NOT NULL DEFAULT 'free',
                credits REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            
            # Passports table
            """
            CREATE TABLE IF NOT EXISTS passports (
                passport_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                passport_key TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                permissions TEXT,  -- JSON string
                is_active BOOLEAN DEFAULT TRUE,
                last_used TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """,
            
            # Credit transactions table
            """
            CREATE TABLE IF NOT EXISTS credit_transactions (
                transaction_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                amount REAL NOT NULL,
                source TEXT NOT NULL,
                description TEXT,
                session_id TEXT,
                storage_resource_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """,
            
            # Billing transactions table
            """
            CREATE TABLE IF NOT EXISTS billing_transactions (
                transaction_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                amount REAL NOT NULL,
                billing_type TEXT NOT NULL,
                description TEXT NOT NULL,
                metadata TEXT,  -- JSON string
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """,
            
            # Session billing table
            """
            CREATE TABLE IF NOT EXISTS session_billing (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                hourly_rate REAL NOT NULL,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                total_hours REAL,
                total_cost REAL,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """,
            
            # Service accounts table
            """
            CREATE TABLE IF NOT EXISTS service_accounts (
                user_id TEXT PRIMARY KEY,
                service_account_email TEXT NOT NULL,
                gcp_project_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """,
            
            # Storage resources table
            """
            CREATE TABLE IF NOT EXISTS storage_resources (
                resource_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                storage_type TEXT NOT NULL,
                resource_name TEXT NOT NULL,
                size_gb INTEGER DEFAULT 10,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """,
            
            # Workspaces table
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                workspace_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                resource_package TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """,
            
            # Sessions table
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                storage_config TEXT,  -- JSON string
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
            )
            """,
            
            # Usage tracking table
            """
            CREATE TABLE IF NOT EXISTS usage_tracking (
                tracking_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                usage_gb REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """,
            
            # Spaces table
            """
            CREATE TABLE IF NOT EXISTS spaces (
                space_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                size_gb INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                is_public BOOLEAN DEFAULT TRUE,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            
            # User spaces table (purchased spaces)
            """
            CREATE TABLE IF NOT EXISTS user_spaces (
                user_space_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                space_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                instance_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (space_id) REFERENCES spaces(space_id) ON DELETE CASCADE,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
            )
            """
        ]
        
        for table_sql in tables:
            await self._connection.execute(table_sql)
        
        await self._connection.commit()
        logger.info("Database tables created successfully")
    
    async def _execute_query(self, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """Execute a query and return results as list of dictionaries"""
        async with self._lock:
            cursor = await self._connection.execute(query, params)
            rows = await cursor.fetchall()
            return [self._convert_datetime_fields(dict(row)) for row in rows]
    
    async def _execute_single(self, query: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute a query and return single result"""
        async with self._lock:
            cursor = await self._connection.execute(query, params)
            row = await cursor.fetchone()
            return self._convert_datetime_fields(dict(row)) if row else None
    
    async def _execute_update(self, query: str, params: Tuple = ()) -> bool:
        """Execute an update/insert query"""
        try:
            async with self._lock:
                await self._connection.execute(query, params)
                await self._connection.commit()
                return True
        except Exception as e:
            logger.error(f"Database update failed: {e}")
            return False
    
    def _convert_datetime_fields(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert datetime string fields to datetime objects and parse JSON fields"""
        datetime_fields = [
            'created_at', 'updated_at', 'start_time', 'end_time', 'timestamp', 'last_used'
        ]
        
        json_fields = ['permissions', 'metadata', 'storage_config']
        
        for field in datetime_fields:
            if field in row and row[field] and isinstance(row[field], str):
                try:
                    # Handle different datetime formats
                    if 'T' in row[field]:
                        # ISO format with T
                        row[field] = datetime.fromisoformat(row[field].replace('Z', '+00:00'))
                    else:
                        # SQLite format: YYYY-MM-DD HH:MM:SS
                        row[field] = datetime.strptime(row[field], '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    # Keep as string if conversion fails
                    pass
        
        for field in json_fields:
            if field in row and row[field] and isinstance(row[field], str):
                try:
                    # Handle both list and dict JSON strings
                    if row[field].startswith('[') or row[field].startswith('{'):
                        row[field] = json.loads(row[field])
                    else:
                        # Handle legacy format where lists were stored as string representation
                        row[field] = eval(row[field]) if row[field] != '[]' else []
                except (ValueError, TypeError, SyntaxError):
                    # Keep as string if parsing fails
                    pass
        
        return row
    
    # ============================================================================
    # DatabaseInterface Implementation
    # ============================================================================
    
    async def create_user(self, user_id: str, email: str, user_type: UserType = UserType.FREE, 
                         name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new user"""
        try:
            # Set initial credits based on user type
            initial_credits = 5.0 if user_type == UserType.FREE else 0.0
            
            query = """
                INSERT INTO users (user_id, email, name, user_type, credits)
                VALUES (?, ?, ?, ?, ?)
            """
            success = await self._execute_update(query, (user_id, email, name, user_type.value, initial_credits))
            
            if success:
                user = await self.get_user(user_id)
                # Add 'id' field to match expected format
                if user:
                    user['id'] = user['user_id']
                return user
            else:
                raise Exception("Failed to create user")
                
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise
    
    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            query = "SELECT * FROM users WHERE user_id = ?"
            return await self._execute_single(query, (user_id,))
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None
    
    async def update_user(self, user_id: str, **kwargs) -> bool:
        """Update user information"""
        try:
            if not kwargs:
                return True
            
            # Build dynamic update query
            set_clauses = []
            params = []
            
            for key, value in kwargs.items():
                if key in ['email', 'name', 'user_type', 'credits']:
                    set_clauses.append(f"{key} = ?")
                    params.append(value)
            
            if not set_clauses:
                return True
            
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            params.append(user_id)
            
            query = f"UPDATE users SET {', '.join(set_clauses)} WHERE user_id = ?"
            return await self._execute_update(query, tuple(params))
            
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return False
    
    async def delete_user(self, user_id: str) -> bool:
        """Delete user"""
        try:
            query = "DELETE FROM users WHERE user_id = ?"
            return await self._execute_update(query, (user_id,))
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False
    
    # ============================================================================
    # PassportInterface Implementation
    # ============================================================================
    
    async def create_passport(self, user_id: str, name: str, permissions: List[str] = None) -> Dict[str, Any]:
        """Create a passport (API key) for a user"""
        try:
            passport_id = str(uuid.uuid4())
            passport_key = str(uuid.uuid4()).replace('-', '')
            
            # Convert permissions to JSON string
            permissions_json = json.dumps(permissions) if permissions else '[]'
            
            query = """
                INSERT INTO passports (passport_id, user_id, passport_key, name, permissions)
                VALUES (?, ?, ?, ?, ?)
            """
            success = await self._execute_update(query, (passport_id, user_id, passport_key, name, permissions_json))
            
            if success:
                return await self.get_passport(passport_id)
            else:
                raise Exception("Failed to create passport")
                
        except Exception as e:
            logger.error(f"Error creating passport: {e}")
            raise
    
    async def get_passport(self, passport_id: str) -> Optional[Dict[str, Any]]:
        """Get passport by ID"""
        try:
            query = "SELECT * FROM passports WHERE passport_id = ?"
            return await self._execute_single(query, (passport_id,))
        except Exception as e:
            logger.error(f"Error getting passport: {e}")
            return None
    
    async def get_user_passports(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all passports for a user"""
        try:
            query = "SELECT * FROM passports WHERE user_id = ? AND is_active = TRUE"
            return await self._execute_query(query, (user_id,))
        except Exception as e:
            logger.error(f"Error getting user passports: {e}")
            return []
    
    async def validate_passport(self, passport_key: str) -> Optional[Dict[str, Any]]:
        """Validate a passport key and return user info"""
        try:
            query = """
                SELECT p.*, u.* FROM passports p
                JOIN users u ON p.user_id = u.user_id
                WHERE p.passport_key = ? AND p.is_active = TRUE
            """
            result = await self._execute_single(query, (passport_key,))
            
            if result:
                # Update last_used timestamp
                await self._execute_update(
                    "UPDATE passports SET last_used = CURRENT_TIMESTAMP WHERE passport_key = ?",
                    (passport_key,)
                )
            
            return result
        except Exception as e:
            logger.error(f"Error validating passport: {e}")
            return None
    
    async def revoke_passport(self, passport_id: str) -> bool:
        """Revoke a passport"""
        try:
            query = "UPDATE passports SET is_active = FALSE WHERE passport_id = ?"
            return await self._execute_update(query, (passport_id,))
        except Exception as e:
            logger.error(f"Error revoking passport: {e}")
            return False
    
    # ============================================================================
    # CreditInterface Implementation
    # ============================================================================
    
    async def get_user_credits(self, user_id: str) -> float:
        """Get user's current credit balance"""
        try:
            query = "SELECT credits FROM users WHERE user_id = ?"
            result = await self._execute_single(query, (user_id,))
            return result['credits'] if result else 0.0
        except Exception as e:
            logger.error(f"Error getting user credits: {e}")
            return 0.0
    
    async def add_credits(self, user_id: str, amount: float, source: str, 
                         description: str = None) -> bool:
        """Add credits to user account"""
        try:
            # Start transaction
            async with self._lock:
                # Update user credits
                query = "UPDATE users SET credits = credits + ? WHERE user_id = ?"
                await self._connection.execute(query, (amount, user_id))
                
                # Record transaction
                transaction_id = str(uuid.uuid4())
                query = """
                    INSERT INTO credit_transactions (transaction_id, user_id, amount, source, description)
                    VALUES (?, ?, ?, ?, ?)
                """
                await self._connection.execute(query, (transaction_id, user_id, amount, source, description))
                
                await self._connection.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error adding credits: {e}")
            return False
    
    async def deduct_credits(self, user_id: str, amount: float, reason: str, 
                           session_id: str = None, storage_resource_id: str = None) -> bool:
        """Deduct credits from user account"""
        try:
            # Check if user has enough credits
            current_credits = await self.get_user_credits(user_id)
            if current_credits < amount:
                logger.warning(f"Insufficient credits for user {user_id}: {current_credits} < {amount}")
                return False
            
            # Start transaction
            async with self._lock:
                # Update user credits
                query = "UPDATE users SET credits = credits - ? WHERE user_id = ?"
                await self._connection.execute(query, (amount, user_id))
                
                # Record transaction (negative amount for deduction)
                transaction_id = str(uuid.uuid4())
                query = """
                    INSERT INTO credit_transactions 
                    (transaction_id, user_id, amount, source, description, session_id, storage_resource_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                await self._connection.execute(query, (transaction_id, user_id, -amount, reason, reason, session_id, storage_resource_id))
                
                await self._connection.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error deducting credits: {e}")
            return False
    
    async def get_credit_history(self, user_id: str, start_date: datetime = None, 
                               end_date: datetime = None) -> List[Dict[str, Any]]:
        """Get user's credit transaction history"""
        try:
            query = "SELECT * FROM credit_transactions WHERE user_id = ?"
            params = [user_id]
            
            if start_date:
                query += " AND created_at >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                query += " AND created_at <= ?"
                params.append(end_date.isoformat())
            
            query += " ORDER BY created_at DESC"
            results = await self._execute_query(query, tuple(params))
            
            # Add transaction_type field based on amount
            for result in results:
                if result['amount'] > 0:
                    result['transaction_type'] = 'credit'
                else:
                    result['transaction_type'] = 'debit'
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting credit history: {e}")
            return []
    
    # ============================================================================
    # PaymentConfigInterface Implementation
    # ============================================================================
    
    async def get_payment_config(self) -> Dict[str, Any]:
        """Get payment configuration"""
        # For development, return default configuration
        return {
            "session_rates": {
                "free": 0.05,
                "pro": 0.025,
                "enterprise": 0.01,
                "admin": 0.0
            },
            "storage_limits": {
                "free": {"buckets": 1, "filestores": 1},
                "pro": {"buckets": 5, "filestores": 3},
                "enterprise": {"buckets": 100, "filestores": 50},
                "admin": {"buckets": -1, "filestores": -1}  # Unlimited
            },
            "credit_bonus": {
                "free": 5.0,
                "pro": 0.0,
                "enterprise": 0.0,
                "admin": 0.0
            }
        }
    
    async def update_payment_config(self, config: Dict[str, Any]) -> bool:
        """Update payment configuration"""
        # For development, just log the update
        logger.info(f"Payment config updated: {config}")
        return True
    
    # ============================================================================
    # BillingInterface Implementation
    # ============================================================================
    
    async def create_transaction(self, user_id: str, amount: float, billing_type: BillingType,
                               description: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a billing transaction"""
        try:
            transaction_id = str(uuid.uuid4())
            metadata_json = json.dumps(metadata) if metadata else None
            
            query = """
                INSERT INTO billing_transactions 
                (transaction_id, user_id, amount, billing_type, description, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            success = await self._execute_update(query, (transaction_id, user_id, amount, billing_type.value, description, metadata_json))
            
            if success:
                return await self._execute_single("SELECT * FROM billing_transactions WHERE transaction_id = ?", (transaction_id,))
            else:
                raise Exception("Failed to create transaction")
                
        except Exception as e:
            logger.error(f"Error creating transaction: {e}")
            raise
    
    async def get_user_transactions(self, user_id: str, start_date: datetime = None,
                                  end_date: datetime = None) -> List[Dict[str, Any]]:
        """Get user's transaction history"""
        try:
            query = "SELECT * FROM billing_transactions WHERE user_id = ?"
            params = [user_id]
            
            if start_date:
                query += " AND created_at >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                query += " AND created_at <= ?"
                params.append(end_date.isoformat())
            
            query += " ORDER BY created_at DESC"
            return await self._execute_query(query, tuple(params))
            
        except Exception as e:
            logger.error(f"Error getting user transactions: {e}")
            return []
    
    async def update_transaction_status(self, transaction_id: str, status: PaymentStatus) -> bool:
        """Update transaction status"""
        try:
            query = """
                UPDATE billing_transactions 
                SET status = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE transaction_id = ?
            """
            return await self._execute_update(query, (status.value, transaction_id))
        except Exception as e:
            logger.error(f"Error updating transaction status: {e}")
            return False
    
    # ============================================================================
    # SessionBillingInterface Implementation
    # ============================================================================
    
    async def start_session_billing(self, session_id: str, user_id: str, 
                                  hourly_rate: float) -> Dict[str, Any]:
        """Start billing for a session"""
        try:
            query = """
                INSERT INTO session_billing (session_id, user_id, hourly_rate)
                VALUES (?, ?, ?)
            """
            success = await self._execute_update(query, (session_id, user_id, hourly_rate))
            
            if success:
                return await self.get_session_billing_info(session_id)
            else:
                raise Exception("Failed to start session billing")
                
        except Exception as e:
            logger.error(f"Error starting session billing: {e}")
            raise
    
    async def stop_session_billing(self, session_id: str, total_hours: float) -> bool:
        """Stop billing for a session and calculate final cost"""
        try:
            # Get session billing info
            billing_info = await self.get_session_billing_info(session_id)
            if not billing_info:
                return False
            
            hourly_rate = billing_info['hourly_rate']
            total_cost = hourly_rate * total_hours
            
            query = """
                UPDATE session_billing 
                SET end_time = CURRENT_TIMESTAMP, total_hours = ?, total_cost = ?, status = 'completed'
                WHERE session_id = ?
            """
            return await self._execute_update(query, (total_hours, total_cost, session_id))
            
        except Exception as e:
            logger.error(f"Error stopping session billing: {e}")
            return False
    
    async def get_session_billing_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get billing information for a session"""
        try:
            query = "SELECT * FROM session_billing WHERE session_id = ?"
            return await self._execute_single(query, (session_id,))
        except Exception as e:
            logger.error(f"Error getting session billing info: {e}")
            return None
    
    # ============================================================================
    # ServiceAccountInterface Implementation
    # ============================================================================
    
    async def create_service_account(self, user_id: str, service_account_email: str, 
                                   gcp_project_id: str) -> Dict[str, Any]:
        """Create a service account for a user"""
        try:
            query = """
                INSERT INTO service_accounts (user_id, service_account_email, gcp_project_id)
                VALUES (?, ?, ?)
            """
            success = await self._execute_update(query, (user_id, service_account_email, gcp_project_id))
            
            if success:
                return await self.get_service_account(user_id)
            else:
                raise Exception("Failed to create service account")
                
        except Exception as e:
            logger.error(f"Error creating service account: {e}")
            raise
    
    async def get_service_account(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get service account for a user"""
        try:
            query = "SELECT * FROM service_accounts WHERE user_id = ?"
            return await self._execute_single(query, (user_id,))
        except Exception as e:
            logger.error(f"Error getting service account: {e}")
            return None
    
    async def update_service_account(self, user_id: str, **kwargs) -> bool:
        """Update service account information"""
        try:
            if not kwargs:
                return True
            
            # Build dynamic update query
            set_clauses = []
            params = []
            
            for key, value in kwargs.items():
                if key in ['service_account_email', 'gcp_project_id']:
                    set_clauses.append(f"{key} = ?")
                    params.append(value)
            
            if not set_clauses:
                return True
            
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            params.append(user_id)
            
            query = f"UPDATE service_accounts SET {', '.join(set_clauses)} WHERE user_id = ?"
            return await self._execute_update(query, tuple(params))
            
        except Exception as e:
            logger.error(f"Error updating service account: {e}")
            return False
    
    # ============================================================================
    # StorageInterface Implementation
    # ============================================================================
    
    async def create_storage_resource(self, user_id: str, storage_type: StorageType, 
                                    resource_name: str, size_gb: int = 10) -> Dict[str, Any]:
        """Create a storage resource (bucket or filestore) for a user"""
        try:
            resource_id = str(uuid.uuid4())
            
            query = """
                INSERT INTO storage_resources (resource_id, user_id, storage_type, resource_name, size_gb)
                VALUES (?, ?, ?, ?, ?)
            """
            success = await self._execute_update(query, (resource_id, user_id, storage_type.value, resource_name, size_gb))
            
            if success:
                return await self._execute_single("SELECT * FROM storage_resources WHERE resource_id = ?", (resource_id,))
            else:
                raise Exception("Failed to create storage resource")
                
        except Exception as e:
            logger.error(f"Error creating storage resource: {e}")
            raise
    
    async def get_user_storage_resources(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all storage resources for a user"""
        try:
            query = "SELECT * FROM storage_resources WHERE user_id = ?"
            return await self._execute_query(query, (user_id,))
        except Exception as e:
            logger.error(f"Error getting user storage resources: {e}")
            return []
    
    async def delete_storage_resource(self, resource_id: str) -> bool:
        """Delete a storage resource"""
        try:
            query = "DELETE FROM storage_resources WHERE resource_id = ?"
            return await self._execute_update(query, (resource_id,))
        except Exception as e:
            logger.error(f"Error deleting storage resource: {e}")
            return False
    
    # ============================================================================
    # WorkspaceInterface Implementation
    # ============================================================================
    
    async def create_workspace(self, user_id: str, workspace_id: str, name: str, 
                             resource_package: str, description: Optional[str] = None) -> Dict[str, Any]:
        """Create a workspace for a user"""
        try:
            query = """
                INSERT INTO workspaces (workspace_id, user_id, name, resource_package, description)
                VALUES (?, ?, ?, ?, ?)
            """
            success = await self._execute_update(query, (workspace_id, user_id, name, resource_package, description))
            
            if success:
                return await self.get_workspace(workspace_id)
            else:
                raise Exception("Failed to create workspace")
                
        except Exception as e:
            logger.error(f"Error creating workspace: {e}")
            raise
    
    async def get_user_workspaces(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all workspaces for a user"""
        try:
            query = "SELECT * FROM workspaces WHERE user_id = ? ORDER BY created_at DESC"
            return await self._execute_query(query, (user_id,))
        except Exception as e:
            logger.error(f"Error getting user workspaces: {e}")
            return []
    
    async def get_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Get workspace by ID"""
        try:
            query = "SELECT * FROM workspaces WHERE workspace_id = ?"
            return await self._execute_single(query, (workspace_id,))
        except Exception as e:
            logger.error(f"Error getting workspace: {e}")
            return None
    
    async def delete_workspace(self, workspace_id: str) -> bool:
        """Delete a workspace"""
        try:
            query = "DELETE FROM workspaces WHERE workspace_id = ?"
            return await self._execute_update(query, (workspace_id,))
        except Exception as e:
            logger.error(f"Error deleting workspace: {e}")
            return False
    
    # ============================================================================
    # SessionInterface Implementation
    # ============================================================================
    
    async def create_session(self, workspace_id: str, session_id: str, provider: str, 
                           storage_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a session"""
        try:
            # Convert storage_config to JSON string
            storage_config_json = json.dumps(storage_config)
            
            query = """
                INSERT INTO sessions (session_id, workspace_id, provider, storage_config)
                VALUES (?, ?, ?, ?)
            """
            success = await self._execute_update(query, (session_id, workspace_id, provider, storage_config_json))
            
            if success:
                return await self.get_session(session_id)
            else:
                raise Exception("Failed to create session")
                
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID"""
        try:
            query = "SELECT * FROM sessions WHERE session_id = ?"
            result = await self._execute_single(query, (session_id,))
            return result
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None
    
    async def update_session(self, session_id: str, **kwargs) -> bool:
        """Update session information"""
        try:
            if not kwargs:
                return True
            
            # Build dynamic update query
            set_clauses = []
            params = []
            
            for key, value in kwargs.items():
                if key == 'storage_config':
                    import json
                    set_clauses.append(f"{key} = ?")
                    params.append(json.dumps(value))
                elif key in ['provider', 'status']:
                    set_clauses.append(f"{key} = ?")
                    params.append(value)
            
            if not set_clauses:
                return True
            
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            params.append(session_id)
            
            query = f"UPDATE sessions SET {', '.join(set_clauses)} WHERE session_id = ?"
            return await self._execute_update(query, tuple(params))
            
        except Exception as e:
            logger.error(f"Error updating session: {e}")
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        try:
            query = "DELETE FROM sessions WHERE session_id = ?"
            return await self._execute_update(query, (session_id,))
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False
    
    # ============================================================================
    # UsageInterface Implementation
    # ============================================================================
    
    async def track_storage_usage(self, user_id: str, resource_id: str, 
                                usage_gb: float, timestamp: datetime) -> bool:
        """Track storage usage"""
        try:
            tracking_id = str(uuid.uuid4())
            
            query = """
                INSERT INTO usage_tracking (tracking_id, user_id, resource_id, usage_gb, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """
            return await self._execute_update(query, (tracking_id, user_id, resource_id, usage_gb, timestamp.isoformat()))
            
        except Exception as e:
            logger.error(f"Error tracking storage usage: {e}")
            return False
    
    async def get_user_usage(self, user_id: str, start_date: datetime, 
                           end_date: datetime) -> Dict[str, Any]:
        """Get user usage statistics"""
        try:
            query = """
                SELECT 
                    resource_id,
                    SUM(usage_gb) as total_usage_gb,
                    COUNT(*) as usage_entries,
                    MIN(timestamp) as first_usage,
                    MAX(timestamp) as last_usage
                FROM usage_tracking 
                WHERE user_id = ? AND timestamp BETWEEN ? AND ?
                GROUP BY resource_id
            """
            results = await self._execute_query(query, (user_id, start_date.isoformat(), end_date.isoformat()))
            
            return {
                "user_id": user_id,
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "usage_by_resource": results,
                "total_usage_gb": sum(r['total_usage_gb'] for r in results)
            }
            
        except Exception as e:
            logger.error(f"Error getting user usage: {e}")
            return {
                "user_id": user_id,
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "usage_by_resource": [],
                "total_usage_gb": 0.0
            }
    
    # ============================================================================
    # TierInterface Implementation
    # ============================================================================
    
    async def get_user_tier_limits(self, user_type: UserType) -> Dict[str, Any]:
        """Get storage limits for a user type"""
        # Return hardcoded limits for development
        limits = {
            UserType.FREE: {"buckets": 1, "filestores": 1},
            UserType.PRO: {"buckets": 5, "filestores": 3},
            UserType.ENTERPRISE: {"buckets": 100, "filestores": 50},
            UserType.ADMIN: {"buckets": -1, "filestores": -1}  # Unlimited
        }
        return limits.get(user_type, {"buckets": 0, "filestores": 0})
    
    async def check_user_storage_quota(self, user_id: str, storage_type: StorageType) -> bool:
        """Check if user can create more storage resources"""
        try:
            # Get user info
            user = await self.get_user(user_id)
            if not user:
                return False
            
            user_type = UserType(user['user_type'])
            limits = await self.get_user_tier_limits(user_type)
            
            # Check if unlimited
            if limits.get(storage_type.value, 0) == -1:
                return True
            
            # Count current resources
            query = "SELECT COUNT(*) as count FROM storage_resources WHERE user_id = ? AND storage_type = ?"
            result = await self._execute_single(query, (user_id, storage_type.value))
            current_count = result['count'] if result else 0
            
            return current_count < limits.get(storage_type.value, 0)
            
        except Exception as e:
            logger.error(f"Error checking user storage quota: {e}")
            return False
    
    # ============================================================================
    # SpacesInterface Implementation
    # ============================================================================
    
    async def create_space(self, space_id: str, name: str, description: str, category: str,
                          size_gb: int, cost_usd: float, is_public: bool = True,
                          created_by: str = None) -> Dict[str, Any]:
        """Create a space template"""
        try:
            query = """
                INSERT INTO spaces (space_id, name, description, category, size_gb, cost_usd, is_public, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            success = await self._execute_update(query, (space_id, name, description, category, size_gb, cost_usd, is_public, created_by))
            
            if success:
                return await self._execute_single("SELECT * FROM spaces WHERE space_id = ?", (space_id,))
            else:
                raise Exception("Failed to create space")
                
        except Exception as e:
            logger.error(f"Error creating space: {e}")
            raise
    
    async def get_available_spaces(self) -> List[Dict[str, Any]]:
        """Get all available spaces for purchase"""
        try:
            query = "SELECT * FROM spaces WHERE is_public = TRUE ORDER BY category, name"
            return await self._execute_query(query)
        except Exception as e:
            logger.error(f"Error getting available spaces: {e}")
            return []
    
    async def purchase_space(self, user_id: str, space_id: str, workspace_id: str,
                           instance_name: str) -> Dict[str, Any]:
        """Purchase and clone a space to a workspace"""
        try:
            # Get space info
            space = await self._execute_single("SELECT * FROM spaces WHERE space_id = ?", (space_id,))
            if not space:
                raise Exception("Space not found")
            
            # Check if user has enough credits
            user_credits = await self.get_user_credits(user_id)
            if user_credits < space['cost_usd']:
                raise Exception(f"Insufficient credits: {user_credits} < {space['cost_usd']}")
            
            # Start transaction
            async with self._lock:
                # Deduct credits
                success = await self.deduct_credits(user_id, space['cost_usd'], f"Space purchase: {space['name']}")
                if not success:
                    raise Exception("Failed to deduct credits")
                
                # Create user space instance
                user_space_id = str(uuid.uuid4())
                query = """
                    INSERT INTO user_spaces (user_space_id, user_id, space_id, workspace_id, instance_name)
                    VALUES (?, ?, ?, ?, ?)
                """
                await self._connection.execute(query, (user_space_id, user_id, space_id, workspace_id, instance_name))
                
                # Create billing transaction
                transaction_id = str(uuid.uuid4())
                query = """
                    INSERT INTO billing_transactions 
                    (transaction_id, user_id, amount, billing_type, description, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                metadata = {"space_id": space_id, "workspace_id": workspace_id, "instance_name": instance_name}
                await self._connection.execute(query, (transaction_id, user_id, -space['cost_usd'], BillingType.SPACE_PURCHASE.value, f"Space purchase: {space['name']}", json.dumps(metadata)))
                
                await self._connection.commit()
                
                return await self._execute_single("SELECT * FROM user_spaces WHERE user_space_id = ?", (user_space_id,))
                
        except Exception as e:
            logger.error(f"Error purchasing space: {e}")
            raise
    
    async def get_workspace_spaces(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get spaces attached to a workspace"""
        try:
            query = """
                SELECT us.*, s.name as space_name, s.description as space_description, s.category
                FROM user_spaces us
                JOIN spaces s ON us.space_id = s.space_id
                WHERE us.workspace_id = ?
                ORDER BY us.created_at DESC
            """
            return await self._execute_query(query, (workspace_id,))
        except Exception as e:
            logger.error(f"Error getting workspace spaces: {e}")
            return []
