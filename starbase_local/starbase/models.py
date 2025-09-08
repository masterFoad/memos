from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class Shuttle:
    id: str
    dock_id: str
    provider: str
    status: str
    launchpad: Optional[str] = None  # k8s namespace
    pod: Optional[str] = None
    mounts: Dict[str, bool] | None = None  # {"vault": bool, "drive": bool}
    created_at: Optional[str] = None
    ttl_minutes: Optional[int] = None


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


@dataclass
class WSToken:
    token: str
    expires_in: int


@dataclass
class Mission:
    id: str
    job_name: str
    submitted_at: Optional[str] = None


@dataclass
class MissionStatus:
    status: str
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    returncode: Optional[int] = None


