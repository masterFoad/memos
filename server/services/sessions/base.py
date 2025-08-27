# server/services/sessions/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from server.models.sessions import SessionInfo, CreateSessionRequest


class SessionProviderBase(ABC):
    @abstractmethod
    def create(self, req: CreateSessionRequest) -> SessionInfo: ...

    @abstractmethod
    def get(self, session_id: str) -> Optional[SessionInfo]: ...

    @abstractmethod
    def delete(self, session_id: str) -> bool: ...

    def execute(self, session_id: str, command: str, timeout: int = 120) -> Dict[str, Any]:
        raise NotImplementedError("execute is not supported by this provider")
