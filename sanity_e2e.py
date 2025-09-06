#!/usr/bin/env python3
"""
OnMemOS v3 – end-to-end sanity script

What this does:
1) Admin bootstrap (internal X-API-Key):
   - create PRO user
   - create passport (API key)
   - add credits
   - create workspace

2) User flow (passport auth):
   - create a GKE session requesting bucket + PVC
   - poll until running (best-effort)
   - run a few sanity commands
   - (optional) open interactive WebSocket shell
   - cleanup (delete session) unless --keep

Requirements:
  pip install requests websocket-client
"""

import os
import sys
import time
import json
import uuid
import argparse
from typing import Any, Dict, Optional

import requests

try:
    from websocket import create_connection
except ImportError:
    create_connection = None  # will only be used with --ws

DEFAULT_HOST = os.getenv("ONMEM_HOST", "http://localhost:8000")
DEFAULT_INTERNAL_KEY = os.getenv("ONMEM_INTERNAL_KEY", "onmemos-internal-key-2024-secure")

SESSION_POLL_TIMEOUT_S = 180
SESSION_POLL_INTERVAL_S = 4
REQ_TIMEOUT = (5, 60)  # (connect, read)

# ---------- HTTP helpers ----------

class ApiError(RuntimeError):
    pass

def _h_admin(internal_key: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-API-Key": internal_key,
    }

def _h_user(passport_key: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-API-Key": passport_key,
    }

def _req(method: str, url: str, headers: Dict[str, str], *, timeout=None, **kw) -> Dict[str, Any]:
    r = requests.request(method, url, headers=headers, timeout=(timeout or REQ_TIMEOUT), **kw)
    if r.status_code // 100 != 2:
        msg = f"{method} {url} -> {r.status_code} {r.text}"
        raise ApiError(msg)
    if not r.text:
        return {}
    try:
        return r.json()
    except ValueError:
        return {"raw": r.text}

# ---------- Admin calls ----------

def admin_create_user(host: str, ikey: str, email: str, name: Optional[str]) -> Dict[str, Any]:
    url = f"{host}/v1/admin/users"
    body = {"email": email, "name": name, "user_type": "pro"}
    return _req("POST", url, _h_admin(ikey), data=json.dumps(body))

def admin_create_passport(host: str, ikey: str, user_id: str) -> Dict[str, Any]:
    url = f"{host}/v1/admin/passports"
    body = {"user_id": user_id, "name": "default", "permissions": []}
    return _req("POST", url, _h_admin(ikey), data=json.dumps(body))

def admin_add_credits(host: str, ikey: str, user_id: str, amount: float) -> Dict[str, Any]:
    url = f"{host}/v1/admin/credits/add"
    body = {"user_id": user_id, "amount": amount, "source": "sanity_e2e", "description": "bootstrap credits"}
    return _req("POST", url, _h_admin(ikey), data=json.dumps(body))

def admin_create_workspace(host: str, ikey: str, user_id: str, name: str) -> Dict[str, Any]:
    url = f"{host}/v1/admin/workspaces"
    body = {
        "user_id": user_id,
        "name": name,
        "resource_package": "dev_small",
        "description": "sanity workspace",
    }
    return _req("POST", url, _h_admin(ikey), data=json.dumps(body))

# ---------- User (passport) calls ----------

def user_create_session(
    host: str,
    passport: str,
    workspace_id: str,
    provider: str,
    bucket_size_gb: int,
    pvc_size_gb: int,
    request_bucket: bool = True,
    request_persistent_storage: bool = True,
) -> Dict[str, Any]:
    """
    Creates a session using the unified /v1/sessions (passport-protected).
    We request GKE provider with both bucket + persistent storage.
    """
    url = f"{host}/v1/sessions"
    body = {
        "workspace_id": workspace_id,
        "provider": provider,             # "gke"
        "template": "python",           # required by CreateSessionRequest
        "namespace": workspace_id,        # simple default: reuse WS id
        "template_id": "dev-python",
        "request_bucket": bool(request_bucket),
        "bucket_size_gb": bucket_size_gb,
        "request_persistent_storage": bool(request_persistent_storage),
        "persistent_storage_size_gb": pvc_size_gb,
    }
    # GKE provisioning can take a bit; extend read timeout for this call
    return _req("POST", url, _h_user(passport), data=json.dumps(body), timeout=(5, 600))

