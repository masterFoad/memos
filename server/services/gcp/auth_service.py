"""
GCP Authentication Service for OnMemOS v3
"""

import os
import json
from typing import Optional

from google.auth import default as google_auth_default
from google.auth import load_credentials_from_file
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import storage

from server.core.logging import get_storage_logger

logger = get_storage_logger()


class GCPAuthService:
    """Handles GCP authentication for the OnMemOS server"""

    def __init__(self):
        # Prefer env; fall back to project used elsewhere in the repo
        self.project_id = os.getenv("PROJECT_ID", "ai-engine-448418")
        # Respect explicit env first; don't force a default path unless it exists
        self.service_account_key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self._credentials = None
        self._storage_client: Optional[storage.Client] = None
        self._authenticated = False

    # ---------------- Public API (unchanged signatures) ----------------

    def setup_credentials(self) -> bool:
        """Set up GCP credentials using best-available strategy.

        Order:
          1) GOOGLE_APPLICATION_CREDENTIALS if it points to a real file
          2) google.auth.default() (Workload Identity / metadata server / gcloud)
          3) ./service-account-key.json if present
        """
        try:
            # 1) Explicit service account file via env
            if self.service_account_key_path and os.path.exists(self.service_account_key_path):
                self._credentials, detected_project = load_credentials_from_file(self.service_account_key_path)
                # Ensure env is consistent for libraries that rely on it
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.service_account_key_path
                self.project_id = detected_project or self.project_id
                logger.info(f"✅ GCP auth via service account file: {self.service_account_key_path}")
                self._authenticated = True
                return True

            # 2) Application Default Credentials (Workload Identity / gcloud / user creds)
            try:
                creds, detected_project = google_auth_default()
                self._credentials = creds
                self.project_id = detected_project or self.project_id
                logger.info(f"✅ GCP auth via ADC; project={self.project_id}")
                self._authenticated = True
                return True
            except DefaultCredentialsError as adc_err:
                logger.warning(f"ADC not available: {adc_err}")

            # 3) Local fallback key file if present
            fallback_path = "./service-account-key.json"
            if os.path.exists(fallback_path):
                self._credentials, detected_project = load_credentials_from_file(fallback_path)
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = fallback_path
                self.project_id = detected_project or self.project_id
                self.service_account_key_path = fallback_path
                logger.info(f"✅ GCP auth via local fallback key: {fallback_path}")
                self._authenticated = True
                return True

            logger.error("❌ No valid GCP credentials found (env key, ADC, or local fallback).")
            self._authenticated = False
            return False

        except Exception as e:
            logger.error(f"❌ GCP authentication setup failed: {e}")
            self._authenticated = False
            return False

    def get_storage_client(self) -> Optional[storage.Client]:
        """Get authenticated storage client"""
        if not self._authenticated and not self.setup_credentials():
            return None

        if self._storage_client is None:
            try:
                if self._credentials is not None:
                    self._storage_client = storage.Client(credentials=self._credentials, project=self.project_id)
                else:
                    # Last-resort: let library resolve ADC again
                    self._storage_client = storage.Client(project=self.project_id)
                logger.info(f"✅ Storage client initialized for project: {self.project_id}")
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

            # Try to list buckets; small, non-invasive call
            _ = list(client.list_buckets(max_results=1))
            logger.info("✅ GCP authentication test successful")
            return True

        except Exception as e:
            logger.error(f"❌ GCP authentication test failed: {e}")
            return False

    def get_service_account_info(self) -> Optional[dict]:
        """Get service account information from key file (if used)"""
        try:
            path = self.service_account_key_path
            if not path or not os.path.exists(path):
                return None

            with open(path, "r") as f:
                key_data = json.load(f)

            return {
                "client_email": key_data.get("client_email"),
                "project_id": key_data.get("project_id"),
                "type": key_data.get("type"),
            }

        except Exception as e:
            logger.error(f"Failed to read service account info: {e}")
            return None


# Global auth service instance
auth_service = GCPAuthService()
