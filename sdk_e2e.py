#!/usr/bin/env python3
"""
Starbase SDK E2E: admin bootstrap via REST, user flow via SDK

Steps:
 1) Admin (X-API-Key): create user, passport, add credits, create dock (workspace)
 2) User (SDK with Passport): launch shuttle, wait running, execute commands, cleanup

Requires: pip install -e starbase/ (already installed)
"""
import os
import sys
import time
import json
import argparse
from typing import Any, Dict, Optional

import requests
from starbase import Starbase
try:
    from websocket import create_connection  # type: ignore
except Exception:
    create_connection = None


class ApiError(RuntimeError):
    pass


def _h_admin(ikey: str) -> Dict[str, str]:
    return {"Content-Type": "application/json", "X-API-Key": ikey}


def _req(method: str, url: str, headers: Dict[str, str], **kw) -> Dict[str, Any]:
    timeout = kw.pop("timeout", (5, 60))
    r = requests.request(method, url, headers=headers, timeout=timeout, **kw)
    if r.status_code // 100 != 2:
        raise ApiError(f"{method} {url} -> {r.status_code} {r.text}")
    if not r.text:
        return {}
    try:
        return r.json()
    except ValueError:
        return {"raw": r.text}


def admin_create_user(host: str, ikey: str, email: str, name: Optional[str]) -> Dict[str, Any]:
    url = f"{host}/admin/v1/admin/users"
    body = {"email": email, "name": name, "user_type": "pro"}
    try:
        return _req("POST", url, _h_admin(ikey), data=json.dumps(body))
    except ApiError as e:
        # Handle idempotency: if user already exists, try to get existing user
        if "409" in str(e) or "already exists" in str(e).lower():
            print(f"    User {email} already exists, fetching existing user...")
            # For now, we'll let the caller handle this by re-raising
            # In a full implementation, we'd add a GET /admin/users?email=... endpoint
            raise ApiError(f"User {email} already exists. Please use a different email or implement user lookup.")
        raise


def admin_create_passport(host: str, ikey: str, user_id: str) -> Dict[str, Any]:
    url = f"{host}/admin/v1/admin/passports"
    body = {"user_id": user_id, "name": "default", "permissions": []}
    return _req("POST", url, _h_admin(ikey), data=json.dumps(body))


def admin_add_credits(host: str, ikey: str, user_id: str, amount: float) -> Dict[str, Any]:
    url = f"{host}/admin/v1/admin/credits/add"
    body = {"user_id": user_id, "amount": amount, "source": "sdk_e2e", "description": "bootstrap credits"}
    return _req("POST", url, _h_admin(ikey), data=json.dumps(body))


def admin_create_workspace(host: str, ikey: str, user_id: str, name: str) -> Dict[str, Any]:
    url = f"{host}/admin/v1/admin/workspaces"
    body = {"user_id": user_id, "name": name, "resource_package": "dev_small", "description": "sdk e2e"}
    return _req("POST", url, _h_admin(ikey), data=json.dumps(body))


def wait_until_running(sb: Starbase, sid: str, timeout_s: int = 300) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    delay = 2.0
    last = None
    last_error = None
    
    while time.time() < deadline:
        try:
            s = sb.shuttles.get(sid)
            last = s
            status = (s.status or "").lower()
            print(f"    Shuttle status: {status}")
            
            if status in ("running", "ready", "active"):
                return s.__dict__
                
        except Exception as e:
            last_error = e
            print(f"    Polling error: {e}")
            
        time.sleep(delay)
        delay = min(delay * 1.5, 10.0)  # Exponential backoff, max 10s
    
    # Timeout reached
    if last_error:
        print(f"    Final error: {last_error}")
    return (last.__dict__ if last else {})