def user_get_session(host: str, passport: str, session_id: str) -> Dict[str, Any]:
    url = f"{host}/v1/sessions/{session_id}"
    return _req("GET", url, _h_user(passport))

def user_execute(host: str, passport: str, session_id: str, command: str, timeout_s: int = 120) -> Dict[str, Any]:
    url = f"{host}/v1/sessions/{session_id}/execute"
    params = {"command": command, "timeout": str(timeout_s), "async_execution": "false"}
    return _req("POST", url, _h_user(passport), params=params)

def user_delete_session(host: str, passport: str, session_id: str) -> Dict[str, Any]:
    url = f"{host}/v1/sessions/{session_id}"
    return _req("DELETE", url, _h_user(passport))

# ---------- Helpers ----------

def wait_until_running(host: str, passport: str, session_id: str, timeout_s: int = SESSION_POLL_TIMEOUT_S) -> Dict[str, Any]:
    """Poll the session until status looks running/ready (best-effort)."""
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            res = user_get_session(host, passport, session_id)
            last = res.get("session") or res
            status = (last or {}).get("status") or (last or {}).get("state")
            if status and status.lower() in ("running", "ready", "active"):
                return last
        except Exception:
            pass
        time.sleep(SESSION_POLL_INTERVAL_S)
    return last or {}

def maybe_open_ws_shell(host: str, passport: str, session: Dict[str, Any]) -> None:
    """
    Tries to open an interactive WebSocket shell for GKE.
    Requires:
      - websocket-client installed
      - session details include namespace/pod info (keys vary by provider)
    """
    if create_connection is None:
        print("[-] websocket-client not installed; skipping WS shell. pip install websocket-client")
        return

    sid = session.get("id") or session.get("session_id")
    details = session.get("details", {}) or {}
    ns = details.get("k8s_ns") or details.get("namespace") or session.get("namespace")
    pod = details.get("pod") or details.get("pod_name") or details.get("podName")

    if not (sid and ns and pod):
        print("[-] Could not determine k8s namespace/pod from session details; skipping WS shell.")
        print("    details keys available:", list(details.keys()))
        return

    ws_url = f"{host.replace('http', 'ws')}/v1/gke/shell/{sid}?k8s_ns={ns}&pod={pod}&passport={passport}"
    print(f"[~] Opening WS shell: {ws_url}")

    try:
        ws = create_connection(ws_url)
        print("[+] Connected. Type commands, or '/exit' to quit.")
        try:
            while True:
                cmd = input("$ ").strip()
                if not cmd:
                    continue
                payload = json.dumps({"type": "command", "command": cmd})
                ws.send(payload)
                # read until we get a result chunk; very simple loop:
                ws.settimeout(10)
                try:
                    msg = ws.recv()
                    if not msg:
                        print("[-] WS closed by server.")
                        break
                    print(json.loads(msg))
                except Exception:
                    pass
                if cmd == "/exit":
                    break
        finally:
            ws.close()
    except Exception as e:
        print(f"[-] WS shell error: {e}")

# ---------- main ----------

