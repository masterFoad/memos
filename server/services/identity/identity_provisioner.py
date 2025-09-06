"""
Identity Provisioner

Automates per-workspace identity on GKE:
- Ensure namespace
- Ensure KSA (ws-sa)
- Ensure GSA (<hashed>-sa)
- Bind Workload Identity (KSA -> GSA)
- Annotate KSA to use GSA
- Optionally grant bucket IAM (roles/storage.objectAdmin)

All operations are idempotent and best-effort.
"""

from __future__ import annotations

import os
import hashlib
import subprocess
from typing import Dict, Any, Optional

from server.core.logging import get_gke_logger
from server.database.factory import get_database_client


logger = get_gke_logger()


def _namespace_prefix() -> str:
    return os.getenv("GKE_NAMESPACE_PREFIX", "onmemos")


def _safe_name(raw: str, max_len: int = 63) -> str:
    import re
    s = raw.lower()
    s = re.sub(r"[^a-z0-9-]", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if not s:
        s = "x"
    if len(s) > max_len:
        s = s[:max_len].strip("-") or "x"
    return s


def _run(cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    logger.info("$ %s", " ".join(cmd))
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)


class IdentityProvisioner:
    def __init__(self) -> None:
        self.ns_prefix = _namespace_prefix()

    def _ns_for_workspace(self, workspace_id: str) -> str:
        return _safe_name(f"{self.ns_prefix}-{workspace_id}")

    def _gsa_id_for_workspace(self, workspace_id: str) -> str:
        short = hashlib.sha1(workspace_id.encode()).hexdigest()[:10]
        return f"gsa-{short}-sa"

    def ensure_gcloud_context(self, project: str, region: str, cluster: str) -> None:
        # Non-fatal if this fails and kube context is already set
        try:
            _run(["gcloud", "container", "clusters", "get-credentials", cluster, "--region", region, "--project", project], timeout=120)
        except Exception as e:
            logger.warning("get-credentials failed or skipped: %s", e)

    def ensure_namespace(self, ns: str) -> None:
        proc = _run(["kubectl", "get", "ns", ns], timeout=20)
        if proc.returncode != 0:
            create = _run(["kubectl", "create", "ns", ns], timeout=20)
            if create.returncode != 0:
                logger.warning("Failed to create namespace %s: %s", ns, create.stderr)
            else:
                logger.info("Created namespace: %s", ns)

    def ensure_ksa(self, ns: str, ksa: str = "ws-sa") -> None:
        proc = _run(["kubectl", "-n", ns, "get", "sa", ksa], timeout=20)
        if proc.returncode != 0:
            create = _run(["kubectl", "-n", ns, "create", "sa", ksa], timeout=20)
            if create.returncode != 0:
                logger.warning("Failed to create KSA %s/%s: %s", ns, ksa, create.stderr)
            else:
                logger.info("Created KSA: %s/%s", ns, ksa)

    def ensure_gsa(self, project: str, gsa_id: str) -> str:
        email = f"{gsa_id}@{project}.iam.gserviceaccount.com"
        # Check if exists
        getp = _run(["gcloud", "iam", "service-accounts", "describe", email, "--project", project], timeout=30)
        if getp.returncode != 0:
            create = _run(["gcloud", "iam", "service-accounts", "create", gsa_id, "--project", project], timeout=60)
            if create.returncode != 0:
                logger.warning("Failed to create GSA %s: %s", email, create.stderr)
            else:
                logger.info("Created GSA: %s", email)
        return email

    def _get_project_number(self, project: str) -> Optional[str]:
        proc = _run(["gcloud", "projects", "describe", project, "--format", "value(projectNumber)"])
        if proc.returncode == 0:
            return proc.stdout.strip()
        return None

    def bind_workload_identity(self, project: str, ns: str, ksa: str, gsa_email: str) -> None:
        project_number = self._get_project_number(project)
        if not project_number:
            logger.warning("Could not resolve project number for %s", project)
            return
        member = f"principal://iam.googleapis.com/projects/{project_number}/locations/global/workloadIdentityPools/{project}.svc.id.goog/subject/ns/{ns}/sa/{ksa}"
        _run([
            "gcloud", "iam", "service-accounts", "add-iam-policy-binding", gsa_email,
            "--role", "roles/iam.workloadIdentityUser",
            "--member", member,
            "--project", project,
        ], timeout=60)

    def annotate_ksa(self, ns: str, ksa: str, gsa_email: str) -> None:
        _run([
            "kubectl", "-n", ns, "annotate", "sa", ksa,
            f"iam.gke.io/gcp-service-account={gsa_email}", "--overwrite"
        ], timeout=20)

    def grant_bucket_iam(self, project: str, bucket: str, gsa_email: str) -> None:
        if not bucket:
            return
        _run([
            "gcloud", "storage", "buckets", "add-iam-policy-binding", f"gs://{bucket}",
            "--member", f"serviceAccount:{gsa_email}",
            "--role", "roles/storage.objectAdmin",
            "--project", project,
        ], timeout=60)

    async def ensure_workspace_identity(self, *, project: str, region: str, cluster: str, workspace_id: str, bucket: Optional[str] = None) -> Dict[str, Any]:
        ns = self._ns_for_workspace(workspace_id)
        ksa = "ws-sa"
        gsa_id = self._gsa_id_for_workspace(workspace_id)

        self.ensure_gcloud_context(project, region, cluster)
        self.ensure_namespace(ns)
        self.ensure_ksa(ns, ksa)
        gsa_email = self.ensure_gsa(project, gsa_id)
        self.bind_workload_identity(project, ns, ksa, gsa_email)
        self.annotate_ksa(ns, ksa, gsa_email)
        if bucket:
            self.grant_bucket_iam(project, bucket, gsa_email)

        # Persist to DB
        db = get_database_client()
        await db.connect()
        await db._execute_update(
            "UPDATE workspaces SET k8s_namespace = ?, ksa_name = ?, gsa_email = ?, updated_at = CURRENT_TIMESTAMP WHERE workspace_id = ?",
            (ns, ksa, gsa_email, workspace_id)
        )

        return {
            "namespace": ns,
            "ksa": ksa,
            "gsa": gsa_email,
            "bucket": bucket,
        }


identity_provisioner = IdentityProvisioner()



