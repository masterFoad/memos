from __future__ import annotations

from typing import Optional

from .config import Config
from .http import HttpClient
from .shuttles import Shuttles
from .missions import Missions


class Starbase:
    """
    Starbase SDK facade.

    User-only SDK. All calls authenticate via X-API-Key (Passport).

    Example:
        sb = Starbase(base_url="https://api.onmemos.dev", api_key="ppk_...")
        shuttle = sb.shuttles.launch(dock_id, provider="gke", template_id="dev-python")
    """

    def __init__(self, *, base_url: Optional[str] = None, api_key: Optional[str] = None, timeout: float | tuple = (5, 60), retries: int = 2, user_agent: Optional[str] = None) -> None:
        self._config = Config(base_url, api_key, timeout, retries, user_agent)
        self._http = HttpClient(self._config)

        # Public service groups
        self.shuttles = Shuttles(self._http)
        self.missions = Missions(self._http)


