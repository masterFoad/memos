"""
Real GCS Bucket Service for OnMemOS v3
"""
import os
import tempfile
import subprocess
from typing import Dict, List, Optional, Any
from google.cloud import storage
from google.cloud.exceptions import NotFound, Conflict

from server.core.logging import get_storage_logger

logger = get_storage_logger()

class GCSBucketService:
    """Real GCS bucket service using google-cloud-storage"""
    
    def __init__(self):
        self.project_id = os.getenv("PROJECT_ID", "ai-engine-448418")
        self.region = os.getenv("REGION", "us-central1")
        
        # Production-ready authentication strategy
        try:
            # 1. Try Service Account Key File (Primary method for VM-based services)
            key_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./service-account-key.json")
            if key_file and os.path.exists(key_file):
                self.client = storage.Client.from_service_account_json(key_file, project=self.project_id)
                logger.info(f"✅ Using Service Account Key File: {key_file}")
                
            else:
                raise Exception("No service account key file found")
                
        except Exception as e:
            logger.warning(f"Service Account Key failed: {e}")
            
            try:
                # 2. Try Workload Identity / Metadata Server (GKE/GCE)
                from google.auth import default
                credentials, project = default()
                self.client = storage.Client(credentials=credentials, project=project or self.project_id)
                logger.info(f"✅ Using Workload Identity / Metadata Server authentication")
                    
            except Exception as e2:
                logger.warning(f"Service Account Key failed: {e2}")
                
                try:
                    # 3. Try gcloud CLI (development only)
                    import subprocess
                    result = subprocess.run(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        service_account = result.stdout.strip()
                        logger.info(f"Using gcloud CLI: {service_account}")
                        # Clear any existing credentials to force gcloud auth
                        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = ""
                        credentials, project = default()
                        self.client = storage.Client(credentials=credentials, project=project or self.project_id)
                    else:
                        raise Exception("No active gcloud account")
                        
                except Exception as e3:
                    logger.error(f"All authentication methods failed: {e3}")
                    # 4. Fallback to basic client (will fail but provides clear error)
                    self.client = storage.Client(project=self.project_id)
        
    def create_bucket(self, bucket_name: str, namespace: str, user: str) -> Dict[str, Any]:
        """Create a real GCS bucket"""
        try:
            # Create bucket with proper settings
            bucket = self.client.bucket(bucket_name)
            bucket.create(location=self.region)
            
            # Enable uniform bucket-level access
            bucket.iam_configuration.uniform_bucket_level_access_enabled = True
            bucket.patch()
            
            # Create namespace/user prefix structure
            prefix = f"{namespace}/{user}/"
            blob = bucket.blob(f"{prefix}.metadata")
            blob.upload_from_string(f"Created for namespace={namespace}, user={user}")
            
            logger.info(f"✅ Created real GCS bucket: {bucket_name}")
            
            return {
                "bucket_name": bucket_name,
                "namespace": namespace,
                "user": user,
                "prefix": prefix,
                "location": self.region,
                "url": f"gs://{bucket_name}",
                "mount_path": f"/buckets/{namespace}/{user}"
            }
            
        except Conflict:
            logger.warning(f"Bucket {bucket_name} already exists")
            return self.get_bucket_info(bucket_name, namespace, user)
        except Exception as e:
            logger.error(f"Failed to create bucket {bucket_name}: {e}")
            raise
    
    def get_bucket_info(self, bucket_name: str, namespace: str, user: str) -> Dict[str, Any]:
        """Get bucket information"""
        try:
            bucket = self.client.bucket(bucket_name)
            bucket.reload()
            
            prefix = f"{namespace}/{user}/"
            
            return {
                "bucket_name": bucket_name,
                "namespace": namespace,
                "user": user,
                "prefix": prefix,
                "location": bucket.location,
                "url": f"gs://{bucket_name}",
                "mount_path": f"/buckets/{namespace}/{user}",
                "created": bucket.time_created.isoformat() if bucket.time_created else None
            }
        except NotFound:
            raise Exception(f"Bucket {bucket_name} not found")
        except Exception as e:
            logger.error(f"Failed to get bucket info for {bucket_name}: {e}")
            raise
    
    def list_buckets_in_namespace(self, namespace: str) -> List[Dict[str, Any]]:
        """List buckets for a namespace"""
        try:
            buckets = []
            for bucket in self.client.list_buckets():
                # Check if bucket has namespace metadata
                try:
                    metadata_blob = bucket.blob(f"{namespace}/.metadata")
                    if metadata_blob.exists():
                        buckets.append({
                            "bucket_name": bucket.name,
                            "namespace": namespace,
                            "location": bucket.location,
                            "url": f"gs://{bucket.name}",
                            "created": bucket.time_created.isoformat() if bucket.time_created else None
                        })
                except:
                    continue
            return buckets
        except Exception as e:
            logger.error(f"Failed to list buckets for namespace {namespace}: {e}")
            return []
    
    def delete_bucket(self, bucket_name: str) -> bool:
        """Delete a GCS bucket"""
        try:
            bucket = self.client.bucket(bucket_name)
            bucket.delete(force=True)
            logger.info(f"✅ Deleted GCS bucket: {bucket_name}")
            return True
        except NotFound:
            logger.warning(f"Bucket {bucket_name} not found for deletion")
            return True
        except Exception as e:
            logger.error(f"Failed to delete bucket {bucket_name}: {e}")
            return False
    
    def clone_bucket(self, source_bucket: str, new_bucket: str, namespace: str, user: str) -> Dict[str, Any]:
        """Clone a bucket by copying all objects"""
        try:
            # Create new bucket
            new_bucket_info = self.create_bucket(new_bucket, namespace, user)
            
            # Copy all objects
            source_bucket_obj = self.client.bucket(source_bucket)
            new_bucket_obj = self.client.bucket(new_bucket)
            
            blobs = list(source_bucket_obj.list_blobs())
            for blob in blobs:
                new_blob = new_bucket_obj.blob(blob.name)
                new_blob.rewrite(blob)
            
            logger.info(f"✅ Cloned bucket {source_bucket} -> {new_bucket}")
            return new_bucket_info
            
        except Exception as e:
            logger.error(f"Failed to clone bucket {source_bucket}: {e}")
            raise
    
    def mount_bucket_in_container(self, bucket_name: str, namespace: str, user: str, container_id: str) -> str:
        """Mount GCS bucket in container using gcsfuse"""
        try:
            # Create mount point
            mount_path = f"/buckets/{namespace}/{user}"
            
            # Install gcsfuse if not available
            subprocess.run([
                "docker", "exec", container_id,
                "sh", "-c", "which gcsfuse || (apt-get update && apt-get install -y gcsfuse)"
            ], check=False)
            
            # Mount bucket
            subprocess.run([
                "docker", "exec", container_id,
                "gcsfuse", "--implicit-dirs", "--only-dir", f"{namespace}/{user}",
                bucket_name, mount_path
            ], check=True)
            
            logger.info(f"✅ Mounted GCS bucket {bucket_name} at {mount_path} in container {container_id}")
            return mount_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to mount bucket {bucket_name}: {e}")
            raise Exception(f"Failed to mount GCS bucket: {e}")
        except Exception as e:
            logger.error(f"Failed to mount bucket {bucket_name}: {e}")
            raise

# Global instance
bucket_service = GCSBucketService()
