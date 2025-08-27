"""
Unified Storage Manager for OnMemOS v3
"""
import os
import logging
from typing import Dict, List, Optional, Any
from server.services.gcp.bucket_service import GCSBucketService
from server.services.gcp.disk_service import GCPDiskService

logger = logging.getLogger(__name__)

class StorageManager:
    """Unified storage manager for GCS buckets and GCP persistent disks"""
    
    def __init__(self):
        self.bucket_service = GCSBucketService()
        self.disk_service = GCPDiskService()
        self.project_id = os.getenv("PROJECT_ID", "ai-engine-448418")
    
    def create_namespace_storage(self, namespace: str, user: str, options: Dict = None):
        """Create complete storage setup for a namespace"""
        if not options:
            options = {}
        
        try:
            # Check if resources already exist
            disk_name = f"onmemos-persist-{namespace}-{user}"
            bucket_name = f"onmemos-{namespace}-{user}"
            
            # Try to get existing disk info
            try:
                disk_info = self.disk_service.get_disk_info(disk_name)
                logger.info(f"✅ Using existing disk: {disk_name}")
            except Exception:
                # Create new disk if it doesn't exist
                disk_size_gb = options.get("disk_size_gb", 10)
                disk_info = self.disk_service.create_disk(disk_name, namespace, user, disk_size_gb)
                logger.info(f"✅ Created new disk: {disk_name}")
            
            # Try to get existing bucket info
            try:
                bucket_info = self.bucket_service.get_bucket_info(bucket_name)
                logger.info(f"✅ Using existing bucket: {bucket_name}")
            except Exception:
                # Create new bucket if it doesn't exist
                bucket_info = self.bucket_service.create_bucket(bucket_name, namespace, user)
                logger.info(f"✅ Created new bucket: {bucket_name}")
            
            logger.info(f"✅ Namespace storage ready for {namespace}/{user}")
            
            return {
                "namespace": namespace,
                "user": user,
                "disk": disk_info,
                "bucket": bucket_info,
                "mounts": {
                    "persistent": disk_info["mount_path"],
                    "bucket": bucket_info["mount_path"]
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to create namespace storage for {namespace}/{user}: {e}")
            raise
    
    def list_namespace_storage(self, namespace: str) -> Dict[str, Any]:
        """List storage resources for a namespace"""
        try:
            buckets = self.bucket_service.list_buckets_in_namespace(namespace)
            disks = self.disk_service.list_disks_in_namespace(namespace)
            
            return {
                "namespace": namespace,
                "buckets": buckets,
                "disks": disks,
                "total_buckets": len(buckets),
                "total_disks": len(disks)
            }
            
        except Exception as e:
            logger.error(f"Failed to list namespace storage for {namespace}: {e}")
            return {
                "namespace": namespace,
                "buckets": [],
                "disks": [],
                "total_buckets": 0,
                "total_disks": 0,
                "error": str(e)
            }
    
    def delete_namespace_storage(self, namespace: str, user: str) -> bool:
        """Delete all storage resources for a namespace/user"""
        try:
            # List and delete buckets
            buckets = self.bucket_service.list_buckets_in_namespace(namespace)
            for bucket in buckets:
                if bucket.get("user") == user:
                    self.bucket_service.delete_bucket(bucket["bucket_name"])
            
            # List and delete disks
            disks = self.disk_service.list_disks_in_namespace(namespace)
            for disk in disks:
                if disk.get("user") == user:
                    self.disk_service.delete_disk(disk["disk_name"])
            
            logger.info(f"✅ Deleted namespace storage for {namespace}/{user}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete namespace storage for {namespace}/{user}: {e}")
            return False
    
    def clone_namespace_storage(self, source_namespace: str, source_user: str,
                              new_namespace: str, new_user: str) -> Dict[str, Any]:
        """Clone storage resources from one namespace/user to another"""
        try:
            # Clone bucket
            source_buckets = self.bucket_service.list_buckets_in_namespace(source_namespace)
            source_bucket = None
            for bucket in source_buckets:
                if bucket.get("user") == source_user:
                    source_bucket = bucket
                    break
            
            if source_bucket:
                new_bucket_name = f"onmemos-{new_namespace}-{new_user}"
                bucket_info = self.bucket_service.clone_bucket(
                    source_bucket["bucket_name"], new_bucket_name, new_namespace, new_user
                )
            else:
                bucket_info = self.bucket_service.create_bucket(
                    f"onmemos-{new_namespace}-{new_user}", new_namespace, new_user
                )
            
            # Clone disk
            source_disks = self.disk_service.list_disks_in_namespace(source_namespace)
            source_disk = None
            for disk in source_disks:
                if disk.get("user") == source_user:
                    source_disk = disk
                    break
            
            if source_disk:
                new_disk_name = f"onmemos-persist-{new_namespace}-{new_user}"
                disk_info = self.disk_service.clone_disk(
                    source_disk["disk_name"], new_disk_name, new_namespace, new_user
                )
            else:
                disk_info = self.disk_service.create_disk(
                    f"onmemos-persist-{new_namespace}-{new_user}", new_namespace, new_user
                )
            
            logger.info(f"✅ Cloned storage from {source_namespace}/{source_user} to {new_namespace}/{new_user}")
            
            return {
                "source": {"namespace": source_namespace, "user": source_user},
                "target": {"namespace": new_namespace, "user": new_user},
                "disk": disk_info,
                "bucket": bucket_info
            }
            
        except Exception as e:
            logger.error(f"Failed to clone namespace storage: {e}")
            raise

# Global storage manager instance
storage_manager = StorageManager()
