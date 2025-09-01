"""
MySQL Database Client for OnMemOS v3
Implements the DatabaseInterface for MySQL
"""

import asyncio
import aiomysql
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import logging
import secrets
import hashlib

from .base import DatabaseInterface, UserType, StorageType, PaymentStatus, BillingType

logger = logging.getLogger(__name__)

class MySQLClient(DatabaseInterface):
    """MySQL implementation of the database interface"""
    
    def __init__(self, host: str = "localhost", port: int = 3306, 
                 user: str = "onmemos", password: str = "", 
                 database: str = "onmemos_v3"):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.pool = None
    
    async def connect(self) -> bool:
        """Connect to MySQL database"""
        try:
            self.pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.database,
                autocommit=True,
                maxsize=10,
                minsize=1
            )
            logger.info(f"✅ Connected to MySQL database: {self.database}")
            await self._create_tables()
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to MySQL: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from MySQL database"""
        try:
            if self.pool:
                self.pool.close()
                await self.pool.wait_closed()
                logger.info("✅ Disconnected from MySQL database")
            return True
        except Exception as e:
            logger.error(f"❌ Error disconnecting from MySQL: {e}")
            return False
    
    async def _create_tables(self):
        """Create database tables if they don't exist"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # Users table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id VARCHAR(255) PRIMARY KEY,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        name VARCHAR(255),
                        user_type ENUM('free', 'pro', 'enterprise', 'admin') DEFAULT 'free',
                        credits DECIMAL(10,2) DEFAULT 0.00,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                """)
                
                # Passports table (API Keys)
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS passports (
                        id VARCHAR(255) PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        passport_key VARCHAR(255) UNIQUE NOT NULL,
                        permissions JSON,
                        is_active BOOLEAN DEFAULT TRUE,
                        last_used TIMESTAMP NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                
                # Credit transactions table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS credit_transactions (
                        id VARCHAR(255) PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        amount DECIMAL(10,2) NOT NULL,
                        transaction_type ENUM('credit', 'debit') NOT NULL,
                        source VARCHAR(255) NOT NULL,
                        description TEXT,
                        session_id VARCHAR(255) NULL,
                        storage_resource_id VARCHAR(255) NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                
                # Payment configuration table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS payment_config (
                        id VARCHAR(255) PRIMARY KEY,
                        config_key VARCHAR(255) UNIQUE NOT NULL,
                        config_value JSON NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                """)
                
                # Billing transactions table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS billing_transactions (
                        id VARCHAR(255) PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        amount DECIMAL(10,2) NOT NULL,
                        billing_type ENUM('credit_purchase', 'storage_creation', 'session_runtime', 'space_purchase') NOT NULL,
                        description TEXT NOT NULL,
                        metadata JSON,
                        status ENUM('pending', 'completed', 'failed', 'refunded') DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                
                # Session billing table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS session_billing (
                        id VARCHAR(255) PRIMARY KEY,
                        session_id VARCHAR(255) NOT NULL,
                        user_id VARCHAR(255) NOT NULL,
                        hourly_rate DECIMAL(10,4) NOT NULL,
                        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        end_time TIMESTAMP NULL,
                        total_hours DECIMAL(10,4) NULL,
                        total_cost DECIMAL(10,2) NULL,
                        status ENUM('active', 'completed', 'cancelled') DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                
                # Service accounts table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS service_accounts (
                        id VARCHAR(255) PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        service_account_email VARCHAR(255) UNIQUE NOT NULL,
                        gcp_project_id VARCHAR(255) NOT NULL,
                        workload_identity_configured BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                
                # Storage resources table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS storage_resources (
                        id VARCHAR(255) PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        storage_type ENUM('gcs_bucket', 'filestore_pvc') NOT NULL,
                        resource_name VARCHAR(255) NOT NULL,
                        size_gb INT DEFAULT 10,
                        status ENUM('creating', 'active', 'deleting', 'deleted') DEFAULT 'creating',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                
                # Workspaces table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS workspaces (
                        id VARCHAR(255) PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        resource_package VARCHAR(255) NOT NULL,
                        description TEXT,
                        status ENUM('active', 'suspended', 'deleted') DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                
                # Sessions table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id VARCHAR(255) PRIMARY KEY,
                        workspace_id VARCHAR(255) NOT NULL,
                        provider VARCHAR(255) NOT NULL,
                        storage_config JSON,
                        status ENUM('creating', 'running', 'stopped', 'deleted') DEFAULT 'creating',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
                    )
                """)
                
                # Usage tracking table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS usage_tracking (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        resource_id VARCHAR(255) NOT NULL,
                        usage_gb FLOAT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                
                # Tier limits table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tier_limits (
                        user_type ENUM('free', 'pro', 'enterprise', 'admin') PRIMARY KEY,
                        max_buckets INT NOT NULL,
                        max_filestores INT NOT NULL,
                        max_total_storage_gb INT NOT NULL,
                        can_share_storage BOOLEAN DEFAULT FALSE,
                        can_cross_namespace BOOLEAN DEFAULT FALSE,
                        hourly_rate DECIMAL(10,4) NOT NULL,
                        credit_bonus DECIMAL(10,2) DEFAULT 0.00
                    )
                """)
                
                # Spaces table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS spaces (
                        id VARCHAR(255) PRIMARY KEY,
                        space_id VARCHAR(255) UNIQUE NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        description TEXT,
                        category VARCHAR(255) NOT NULL,
                        size_gb INT NOT NULL,
                        cost_usd DECIMAL(10,2) NOT NULL,
                        is_public BOOLEAN DEFAULT TRUE,
                        created_by VARCHAR(255) NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                """)
                
                # User spaces table (cloned spaces)
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_spaces (
                        id VARCHAR(255) PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        workspace_id VARCHAR(255) NOT NULL,
                        space_id VARCHAR(255) NOT NULL,
                        instance_name VARCHAR(255) NOT NULL,
                        storage_resource_id VARCHAR(255) NULL,
                        cloned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status ENUM('active', 'archived', 'deleted') DEFAULT 'active',
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                        FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                        FOREIGN KEY (space_id) REFERENCES spaces(id) ON DELETE CASCADE
                    )
                """)
                
                # Insert default tier limits
                await cursor.execute("""
                    INSERT IGNORE INTO tier_limits (user_type, max_buckets, max_filestores, max_total_storage_gb, can_share_storage, can_cross_namespace, hourly_rate, credit_bonus) VALUES
                    ('free', 1, 1, 50, FALSE, FALSE, 0.0500, 5.00),
                    ('pro', 5, 3, 500, TRUE, TRUE, 0.0250, 0.00),
                    ('enterprise', 100, 50, 10000, TRUE, TRUE, 0.0100, 0.00),
                    ('admin', 1000, 1000, 100000, TRUE, TRUE, 0.0000, 0.00)
                """)
                
                # Insert default payment configuration
                await cursor.execute("""
                    INSERT IGNORE INTO payment_config (id, config_key, config_value, description) VALUES
                    ('default', 'pricing', '{"credit_purchase": {"min_amount": 10, "bonus_percent": 0}, "storage_pricing": {"bucket_per_gb_monthly": 0.02, "filestore_per_gb_monthly": 0.17}, "session_pricing": {"cpu_hourly": 0.05, "gpu_hourly": 0.50}}', 'Default pricing configuration'),
                    ('default', 'billing', '{"billing_cycle": "monthly", "grace_period_days": 7, "auto_suspend": true}', 'Billing configuration'),
                    ('default', 'limits', '{"free_tier_credits": 5, "max_concurrent_sessions": 1, "session_timeout_hours": 24}', 'Usage limits configuration')
                """)
                
                # Insert default spaces
                await cursor.execute("""
                    INSERT IGNORE INTO spaces (id, space_id, name, description, category, size_gb, cost_usd) VALUES
                    ('ml-ready', 'ml-ready', 'ML Ready Environment', 'Pre-configured with PyTorch, TensorFlow, Jupyter, and common ML datasets', 'machine-learning', 50, 5.00),
                    ('data-science', 'data-science', 'Data Science Toolkit', 'Pandas, NumPy, Matplotlib, Seaborn, and sample datasets', 'data-science', 30, 3.00),
                    ('web-dev', 'web-dev', 'Web Development Stack', 'Node.js, React, Python Flask, and development tools', 'web-development', 20, 2.00),
                    ('research', 'research', 'Research Environment', 'Academic tools, LaTeX, research papers, and citation tools', 'research', 40, 4.00)
                """)
                
                logger.info("✅ Database tables created/verified")
    
    # ... existing methods remain the same ...
    
    # Passport Management Methods
    async def create_passport(self, user_id: str, name: str, permissions: List[str] = None) -> Dict[str, Any]:
        """Create a passport (API key) for a user"""
        passport_id = f"passport-{user_id}-{int(datetime.now().timestamp())}"
        passport_key = f"onmemos_{secrets.token_urlsafe(32)}"
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO passports (id, user_id, name, passport_key, permissions) 
                    VALUES (%s, %s, %s, %s, %s)
                """, (passport_id, user_id, name, passport_key, json.dumps(permissions or [])))
                
                return {
                    "id": passport_id,
                    "user_id": user_id,
                    "name": name,
                    "passport_key": passport_key,
                    "permissions": permissions or [],
                    "is_active": True,
                    "created_at": datetime.now()
                }
    
    async def get_passport(self, passport_id: str) -> Optional[Dict[str, Any]]:
        """Get passport by ID"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT id, user_id, name, passport_key, permissions, is_active, last_used, created_at, updated_at 
                    FROM passports WHERE id = %s
                """, (passport_id,))
                
                result = await cursor.fetchone()
                if result:
                    return {
                        "id": result[0],
                        "user_id": result[1],
                        "name": result[2],
                        "passport_key": result[3],
                        "permissions": json.loads(result[4]) if result[4] else [],
                        "is_active": result[5],
                        "last_used": result[6],
                        "created_at": result[7],
                        "updated_at": result[8]
                    }
                return None
    
    async def get_user_passports(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all passports for a user"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT id, user_id, name, passport_key, permissions, is_active, last_used, created_at, updated_at 
                    FROM passports WHERE user_id = %s AND is_active = TRUE
                """, (user_id,))
                
                results = await cursor.fetchall()
                return [
                    {
                        "id": row[0],
                        "user_id": row[1],
                        "name": row[2],
                        "passport_key": row[3],
                        "permissions": json.loads(row[4]) if row[4] else [],
                        "is_active": row[5],
                        "last_used": row[6],
                        "created_at": row[7],
                        "updated_at": row[8]
                    }
                    for row in results
                ]
    
    async def validate_passport(self, passport_key: str) -> Optional[Dict[str, Any]]:
        """Validate a passport key and return user info"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT p.id, p.user_id, p.name, p.permissions, p.is_active, u.email, u.user_type, u.credits
                    FROM passports p
                    JOIN users u ON p.user_id = u.id
                    WHERE p.passport_key = %s AND p.is_active = TRUE
                """, (passport_key,))
                
                result = await cursor.fetchone()
                if result:
                    # Update last used timestamp
                    await cursor.execute("""
                        UPDATE passports SET last_used = NOW() WHERE id = %s
                    """, (result[0],))
                    
                    return {
                        "passport_id": result[0],
                        "user_id": result[1],
                        "passport_name": result[2],
                        "permissions": json.loads(result[3]) if result[3] else [],
                        "is_active": result[4],
                        "email": result[5],
                        "user_type": result[6],
                        "credits": float(result[7])
                    }
                return None
    
    async def revoke_passport(self, passport_id: str) -> bool:
        """Revoke a passport"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    UPDATE passports SET is_active = FALSE WHERE id = %s
                """, (passport_id,))
                return cursor.rowcount > 0
    
    # Credit System Methods
    async def get_user_credits(self, user_id: str) -> float:
        """Get user's current credit balance"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT credits FROM users WHERE id = %s
                """, (user_id,))
                
                result = await cursor.fetchone()
                return float(result[0]) if result else 0.0
    
    async def add_credits(self, user_id: str, amount: float, source: str, 
                         description: str = None) -> bool:
        """Add credits to user account"""
        transaction_id = f"credit-{user_id}-{int(datetime.now().timestamp())}"
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # Update user credits
                await cursor.execute("""
                    UPDATE users SET credits = credits + %s WHERE id = %s
                """, (amount, user_id))
                
                # Record transaction
                await cursor.execute("""
                    INSERT INTO credit_transactions (id, user_id, amount, transaction_type, source, description) 
                    VALUES (%s, %s, %s, 'credit', %s, %s)
                """, (transaction_id, user_id, amount, source, description))
                
                return cursor.rowcount > 0
    
    async def deduct_credits(self, user_id: str, amount: float, reason: str, 
                           session_id: str = None, storage_resource_id: str = None) -> bool:
        """Deduct credits from user account"""
        transaction_id = f"debit-{user_id}-{int(datetime.now().timestamp())}"
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # Check if user has enough credits
                current_credits = await self.get_user_credits(user_id)
                if current_credits < amount:
                    return False
                
                # Update user credits
                await cursor.execute("""
                    UPDATE users SET credits = credits - %s WHERE id = %s
                """, (amount, user_id))
                
                # Record transaction
                await cursor.execute("""
                    INSERT INTO credit_transactions (id, user_id, amount, transaction_type, source, description, session_id, storage_resource_id) 
                    VALUES (%s, %s, %s, 'debit', %s, %s, %s, %s)
                """, (transaction_id, user_id, amount, reason, reason, session_id, storage_resource_id))
                
                return cursor.rowcount > 0
    
    async def get_credit_history(self, user_id: str, start_date: datetime = None, 
                               end_date: datetime = None) -> List[Dict[str, Any]]:
        """Get user's credit transaction history"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = """
                    SELECT id, amount, transaction_type, source, description, session_id, storage_resource_id, created_at 
                    FROM credit_transactions WHERE user_id = %s
                """
                params = [user_id]
                
                if start_date:
                    query += " AND created_at >= %s"
                    params.append(start_date)
                
                if end_date:
                    query += " AND created_at <= %s"
                    params.append(end_date)
                
                query += " ORDER BY created_at DESC"
                
                await cursor.execute(query, params)
                results = await cursor.fetchall()
                
                return [
                    {
                        "id": row[0],
                        "amount": float(row[1]),
                        "transaction_type": row[2],
                        "source": row[3],
                        "description": row[4],
                        "session_id": row[5],
                        "storage_resource_id": row[6],
                        "created_at": row[7]
                    }
                    for row in results
                ]
    
    # Payment Configuration Methods
    async def get_payment_config(self) -> Dict[str, Any]:
        """Get payment configuration"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT config_key, config_value FROM payment_config
                """)
                
                results = await cursor.fetchall()
                config = {}
                for row in results:
                    config[row[0]] = json.loads(row[1])
                
                return config
    
    async def update_payment_config(self, config: Dict[str, Any]) -> bool:
        """Update payment configuration"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                for key, value in config.items():
                    await cursor.execute("""
                        INSERT INTO payment_config (id, config_key, config_value) 
                        VALUES (%s, %s, %s) 
                        ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
                    """, (key, key, json.dumps(value)))
                
                return True
    
    # Billing & Transactions Methods
    async def create_transaction(self, user_id: str, amount: float, billing_type: BillingType,
                               description: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a billing transaction"""
        transaction_id = f"txn-{user_id}-{int(datetime.now().timestamp())}"
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO billing_transactions (id, user_id, amount, billing_type, description, metadata) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (transaction_id, user_id, amount, billing_type.value, description, json.dumps(metadata or {})))
                
                return {
                    "id": transaction_id,
                    "user_id": user_id,
                    "amount": amount,
                    "billing_type": billing_type.value,
                    "description": description,
                    "metadata": metadata or {},
                    "status": "pending",
                    "created_at": datetime.now()
                }
    
    async def get_user_transactions(self, user_id: str, start_date: datetime = None,
                                  end_date: datetime = None) -> List[Dict[str, Any]]:
        """Get user's transaction history"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = """
                    SELECT id, amount, billing_type, description, metadata, status, created_at 
                    FROM billing_transactions WHERE user_id = %s
                """
                params = [user_id]
                
                if start_date:
                    query += " AND created_at >= %s"
                    params.append(start_date)
                
                if end_date:
                    query += " AND created_at <= %s"
                    params.append(end_date)
                
                query += " ORDER BY created_at DESC"
                
                await cursor.execute(query, params)
                results = await cursor.fetchall()
                
                return [
                    {
                        "id": row[0],
                        "amount": float(row[1]),
                        "billing_type": row[2],
                        "description": row[3],
                        "metadata": json.loads(row[4]) if row[4] else {},
                        "status": row[5],
                        "created_at": row[6]
                    }
                    for row in results
                ]
    
    async def update_transaction_status(self, transaction_id: str, status: PaymentStatus) -> bool:
        """Update transaction status"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    UPDATE billing_transactions SET status = %s WHERE id = %s
                """, (status.value, transaction_id))
                return cursor.rowcount > 0
    
    # Session Billing Methods
    async def start_session_billing(self, session_id: str, user_id: str, 
                                  hourly_rate: float) -> Dict[str, Any]:
        """Start billing for a session"""
        billing_id = f"billing-{session_id}"
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO session_billing (id, session_id, user_id, hourly_rate) 
                    VALUES (%s, %s, %s, %s)
                """, (billing_id, session_id, user_id, hourly_rate))
                
                return {
                    "id": billing_id,
                    "session_id": session_id,
                    "user_id": user_id,
                    "hourly_rate": hourly_rate,
                    "start_time": datetime.now(),
                    "status": "active"
                }
    
    async def stop_session_billing(self, session_id: str, total_hours: float) -> bool:
        """Stop billing for a session and calculate final cost"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # Get billing info
                await cursor.execute("""
                    SELECT id, user_id, hourly_rate FROM session_billing 
                    WHERE session_id = %s AND status = 'active'
                """, (session_id,))
                
                result = await cursor.fetchone()
                if not result:
                    return False
                
                billing_id, user_id, hourly_rate = result
                total_cost = hourly_rate * total_hours
                
                # Update billing record
                await cursor.execute("""
                    UPDATE session_billing 
                    SET end_time = NOW(), total_hours = %s, total_cost = %s, status = 'completed' 
                    WHERE id = %s
                """, (total_hours, total_cost, billing_id))
                
                # Deduct credits
                await self.deduct_credits(user_id, total_cost, f"Session runtime: {session_id}", session_id)
                
                return True
    
    async def get_session_billing_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get billing information for a session"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT id, user_id, hourly_rate, start_time, end_time, total_hours, total_cost, status 
                    FROM session_billing WHERE session_id = %s
                """, (session_id,))
                
                result = await cursor.fetchone()
                if result:
                    return {
                        "id": result[0],
                        "user_id": result[1],
                        "hourly_rate": float(result[2]),
                        "start_time": result[3],
                        "end_time": result[4],
                        "total_hours": float(result[5]) if result[5] else None,
                        "total_cost": float(result[6]) if result[6] else None,
                        "status": result[7]
                    }
                return None
    
    # Spaces Management Methods
    async def create_space(self, space_id: str, name: str, description: str, category: str,
                          size_gb: int, cost_usd: float, is_public: bool = True,
                          created_by: str = None) -> Dict[str, Any]:
        """Create a space template"""
        space_db_id = f"space-{space_id}-{int(datetime.now().timestamp())}"
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO spaces (id, space_id, name, description, category, size_gb, cost_usd, is_public, created_by) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (space_db_id, space_id, name, description, category, size_gb, cost_usd, is_public, created_by))
                
                return {
                    "id": space_db_id,
                    "space_id": space_id,
                    "name": name,
                    "description": description,
                    "category": category,
                    "size_gb": size_gb,
                    "cost_usd": float(cost_usd),
                    "is_public": is_public,
                    "created_by": created_by,
                    "created_at": datetime.now()
                }
    
    async def get_available_spaces(self) -> List[Dict[str, Any]]:
        """Get all available spaces for purchase"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT id, space_id, name, description, category, size_gb, cost_usd, is_public, created_by, created_at 
                    FROM spaces WHERE is_public = TRUE
                """)
                
                results = await cursor.fetchall()
                return [
                    {
                        "id": row[0],
                        "space_id": row[1],
                        "name": row[2],
                        "description": row[3],
                        "category": row[4],
                        "size_gb": row[5],
                        "cost_usd": float(row[6]),
                        "is_public": row[7],
                        "created_by": row[8],
                        "created_at": row[9]
                    }
                    for row in results
                ]
    
    async def purchase_space(self, user_id: str, space_id: str, workspace_id: str,
                           instance_name: str) -> Dict[str, Any]:
        """Purchase and clone a space to a workspace"""
        # Get space details
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT id, cost_usd, size_gb FROM spaces WHERE space_id = %s AND is_public = TRUE
                """, (space_id,))
                
                space = await cursor.fetchone()
                if not space:
                    raise ValueError(f"Space {space_id} not found or not available")
                
                space_db_id, cost_usd, size_gb = space
                
                # Check if user has enough credits
                user_credits = await self.get_user_credits(user_id)
                if user_credits < cost_usd:
                    raise ValueError(f"Insufficient credits. Required: ${cost_usd}, Available: ${user_credits}")
                
                # Create storage resource for the space
                storage_resource = await self.create_storage_resource(
                    user_id, StorageType.FILESTORE_PVC, f"pvc-{instance_name}-{int(datetime.now().timestamp())}", size_gb
                )
                
                # Create user space instance
                user_space_id = f"user-space-{user_id}-{int(datetime.now().timestamp())}"
                await cursor.execute("""
                    INSERT INTO user_spaces (id, user_id, workspace_id, space_id, instance_name, storage_resource_id) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (user_space_id, user_id, workspace_id, space_db_id, instance_name, storage_resource["id"]))
                
                # Deduct credits
                await self.deduct_credits(user_id, cost_usd, f"Purchased space: {space_id}", storage_resource_id=storage_resource["id"])
                
                # Create transaction record
                await self.create_transaction(
                    user_id, cost_usd, BillingType.SPACE_PURCHASE, 
                    f"Purchased space: {space_id}", {"space_id": space_id, "instance_name": instance_name}
                )
                
                return {
                    "id": user_space_id,
                    "user_id": user_id,
                    "workspace_id": workspace_id,
                    "space_id": space_id,
                    "instance_name": instance_name,
                    "storage_resource_id": storage_resource["id"],
                    "cost_usd": float(cost_usd),
                    "cloned_at": datetime.now()
                }
    
    async def get_workspace_spaces(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get spaces attached to a workspace"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT us.id, us.user_id, us.space_id, us.instance_name, us.storage_resource_id, 
                           us.cloned_at, us.last_used, us.status,
                           s.name, s.description, s.category
                    FROM user_spaces us
                    JOIN spaces s ON us.space_id = s.id
                    WHERE us.workspace_id = %s AND us.status = 'active'
                """, (workspace_id,))
                
                results = await cursor.fetchall()
                return [
                    {
                        "id": row[0],
                        "user_id": row[1],
                        "space_id": row[2],
                        "instance_name": row[3],
                        "storage_resource_id": row[4],
                        "cloned_at": row[5],
                        "last_used": row[6],
                        "status": row[7],
                        "space_name": row[8],
                        "space_description": row[9],
                        "space_category": row[10]
                    }
                    for row in results
                ]
    
    # ... existing methods remain the same ...
