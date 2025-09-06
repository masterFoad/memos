#!/usr/bin/env python3
"""
Verbose sanity runner that calls the sanity_e2e functions step-by-step
and prints all responses/errors to the console.

Usage (example):
  python run_sanity_driver.py \
    --host http://127.0.0.1:8001 \
    --internal-key onmemos-internal-key-2024-secure \
    --credits 25 --bucket-size 10 --pvc-size 10 --provider gke
"""

import argparse
import json
import sys
import time
import traceback

from typing import Any, Dict

# Ensure local import works
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from sanity_e2e import (
    ApiError,
    admin_create_user,
    admin_create_passport,
    admin_add_credits,
    admin_create_workspace,
    user_create_session,
    wait_until_running,
    user_execute,
    user_get_session,
    user_delete_session,
)


def pretty(obj: Any) -> str:
    try:
        return json.dumps(obj, indent=2, default=str)
    except Exception:
        return str(obj)


def main():
    p = argparse.ArgumentParser(description="Verbose sanity runner")
    p.add_argument("--host", required=True, help="API base, e.g. http://127.0.0.1:8001")
    p.add_argument("--internal-key", required=True, help="X-API-Key for /v1/admin/*")
    p.add_argument("--email", default=None, help="Optional email; if omitted, a unique email is generated")
    p.add_argument("--name", default="Pro User", help="User display name")
    p.add_argument("--credits", type=float, default=25.0)
    p.add_argument("--provider", default="gke", choices=["gke", "cloud_run"])
    p.add_argument("--bucket-size", type=int, default=10)
    p.add_argument("--pvc-size", type=int, default=10)
    p.add_argument("--keep", action="store_true")
    p.add_argument("--no-bucket", action="store_true", help="Skip GCS Fuse bucket mount")
    p.add_argument("--no-pvc", action="store_true", help="Skip Filestore PVC mount")
    args = p.parse_args()

    host = args.host.rstrip("/")
    internal_key = args.internal_key
    email = args.email or f"pro.user+e2e-{int(time.time())}@example.com"

    print(f"[cfg] host={host}")
    print(f"[cfg] email={email}")

    try:
        print("[1] Admin: create user")
        user_res = admin_create_user(host, internal_key, email, args.name)
        print(pretty(user_res))
        user = user_res.get("user") or user_res
        user_id = user.get("user_id") or user.get("id")
        if not user_id:
            raise ApiError(f"could not parse user id: {pretty(user_res)}")

        print("[2] Admin: create passport")
        pp = admin_create_passport(host, internal_key, user_id)
        print(pretty(pp))
        passport_key = pp.get("passport_key") or pp.get("passport") or pp.get("key")
        if not passport_key:
            raise ApiError(f"could not parse passport key: {pretty(pp)}")

        if args.credits > 0:
            print(f"[3] Admin: add credits +{args.credits}")
            cr = admin_add_credits(host, internal_key, user_id, args.credits)
            print(pretty(cr))

        print("[4] Admin: create workspace")
        ws_res = admin_create_workspace(host, internal_key, user_id, name="dev")
        print(pretty(ws_res))
        workspace = ws_res.get("workspace") or ws_res
        workspace_id = workspace.get("workspace_id") or workspace.get("id")
        if not workspace_id:
            raise ApiError(f"could not parse workspace id: {pretty(ws_res)}")

        print("[5] User: create session (bucket+PVC)")
        sess_res = user_create_session(
            host=host,
            passport=passport_key,
            workspace_id=workspace_id,
            provider=args.provider,
            bucket_size_gb=args.bucket_size,
            pvc_size_gb=args.pvc_size,
            request_bucket=not args.no_bucket,
            request_persistent_storage=not args.no_pvc,
        )
        print(pretty(sess_res))
        session = (sess_res.get("session") or sess_res)
        session_id = session.get("id") or session.get("session_id")
        if not session_id:
            raise ApiError(f"could not parse session id: {pretty(sess_res)}")

        print("[6] Poll until running (best-effort)")
        sinfo = wait_until_running(host, passport_key, session_id)
        print(pretty(sinfo))

        print("[7] Execute sanity commands")
        for cmd in ["pwd", "ls -la", "echo 'hello from REST'"]:
            try:
                ex = user_execute(host, passport_key, session_id, cmd, timeout_s=60)
                print(f"$ {cmd}\n{pretty(ex)}\n---")
            except Exception as e:
                print(f"[-] execute failed for '{cmd}': {e}")

        if args.keep:
            print("[9] Keeping session (--keep)")
            return

        print("[9] Cleanup: delete session")
        dr = user_delete_session(host, passport_key, session_id)
        print(pretty(dr))

        print("[✓] Done")

    except ApiError as e:
        print(f"[API ERROR] {e}")
        sys.exit(2)
    except Exception:
        print("[UNEXPECTED ERROR]")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


