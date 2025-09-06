"""
Database Factory for OnMemOS v3
Factory pattern to create database clients
"""

from typing import Optional
import os
import logging

from .base import DatabaseInterface
from .sqlite_temp_client import SQLiteTempClient

# Conditional import for MySQL client
try:
    from .mysql_client import MySQLClient
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    MySQLClient = None

logger = logging.getLogger(__name__)

class DatabaseFactory:
    """Factory for creating database clients"""
    
    @staticmethod
    def create_database_client(database_type: str = None) -> DatabaseInterface:
        """
        Create a database client based on configuration
        
        Args:
            database_type: Type of database ('mysql', 'supabase', etc.)
                          If None, reads from environment variable DATABASE_TYPE
        
        Returns:
            DatabaseInterface: Configured database client
        """
        if database_type is None:
            database_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
        
        if database_type == "mysql":
            if not MYSQL_AVAILABLE:
                raise ImportError("MySQL client not available. Install aiomysql to use MySQL.")
            return DatabaseFactory._create_mysql_client()
        elif database_type == "sqlite":
            return DatabaseFactory._create_sqlite_client()
        elif database_type == "supabase":
            # TODO: Implement Supabase client
            raise NotImplementedError("Supabase client not yet implemented")
        else:
            raise ValueError(f"Unsupported database type: {database_type}")
    
    @staticmethod
    def _create_mysql_client() -> MySQLClient:
        """Create MySQL client with configuration from environment variables"""
        host = os.getenv("MYSQL_HOST", "localhost")
        port = int(os.getenv("MYSQL_PORT", "3306"))
        user = os.getenv("MYSQL_USER", "onmemos")
        password = os.getenv("MYSQL_PASSWORD", "")
        database = os.getenv("MYSQL_DATABASE", "onmemos_v3")
        
        logger.info(f"Creating MySQL client: {user}@{host}:{port}/{database}")
        
        return MySQLClient(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
    
    @staticmethod
    def _create_sqlite_client() -> SQLiteTempClient:
        """Create SQLite client with configuration from environment variables"""
        db_path = os.getenv("SQLITE_DB_PATH", None)
        
        logger.info(f"Creating SQLite client with database: {db_path or 'default'}")
        
        return SQLiteTempClient(db_path=db_path)

# Global database client instance
_db_client: Optional[DatabaseInterface] = None

def get_database_client() -> DatabaseInterface:
    """Get the global database client instance"""
    global _db_client
    
    if _db_client is None:
        _db_client = DatabaseFactory.create_database_client()
    
    return _db_client

async def get_database_client_async() -> DatabaseInterface:
    """Get the global database client instance (async version)"""
    global _db_client
    
    if _db_client is None:
        _db_client = DatabaseFactory.create_database_client()
    
    return _db_client

async def initialize_database() -> bool:
    """Initialize the database connection"""
    global _db_client
    
    if _db_client is None:
        _db_client = DatabaseFactory.create_database_client()
    
    return await _db_client.connect()

async def close_database() -> bool:
    """Close the database connection"""
    global _db_client
    
    if _db_client:
        result = await _db_client.disconnect()
        _db_client = None
        return result
    
    return True
