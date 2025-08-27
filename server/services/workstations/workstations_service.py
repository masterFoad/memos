# server/services/workstations/workstations_service.py
from __future__ import annotations

import os
import logging
import subprocess
import time
import json
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class WorkstationsService:
    """
    Thin wrapper over gcloud Workstations.
    Expects:
      WORKSTATIONS_REGION
      WORKSTATIONS_CLUSTER
      WORKSTATIONS_CONFIG
    """

    def __init__(self) -> None:
        self.project_id = os.getenv("PROJECT_ID", "")
        self.region = os.getenv("WORKSTATIONS_REGION", "us-central1")
        self.cluster = os.getenv("WORKSTATIONS_CLUSTER", "")
        self.config = os.getenv("WORKSTATIONS_CONFIG", "")
        if not (self.cluster and self.config):
            logger.warning("Cloud Workstations cluster/config not set. Set WORKSTATIONS_CLUSTER and WORKSTATIONS_CONFIG.")

    def _ws_name(self, namespace: str, user: str, ts: int) -> str:
        return f"ws-{namespace}-{user}-{ts}"

    def create_workspace(self, namespace: str, user: str, bucket_name: Optional[str] = None,
                         filestore_ip: Optional[str] = None, filestore_share: str = "workspace") -> Dict[str, Any]:
        ts = int(time.time())
        ws_name = self._ws_name(namespace, user, ts)

        labels = f"onmemos_workspace_id={ws_name},namespace={namespace},user={user}"
        create_cmd = [
            "gcloud", "workstations", "workstations", "create", ws_name,
            "--cluster", self.cluster,
            "--config", self.config,
            "--region", self.region,
            "--labels", labels,
            "--quiet",
        ]
        proc = subprocess.run(create_cmd, text=True, capture_output=True)
        if proc.returncode != 0:
            logger.error("Failed to create workstation: %s", proc.stderr)
            raise RuntimeError(proc.stderr)

        # describe to obtain URLs
        desc = subprocess.run(
            ["gcloud", "workstations", "workstations", "describe", ws_name, "--cluster", self.cluster, "--region", self.region, "--format", "json"],
            text=True, capture_output=True
        )
        url = None; ssh = False
        if desc.returncode == 0:
            try:
                data = json.loads(desc.stdout or "{}")
                url = (data.get("httpTargetUri") or data.get("host"))  # httpTargetUri if available
                ssh = True
            except Exception:
                pass

        return {
            "workstation_name": ws_name,
            "url": url,
            "ssh": ssh,
            "status": "running",
        }

    def get_workspace(self, ws_name: str) -> Optional[Dict[str, Any]]:
        desc = subprocess.run(
            ["gcloud", "workstations", "workstations", "describe", ws_name, "--cluster", self.cluster, "--region", self.region, "--format", "json"],
            text=True, capture_output=True
        )
        if desc.returncode != 0:
            return None
        try:
            data = json.loads(desc.stdout or "{}")
            return {"workstation_name": ws_name, "url": data.get("httpTargetUri") or data.get("host"), "ssh": True, "status": data.get("state", "UNKNOWN")}
        except Exception:
            return None

    def delete_workspace(self, ws_name: str) -> bool:
        subprocess.run(
            ["gcloud", "workstations", "workstations", "delete", ws_name, "--cluster", self.cluster, "--region", self.region, "--quiet"],
            text=True, capture_output=True
        )
        return True

    # Workstations are interactive endpoints; we generally don't "exec" one-off commands.
    # If you really want remote exec, you could script SSH, but we leave it unsupported here.
    # def exec_in_workspace(...): raise NotImplementedError


workstations_service = WorkstationsService()
