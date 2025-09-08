from __future__ import annotations

from typing import Dict

from .models import Mission, MissionStatus
from .http import HttpClient


class Missions:
    """
    Mission (asynchronous job) helpers.

    Design-only; methods raise NotImplementedError.
    """

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def submit(self, shuttle_id: str, command: str) -> Mission:
        # Use async execution flow by submitting as a job via execute async if exposed;
        # for now assume server provides a job submission internally in provider (GKE).
        # Here we reuse the shuttles async path via dedicated endpoint semantics.
        # If a dedicated endpoint is added later, update here.
        from .http import HttpClient  # type: ignore
        # Submit as async job via provider-specific semantics is handled server-side.
        # We will simulate a response structure: { job_id, job_name }
        res = self._http.request("POST", f"/v1/sessions/{shuttle_id}/execute", params={
            "command": command,
            "async_execution": "true",
            "timeout": "120",
        })
        job_id = res.get("job_id") or res.get("id") or ""
        job_name = res.get("job_name") or ""
        return Mission(id=job_id, job_name=job_name)

    def status(self, shuttle_id: str, mission_id: str, job_name: str) -> MissionStatus:
        res = self._http.request("GET", f"/v1/sessions/{shuttle_id}/jobs/{mission_id}/status", params={"job_name": job_name})
        return MissionStatus(
            status=res.get("status") or "unknown",
            stdout=res.get("stdout"),
            stderr=res.get("stderr"),
            returncode=res.get("returncode"),
        )


