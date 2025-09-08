import os


class Config:
    """
    SDK configuration container.

    Attributes:
        base_url: API base URL (e.g., https://api.onmemos.dev)
        api_key: Passport API key (sent as X-API-Key)
        timeout: Request timeout (seconds or (connect, read) tuple)
        retries: Idempotent retry attempts for transient errors
        user_agent: Optional custom user agent string
    """

    def __init__(self, base_url: str | None, api_key: str | None, timeout: float | tuple = (5, 60), retries: int = 2, user_agent: str | None = None) -> None:
        # Resolve from env with sensible defaults
        env_base = os.getenv("STARBASE_API_URL")
        env_key = os.getenv("STARBASE_API_KEY")

        self.base_url = (base_url or env_base or "http://127.0.0.1:8080").rstrip("/")
        self.api_key = api_key or env_key
        self.timeout = timeout
        self.retries = retries
        self.user_agent = user_agent or "starbase/0.1"


