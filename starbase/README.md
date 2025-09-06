Starbase SDK (design-only)

Starbase is a compact, user-friendly REST client SDK for end-users of OnMemOS. It talks to the public user API using your Passport (API key) and never calls admin endpoints.

- Install name: starbase
- Auth: X-API-Key (your Passport)
- Scope: user-only (sessions/shuttles, jobs/missions). Billing and auth are handled server-side.

Allegory
- Dock: your workspace (created in the UI)
- Shuttle: a running compute session
- Launchpad: the Kubernetes namespace for your shuttle
- Vault: object storage (GCS bucket) mounted at /vault
- Drive: persistent disk (Filestore/PVC) mounted at /drive
- Commlink: interactive shell (WebSocket)

Quick start (planned)
```python
from starbase import Starbase

sb = Starbase(base_url="https://api.onmemos.dev", api_key="ppk_...")

dock_id = "ws-user-abc-123"

shuttle = sb.shuttles.launch(
  dock_id=dock_id,
  provider="gke",
  template_id="dev-python",
  use_vault=True,
  vault_size_gb=10,
  use_drive=True,
  drive_size_gb=10,
  ttl_minutes=60,
)

info = sb.shuttles.get(shuttle.id)
print(info.status, info.launchpad, info.mounts)

res = sb.shuttles.execute(shuttle.id, "echo hello", timeout_s=60)
print(res.stdout)

sb.shuttles.terminate(shuttle.id)
```

Package layout
- starbase/client.py: facade class Starbase
- starbase/shuttles.py: session operations
- starbase/missions.py: async jobs
- starbase/models.py: typed models
- starbase/http.py: HTTP wrapper (headers, retries, timeouts)
- starbase/config.py: configuration resolution
- starbase/errors.py: exceptions

Implementation is intentionally omitted in this design scaffold.

