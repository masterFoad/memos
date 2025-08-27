"""
GCP Authentication Service for OnMemOS v3
"""

import os
import json
from typing import Optional
from google.auth import default
from google.cloud import storage
from google.auth.exceptions import DefaultCredentialsError

from server.core.logging import get_storage_logger

logger = get_storage_logger()

class GCPAuthService:
    """Handles GCP authentication for the OnMemOS server"""
    
    def __init__(self):
        self.project_id = "ai-engine-448418"
        self.service_account_key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./service-account-key.json")
        self._storage_client = None
        self._authenticated = False
        
    def setup_credentials(self) -> bool:
        """Set up GCP credentials using service account key"""
        try:
            # Check if service account key file exists
            if not os.path.exists(self.service_account_key_path):
                logger.warning(f"Service account key file not found: {self.service_account_key_path}")
                return False
            
            # Set environment variable
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.service_account_key_path
            
            # Test authentication
            credentials, project = default()
            logger.info(f"✅ GCP authentication successful with project: {project}")
            
            self._authenticated = True
            return True
            
        except Exception as e:
            logger.error(f"❌ GCP authentication failed: {e}")
            self._authenticated = False
            return False
    
    def get_storage_client(self) -> Optional[storage.Client]:
        """Get authenticated storage client"""
        if not self._authenticated:
            if not self.setup_credentials():
                return None
        
        if self._storage_client is None:
            try:
                credentials, project = default()
                self._storage_client = storage.Client(credentials=credentials, project=project)
                logger.info(f"✅ Storage client initialized for project: {project}")
            except Exception as e:
                logger.error(f"❌ Failed to create storage client: {e}")
                return None
        
        return self._storage_client
    
    def test_authentication(self) -> bool:
        """Test GCP authentication by listing buckets"""
        try:
            client = self.get_storage_client()
            if client is None:
                return False
            
            # Try to list buckets (this will test authentication)
            buckets = list(client.list_buckets(max_results=1))
            logger.info(f"✅ GCP authentication test successful - found {len(buckets)} buckets")
            return True
            
        except Exception as e:
            logger.error(f"❌ GCP authentication test failed: {e}")
            return False
    
    def get_service_account_info(self) -> Optional[dict]:
        """Get service account information from key file"""
        try:
            if not os.path.exists(self.service_account_key_path):
                return None
            
            with open(self.service_account_key_path, 'r') as f:
                key_data = json.load(f)
            
            return {
                "client_email": key_data.get("client_email"),
                "project_id": key_data.get("project_id"),
                "type": key_data.get("type")
            }
            
        except Exception as e:
            logger.error(f"Failed to read service account info: {e}")
            return None

# Global auth service instance
auth_service = GCPAuthService()