def main():
    p = argparse.ArgumentParser(description="Starbase SDK E2E")
    p.add_argument("--host", default=os.getenv("ONMEM_HOST", "http://127.0.0.1:8080"), help="Public API host")
    p.add_argument("--admin-host", default=os.getenv("ONMEM_ADMIN_HOST", "http://127.0.0.1:8001"), help="Admin API host")
    p.add_argument("--internal-key", default=os.getenv("ONMEM_INTERNAL_KEY"), required=not os.getenv("ONMEM_INTERNAL_KEY"), help="Internal API key (required via env var ONMEM_INTERNAL_KEY or --internal-key)")
    p.add_argument("--email", required=True)
    p.add_argument("--name", default=None)
    p.add_argument("--credits", type=float, default=25.0)
    p.add_argument("--provider", default="gke", choices=["gke", "cloud_run"])
    p.add_argument("--use-vault", action="store_true")
    p.add_argument("--vault-size", type=int, default=10)
    p.add_argument("--use-drive", action="store_true")
    p.add_argument("--drive-size", type=int, default=10)
    p.add_argument("--test-reusable", action="store_true", help="Test reusable storage resources")
    p.add_argument("--keep", action="store_true")
    p.add_argument("--interactive", action="store_true", help="Open interactive WS shell after launch")
    args = p.parse_args()

    host = args.host.rstrip("/")
    admin_host = args.admin_host.rstrip("/")
    ikey = args.internal_key

    print("[1] Admin: create user")
    u = admin_create_user(admin_host, ikey, args.email, args.name).get("user")
    user_id = u.get("user_id") or u.get("id")
    print("    user_id=", user_id)

    print("[2] Admin: create passport")
    pp = admin_create_passport(admin_host, ikey, user_id)
    passport = pp.get("passport_key") or pp.get("passport") or pp.get("key")
    print("    passport=", (passport or "")[:8] + "...")

    if args.credits > 0:
        print(f"[3] Admin: add credits +{args.credits}")
        admin_add_credits(admin_host, ikey, user_id, args.credits)

    print("[4] Admin: create dock (workspace)")
    ws = admin_create_workspace(admin_host, ikey, user_id, name="dev").get("workspace")
    dock_id = ws.get("workspace_id") or ws.get("id")
    print("    dock_id=", dock_id)

    # Test reusable storage if requested
    vault_id = None
    drive_id = None
    if args.test_reusable:
        print("[5] Testing reusable storage resources...")
        sb = Starbase(base_url=host, api_key=passport, timeout=(5, 600), retries=2)
        
        # Create a reusable vault
        print("    Creating reusable vault...")
        vault = sb.vaults.create_vault(dock_id, "test-vault", size_gb=5)
        vault_id = vault["resource_id"]
        print(f"    vault_id={vault_id[:8]}...")
        
        # Create a reusable drive
        print("    Creating reusable drive...")
        drive = sb.drives.create_drive(dock_id, "test-drive", size_gb=5)
        drive_id = drive["resource_id"]
        print(f"    drive_id={drive_id[:8]}...")
        
        # List storage resources
        storage = sb.vaults.list(dock_id)
        print(f"    storage resources: {len(storage.get('resources', []))}")

    print("[6] User: launch shuttle via Starbase")
    sb = Starbase(base_url=host, api_key=passport, timeout=(5, 600), retries=2)
    
    if args.test_reusable and vault_id and drive_id:
        # Use reusable storage
        shuttle = sb.shuttles.launch(
            dock_id=dock_id,
            provider=args.provider,
            template_id="dev-python",
            vault_id=vault_id,
            drive_id=drive_id,
            ttl_minutes=60,
        )
        print(f"    Using reusable storage: vault={vault_id[:8]}..., drive={drive_id[:8]}...")
    else:
        # Use traditional on-demand storage
        shuttle = sb.shuttles.launch(
            dock_id=dock_id,
            provider=args.provider,
            template_id="dev-python",
            use_vault=args.use_vault,
            vault_size_gb=args.vault_size,
            use_drive=args.use_drive,
            drive_size_gb=args.drive_size,
            ttl_minutes=60,
        )
        print(f"    Using on-demand storage: vault={args.use_vault}, drive={args.use_drive}")
    
    sid = shuttle.id
    print("    shuttle_id=", sid)

    print("[7] Wait until running")
    info = wait_until_running(sb, sid)
    print("    status=", info.get("status"))

    print("[8] Execute commands")
    for cmd in ["pwd", "ls -la", "echo 'hello from SDK'"]:
        try:
            res = sb.shuttles.execute(sid, cmd, timeout_s=60)
            print(f"$ {cmd}\n{res.stdout}\n---")
        except Exception as e:
            print(f"[-] execute failed: {e}")

    if args.interactive:
        print("[9] Interactive shell (WebSocket)...")
        if create_connection is None:
            print("[-] websocket-client not installed. pip install websocket-client")
        else:
            try:
                token = sb.shuttles.ws_token(sid)
                ns = info.get("launchpad") or info.get("k8s_namespace")
                pod = info.get("pod") or info.get("pod_name")
                if not (ns and pod):
                    # refresh
                    sref = sb.shuttles.get(sid)
                    ns = sref.launchpad
                    pod = sref.pod
                if not (ns and pod):
                    print("[-] Could not determine namespace/pod for WS. Skipping.")
                else:
                    # Use JWT token for WebSocket authentication (more secure than passport in URL)
                    ws_base = host.replace("https://", "wss://").replace("http://", "ws://")
                    ws_url = f"{ws_base}/v1/gke/shell/{sid}?k8s_ns={ns}&pod={pod}&token={token}"
                    print(f"    connecting: {ws_base}/v1/gke/shell/{sid}?k8s_ns={ns}&pod={pod}&token=<JWT>")
                    ws = create_connection(ws_url)
                    print("[+] Connected. Type commands, or '/exit' to quit.")
                    try:
                        while True:
                            try:
                                cmd = input("$ ").strip()
                            except EOFError:
                                break
                            if not cmd:
                                continue
                            ws.send(json.dumps({"type": "command", "command": cmd}))
                            ws.settimeout(10)
                            try:
                                msg = ws.recv()
                                if not msg:
                                    print("[-] WS closed by server.")
                                    break
                                try:
                                    parsed = json.loads(msg)
                                except Exception:
                                    parsed = msg
                                print(parsed)
                            except Exception:
                                pass
                            if cmd == "/exit":
                                break
                    finally:
                        try:
                            ws.close()
                        except Exception:
                            pass
            except Exception as e:
                print(f"[-] WS shell error: {e}")

    # Clean up reusable storage if created
    if args.test_reusable and vault_id and drive_id:
        print("[10] Cleaning up reusable storage...")
        try:
            sb.vaults.delete(vault_id)
            print(f"    ✅ Vault {vault_id[:8]}... deleted")
        except Exception as e:
            print(f"    ⚠️ Failed to delete vault: {e}")
        
        try:
            sb.drives.delete(drive_id)
            print(f"    ✅ Drive {drive_id[:8]}... deleted")
        except Exception as e:
            print(f"    ⚠️ Failed to delete drive: {e}")

    if args.keep:
        print("[11] Keeping shuttle as requested (--keep). Done.")
        return

    print("[11] Terminate shuttle")
    try:
        sb.shuttles.terminate(sid)
        print("    terminated")
    except Exception as e:
        print(f"[-] terminate failed: {e}")

    # JSON summary for CI parsing
    summary = {
        "user_id": user_id,
        "dock_id": dock_id,
        "shuttle_id": sid,
        "vault_id": vault_id if args.test_reusable else None,
        "drive_id": drive_id if args.test_reusable else None,
        "status": "success"
    }
    print(f"\n[SUMMARY] {json.dumps(summary)}")
    print("[✓] SDK E2E complete")


if __name__ == "__main__":
    try:
        main()
    except ApiError as e:
        print(f"[API ERROR] {e}")
        sys.exit(2)
    except KeyboardInterrupt:
        print("\n[ABORTED]")
        sys.exit(130)
    except Exception as e:
        print(f"[UNEXPECTED ERROR] {e}")
        sys.exit(1)


