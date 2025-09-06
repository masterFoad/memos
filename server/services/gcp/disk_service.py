"""
Real GCP Persistent Disk Service for OnMemOS v3
"""
import os
import time
import subprocess
from typing import Dict, List, Optional, Any

from google.cloud import compute_v1
from google.api_core.exceptions import NotFound, AlreadyExists, GoogleAPICallError

from server.core.logging import get_storage_logger

logger = get_storage_logger()


class GCPDiskService:
    """Real GCP persistent disk service using google-cloud-compute"""

    def __init__(self):
        self.project_id = os.getenv("PROJECT_ID", "ai-engine-448418")
        self.zone = os.getenv("ZONE", "us-central1-a")
        self.region = os.getenv("REGION", "us-central1")
        self.client = compute_v1.DisksClient()
        self.snapshots_client = compute_v1.SnapshotsClient()
        self.zone_ops_client = compute_v1.ZoneOperationsClient()
        self.global_ops_client = compute_v1.GlobalOperationsClient()

    # --------------------------- helpers --------------------------- #

    def _wait_for_zone_operation(self, operation_name: str, timeout: int = 600) -> None:
        """Wait for a Zonal compute operation to complete."""
        start = time.time()
        sleep_s = 1.0
        while True:
            op = self.zone_ops_client.get(
                project=self.project_id, zone=self.zone, operation=operation_name
            )
            status = getattr(op, "status", None)
            # status may be enum (int) or string depending on library version
            is_done = (status == compute_v1.Operation.Status.DONE) or (str(status) == "DONE")
            if is_done:
                if getattr(op, "error", None):
                    # op.error.errors is a repeated field; include short message
                    raise RuntimeError(f"Operation failed: {op.error}")
                return
            if time.time() - start > timeout:
                raise TimeoutError(f"Operation {operation_name} timed out after {timeout}s")
            time.sleep(sleep_s)
            sleep_s = min(5.0, sleep_s * 1.5)

    def _wait_for_global_operation(self, operation_name: str, timeout: int = 600) -> None:
        """Wait for a Global compute operation to complete."""
        start = time.time()
        sleep_s = 1.0
        while True:
            op = self.global_ops_client.get(project=self.project_id, operation=operation_name)
            status = getattr(op, "status", None)
            is_done = (status == compute_v1.Operation.Status.DONE) or (str(status) == "DONE")
            if is_done:
                if getattr(op, "error", None):
                    raise RuntimeError(f"Operation failed: {op.error}")
                return
            if time.time() - start > timeout:
                raise TimeoutError(f"Global operation {operation_name} timed out after {timeout}s")
            time.sleep(sleep_s)
            sleep_s = min(5.0, sleep_s * 1.5)

    def _labels_or_empty(self, labels) -> Dict[str, str]:
        return dict(labels) if labels else {}

    # ----------------------------- CRUD ---------------------------- #

    def create_disk(self, disk_name: str, namespace: str, user: str, size_gb: int = 10) -> Dict[str, Any]:
        """Create a real GCP persistent disk"""
        try:
            disk = compute_v1.Disk()
            disk.name = disk_name
            disk.size_gb = size_gb
            disk.type = f"projects/{self.project_id}/zones/{self.zone}/diskTypes/pd-standard"
            disk.labels = {
                "onmemos": "true",
                "namespace": namespace,
                "user": user,
                "created_by": "onmemos-v3",
            }

            op = self.client.insert(project=self.project_id, zone=self.zone, disk_resource=disk)
            self._wait_for_zone_operation(op.name)

            logger.info(f"✅ Created real GCP persistent disk: {disk_name}")

            return {
                "disk_name": disk_name,
                "namespace": namespace,
                "user": user,
                "size_gb": size_gb,
                "zone": self.zone,
                "type": "pd-standard",
                "status": "READY",
                "mount_path": f"/persist/{namespace}/{user}",
            }

        except AlreadyExists:
            logger.warning(f"Disk {disk_name} already exists")
            return self.get_disk_info(disk_name)
        except GoogleAPICallError as e:
            logger.error(f"Failed to create disk {disk_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to create disk {disk_name}: {e}")
            raise

    def get_disk_info(self, disk_name: str) -> Dict[str, Any]:
        """Get disk information"""
        try:
            disk = self.client.get(project=self.project_id, zone=self.zone, disk=disk_name)
            labels = self._labels_or_empty(getattr(disk, "labels", {}))

            return {
                "disk_name": disk.name,
                "namespace": labels.get("namespace", "unknown"),
                "user": labels.get("user", "unknown"),
                "size_gb": getattr(disk, "size_gb", None),
                "zone": str(disk.zone).split("/")[-1] if getattr(disk, "zone", None) else self.zone,
                "type": str(disk.type).split("/")[-1] if getattr(disk, "type", None) else "pd-standard",
                "status": getattr(disk, "status", "UNKNOWN"),
                "mount_path": f"/persist/{labels.get('namespace', 'unknown')}/{labels.get('user', 'unknown')}",
                "created": getattr(disk, "creation_timestamp", None),
            }
        except NotFound:
            raise Exception(f"Disk {disk_name} not found")
        except Exception as e:
            logger.error(f"Failed to get disk info for {disk_name}: {e}")
            raise

    def list_disks_in_namespace(self, namespace: str) -> List[Dict[str, Any]]:
        """List disks for a namespace (zonal scope)"""
        try:
            out: List[Dict[str, Any]] = []
            req = compute_v1.ListDisksRequest(project=self.project_id, zone=self.zone)
            for disk in self.client.list(request=req):
                labels = self._labels_or_empty(getattr(disk, "labels", {}))
                if labels.get("onmemos") == "true" and labels.get("namespace") == namespace:
                    out.append({
                        "disk_name": disk.name,
                        "namespace": labels.get("namespace"),
                        "user": labels.get("user"),
                        "size_gb": getattr(disk, "size_gb", None),
                        "zone": str(disk.zone).split("/")[-1] if getattr(disk, "zone", None) else self.zone,
                        "type": str(disk.type).split("/")[-1] if getattr(disk, "type", None) else "pd-standard",
                        "status": getattr(disk, "status", "UNKNOWN"),
                        "created": getattr(disk, "creation_timestamp", None),
                    })
            return out
        except Exception as e:
            logger.error(f"Failed to list disks for namespace {namespace}: {e}")
            return []

    def delete_disk(self, disk_name: str) -> bool:
        """Delete a GCP persistent disk"""
        try:
            op = self.client.delete(project=self.project_id, zone=self.zone, disk=disk_name)
            self._wait_for_zone_operation(op.name)
            logger.info(f"✅ Deleted GCP persistent disk: {disk_name}")
            return True
        except NotFound:
            logger.warning(f"Disk {disk_name} not found for deletion")
            return True
        except Exception as e:
            logger.error(f"Failed to delete disk {disk_name}: {e}")
            return False

    def clone_disk(self, source_disk: str, new_disk: str, namespace: str, user: str) -> Dict[str, Any]:
        """Clone a disk by snapshotting the source and creating a new disk from that snapshot."""
        try:
            # 1) Create a snapshot from the source disk (zonal -> global snapshot)
            snapshot_name = f"{source_disk}-snapshot-{int(time.time())}"
            snapshot = compute_v1.Snapshot()
            snapshot.name = snapshot_name
            # Labels are optional; helps cleanup
            snapshot.labels = {"onmemos": "true", "source_disk": source_disk}

            # Use DisksClient.create_snapshot to snapshot the zonal disk
            op = self.client.create_snapshot(
                project=self.project_id,
                zone=self.zone,
                disk=source_disk,
                snapshot_resource=snapshot,
            )
            # This returns a ZONE operation
            self._wait_for_zone_operation(op.name)

            # 2) Create the new disk from the snapshot
            new_disk_res = compute_v1.Disk()
            new_disk_res.name = new_disk
            new_disk_res.type = f"projects/{self.project_id}/zones/{self.zone}/diskTypes/pd-standard"
            new_disk_res.source_snapshot = f"projects/{self.project_id}/global/snapshots/{snapshot_name}"
            new_disk_res.labels = {
                "onmemos": "true",
                "namespace": namespace,
                "user": user,
                "created_by": "onmemos-v3",
                "cloned_from": source_disk,
            }

            op2 = self.client.insert(
                project=self.project_id,
                zone=self.zone,
                disk_resource=new_disk_res,
            )
            self._wait_for_zone_operation(op2.name)

            logger.info(f"✅ Cloned disk {source_disk} -> {new_disk}")

            # 3) Return info in same shape as create_disk
            return {
                "disk_name": new_disk,
                "namespace": namespace,
                "user": user,
                "size_gb": self.get_disk_info(new_disk).get("size_gb"),
                "zone": self.zone,
                "type": "pd-standard",
                "status": "READY",
                "mount_path": f"/persist/{namespace}/{user}",
            }

        except Exception as e:
            logger.error(f"Failed to clone disk {source_disk}: {e}")
            raise

    # ----------------------- k8s PVC helpers ----------------------- #

    def create_persistent_volume_claim(self, pvc_name: str, namespace: str, size: str = "10Gi", storage_class: str = "standard-rwo") -> Dict[str, Any]:
        """Create a Kubernetes Persistent Volume Claim"""
        try:
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
  storageClassName: {storage_class}
