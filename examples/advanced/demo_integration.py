#!/usr/bin/env python3
"""
OnMemOS v3 Integration Demo
Demonstrates the key features working with real containers
"""

import os
import sys
import tempfile
import pathlib
import jwt
import docker

# Add the project root to the path
sys.path.append(os.path.dirname(__file__))

TEST_SECRET = "integration-secret"

def setup_test_environment():
    """Setup test environment with temporary config"""
    root = tempfile.mkdtemp(prefix="onmemos-demo-")
    persist = pathlib.Path(root) / "persist"
    cas = pathlib.Path(root) / "cas"
    persist.mkdir(parents=True, exist_ok=True)
    cas.mkdir(parents=True, exist_ok=True)
    
    cfg = pathlib.Path(root) / "config.yaml"
    cfg.write_text(f"""
server:
  bind: "127.0.0.1"
  port: 8080
  base_url: "https://unit.test"
  jwt_secret: "{TEST_SECRET}"
runtime:
  engine: "docker"
  default_network: "bridge"
  security:
    no_new_privileges: true
    drop_caps: ["ALL"]
    seccomp_profile: null
storage:
  persist_root: "{persist}"
  cas_root: "{cas}"
workspaces:
  default_ttl_minutes: 60
  enforce_net_profile: false
pools:
  - template: "python"
    warm_size: 1
    max_size: 4
limits:
  per_user:
    max_live_workspaces: 4
    cpu_quota: 4
    mem_limit: "8g"
    persist_quota_gb: 20
""")
    
    os.environ["ONMEMOS_CONFIG"] = str(cfg)
    return {"root": root, "persist": persist, "cas": cas, "cfg": cfg}

def demo_workspace_lifecycle():
    """Demo workspace creation and Python execution"""
    print("🚀 Demo: Workspace Lifecycle")
    print("=" * 40)
    
    # Setup environment
    env = setup_test_environment()
    
    # Import app after environment setup
    import server.app as appmod
    appmod.TEMPLATES["python"]["image"] = "onmemos/python-runner:3.11"
    
    # Create test client
    from fastapi.testclient import TestClient
    token = jwt.encode({"sub":"user:alice"}, TEST_SECRET, algorithm="HS256")
    client = TestClient(appmod.app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    
    # 1. Create workspace
    print("1. Creating workspace...")
    r = client.post("/v1/workspaces", json={
        "template": "python",
        "namespace": "team-a", 
        "user": "alice",
        "ttl_minutes": 30
    })
    assert r.status_code == 200, f"Failed to create workspace: {r.text}"
    data = r.json()
    wid = data["id"]
    print(f"   ✅ Workspace created: {wid}")
    print(f"   Template: {data['template']}")
    print(f"   Shell WS: {data['shell_ws']}")
    
    # 2. Run Python code
    print("\n2. Running Python code...")
    r = client.post(f"/v1/workspaces/{wid}/runpy", json={
        "code": "x = 2 + 2; print(f'Result: {x}')",
        "timeout": 5
    })
    assert r.status_code == 200, f"Failed to run Python: {r.text}"
    result = r.json()
    print(f"   ✅ Python execution: {result}")
    
    # 3. Run shell command
    print("\n3. Running shell command...")
    r = client.post(f"/v1/workspaces/{wid}/runsh", json={
        "cmd": "echo 'Hello from OnMemOS!' && pwd",
        "timeout": 5
    })
    assert r.status_code == 200, f"Failed to run shell: {r.text}"
    result = r.json()
    print(f"   ✅ Shell execution: {result}")
    
    # 4. Upload and download file
    print("\n4. Testing file upload/download...")
    files = {"file": ("demo.txt", b"Hello OnMemOS v3!")}
    r = client.post("/v1/fs/persist/upload", 
                   params={"namespace": "team-a", "user": "alice", "dst": "demo"},
                   files=files)
    assert r.status_code == 200, f"Failed to upload: {r.text}"
    upload_result = r.json()
    print(f"   ✅ File uploaded: {upload_result}")
    
    # Download the file
    r = client.get("/v1/fs/persist/download", 
                  params={"namespace": "team-a", "user": "alice", "path": "demo/demo.txt"})
    assert r.status_code == 200, f"Failed to download: {r.text}"
    assert r.content == b"Hello OnMemOS v3!", "File content mismatch"
    print(f"   ✅ File downloaded: {len(r.content)} bytes")
    
    # 5. Create snapshot
    print("\n5. Creating snapshot...")
    r = client.post(f"/v1/workspaces/{wid}/snapshot", json={"comment": "demo snapshot"})
    assert r.status_code == 200, f"Failed to create snapshot: {r.text}"
    snap_data = r.json()
    print(f"   ✅ Snapshot created: {snap_data['id']}")
    print(f"   Size: {snap_data['bytes']} bytes")
    print(f"   Files: {snap_data['files']}")
    
    # 6. Cleanup
    print("\n6. Cleaning up...")
    r = client.delete(f"/v1/workspaces/{wid}")
    assert r.status_code == 200, f"Failed to delete workspace: {r.text}"
    print(f"   ✅ Workspace deleted")
    
    # Verify container is gone
    cli = docker.from_env()
    names = [c.name for c in cli.containers.list(all=True)]
    assert wid not in names, f"Container {wid} still exists"
    print(f"   ✅ Container verified as deleted")
    
    print("\n🎉 All tests passed! OnMemOS v3 is working correctly.")
    print(f"📁 Test data location: {env['root']}")

if __name__ == "__main__":
    # Check prerequisites
    try:
        cli = docker.from_env()
        cli.ping()
        print("✅ Docker is available")
    except Exception as e:
        print(f"❌ Docker not available: {e}")
        sys.exit(1)
    
    try:
        cli.images.get("onmemos/python-runner:3.11")
        print("✅ Runtime image is available")
    except docker.errors.ImageNotFound:
        print("❌ Runtime image not found. Please build it first:")
        print("   docker build -t onmemos/python-runner:3.11 images/python-runner")
        sys.exit(1)
    
    # Run the demo
    demo_workspace_lifecycle()
