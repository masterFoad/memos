from __future__ import annotations

from typing import Any, Dict, Optional
import time
import json as _json
import requests

from .errors import AuthError, NotFoundError, ValidationError, ServerError, TimeoutError, StarbaseError

from .config import Config


class HttpClient:
    """
    Minimal HTTP wrapper for Starbase.

    Design-only: request methods are declared but not implemented.
    """

    def __init__(self, config: Config) -> None:
        self._config = config

    def request(self, method: str, path: str, *, params: Optional[Dict[str, str]] = None, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Perform an HTTP request.

        - Sends X-API-Key header with the Passport
        - Applies timeout and basic retries

        Returns: parsed JSON dict
        """
        url = f"{self._config.base_url}{path}"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": self._config.user_agent,
        }
        if self._config.api_key:
            headers["X-API-Key"] = self._config.api_key

        # Basic retry with exponential backoff on 429/5xx
        attempts = max(1, int(self._config.retries) + 1)
        backoff = 0.5
        last_exc: Optional[Exception] = None

        for attempt in range(attempts):
            try:
                r = requests.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    data=(None if json is None else _json.dumps(json)),
                    timeout=self._config.timeout,
                )

                if r.status_code // 100 == 2:
                    if not r.text:
                        return {}
                    try:
                        return r.json()
                    except ValueError:
                        return {"raw": r.text}

                # Non-2xx → map errors
                self._raise_for_status(r)
            except (requests.Timeout, requests.ConnectTimeout) as e:
                last_exc = e
                if attempt == attempts - 1:
                    raise TimeoutError(str(e))
            except (requests.ConnectionError, requests.HTTPError) as e:
                last_exc = e
                # Already mapped in _raise_for_status for HTTP
                if isinstance(e, requests.HTTPError):
                    raise
                # ConnectionError: retry unless last attempt
            except StarbaseError:
                # Already mapped; don't retry unless 5xx which we handled above
                raise

            # Retry backoff
            if attempt < attempts - 1:
                time.sleep(backoff)
                backoff *= 2

        # Exhausted without raising a specific error
        if last_exc:
            raise ServerError(f"request failed: {last_exc}")
        raise ServerError("request failed: unknown error")

    def _raise_for_status(self, r: requests.Response) -> None:
        body_snippet = (r.text or "")[:512]
        rid = r.headers.get("X-Request-ID") or None
        msg = f"{r.request.method} {r.url} -> {r.status_code} {body_snippet}"
        if r.status_code in (401, 403):
            raise AuthError(msg, status_code=r.status_code, request_id=rid)
        if r.status_code == 404:
            raise NotFoundError(msg, status_code=r.status_code, request_id=rid)
        if r.status_code == 400:
            raise ValidationError(msg, status_code=r.status_code, request_id=rid)
        if r.status_code in (429, 500, 502, 503, 504):
            # Let caller retry via loop by raising requests.HTTPError
            http_err = requests.HTTPError(msg)
            raise http_err
        # Other 4xx
        if 400 <= r.status_code < 500:
            raise ValidationError(msg, status_code=r.status_code, request_id=rid)
        # Other 5xx
        if r.status_code >= 500:
            raise ServerError(msg, status_code=r.status_code, request_id=rid)


