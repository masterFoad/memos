"""
Database Interface for OnMemOS v3
Abstract base class for database operations that can be implemented by SQLite, Supabase, etc.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

class UserType(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    ADMIN = "admin"

class StorageType(str, Enum):
    GCS_BUCKET = "gcs_bucket"
    FILESTORE_PVC = "filestore_pvc"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class BillingType(str, Enum):
    CREDIT_PURCHASE = "credit_purchase"
    STORAGE_CREATION = "storage_creation"
    SESSION_RUNTIME = "session_runtime"
    SPACE_PURCHASE = "space_purchase"

# ============================================================================
# Core Database Interface
# ============================================================================

class DatabaseInterface(ABC):
    """Abstract database interface for OnMemOS v3"""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the database"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from the database"""
        pass
    
    # User Management
    @abstractmethod
    async def create_user(self, user_id: str, email: str, user_type: UserType = UserType.FREE, 
                         name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new user"""
        pass
    
    @abstractmethod
    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        pass
    
    @abstractmethod
    async def update_user(self, user_id: str, **kwargs) -> bool:
        """Update user information"""
        pass
    
    @abstractmethod
    async def delete_user(self, user_id: str) -> bool:
        """Delete user"""
        pass

# ============================================================================
# Passport Management Interface
# ============================================================================

class PassportInterface(ABC):
    """Interface for passport (API key) management"""
    
    @abstractmethod
    async def create_passport(self, user_id: str, name: str, permissions: List[str] = None) -> Dict[str, Any]:
        """Create a passport (API key) for a user"""
        pass
    
    @abstractmethod
    async def get_passport(self, passport_id: str) -> Optional[Dict[str, Any]]:
        """Get passport by ID"""
        pass
    
    @abstractmethod
    async def get_user_passports(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all passports for a user"""
        pass
    
    @abstractmethod
    async def validate_passport(self, passport_key: str) -> Optional[Dict[str, Any]]:
        """Validate a passport key and return user info"""
        pass
    
    @abstractmethod
    async def revoke_passport(self, passport_id: str) -> bool:
        """Revoke a passport"""
        pass

# ============================================================================
# Credit System Interface
# ============================================================================

class CreditInterface(ABC):
    """Interface for credit system management"""
    
    @abstractmethod
    async def get_user_credits(self, user_id: str) -> float:
        """Get user's current credit balance"""
        pass
    
    @abstractmethod
    async def add_credits(self, user_id: str, amount: float, source: str, 
                         description: str = None) -> bool:
        """Add credits to user account"""
        pass
    
    @abstractmethod
    async def deduct_credits(self, user_id: str, amount: float, reason: str, 
                           session_id: str = None, storage_resource_id: str = None) -> bool:
        """Deduct credits from user account"""
        pass
    
    @abstractmethod
    async def get_credit_history(self, user_id: str, start_date: datetime = None, 
                               end_date: datetime = None) -> List[Dict[str, Any]]:
        """Get user's credit transaction history"""
        pass

# ============================================================================
# Payment Configuration Interface
# ============================================================================

class PaymentConfigInterface(ABC):
    """Interface for payment configuration management"""
    
    @abstractmethod
    async def get_payment_config(self) -> Dict[str, Any]:
        """Get payment configuration"""
        pass
    
    @abstractmethod
    async def update_payment_config(self, config: Dict[str, Any]) -> bool:
        """Update payment configuration"""
        pass

# ============================================================================
# Billing & Transactions Interface
# ============================================================================

class BillingInterface(ABC):
    """Interface for billing and transaction management"""
    
    @abstractmethod
    async def create_transaction(self, user_id: str, amount: float, billing_type: BillingType,
                               description: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a billing transaction"""
        pass
    
    @abstractmethod
    async def get_user_transactions(self, user_id: str, start_date: datetime = None,
                                  end_date: datetime = None) -> List[Dict[str, Any]]:
        """Get user's transaction history"""
        pass
    
    @abstractmethod
    async def update_transaction_status(self, transaction_id: str, status: PaymentStatus) -> bool:
        """Update transaction status"""
        pass

# ============================================================================
# Session Billing Interface
# ============================================================================

class SessionBillingInterface(ABC):
    """Interface for session billing management"""
    
    @abstractmethod
    async def start_session_billing(self, session_id: str, user_id: str, 
                                  hourly_rate: float) -> Dict[str, Any]:
        """Start billing for a session"""
        pass
    
    @abstractmethod
    async def stop_session_billing(self, session_id: str, total_hours: float) -> bool:
        """Stop billing for a session and calculate final cost"""
        pass
    
    @abstractmethod
    async def get_session_billing_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get billing information for a session"""
        pass

# ============================================================================
# Service Account Management Interface
# ============================================================================

class ServiceAccountInterface(ABC):
    """Interface for service account management"""
    
    @abstractmethod
    async def create_service_account(self, user_id: str, service_account_email: str, 
                                   gcp_project_id: str) -> Dict[str, Any]:
        """Create a service account for a user"""
        pass
    
    @abstractmethod
    async def get_service_account(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get service account for a user"""
        pass
    
    @abstractmethod
    async def update_service_account(self, user_id: str, **kwargs) -> bool:
        """Update service account information"""
        pass

# ============================================================================
# Storage Management Interface
# ============================================================================

class StorageInterface(ABC):
    """Interface for storage resource management"""
    
    @abstractmethod
    async def create_storage_resource(self, user_id: str, storage_type: StorageType, 
                                    resource_name: str, size_gb: int = 10) -> Dict[str, Any]:
        """Create a storage resource (bucket or filestore) for a user"""
        pass
    
    @abstractmethod
    async def get_user_storage_resources(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all storage resources for a user"""
        pass
    
    @abstractmethod
    async def delete_storage_resource(self, resource_id: str) -> bool:
        """Delete a storage resource"""
        pass

# ============================================================================
# Workspace Management Interface
# ============================================================================

class WorkspaceInterface(ABC):
    """Interface for workspace management"""
    
    @abstractmethod
    async def create_workspace(self, user_id: str, workspace_id: str, name: str, 
                             resource_package: str, description: Optional[str] = None) -> Dict[str, Any]:
        """Create a workspace for a user"""
        pass
    
    @abstractmethod
    async def get_user_workspaces(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all workspaces for a user"""
        pass
    
    @abstractmethod
    async def get_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Get workspace by ID"""
        pass
    
    @abstractmethod
    async def delete_workspace(self, workspace_id: str) -> bool:
        """Delete a workspace"""
        pass

# ============================================================================
# Session Management Interface
# ============================================================================

class SessionInterface(ABC):
    """Interface for session management"""
    
    @abstractmethod
    async def create_session(self, workspace_id: str, session_id: str, provider: str, 
                           storage_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a session"""
        pass
    
    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID"""
        pass
    
    @abstractmethod
    async def update_session(self, session_id: str, **kwargs) -> bool:
        """Update session information"""
        pass
    
    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        pass

# ============================================================================
# Usage Tracking Interface
# ============================================================================

class UsageInterface(ABC):
    """Interface for usage tracking"""
    
    @abstractmethod
    async def track_storage_usage(self, user_id: str, resource_id: str, 
                                usage_gb: float, timestamp: datetime) -> bool:
        """Track storage usage"""
        pass
    
    @abstractmethod
    async def get_user_usage(self, user_id: str, start_date: datetime, 
                           end_date: datetime) -> Dict[str, Any]:
        """Get user usage statistics"""
        pass

# ============================================================================
# Tier Management Interface
# ============================================================================

class TierInterface(ABC):
    """Interface for tier and limit management"""
    
    @abstractmethod
    async def get_user_tier_limits(self, user_type: UserType) -> Dict[str, Any]:
        """Get storage limits for a user type"""
        pass
    
    @abstractmethod
    async def check_user_storage_quota(self, user_id: str, storage_type: StorageType) -> bool:
        """Check if user can create more storage resources"""
        pass

# ============================================================================
# Spaces Management Interface
# ============================================================================

class SpacesInterface(ABC):
    """Interface for spaces management"""
    
    @abstractmethod
    async def create_space(self, space_id: str, name: str, description: str, category: str,
                          size_gb: int, cost_usd: float, is_public: bool = True,
                          created_by: str = None) -> Dict[str, Any]:
        """Create a space template"""
        pass
    
    @abstractmethod
    async def get_available_spaces(self) -> List[Dict[str, Any]]:
        """Get all available spaces for purchase"""
        pass
    
    @abstractmethod
    async def purchase_space(self, user_id: str, space_id: str, workspace_id: str,
                           instance_name: str) -> Dict[str, Any]:
        """Purchase and clone a space to a workspace"""
        pass
    
    @abstractmethod
    async def get_workspace_spaces(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get spaces attached to a workspace"""
        pass

# ============================================================================
# Complete Database Interface (Combines All Interfaces)
# ============================================================================

class CompleteDatabaseInterface(
    DatabaseInterface,
    PassportInterface,
    CreditInterface,
    PaymentConfigInterface,
    BillingInterface,
    SessionBillingInterface,
    ServiceAccountInterface,
    StorageInterface,
    WorkspaceInterface,
    SessionInterface,
    UsageInterface,
    TierInterface,
    SpacesInterface
):
    """Complete database interface combining all sub-interfaces"""
    pass