def main():
    p = argparse.ArgumentParser(description="OnMemOS v3 sanity E2E")
    p.add_argument("--host", default=DEFAULT_HOST, help=f"API base, default {DEFAULT_HOST}")
    p.add_argument("--internal-key", default=DEFAULT_INTERNAL_KEY, help="X-API-Key for /v1/admin/*")
    p.add_argument("--email", required=True, help="User email to create")
    p.add_argument("--name", default=None, help="User display name")
    p.add_argument("--credits", type=float, default=25.0, help="Credits to seed")
    p.add_argument("--provider", default="gke", choices=["gke", "cloud_run"], help="Session provider")
    p.add_argument("--bucket-size", type=int, default=10, help="Bucket size GB")
    p.add_argument("--pvc-size", type=int, default=10, help="PVC size GB")
    p.add_argument("--keep", action="store_true", help="Keep session (skip deletion)")
    p.add_argument("--ws", action="store_true", help="Open interactive WS shell (GKE only)")
    args = p.parse_args()

    host = args.host.rstrip("/")
    ikey = args.internal_key

    # 1) Admin bootstrap
    print("[1] Creating PRO user...")
    user_res = admin_create_user(host, ikey, args.email, args.name)
    user = user_res.get("user") or user_res
    user_id = user.get("user_id") or user.get("id")
    if not user_id:
        raise ApiError(f"could not parse user id: {user_res}")
    print(f"    user_id={user_id}")

    print("[2] Creating passport...")
    pp = admin_create_passport(host, ikey, user_id)
    passport_key = pp.get("passport_key") or pp.get("passport") or pp.get("key")
    if not passport_key:
        raise ApiError(f"could not parse passport key: {pp}")
    print(f"    passport={passport_key[:8]}...")

    if args.credits > 0:
        print(f"[3] Adding credits: +{args.credits} USD")
        admin_add_credits(host, ikey, user_id, args.credits)

    print("[4] Creating workspace...")
    ws_res = admin_create_workspace(host, ikey, user_id, name="dev")
    workspace = ws_res.get("workspace") or ws_res
    workspace_id = workspace.get("workspace_id") or workspace.get("id")
    if not workspace_id:
        raise ApiError(f"could not parse workspace id: {ws_res}")
    print(f"    workspace_id={workspace_id}")

    # 2) User flow
    print("[5] Creating session (provider=%s, bucket+PVC requested)..." % args.provider)
    sess_res = user_create_session(
        host=host,
        passport=passport_key,
        workspace_id=workspace_id,
        provider=args.provider,
        bucket_size_gb=args.bucket_size,
        pvc_size_gb=args.pvc_size,
    )
    session = (sess_res.get("session") or sess_res)
    session_id = session.get("id") or session.get("session_id")
    if not session_id:
        raise ApiError(f"could not parse session id: {sess_res}")
    print(f"    session_id={session_id}")

    print("[6] Waiting for session to be running...")
    session_info = wait_until_running(host, passport_key, session_id)
    state = session_info.get("status") or session_info.get("state")
    print(f"    status={state}")

    print("[7] Running sanity commands...")
    for cmd in ["pwd", "ls -la", "echo 'hello from REST'"]:
        try:
            ex = user_execute(host, passport_key, session_id, cmd, timeout_s=60)
            stdout = ex.get("stdout", "").strip()
            print(f"$ {cmd}\n{stdout}\n---")
        except Exception as e:
            print(f"[-] execute failed for '{cmd}': {e}")

    if args.ws and args.provider == "gke":
        print("[8] Attempting interactive GKE WS shell...")
        try:
            full = user_get_session(host, passport_key, session_id).get("session") or {}
            maybe_open_ws_shell(host, passport_key, full)
        except Exception as e:
            print(f"[-] WS shell skipped: {e}")

    if args.keep:
        print("[9] Keeping session as requested (--keep). Done.")
        return

    print("[9] Cleaning up session...")
    try:
        user_delete_session(host, passport_key, session_id)
        print("    session deleted.")
    except Exception as e:
        print(f"[-] session delete failed: {e}")

    print("[✓] Sanity flow complete.")

if __name__ == "__main__":
    try:
        main()
    except ApiError as e:
        print(f"[API ERROR] {e}")
        sys.exit(2)
    except KeyboardInterrupt:
        print("\n[ABORTED]")
        sys.exit(130)