"""
            subprocess.run(["kubectl", "apply", "-f", "-"], input=pvc_yaml, text=True, check=True)
            logger.info(f"✅ Created PVC: {pvc_name}")
            return {
                "pvc_name": pvc_name,
                "namespace": namespace,
                "size": size,
                "storage_class": storage_class,
                "status": "Bound",
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
            subprocess.run(
                ["kubectl", "-n", namespace, "delete", "pvc", pvc_name, "--ignore-not-found"],
                check=True,
            )
            logger.info(f"✅ Deleted PVC: {pvc_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to delete PVC {pvc_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete PVC {pvc_name}: {e}")
            return False

    # ------------------------- placeholders ------------------------ #

    def attach_disk_to_container(self, disk_name: str, namespace: str, user: str, container_id: str) -> str:
        """Attach GCP persistent disk to container (placeholder, returns mount point)."""
        try:
            mount_path = f"/persist/{namespace}/{user}"
            subprocess.run(["docker", "exec", container_id, "mkdir", "-p", mount_path], check=True)
            logger.info(f"✅ Prepared mount point {mount_path} in container {container_id}")
            return mount_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to prepare disk mount for {disk_name}: {e}")
            raise Exception(f"Failed to prepare disk mount: {e}")
        except Exception as e:
            logger.error(f"Failed to prepare disk mount for {disk_name}: {e}")
            raise


# Global instance
disk_service = GCPDiskService()
