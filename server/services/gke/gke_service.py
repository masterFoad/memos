"""
GKE Service - Enhanced with bucket mounting and persistent storage
"""

import os
import re
import subprocess
import time
from typing import Dict, Any, Optional
from datetime import datetime

from server.core.logging import get_gke_logger
from server.models.sessions import StorageConfig, StorageType, ResourceTier
from server.services.identity.identity_provisioner import identity_provisioner

logger = get_gke_logger()

# ----------------------------- helpers ----------------------------- #

def _rfc1123_name(raw: str, max_len: int = 63) -> str:
    """
    Convert an arbitrary string to a valid DNS-1123 label:
    - lowercase alphanumeric and '-'
    - start/end with alphanumeric
    - max length 63 (default)
    """
    s = raw.lower()
    s = re.sub(r"[^a-z0-9-]", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if not s:
        s = "x"
    if len(s) > max_len:
        s = s[:max_len].strip("-")
        if not s:
            s = "x"
    return s

def _event_dump(namespace: str, pod: str) -> str:
    """Return a short event summary for diagnostics (best-effort)."""
    try:
        proc = subprocess.run(
            ["kubectl", "-n", namespace, "get", "events", "--sort-by=.lastTimestamp", "--field-selector", f"involvedObject.name={pod}"],
            capture_output=True, text=True, timeout=20
        )
        if proc.returncode == 0:
            return proc.stdout
        return f"(events unavailable: rc={proc.returncode} err={proc.stderr})"
    except Exception as e:
        return f"(events unavailable: {e})"


class GkeService:
    """Enhanced GKE service with bucket mounting and persistent storage support"""
    
    def __init__(self) -> None:
        self.namespace_prefix = os.getenv("GKE_NAMESPACE_PREFIX", "onmemos")
        # Keep defaults; allow override
        self.image_default = os.getenv("GKE_DEFAULT_IMAGE", "alpine:latest")  # Multi-arch, tiny
        self.shell = os.getenv("GKE_SHELL", "/bin/sh")

        # Wait timeouts (seconds)
        self.wait_schedule_timeout = int(os.getenv("GKE_WAIT_SCHEDULE_TIMEOUT_SEC", "600"))  # up to 10m for scale-up
        self.wait_ready_timeout = int(os.getenv("GKE_WAIT_READY_TIMEOUT_SEC", "300"))        # up to 5m for image pull/start

        # Resource tier configurations (unchanged semantics)
        self.resource_limits = {
            ResourceTier.SMALL:  {"cpu_request": "250m", "cpu_limit": "500m", "memory_request": "512Mi", "memory_limit": "1Gi"},
            ResourceTier.MEDIUM: {"cpu_request": "500m", "cpu_limit": "1",    "memory_request": "1Gi",   "memory_limit": "2Gi"},
            ResourceTier.LARGE:  {"cpu_request": "1",    "cpu_limit": "2",    "memory_request": "2Gi",   "memory_limit": "4Gi"},
            ResourceTier.XLARGE: {"cpu_request": "2",    "cpu_limit": "4",    "memory_request": "4Gi",   "memory_limit": "8Gi"},
        }

    # ----------------------------- capability checks / helpers ----------------------------- #

    def _csidriver_exists(self, driver_name: str) -> bool:
        try:
            proc = subprocess.run(["kubectl", "get", "csidrivers", driver_name], capture_output=True, text=True, timeout=10)
            return proc.returncode == 0
        except Exception:
            return False

    def _ensure_service_account(self, k8s_ns: str, sa_name: str = "ws-sa") -> None:
        try:
            get_sa = subprocess.run(["kubectl", "-n", k8s_ns, "get", "sa", sa_name], capture_output=True, text=True)
            if get_sa.returncode != 0:
                create_sa = subprocess.run(["kubectl", "-n", k8s_ns, "create", "sa", sa_name], capture_output=True, text=True)
                if create_sa.returncode != 0:
                    logger.warning("Failed to create serviceaccount %s/%s: %s", k8s_ns, sa_name, create_sa.stderr)
                else:
                    logger.info("Created serviceaccount: %s/%s", k8s_ns, sa_name)
        except Exception as e:
            logger.warning("Error ensuring serviceaccount %s/%s: %s", k8s_ns, sa_name, e)

    def _maybe_downgrade_storage(self, k8s_ns: str, storage_config: StorageConfig) -> StorageConfig:
        """If CSI drivers are not available and fallback is allowed, switch to EPHEMERAL."""
        allow_fallback = os.getenv("GKE_ALLOW_STORAGE_FALLBACK", "true").lower() in ("1", "true", "yes")
        if not allow_fallback:
            return storage_config

        if storage_config.storage_type == StorageType.GCS_FUSE:
            if not self._csidriver_exists("gcsfuse.csi.storage.gke.io"):
                logger.warning("GCS Fuse CSI driver not found; falling back to EPHEMERAL storage for namespace %s", k8s_ns)
                return StorageConfig(storage_type=StorageType.EPHEMERAL, mount_path=storage_config.mount_path)
        elif storage_config.storage_type == StorageType.PERSISTENT_VOLUME:
            if not self._csidriver_exists("filestore.csi.storage.gke.io"):
                logger.warning("Filestore CSI driver not found; falling back to EPHEMERAL storage for namespace %s", k8s_ns)
                return StorageConfig(storage_type=StorageType.EPHEMERAL, mount_path=storage_config.mount_path)
        return storage_config

    def create_workspace(
        self,
        template: str,
        namespace: str,
        user: str,
        storage_config: Optional[StorageConfig] = None,
        resource_tier: Optional[ResourceTier] = None,
        env: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create workspace with enhanced storage and resource support (no breaking I/O)"""

        # Single timestamp used across names to avoid drift in IDs
        ts = int(time.time())

        # k8s namespace & names
        k8s_ns = _rfc1123_name(f"{self.namespace_prefix}-{namespace}", max_len=63)
        safe_user = _rfc1123_name(user, max_len=30)  # keep user visible but short
        ws_id = _rfc1123_name(f"ws-{namespace}-{user}-{ts}", max_len=63)
        pod = _rfc1123_name(f"onmemos-{namespace}-{safe_user}-{ts}", max_len=63)

        # GCS bucket naming (RFC 1035-ish, all lowercase, dashes, 3–63 chars)
        # Keep original intent, just sanitize
        bucket_name = _rfc1123_name(f"onmemos-{namespace}-{user}-{ts}", max_len=63)

        # Defaults
        if storage_config is None:
            storage_config = StorageConfig(storage_type=StorageType.EPHEMERAL)
        if resource_tier is None:
            resource_tier = ResourceTier.SMALL
        if env is None:
            env = {}

        # Ensure namespace
        logger.info(f"Creating namespace: {k8s_ns}")
        result = subprocess.run(["kubectl", "get", "ns", k8s_ns], capture_output=True, text=True)
        if result.returncode != 0:
            create_result = subprocess.run(["kubectl", "create", "ns", k8s_ns], capture_output=True, text=True)
            if create_result.returncode != 0:
                logger.warning(f"Failed to create namespace {k8s_ns}: {create_result.stderr}")
            else:
                logger.info(f"Created namespace: {k8s_ns}")
        else:
            logger.info(f"Namespace {k8s_ns} already exists")

        # Ensure a per-namespace service account for Workload Identity (fast no-op if exists)
        self._ensure_service_account(k8s_ns, "ws-sa")

        # Optionally auto-provision WI + GSA and bind. Controlled via env AUTO_PROVISION_IDENTITY=true
        if os.getenv("AUTO_PROVISION_IDENTITY", "true").lower() in ("1", "true", "yes"):
            project = os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
            region = os.getenv("GKE_REGION")
            cluster = os.getenv("GKE_CLUSTER")
            if project and region and cluster:
                try:
                    identity_provisioner.ensure_gcloud_context(project, region, cluster)
                    identity_provisioner.ensure_namespace(k8s_ns)
                    identity_provisioner.ensure_ksa(k8s_ns, "ws-sa")
                    gsa_email = identity_provisioner.ensure_gsa(project, identity_provisioner._gsa_id_for_workspace(namespace))
                    identity_provisioner.bind_workload_identity(project, k8s_ns, "ws-sa", gsa_email)
                    identity_provisioner.annotate_ksa(k8s_ns, "ws-sa", gsa_email)
                except Exception as e:
                    logger.warning("Auto identity provision failed or partially applied: %s", e)

        # Storage resource creation (primary storage)
        if storage_config.storage_type == StorageType.GCS_FUSE:
            actual_bucket_name = self._create_gcs_bucket(bucket_name, namespace, user)
            storage_config.bucket_name = actual_bucket_name
            # Grant bucket IAM to workspace GSA if auto-provisioning is configured
            if os.getenv("AUTO_PROVISION_IDENTITY", "true").lower() in ("1", "true", "yes"):
                project = os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
                if project:
                    try:
                        gsa_email = f"{identity_provisioner._gsa_id_for_workspace(namespace)}@{project}.iam.gserviceaccount.com"
                        identity_provisioner.grant_bucket_iam(project, actual_bucket_name, gsa_email)
                        logger.info("Granted bucket IAM to %s on gs://%s", gsa_email, actual_bucket_name)
                    except Exception as e:
                        logger.warning("Failed to grant bucket IAM for %s: %s", actual_bucket_name, e)
        elif storage_config.storage_type == StorageType.PERSISTENT_VOLUME:
            # Generate PVC name if not provided and create it
            if not storage_config.pvc_name:
                pvc_name = _rfc1123_name(f"pvc-{namespace}-{user}-{ts}", max_len=63)
                self._create_persistent_volume_claim(k8s_ns, pvc_name, storage_config)
                storage_config.pvc_name = pvc_name
            else:
                # Ensure the PVC exists (idempotent)
                try:
                    proc_check = subprocess.run(["kubectl", "-n", k8s_ns, "get", "pvc", storage_config.pvc_name], capture_output=True, text=True)
                    if proc_check.returncode != 0:
                        self._create_persistent_volume_claim(k8s_ns, storage_config.pvc_name, storage_config)
                except Exception as e:
                    logger.warning("PVC existence check failed for %s/%s: %s", k8s_ns, storage_config.pvc_name, e)

        # Storage resource creation (additional storage, if any)
        if hasattr(storage_config, "additional_storage") and storage_config.additional_storage:
            for idx, add in enumerate(storage_config.additional_storage):
                try:
                    if add.storage_type == StorageType.GCS_FUSE:
                        # Create bucket if not provided
                        if not add.bucket_name:
                            add_bucket_name = self._create_gcs_bucket(_rfc1123_name(f"{bucket_name}-extra-{idx}", max_len=63), namespace, user)
                            add.bucket_name = add_bucket_name
                        # Grant IAM if configured
                        if os.getenv("AUTO_PROVISION_IDENTITY", "true").lower() in ("1", "true", "yes"):
                            project = os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
                            if project and add.bucket_name:
                                try:
                                    gsa_email = f"{identity_provisioner._gsa_id_for_workspace(namespace)}@{project}.iam.gserviceaccount.com"
                                    identity_provisioner.grant_bucket_iam(project, add.bucket_name, gsa_email)
                                    logger.info("Granted bucket IAM to %s on gs://%s (additional)", gsa_email, add.bucket_name)
                                except Exception as e:
                                    logger.warning("Failed to grant bucket IAM for additional %s: %s", add.bucket_name, e)
                    elif add.storage_type == StorageType.PERSISTENT_VOLUME:
                        # Create PVC if name not provided
                        if not add.pvc_name:
                            add_pvc_name = _rfc1123_name(f"pvc-{namespace}-{user}-{ts}-{idx}", max_len=63)
                            self._create_persistent_volume_claim(k8s_ns, add_pvc_name, add)
                            add.pvc_name = add_pvc_name
                        else:
                            # Ensure PVC exists (idempotent)
                            proc_check = subprocess.run(["kubectl", "-n", k8s_ns, "get", "pvc", add.pvc_name], capture_output=True, text=True)
                            if proc_check.returncode != 0:
                                self._create_persistent_volume_claim(k8s_ns, add.pvc_name, add)
                except Exception as e:
                    logger.warning("Failed to prepare additional storage %s (type=%s): %s", idx, getattr(add, 'storage_type', 'unknown'), e)

        # If CSI drivers not present and fallback allowed, downgrade to EPHEMERAL to avoid blocking startup
        storage_config = self._maybe_downgrade_storage(k8s_ns, storage_config)

        # Create pod manifest/apply
        manifest = self._generate_pod_manifest(
            pod, k8s_ns, ws_id, namespace, user, storage_config.bucket_name or bucket_name,
            storage_config, resource_tier, env
        )
        proc = subprocess.run(
            ["kubectl", "-n", k8s_ns, "apply", "-f", "-"],
            input=manifest, text=True, capture_output=True
        )
        if proc.returncode != 0:
            logger.error("Failed to apply pod manifest: %s", proc.stderr)
            raise RuntimeError(proc.stderr)

        # ---------- Robust wait: PodScheduled then Ready ----------
        logger.info("Waiting for pod %s to be scheduled (timeout=%ss)...", pod, self.wait_schedule_timeout)
        sched = subprocess.run(
            ["kubectl", "-n", k8s_ns, "wait", f"--for=condition=PodScheduled", f"--timeout={self.wait_schedule_timeout}s", "pod", pod],
            capture_output=True, text=True
        )
        if sched.returncode != 0:
            # Dump diagnostics
            desc = subprocess.run(["kubectl", "-n", k8s_ns, "describe", "pod", pod], capture_output=True, text=True)
            events = _event_dump(k8s_ns, pod)
            logger.error("Pod %s failed to schedule within timeout.\nDescribe:\n%s\nEvents:\n%s", pod, desc.stdout, events)
            raise RuntimeError(f"Pod {pod} failed to schedule within {self.wait_schedule_timeout}s")

        logger.info("Pod %s scheduled. Waiting for Ready (timeout=%ss)...", pod, self.wait_ready_timeout)
        ready = subprocess.run(
            ["kubectl", "-n", k8s_ns, "wait", f"--for=condition=Ready", f"--timeout={self.wait_ready_timeout}s", "pod", pod],
            capture_output=True, text=True
        )
        if ready.returncode != 0:
            desc = subprocess.run(["kubectl", "-n", k8s_ns, "describe", "pod", pod], capture_output=True, text=True)
            events = _event_dump(k8s_ns, pod)
            logger.error("Pod %s failed to become Ready.\nDescribe:\n%s\nEvents:\n%s", pod, desc.stdout, events)

            # Attempt resilient fallback to EPHEMERAL if allowed and storage is not EPHEMERAL
            allow_fallback = os.getenv("GKE_ALLOW_STORAGE_FALLBACK", "true").lower() in ("1", "true", "yes")
            if allow_fallback and storage_config.storage_type != StorageType.EPHEMERAL:
                logger.warning("Falling back to EPHEMERAL storage for %s/%s due to readiness failure", k8s_ns, pod)
                # Delete the failing pod
                subprocess.run(["kubectl", "-n", k8s_ns, "delete", "pod", pod, "--ignore-not-found"], capture_output=True, text=True)
                # Build EPHEMERAL manifest and re-apply
                fallback_config = StorageConfig(storage_type=StorageType.EPHEMERAL, mount_path=storage_config.mount_path)
                fallback_manifest = self._generate_pod_manifest(
                    pod, k8s_ns, ws_id, namespace, user, bucket_name, fallback_config, resource_tier, env
                )
                proc2 = subprocess.run(
                    ["kubectl", "-n", k8s_ns, "apply", "-f", "-"],
                    input=fallback_manifest, text=True, capture_output=True
                )
                if proc2.returncode != 0:
                    logger.error("Failed to apply fallback pod manifest: %s", proc2.stderr)
                    raise RuntimeError(f"Pod {pod} failed to become ready (fallback apply failed)")

                # Wait again: PodScheduled then Ready
                sched2 = subprocess.run(
                    ["kubectl", "-n", k8s_ns, "wait", f"--for=condition=PodScheduled", f"--timeout={self.wait_schedule_timeout}s", "pod", pod],
                    capture_output=True, text=True
                )
                if sched2.returncode != 0:
                    desc2 = subprocess.run(["kubectl", "-n", k8s_ns, "describe", "pod", pod], capture_output=True, text=True)
                    events2 = _event_dump(k8s_ns, pod)
                    logger.error("Fallback pod %s failed to schedule within timeout.\nDescribe:\n%s\nEvents:\n%s", pod, desc2.stdout, events2)
                    raise RuntimeError(f"Pod {pod} failed to schedule (fallback)")

                ready2 = subprocess.run(
                    ["kubectl", "-n", k8s_ns, "wait", f"--for=condition=Ready", f"--timeout={self.wait_ready_timeout}s", "pod", pod],
                    capture_output=True, text=True
                )
                if ready2.returncode != 0:
                    desc2 = subprocess.run(["kubectl", "-n", k8s_ns, "describe", "pod", pod], capture_output=True, text=True)
                    events2 = _event_dump(k8s_ns, pod)
                    logger.error("Fallback pod %s failed to become Ready.\nDescribe:\n%s\nEvents:\n%s", pod, desc2.stdout, events2)
                    raise RuntimeError(f"Pod {pod} failed to become ready (fallback)")

                # Overwrite storage_config to EPHEMERAL since fallback succeeded
                storage_config = fallback_config
                logger.info("Fallback to EPHEMERAL succeeded for pod %s", pod)
            else:
                raise RuntimeError(f"Pod {pod} failed to become ready")

        logger.info("Pod %s is Ready", pod)

        return {
            "workspace_id": ws_id,
            "namespace": k8s_ns,
            "pod": pod,
            "status": "running",
            "service_url": None,
            "storage_config": storage_config.dict() if storage_config else None,
            "resource_tier": resource_tier.value if resource_tier else None,
        }

    def _generate_pod_manifest(
        self, pod: str, k8s_ns: str, ws_id: str, 
        namespace: str, user: str, bucket_name: str,
        storage_config: StorageConfig, resource_tier: ResourceTier,
        env: Dict[str, str]
    ) -> str:
        """Generate enhanced pod manifest with storage and resource configuration"""

        limits = self.resource_limits.get(resource_tier, self.resource_limits[ResourceTier.SMALL])

        # Build volume mounts / volumes blocks
        volume_mounts = []
        volumes = []

        if storage_config.storage_type == StorageType.GCS_FUSE:
            volume_mounts.append(
                "      - name: gcs-fuse\n"
                f"        mountPath: {storage_config.mount_path}"
            )
            volumes.append(
                "  - name: gcs-fuse\n"
                "    csi:\n"
                "      driver: gcsfuse.csi.storage.gke.io\n"
                "      readOnly: false\n"
                "      volumeAttributes:\n"
                f"        bucketName: \"{storage_config.bucket_name}\"\n"
                f"        mountOptions: \"{storage_config.gcs_mount_options}\""
            )

        elif storage_config.storage_type == StorageType.PERSISTENT_VOLUME:
            volume_mounts.append(
                "      - name: persistent-storage\n"
                f"        mountPath: {storage_config.mount_path}"
            )
            volumes.append(
                "  - name: persistent-storage\n"
                "    persistentVolumeClaim:\n"
                f"      claimName: {storage_config.pvc_name}"
            )

        if hasattr(storage_config, "additional_storage") and storage_config.additional_storage:
            for i, additional_storage in enumerate(storage_config.additional_storage):
                if additional_storage.storage_type == StorageType.GCS_FUSE:
                    volume_mounts.append(
                        f"      - name: gcs-fuse-{i}\n"
                        f"        mountPath: {additional_storage.mount_path}"
                    )
                    volumes.append(
                        f"  - name: gcs-fuse-{i}\n"
                        "    csi:\n"
                        "      driver: gcsfuse.csi.storage.gke.io\n"
                        "      readOnly: false\n"
                        "      volumeAttributes:\n"
                        f"        bucketName: \"{additional_storage.bucket_name}\"\n"
                        f"        mountOptions: \"{additional_storage.gcs_mount_options}\""
                    )
                elif additional_storage.storage_type == StorageType.PERSISTENT_VOLUME:
                    volume_mounts.append(
                        f"      - name: persistent-storage-{i}\n"
                        f"        mountPath: {additional_storage.mount_path}"
                    )
                    volumes.append(
                        f"  - name: persistent-storage-{i}\n"
                        "    persistentVolumeClaim:\n"
                        f"      claimName: {additional_storage.pvc_name}"
                    )

        # Start YAML parts
        yaml_parts = [
            "apiVersion: v1",
            "kind: Pod",
            "metadata:",
            f"  name: {pod}",
            f"  namespace: {k8s_ns}",
            "  annotations:",
        ]
        if storage_config.storage_type == StorageType.GCS_FUSE:
            yaml_parts.append('    gke-gcsfuse/volumes: "true"')
        yaml_parts.extend([
            "  labels:",
            f"    onmemos_workspace_id: {ws_id}",
            f"    namespace: {namespace}",
            f"    user: {user}",
            f"    resource_tier: {resource_tier.value}",
            "spec:",
            "  serviceAccountName: ws-sa",
            "  restartPolicy: Never",
            "  securityContext:",
            "    seccompProfile:",
            "      type: RuntimeDefault",
            "  containers:",
            "  - name: main",
            f"    image: {self.image_default}",
            "    imagePullPolicy: IfNotPresent",
            f"    command: [\"{self.shell}\", \"-c\", \"sleep 3600\"]",
            "    env:",
            "      - name: WORKSPACE_ID",
            f"        value: \"{ws_id}\"",
            "      - name: NAMESPACE",
            f"        value: \"{namespace}\"",
            "      - name: USER",
            f"        value: \"{user}\"",
            "      - name: BUCKET_NAME",
            f"        value: \"{bucket_name}\"",
        ])

        # Custom env
        for key, value in env.items():
            yaml_parts.extend([
                f"      - name: {key}",
                f"        value: \"{value}\""
            ])

        # Resources
        yaml_parts.extend([
            "    resources:",
            "      requests:",
            f"        cpu: \"{limits['cpu_request']}\"",
            f"        memory: \"{limits['memory_request']}\"",
            "      limits:",
            f"        cpu: \"{limits['cpu_limit']}\"",
            f"        memory: \"{limits['memory_limit']}\"",
        ])

        # Volume mounts
        if volume_mounts:
            yaml_parts.append("    volumeMounts:")
            yaml_parts.extend(volume_mounts)

        # Security context (unchanged)
        yaml_parts.extend([
            "    securityContext:",
            "      runAsNonRoot: false",
            "      allowPrivilegeEscalation: false",
            "      capabilities:",
            "        drop:",
            "        - ALL",
        ])

        # Volumes
        if volumes:
            yaml_parts.append("  volumes:")
            yaml_parts.extend(volumes)

        return "\n".join(yaml_parts)

    def _create_gcs_bucket(self, bucket_name: str, namespace: str, user: str):
        """Create GCS bucket for workspace (keeps original behavior; better naming)"""
        try:
            from server.services.gcp.bucket_service import bucket_service
            bucket_service.create_bucket(bucket_name, namespace, user)
            logger.info("Created GCS bucket: %s", bucket_name)
            return bucket_name
        except Exception as e:
            logger.warning("Failed to create GCS bucket %s: %s", bucket_name, e)
            fallback_bucket = "onmemos-test-bucket-2024"
            logger.info("Using fallback bucket: %s", fallback_bucket)
            return fallback_bucket

    def _create_persistent_volume_claim(self, k8s_ns: str, pvc_name: str, storage_config: StorageConfig):
        """Create persistent volume claim"""
        try:
            from server.services.gcp.disk_service import disk_service
            disk_service.create_persistent_volume_claim(
                pvc_name,
                k8s_ns,
                storage_config.pvc_size or "10Gi",
                storage_config.storage_class or "standard-rwo",
            )
            logger.info("Created PVC: %s", pvc_name)
        except Exception as e:
            logger.error("Failed to create PVC %s: %s", pvc_name, e)
            raise

    def exec_in_workspace(self, workspace_id: str, k8s_ns: str, pod: str, command: str, timeout: int = 120) -> Dict[str, Any]:
        """Execute command in workspace (synchronous)"""
        proc = subprocess.run(
            ["kubectl", "-n", k8s_ns, "get", "pod", pod, "-o", "jsonpath={.status.phase}"],
            capture_output=True, text=True
        )
        if proc.returncode != 0 or proc.stdout.strip() != "Running":
            logger.error("Pod %s is not running. Status: %s", pod, proc.stdout.strip())
            return {
                "stdout": "",
                "stderr": f"Pod {pod} is not running. Status: {proc.stdout.strip()}",
                "returncode": 1,
                "success": False
            }

        shell = os.getenv("GKE_SHELL", "/bin/sh")
        shell_args = os.getenv("GKE_SHELL_ARGS", "-c").split()
        
        proc = subprocess.run(
            ["kubectl", "-n", k8s_ns, "exec", pod, "--", shell, *shell_args, command],
            capture_output=True, text=True, timeout=timeout
        )
        return {"stdout": proc.stdout, "stderr": proc.stderr, "returncode": proc.returncode, "success": proc.returncode == 0}

    def submit_job(self, workspace_id: str, k8s_ns: str, pod: str, command: str) -> Dict[str, Any]:
        """Submit a job for asynchronous execution (like Cloud Run)"""
        import uuid
        job_id = str(uuid.uuid4())
        job_name = _rfc1123_name(f"job-{workspace_id}-{job_id[:8]}", max_len=63)

        job_manifest = self._generate_job_manifest(job_name, k8s_ns, pod, command)
        proc = subprocess.run(
            ["kubectl", "-n", k8s_ns, "apply", "-f", "-"], 
            input=job_manifest, text=True, capture_output=True
        )
        if proc.returncode != 0:
            return {
                "success": False,
                "status": "failed",
                "message": f"Failed to submit job: {proc.stderr}",
                "stdout": "",
                "stderr": proc.stderr,
                "returncode": proc.returncode,
                "job_id": job_id
            }
        
        logger.info("✅ Job submitted successfully: %s", job_id)
        return {
            "success": True,
            "status": "submitted",
            "message": "Job submitted successfully. Use job_id to poll for status.",
            "stdout": f"Job {job_id} submitted successfully",
            "stderr": "",
            "returncode": 0,
            "job_id": job_id,
            "job_name": job_name
        }

    def get_job_status(self, job_id: str, k8s_ns: str, job_name: str) -> Dict[str, Any]:
        """Get the status of a submitted job (same I/O)"""
        try:
            status_cmd = [
                "kubectl", "-n", k8s_ns, "get", "job", job_name,
                "-o", "jsonpath={.status.conditions[0].type}{'\t'}{.status.conditions[0].status}{'\t'}{.status.succeeded}{'\t'}{.status.failed}"
            ]
            status_proc = subprocess.run(status_cmd, text=True, capture_output=True, timeout=10, check=False)
            if status_proc.returncode != 0:
                return {
                    "success": False,
                    "status": "unknown",
                    "message": f"Failed to get job status: {status_proc.stderr}",
                    "stdout": "",
                    "stderr": status_proc.stderr,
                    "returncode": status_proc.returncode,
                    "job_id": job_id
                }
            
            status_output = status_proc.stdout.strip()
            parts = status_output.split('\t')
            if len(parts) >= 4:
                condition_type, condition_status, succeeded, failed = parts[0], parts[1], parts[2], parts[3]
                if condition_type == "Complete" and condition_status == "True":
                    try:
                        pod_cmd = [
                            "kubectl", "-n", k8s_ns, "get", "pods", 
                            "-l", f"job-name={job_name}",
                            "-o", "jsonpath={.items[0].metadata.name}"
                        ]
                        pod_proc = subprocess.run(pod_cmd, text=True, capture_output=True, timeout=10)
                        pod_name = pod_proc.stdout.strip() if pod_proc.returncode == 0 else ""
                        if pod_name:
                            log_cmd = ["kubectl", "-n", k8s_ns, "logs", pod_name]
                            log_proc = subprocess.run(log_cmd, text=True, capture_output=True, timeout=30)
                            stdout = log_proc.stdout.strip() if log_proc.returncode == 0 else ""
                            stderr = log_proc.stderr.strip() if log_proc.returncode == 0 else ""
                            return {
                                "success": True,
                                "status": "completed",
                                "message": "Job completed successfully",
                                "stdout": stdout,
                                "stderr": stderr,
                                "returncode": 0,
                                "job_id": job_id,
                                "job_name": job_name
                            }
                        else:
                            return {
                                "success": True,
                                "status": "completed",
                                "message": "Job completed but could not fetch logs",
                                "stdout": "",
                                "stderr": "Could not find job pod",
                                "returncode": 0,
                                "job_id": job_id,
                                "job_name": job_name
                            }
                    except Exception as e:
                        return {
                            "success": True,
                            "status": "completed",
                            "message": f"Job completed but failed to fetch logs: {e}",
                            "stdout": "",
                            "stderr": str(e),
                            "returncode": 0,
                            "job_id": job_id,
                            "job_name": job_name
                        }
                elif condition_type == "Failed" and condition_status == "True":
                    return {
                        "success": False,
                        "status": "failed",
                        "message": "Job failed",
                        "stdout": "",
                        "stderr": "Job execution failed",
                        "returncode": 1,
                        "job_id": job_id,
                        "job_name": job_name
                    }
                else:
                    return {
                        "success": True,
                        "status": "running",
                        "message": f"Job is {condition_type.lower()}: {condition_status}",
                        "stdout": "",
                        "stderr": "",
                        "returncode": None,
                        "job_id": job_id,
                        "job_name": job_name
                    }

            return {
                "success": False,
                "status": "unknown",
                "message": f"Unexpected status format: {status_output}",
                "stdout": "",
                "stderr": status_output,
                "returncode": None,
                "job_id": job_id,
                "job_name": job_name
            }
        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "message": f"Error checking job status: {e}",
                "stdout": "",
                "stderr": str(e),
                "returncode": None,
                "job_id": job_id,
                "job_name": job_name
            }

    def _generate_job_manifest(self, job_name: str, k8s_ns: str, pod: str, command: str) -> str:
        """Generate Kubernetes Job manifest for command execution (unchanged I/O)"""
        yaml_parts = [
            "apiVersion: batch/v1",
            "kind: Job",
            "metadata:",
            f"  name: {job_name}",
            f"  namespace: {k8s_ns}",
            "spec:",
            "  backoffLimit: 0",
            "  template:",
            "    spec:",
            "      restartPolicy: Never",
            "      containers:",
            "      - name: executor",
            f"        image: {self.image_default}",
            "        imagePullPolicy: IfNotPresent",
            "        command:",
            f"        - {self.shell}",
            "        - -c",
            f"        - {command}",
            "        env:",
            "        - name: WORKSPACE_ID",
            "          valueFrom:",
            "            fieldRef:",
            "              fieldPath: metadata.name",
            "        - name: JOB_ID",
            "          valueFrom:",
            "            fieldRef:",
            "              fieldPath: metadata.name",
            "        resources:",
            "          requests:",
            "            cpu: 100m",
            "            memory: 128Mi",
            "          limits:",
            "            cpu: 500m",
            "            memory: 512Mi",
        ]
        return "\n".join(yaml_parts)

    def delete_workspace(self, k8s_ns: str, pod: str, storage_config: Optional[StorageConfig] = None) -> bool:
        """Delete workspace and cleanup storage resources (same behavior)"""
        subprocess.run(["kubectl", "-n", k8s_ns, "delete", "pod", pod, "--ignore-not-found"], capture_output=True, text=True)
        
        if storage_config:
            if storage_config.storage_type == StorageType.GCS_FUSE and storage_config.bucket_name:
                try:
                    from server.services.gcp.bucket_service import bucket_service
                    bucket_service.delete_bucket(storage_config.bucket_name)
                    logger.info("Deleted GCS bucket: %s", storage_config.bucket_name)
                except Exception as e:
                    logger.warning("Failed to delete GCS bucket %s: %s", storage_config.bucket_name, e)
            elif storage_config.storage_type == StorageType.PERSISTENT_VOLUME and storage_config.pvc_name:
                try:
                    from server.services.gcp.disk_service import disk_service
                    disk_service.delete_persistent_volume_claim(storage_config.pvc_name, k8s_ns)
                    logger.info("Deleted PVC: %s", storage_config.pvc_name)
                except Exception as e:
                    logger.warning("Failed to delete PVC %s: %s", storage_config.pvc_name, e)
        return True


gke_service = GkeService()
