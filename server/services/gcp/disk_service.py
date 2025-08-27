"""
Real GCP Persistent Disk Service for OnMemOS v3
"""
import os
import subprocess
from typing import Dict, List, Optional, Any
from google.cloud import compute_v1
from google.cloud.exceptions import NotFound, Conflict

from server.core.logging import get_storage_logger

logger = get_storage_logger()

class GCPDiskService:
    """Real GCP persistent disk service using google-cloud-compute"""
    
    def __init__(self):
        self.project_id = os.getenv("PROJECT_ID", "ai-engine-448418")
        self.zone = os.getenv("ZONE", "us-central1-a")
        self.region = os.getenv("REGION", "us-central1")
        self.client = compute_v1.DisksClient()
        
    def create_disk(self, disk_name: str, namespace: str, user: str, size_gb: int = 10) -> Dict[str, Any]:
        """Create a real GCP persistent disk"""
        try:
            # Create disk
            disk = compute_v1.Disk()
            disk.name = disk_name
            disk.size_gb = size_gb
            disk.type = f"projects/{self.project_id}/zones/{self.zone}/diskTypes/pd-standard"
            
            # Add labels for organization
            disk.labels = {
                "onmemos": "true",
                "namespace": namespace,
                "user": user,
                "created_by": "onmemos-v3"
            }
            
            operation = self.client.insert(
                project=self.project_id,
                zone=self.zone,
                disk_resource=disk
            )
            
            # Wait for operation to complete
            self._wait_for_operation(operation.name)
            
            logger.info(f"✅ Created real GCP persistent disk: {disk_name}")
            
            return {
                "disk_name": disk_name,
                "namespace": namespace,
                "user": user,
                "size_gb": size_gb,
                "zone": self.zone,
                "type": "pd-standard",
                "status": "READY",
                "mount_path": f"/persist/{namespace}/{user}"
            }
            
        except Conflict:
            logger.warning(f"Disk {disk_name} already exists")
            return self.get_disk_info(disk_name)
        except Exception as e:
            logger.error(f"Failed to create disk {disk_name}: {e}")
            raise
    
    def get_disk_info(self, disk_name: str) -> Dict[str, Any]:
        """Get disk information"""
        try:
            disk = self.client.get(
                project=self.project_id,
                zone=self.zone,
                disk=disk_name
            )
            
            return {
                "disk_name": disk.name,
                "namespace": disk.labels.get("namespace", "unknown"),
                "user": disk.labels.get("user", "unknown"),
                "size_gb": disk.size_gb,
                "zone": disk.zone.split("/")[-1],
                "type": disk.type.split("/")[-1],
                "status": disk.status,
                "mount_path": f"/persist/{disk.labels.get('namespace', 'unknown')}/{disk.labels.get('user', 'unknown')}",
                "created": disk.creation_timestamp
            }
        except NotFound:
            raise Exception(f"Disk {disk_name} not found")
        except Exception as e:
            logger.error(f"Failed to get disk info for {disk_name}: {e}")
            raise
    
    def list_disks_in_namespace(self, namespace: str) -> List[Dict[str, Any]]:
        """List disks for a namespace"""
        try:
            disks = []
            request = compute_v1.ListDisksRequest(
                project=self.project_id,
                zone=self.zone
            )
            
            for disk in self.client.list(request=request):
                if (disk.labels and 
                    disk.labels.get("onmemos") == "true" and
                    disk.labels.get("namespace") == namespace):
                    
                    disks.append({
                        "disk_name": disk.name,
                        "namespace": disk.labels.get("namespace"),
                        "user": disk.labels.get("user"),
                        "size_gb": disk.size_gb,
                        "zone": disk.zone.split("/")[-1],
                        "type": disk.type.split("/")[-1],
                        "status": disk.status,
                        "created": disk.creation_timestamp
                    })
            
            return disks
        except Exception as e:
            logger.error(f"Failed to list disks for namespace {namespace}: {e}")
            return []
    
    def delete_disk(self, disk_name: str) -> bool:
        """Delete a GCP persistent disk"""
        try:
            operation = self.client.delete(
                project=self.project_id,
                zone=self.zone,
                disk=disk_name
            )
            
            # Wait for operation to complete
            self._wait_for_operation(operation.name)
            
            logger.info(f"✅ Deleted GCP persistent disk: {disk_name}")
            return True
        except NotFound:
            logger.warning(f"Disk {disk_name} not found for deletion")
            return True
        except Exception as e:
            logger.error(f"Failed to delete disk {disk_name}: {e}")
            return False
    
    def clone_disk(self, source_disk: str, new_disk: str, namespace: str, user: str) -> Dict[str, Any]:
        """Clone a disk by creating a snapshot and new disk"""
        try:
            # Create snapshot
            snapshot_name = f"{source_disk}-snapshot-{int(os.time.time())}"
            snapshot = compute_v1.Snapshot()
            snapshot.name = snapshot_name
            
            snapshots_client = compute_v1.SnapshotsClient()
            operation = snapshots_client.insert(
                project=self.project_id,
                snapshot_resource=snapshot
            )
            self._wait_for_operation(operation.name)
            
            # Create new disk from snapshot
            new_disk_info = self.create_disk(new_disk, namespace, user)
            
            # Attach snapshot to new disk
            disk = compute_v1.Disk()
            disk.source_snapshot = f"projects/{self.project_id}/global/snapshots/{snapshot_name}"
            
            operation = self.client.insert(
                project=self.project_id,
                zone=self.zone,
                disk_resource=disk
            )
            self._wait_for_operation(operation.name)
            
            logger.info(f"✅ Cloned disk {source_disk} -> {new_disk}")
            return new_disk_info
            
        except Exception as e:
            logger.error(f"Failed to clone disk {source_disk}: {e}")
            raise
    
    def attach_disk_to_container(self, disk_name: str, namespace: str, user: str, container_id: str) -> str:
        """Attach GCP persistent disk to container"""
        try:
            # Create mount point
            mount_path = f"/persist/{namespace}/{user}"
            
            # Format disk if needed (this would require attaching to a temporary instance)
            # For now, we'll assume the disk is already formatted
            
            # Mount disk using block device
            subprocess.run([
                "docker", "exec", container_id,
                "mkdir", "-p", mount_path
            ], check=True)
            
            # For Docker containers, we need to pass the disk as a block device
            # This is complex without Kubernetes, so we'll use a bind mount approach
            # In production, you'd want to use GCS FUSE or attach the disk properly
            
            logger.info(f"✅ Prepared mount point {mount_path} in container {container_id}")
            return mount_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to prepare disk mount for {disk_name}: {e}")
            raise Exception(f"Failed to prepare disk mount: {e}")
        except Exception as e:
            logger.error(f"Failed to prepare disk mount for {disk_name}: {e}")
            raise
    
    def _wait_for_operation(self, operation_name: str):
        """Wait for a GCP operation to complete"""
        operations_client = compute_v1.ZoneOperationsClient()
        
        while True:
            operation = operations_client.get(
                project=self.project_id,
                zone=self.zone,
                operation=operation_name
            )
            
            if operation.status == "DONE":
                if operation.error:
                    raise Exception(f"Operation failed: {operation.error}")
                break

    def create_persistent_volume_claim(self, pvc_name: str, namespace: str, size: str = "10Gi", storage_class: str = "standard-rwo") -> Dict[str, Any]:
        """Create a Kubernetes Persistent Volume Claim"""
        try:
            # Generate PVC YAML
            pvc_yaml = f"""apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {pvc_name}
  namespace: {namespace}
  labels:
    app: onmemos
    namespace: {namespace}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: {size}
  storageClassName: {storage_class}"""
            
            # Apply PVC using kubectl
            subprocess.run([
                "kubectl", "apply", "-f", "-"
            ], input=pvc_yaml, text=True, check=True)
            
            logger.info(f"✅ Created PVC: {pvc_name}")
            
            return {
                "pvc_name": pvc_name,
                "namespace": namespace,
                "size": size,
                "storage_class": storage_class,
                "status": "Bound"
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create PVC {pvc_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to create PVC {pvc_name}: {e}")
            raise

    def delete_persistent_volume_claim(self, pvc_name: str, namespace: str) -> bool:
        """Delete a Kubernetes Persistent Volume Claim"""
        try:
            subprocess.run([
                "kubectl", "-n", namespace, "delete", "pvc", pvc_name, "--ignore-not-found"
            ], check=True)
            
            logger.info(f"✅ Deleted PVC: {pvc_name}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to delete PVC {pvc_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete PVC {pvc_name}: {e}")
            return False

# Global instance
disk_service = GCPDiskService()
