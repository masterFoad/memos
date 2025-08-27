"""
GKE Service - Enhanced with bucket mounting and persistent storage
"""

import os
import subprocess
import time
from typing import Dict, Any, Optional
from datetime import datetime

from server.core.logging import get_gke_logger
from server.models.sessions import StorageConfig, StorageType, ResourceTier

logger = get_gke_logger()

class GkeService:
    """Enhanced GKE service with bucket mounting and persistent storage support"""
    
    def __init__(self) -> None:
        self.namespace_prefix = os.getenv("GKE_NAMESPACE_PREFIX", "onmemos")
        self.image_default = os.getenv("GKE_DEFAULT_IMAGE", "alpine:latest")  # Use Alpine for proper shell
        self.shell = os.getenv("GKE_SHELL", "/bin/sh")
        
        # Resource tier configurations
        self.resource_limits = {
            ResourceTier.SMALL: {
                "cpu_request": "250m", "cpu_limit": "500m",
                "memory_request": "512Mi", "memory_limit": "1Gi"
            },
            ResourceTier.MEDIUM: {
                "cpu_request": "500m", "cpu_limit": "1",
                "memory_request": "1Gi", "memory_limit": "2Gi"
            },
            ResourceTier.LARGE: {
                "cpu_request": "1", "cpu_limit": "2",
                "memory_request": "2Gi", "memory_limit": "4Gi"
            },
            ResourceTier.XLARGE: {
                "cpu_request": "2", "cpu_limit": "4",
                "memory_request": "4Gi", "memory_limit": "8Gi"
            }
        }

    def create_workspace(self, template: str, namespace: str, user: str, 
                        storage_config: Optional[StorageConfig] = None,
                        resource_tier: Optional[ResourceTier] = None,
                        env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Create workspace with enhanced storage and resource support"""
        ws_id = f"ws-{namespace}-{user}-{int(time.time())}"
        k8s_ns = f"{self.namespace_prefix}-{namespace}"
        # Fix pod naming to be Kubernetes compliant (no underscores)
        safe_user = user.replace('_', '-')
        pod = f"onmemos-{namespace}-{safe_user}-{int(time.time())}"
        
        # Generate bucket name for GCS access
        bucket_name = f"onmemos-{namespace}-{user}-{int(time.time())}"
        
        # Use default storage config if none provided
        if storage_config is None:
            storage_config = StorageConfig(storage_type=StorageType.EPHEMERAL)
        
        # Use default resource tier if none provided
        if resource_tier is None:
            resource_tier = ResourceTier.SMALL
        
        # Use default env if none provided
        if env is None:
            env = {}

        # ensure namespace
        logger.info(f"Creating namespace: {k8s_ns}")
        result = subprocess.run(["kubectl", "get", "ns", k8s_ns], capture_output=True, text=True)
        if result.returncode != 0:
            # Namespace doesn't exist, create it
            create_result = subprocess.run(["kubectl", "create", "ns", k8s_ns], capture_output=True, text=True)
            if create_result.returncode != 0:
                logger.warning(f"Failed to create namespace {k8s_ns}: {create_result.stderr}")
            else:
                logger.info(f"Created namespace: {k8s_ns}")
        else:
            logger.info(f"Namespace {k8s_ns} already exists")

        # Create storage resources if needed
        if storage_config.storage_type == StorageType.GCS_FUSE:
            actual_bucket_name = self._create_gcs_bucket(bucket_name, namespace, user)
            storage_config.bucket_name = actual_bucket_name
        elif storage_config.storage_type == StorageType.PERSISTENT_VOLUME:
            pvc_name = f"pvc-{namespace}-{user}-{int(time.time())}"
            self._create_persistent_volume_claim(k8s_ns, pvc_name, storage_config)
            storage_config.pvc_name = pvc_name

        # create pod with enhanced features
        manifest = self._generate_pod_manifest(
            pod, k8s_ns, ws_id, namespace, user, storage_config.bucket_name or bucket_name,
            storage_config, resource_tier, env
        )
        
        proc = subprocess.run(["kubectl", "-n", k8s_ns, "apply", "-f", "-"], input=manifest, text=True, capture_output=True)
        if proc.returncode != 0:
            logger.error("Failed to apply pod manifest: %s", proc.stderr)
            raise RuntimeError(proc.stderr)

        # Wait for pod to be ready
        logger.info("Waiting for pod %s to be ready...", pod)
        for i in range(30):  # Wait up to 30 seconds
            proc = subprocess.run(
                ["kubectl", "-n", k8s_ns, "get", "pod", pod, "-o", "jsonpath={.status.phase}"],
                capture_output=True, text=True
            )
            if proc.returncode == 0 and proc.stdout.strip() == "Running":
                logger.info("Pod %s is ready", pod)
                break
            time.sleep(1)
        else:
            # Check pod events if it's not ready
            proc = subprocess.run(
                ["kubectl", "-n", k8s_ns, "describe", "pod", pod],
                capture_output=True, text=True
            )
            logger.error("Pod %s failed to become ready. Events:\n%s", pod, proc.stdout)
            raise RuntimeError(f"Pod {pod} failed to become ready")

        return {
            "workspace_id": ws_id,
            "namespace": k8s_ns,
            "pod": pod,
            "status": "running",
            "service_url": None,
            "storage_config": storage_config.dict() if storage_config else None,
            "resource_tier": resource_tier.value if resource_tier else None,
        }

    def _generate_pod_manifest(self, pod: str, k8s_ns: str, ws_id: str, 
                              namespace: str, user: str, bucket_name: str,
                              storage_config: StorageConfig, resource_tier: ResourceTier,
                              env: Dict[str, str]) -> str:
        """Generate enhanced pod manifest with storage and resource configuration"""
        
        # Get resource limits for the tier
        limits = self.resource_limits.get(resource_tier, self.resource_limits[ResourceTier.SMALL])
        
        # Generate volume mounts and volumes
        volume_mounts = []
        volumes = []
        
        if storage_config.storage_type == StorageType.GCS_FUSE:
            # GCS FUSE volume
            volume_mounts.append(f"""
        - name: gcs-fuse
          mountPath: {storage_config.mount_path}""")
            
            volumes.append(f"""
  - name: gcs-fuse
    csi:
      driver: gcsfuse.csi.storage.gke.io
      readOnly: false
      volumeAttributes:
        bucketName: "{storage_config.bucket_name}"
        mountOptions: "{storage_config.gcs_mount_options}" """)
        
        elif storage_config.storage_type == StorageType.PERSISTENT_VOLUME:
            # Persistent volume
            volume_mounts.append(f"""
        - name: persistent-storage
          mountPath: {storage_config.mount_path}""")
            
            volumes.append(f"""
  - name: persistent-storage
    persistentVolumeClaim:
      claimName: {storage_config.pvc_name} """)
        
        # Environment variables
        env_vars = [
            f"""
        - name: WORKSPACE_ID
          value: "{ws_id}" """,
            f"""
        - name: NAMESPACE
          value: "{namespace}" """,
            f"""
        - name: USER
          value: "{user}" """,
            f"""
        - name: BUCKET_NAME
          value: "{bucket_name}" """
        ]
        
        # Add custom environment variables
        for key, value in env.items():
            env_vars.append(f"""
        - name: {key}
          value: "{value}" """)
        
        # Build YAML string properly
        yaml_parts = [
            "apiVersion: v1",
            "kind: Pod",
            "metadata:",
            f"  name: {pod}",
            f"  namespace: {k8s_ns}",
            "  annotations:",
            '    gke-gcsfuse/volumes: "true"',
            "  labels:",
            f"    onmemos_workspace_id: {ws_id}",
            f"    namespace: {namespace}",
            f"    user: {user}",
            f"    resource_tier: {resource_tier.value}",
            "spec:",
            "  restartPolicy: Never",
            "  securityContext:",
            "    seccompProfile:",
            "      type: RuntimeDefault",
            "  containers:",
            "  - name: main",
            f"    image: {self.image_default}",
            f"    command: [\"{self.shell}\", \"-c\", \"sleep 365d\"]",
            "    env:"
        ]
        
        # Add environment variables
        yaml_parts.extend([
            "      - name: WORKSPACE_ID",
            f"        value: \"{ws_id}\"",
            "      - name: NAMESPACE",
            f"        value: \"{namespace}\"",
            "      - name: USER",
            f"        value: \"{user}\"",
            "      - name: BUCKET_NAME",
            f"        value: \"{bucket_name}\""
        ])
        
        # Add custom environment variables
        for key, value in env.items():
            yaml_parts.extend([
                f"      - name: {key}",
                f"        value: \"{value}\""
            ])
        
        # Add resources
        yaml_parts.extend([
            "    resources:",
            "      requests:",
            f"        cpu: \"{limits['cpu_request']}\"",
            f"        memory: \"{limits['memory_request']}\"",
            "      limits:",
            f"        cpu: \"{limits['cpu_limit']}\"",
            f"        memory: \"{limits['memory_limit']}\""
        ])
        
        # Add volume mounts
        if volume_mounts:
            yaml_parts.append("    volumeMounts:")
            yaml_parts.extend(volume_mounts)
        
        # Add security context
        yaml_parts.extend([
            "    securityContext:",
            "      runAsNonRoot: false",
            "      allowPrivilegeEscalation: false",
            "      capabilities:",
            "        drop:",
            "        - ALL"
        ])
        
        # Add volumes
        if volumes:
            yaml_parts.append("  volumes:")
            yaml_parts.extend(volumes)
        
        return "\n".join(yaml_parts)

    def _create_gcs_bucket(self, bucket_name: str, namespace: str, user: str):
        """Create GCS bucket for workspace"""
        try:
            from server.services.gcp.bucket_service import bucket_service
            bucket_service.create_bucket(bucket_name, namespace, user)
            logger.info("Created GCS bucket: %s", bucket_name)
            return bucket_name
        except Exception as e:
            logger.warning("Failed to create GCS bucket %s: %s", bucket_name, e)
            # Try to use a fallback bucket if creation fails
            fallback_bucket = "onmemos-test-bucket-2024"
            logger.info("Using fallback bucket: %s", fallback_bucket)
            return fallback_bucket

    def _create_persistent_volume_claim(self, k8s_ns: str, pvc_name: str, storage_config: StorageConfig):
        """Create persistent volume claim"""
        try:
            from server.services.gcp.disk_service import disk_service
            disk_service.create_persistent_volume_claim(
                pvc_name, k8s_ns, 
                storage_config.pvc_size or "10Gi",
                storage_config.storage_class or "standard-rwo"
            )
            logger.info("Created PVC: %s", pvc_name)
        except Exception as e:
            logger.error("Failed to create PVC %s: %s", pvc_name, e)
            raise

    def exec_in_workspace(self, workspace_id: str, k8s_ns: str, pod: str, command: str, timeout: int = 120) -> Dict[str, Any]:
        """Execute command in workspace (synchronous)"""
        # First check if pod is still running
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

        # Use configurable shell with Alpine-compatible arguments
        shell = os.getenv("GKE_SHELL", "/bin/sh")
        shell_args = os.getenv("GKE_SHELL_ARGS", "-c").split()
        
        # Execute command
        proc = subprocess.run(
            ["kubectl", "-n", k8s_ns, "exec", pod, "--", shell, *shell_args, command],
            capture_output=True, text=True, timeout=timeout
        )
        return {"stdout": proc.stdout, "stderr": proc.stderr, "returncode": proc.returncode, "success": proc.returncode == 0}

    def submit_job(self, workspace_id: str, k8s_ns: str, pod: str, command: str) -> Dict[str, Any]:
        """Submit a job for asynchronous execution (like Cloud Run)"""
        import uuid
        
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Create a Kubernetes Job for this command
        job_name = f"job-{workspace_id}-{job_id[:8]}"
        
        # Create job manifest
        job_manifest = self._generate_job_manifest(job_name, k8s_ns, pod, command)
        
        # Apply the job
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
        """Get the status of a submitted job"""
        try:
            # Get job status
            status_cmd = [
                "kubectl", "-n", k8s_ns, "get", "job", job_name,
                "-o", "jsonpath={.status.conditions[0].type,.status.conditions[0].status,.status.succeeded,.status.failed}"
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
                    # Job completed successfully, fetch logs
                    try:
                        # Get the pod name for this job
                        pod_cmd = [
                            "kubectl", "-n", k8s_ns, "get", "pods", 
                            "-l", f"job-name={job_name}",
                            "-o", "jsonpath={.items[0].metadata.name}"
                        ]
                        pod_proc = subprocess.run(pod_cmd, text=True, capture_output=True, timeout=10)
                        pod_name = pod_proc.stdout.strip() if pod_proc.returncode == 0 else ""
                        
                        if pod_name:
                            # Get logs from the pod
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
                    # Still running or pending
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
        """Generate Kubernetes Job manifest for command execution"""
        yaml_parts = [
            "apiVersion: batch/v1",
            "kind: Job",
            f"metadata:",
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
            "            memory: 512Mi"
        ]
        
        return "\n".join(yaml_parts)

    def delete_workspace(self, k8s_ns: str, pod: str, storage_config: Optional[StorageConfig] = None) -> bool:
        """Delete workspace and cleanup storage resources"""
        # Delete the pod
        subprocess.run(["kubectl", "-n", k8s_ns, "delete", "pod", pod, "--ignore-not-found"], capture_output=True, text=True)
        
        # Cleanup storage resources if provided
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
