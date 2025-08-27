#!/usr/bin/env python3
"""
Cloud Run Service for OnMemOS v3
===============================
Replaces Docker-based workspace management with Cloud Run services
"""

from __future__ import annotations

import os
import subprocess
import time
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple

from google.cloud import run_v2
from google.cloud import storage
from google.cloud import compute_v1  # kept for parity

from server.core.logging import get_cloudrun_logger

logger = get_cloudrun_logger()


@dataclass(frozen=True)
class WorkspaceRecord:
    id: str
    namespace: str
    user: str
    service_name: str
    service_url: str
    status: str
    bucket_name: Optional[str] = None


class CloudRunService:
    """Cloud Run service with label-based discovery and Jobs-based command exec."""

    def __init__(self) -> None:
        self.project_id: str = os.getenv("PROJECT_ID", "ai-engine-448418")
        self.region: str = os.getenv("REGION", "us-central1")
        
        # Initialize Cloud Run client with proper authentication
        try:
            # 1. Try Service Account Key File (Primary method for VM-based services)
            key_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if key_file and os.path.exists(key_file):
                from google.auth import load_credentials_from_file
                credentials, project = load_credentials_from_file(key_file)
                self.client = run_v2.ServicesClient(credentials=credentials)
                logger.info(f"✅ CloudRunService using Service Account Key File: {key_file}")
            else:
                # Fallback to local file
                key_file = "./service-account-key.json"
                if key_file and os.path.exists(key_file):
                    from google.auth import load_credentials_from_file
                    credentials, project = load_credentials_from_file(key_file)
                    self.client = run_v2.ServicesClient(credentials=credentials)
                    logger.info(f"✅ CloudRunService using local Service Account Key File: {key_file}")
                else:
                    raise Exception("No service account key file found")
        except Exception as e:
            logger.warning(f"Service Account Key failed: {e}")
            try:
                # 2. Try Workload Identity / Metadata Server (GKE/GCE)
                from google.auth import default
                credentials, project = default()
                self.client = run_v2.ServicesClient(credentials=credentials)
                logger.info(f"✅ CloudRunService using Workload Identity / Metadata Server authentication")
            except Exception as e2:
                logger.error(f"All authentication methods failed: {e2}")
                self.client = run_v2.ServicesClient()
        
        # Initialize storage client with proper authentication
        try:
            # 1. Try Service Account Key File (Primary method for VM-based services)
            key_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if key_file and os.path.exists(key_file):
                self.storage_client = storage.Client.from_service_account_json(key_file, project=self.project_id)
                logger.info(f"✅ CloudRunService storage using Service Account Key File: {key_file}")
            else:
                # Fallback to local file
                key_file = "./service-account-key.json"
                if key_file and os.path.exists(key_file):
                    self.storage_client = storage.Client.from_service_account_json(key_file, project=self.project_id)
                    logger.info(f"✅ CloudRunService storage using local Service Account Key File: {key_file}")
                else:
                    raise Exception("No service account key file found")
        except Exception as e:
            logger.warning(f"Service Account Key failed: {e}")
            try:
                # 2. Try Workload Identity / Metadata Server (GKE/GCE)
                from google.auth import default
                credentials, project = default()
                self.storage_client = storage.Client(credentials=credentials, project=project or self.project_id)
                logger.info(f"✅ CloudRunService storage using Workload Identity / Metadata Server authentication")
            except Exception as e2:
                logger.error(f"All authentication methods failed: {e2}")
                self.storage_client = storage.Client(project=self.project_id)
        
        self.compute_client: compute_v1.DisksClient = compute_v1.DisksClient()
        logger.info("🔧 CloudRunService initialized - Project=%s Region=%s", self.project_id, self.region)

    # ---------- Public API ----------

    def create_workspace(
        self,
        template: str,
        namespace: str,
        user: str,
        ttl_minutes: int = 180,
        storage_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        start = time.time()
        workspace_id = f"ws-{namespace}-{user}-{int(start)}"
        bucket_name = f"onmemos-{namespace}-{user}-{int(start)}"

        # 1) Bucket with labels
        bucket = self.storage_client.bucket(bucket_name)
        bucket.labels = {
            "onmemos_workspace_id": workspace_id,
            "namespace": namespace,
            "user": user,
        }
        bucket.create(location=self.region)
        logger.info("✅ GCS bucket created: %s", bucket_name)

        # 2) Service with labels/env
        service_name = f"onmemos-{workspace_id}"
        url = self._deploy_cloud_run_service(
            service_name=service_name,
            template=template,
            bucket_name=bucket_name,
            namespace=namespace,
            user=user,
            workspace_id=workspace_id,
        )

        record = {
            "id": workspace_id,
            "template": template,
            "namespace": namespace,
            "user": user,
            "service_name": service_name,
            "service_url": url,
            "bucket_name": bucket_name,
            "filestore_instance": "in-memory",
            "created_at": time.time(),
            "ttl_minutes": ttl_minutes,
            "status": "running",
        }
        logger.info("✅ WORKSPACE CREATED id=%s url=%s", workspace_id, url)
        return record

    def list_workspaces(self, namespace: Optional[str] = None, user: Optional[str] = None) -> List[Dict[str, Any]]:
        parent = f"projects/{self.project_id}/locations/{self.region}"
        req = run_v2.ListServicesRequest(parent=parent)
        try:
            services = list(self.client.list_services(request=req))
        except Exception as e:
            logger.error("❌ LIST SERVICES FAILED: %s", e)
            return []

        items: List[Dict[str, Any]] = []
        for svc in services:
            labels = dict(getattr(svc, "labels", {}) or {})
            ws_id = labels.get("onmemos_workspace_id")
            if not ws_id:
                continue
            ws_ns, ws_user = labels.get("namespace", ""), labels.get("user", "")
            if namespace and ws_ns != namespace:
                continue
            if user and ws_user != user:
                continue

            service_name = svc.name.split("/")[-1]
            url = getattr(svc, "uri", "") or getattr(getattr(svc, "status", None), "uri", "") or ""
            items.append(
                {
                    "id": ws_id,
                    "namespace": ws_ns,
                    "user": ws_user,
                    "service_name": service_name,
                    "service_url": url,
                    "status": "running",
                    "bucket_name": labels.get("bucket"),
                }
            )
        logger.info("✅ LIST WORKSPACES count=%d", len(items))
        return items

    def get_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        for it in self.list_workspaces():
            if it["id"] == workspace_id:
                return it
        return None

    def delete_workspace(self, workspace_id: str) -> bool:
        ws = self.get_workspace(workspace_id)
        if not ws:
            logger.warning("⚠️  WORKSPACE NOT FOUND: %s", workspace_id)
            return False

        # delete service
        try:
            subprocess.run(
                ["gcloud", "run", "services", "delete", ws["service_name"], "--region", self.region, "--quiet"],
                check=False, text=True, capture_output=True
            )
            logger.info("🗑️  Deleted Cloud Run service: %s", ws["service_name"])
        except Exception as e:
            logger.warning("⚠️  Failed to delete service %s: %s", ws["service_name"], e)

        # delete bucket (by name if we have it; otherwise scan by label)
        bucket_name = ws.get("bucket_name") or self._find_bucket_by_label("onmemos_workspace_id", workspace_id)
        if bucket_name:
            try:
                self.storage_client.bucket(bucket_name).delete(force=True)
                logger.info("🗑️  Deleted GCS bucket: %s", bucket_name)
            except Exception as e:
                logger.warning("⚠️  Failed to delete bucket %s: %s", bucket_name, e)

        return True

    def execute_in_workspace(self, workspace_id: str, command: str, timeout: int = 120) -> Dict[str, Any]:
        ws = self.get_workspace(workspace_id)
        if not ws:
            raise RuntimeError(f"Workspace {workspace_id} not found")

        service_name = ws["service_name"]
        full_service_name = f"projects/{self.project_id}/locations/{self.region}/services/{service_name}"
        service = self.client.get_service(name=full_service_name)

        tmpl = service.template
        containers = list(getattr(tmpl, "containers", []) or [])
        # Use a proper shell image for jobs instead of the hello image
        image = "gcr.io/cloudrun/hello"  # We'll override this for jobs
        # For jobs, use a proper shell image
        job_image = "alpine:latest"  # Alpine has a proper shell
        service_account = getattr(tmpl, "service_account", None) or f"agent-gcs-accessor@{self.project_id}.iam.gserviceaccount.com"

        job_name = f"{service_name}-exec"
        self._ensure_exec_job(job_name, image=job_image, service_account=service_account, env={
            "WORKSPACE_ID": service_name,
            "NAMESPACE": ws["namespace"],
            "USER": ws["user"],
        })

        # For Cloud Run Jobs, --args expects the format --args=[ARG,...]
        exec_cmd = [
            "gcloud", "run", "jobs", "execute", job_name,
            "--region", self.region,
            f"--args=-c,{command}",
            "--task-timeout", "300s",  # Increase timeout for job execution (5 minutes)
        ]
        logger.info("💻 Exec job: %s", " ".join(exec_cmd))
        try:
            proc = subprocess.run(exec_cmd, text=True, capture_output=True, timeout=30, check=False)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Job submission timed out after 30 seconds")
        
        # Extract execution ID from output
        execution_id = None
        for line in (proc.stdout + "\n" + proc.stderr).splitlines():
            if "Execution [" in line and "] has successfully started running" in line:
                # Extract execution ID from line like "Execution [execution-id] has successfully started running"
                cleaned_line = re.sub(r'\x1b\[[0-9;]*m', '', line)
                start = cleaned_line.find("[") + 1
                end = cleaned_line.find("]")
                if start > 0 and end > start:
                    execution_id = cleaned_line[start:end]
                break
        
        if not execution_id:
            raise RuntimeError("Could not extract execution ID from job submission")
        
        # Return job submission response - client can poll for completion
        logger.info("✅ Job submitted successfully: %s", execution_id)
        
        return {
            "stdout": f"Job {execution_id} submitted successfully",
            "stderr": "",
            "returncode": 0,
            "success": True,
            "execution_id": execution_id,
            "status": "submitted",
            "message": "Job submitted successfully. Use execution_id to poll for status."
        }

    def get_job_status(self, execution_id: str) -> Dict[str, Any]:
        """Get the status of a Cloud Run job execution"""
        try:
            status_cmd = [
                "gcloud", "run", "jobs", "executions", "describe", execution_id,
                "--region", self.region,
                "--format", "value(status.conditions[0].type,status.conditions[0].status,status.conditions[0].message)"
            ]
            status_proc = subprocess.run(status_cmd, text=True, capture_output=True, timeout=10, check=False)
            
            if status_proc.returncode != 0:
                return {
                    "success": False,
                    "status": "unknown",
                    "message": f"Failed to get status: {status_proc.stderr}",
                    "stdout": "",
                    "stderr": status_proc.stderr,
                    "returncode": status_proc.returncode
                }
            
            status_output = status_proc.stdout.strip()
            parts = status_output.split('\t')
            
            if len(parts) >= 3:
                condition_type, condition_status, message = parts[0], parts[1], parts[2]
                
                if condition_type == "Ready" and condition_status == "True":
                    # Job completed successfully, fetch logs
                    try:
                        log_cmd = [
                            "gcloud", "alpha", "run", "jobs", "executions", "logs", "read",
                            execution_id, "--region", self.region
                        ]
                        log_proc = subprocess.run(log_cmd, text=True, capture_output=True, timeout=30)
                        stdout = log_proc.stdout.strip() if log_proc.returncode == 0 else ""
                        
                        return {
                            "success": True,
                            "status": "completed",
                            "message": "Job completed successfully",
                            "stdout": stdout,
                            "stderr": "",
                            "returncode": 0,
                            "execution_id": execution_id
                        }
                    except Exception as e:
                        return {
                            "success": True,
                            "status": "completed",
                            "message": f"Job completed but failed to fetch logs: {e}",
                            "stdout": "",
                            "stderr": str(e),
                            "returncode": 0,
                            "execution_id": execution_id
                        }
                
                elif condition_type == "Failed":
                    return {
                        "success": False,
                        "status": "failed",
                        "message": message or "Job failed",
                        "stdout": "",
                        "stderr": message or "Job failed",
                        "returncode": 1,
                        "execution_id": execution_id
                    }
                
                else:
                    # Still running or pending
                    return {
                        "success": True,
                        "status": "running",
                        "message": f"Job is {condition_type.lower()}: {message or 'In progress'}",
                        "stdout": "",
                        "stderr": "",
                        "returncode": None,
                        "execution_id": execution_id
                    }
            
            return {
                "success": False,
                "status": "unknown",
                "message": f"Unexpected status format: {status_output}",
                "stdout": "",
                "stderr": status_output,
                "returncode": None,
                "execution_id": execution_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "message": f"Error checking job status: {e}",
                "stdout": "",
                "stderr": str(e),
                "returncode": None,
                "execution_id": execution_id
            }

    # ---------- internals ----------

    def _deploy_cloud_run_service(
        self, service_name: str, template: str, bucket_name: str, namespace: str, user: str, workspace_id: str
    ) -> str:
        image_name = "gcr.io/cloudrun/hello"  # Keep for service, but we'll use a different image for jobs
        labels = f"onmemos_workspace_id={workspace_id},namespace={namespace},user={user},bucket={bucket_name}"
        env = f"WORKSPACE_ID={service_name},NAMESPACE={namespace},USER={user},BUCKET_NAME={bucket_name}"
        cmd = [
            "gcloud", "run", "deploy", service_name,
            "--image", image_name,
            "--region", self.region,
            "--platform", "managed",
            "--allow-unauthenticated",
            "--memory", "2Gi",
            "--cpu", "1",
            "--timeout", "3600",
            "--concurrency", "1",
            "--max-instances", "1",
            "--set-env-vars", env,
            "--labels", labels,
            "--service-account", f"agent-gcs-accessor@{self.project_id}.iam.gserviceaccount.com",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        url = self._extract_service_url(res.stdout) or self._extract_service_url(res.stderr)
        if not url:
            logger.error("Could not extract service URL.\nSTDOUT:\n%s\nSTDERR:\n%s", res.stdout, res.stderr)
            raise RuntimeError("Could not extract service URL from deployment output")
        return url

    def _ensure_exec_job(self, job_name: str, image: str, service_account: str, env: Dict[str, str]) -> None:
        desc = subprocess.run(
            ["gcloud", "run", "jobs", "describe", job_name, "--region", self.region],
            capture_output=True, text=True
        )
        if desc.returncode == 0:
            return

        env_kv = ",".join(f"{k}={v}" for k, v in env.items())
        create = [
            "gcloud", "run", "jobs", "create", job_name,
            "--region", self.region,
            "--image", image,
            "--tasks", "1",
            "--max-retries", "0",
            "--task-timeout", "3600s",
            "--command", "/bin/sh",
            "--args", "-c,echo exec-ready",
            "--set-env-vars", env_kv,
            "--service-account", service_account,
        ]
        res = subprocess.run(create, text=True, capture_output=True)
        if res.returncode != 0:
            logger.error("❌ Failed to create exec job:\nSTDOUT:\n%s\nSTDERR:\n%s", res.stdout, res.stderr)
            raise RuntimeError("Failed to create exec job")

    @staticmethod
    def _extract_service_url(text: str) -> Optional[str]:
        for line in (text or "").splitlines():
            if "Service URL:" in line:
                cleaned = re.sub(r"\x1b\[[0-9;]*m", "", line)
                return cleaned.split("Service URL:")[1].strip()
        return None

    @staticmethod
    def _single_quote(s: str) -> str:
        return "'" + s.replace("'", "'\"'\"'") + "'"

    @staticmethod
    def _parse_job_result(text: str) -> Tuple[str, int]:
        status = "unknown"; rc = 0
        if "FAILED" in text.upper(): status, rc = "Failed", 1
        if ("SUCCEEDED" in text.upper()) or ("COMPLETED" in text.upper()): status = "Succeeded"
        m = re.search(r"exit code[:=]\s*(\d+)", text, re.IGNORECASE)
        if m: rc = int(m.group(1)); status = "Succeeded" if rc == 0 else "Failed"
        return status, rc

    def _find_bucket_by_label(self, key: str, value: str) -> Optional[str]:
        # GCS API doesn't support server-side label filtering via python client; do a local scan.
        for b in self.storage_client.list_buckets(project=self.project_id):
            try:
                labels = b.labels or {}
            except Exception:
                labels = {}
            if labels.get(key) == value:
                return b.name
        return None


cloudrun_service = CloudRunService()
