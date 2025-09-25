import os
import uuid

os.environ.setdefault('ONMEMOS_INTERNAL_API_KEY', 'onmemos-internal-key-2024-secure')

from fastapi.testclient import TestClient
from server.app_admin import app

headers = {
    'X-API-Key': 'onmemos-internal-key-2024-secure',
    'Content-Type': 'application/json'
}

email = f"test-{uuid.uuid4().hex[:8]}@example.com"

with TestClient(app) as client:
    resp = client.post('/admin/v1/admin/users', headers=headers, json={'email': email, 'name': 'Test User', 'user_type': 'pro'})
    print(email)
    print(resp.status_code)
    print(resp.text)
