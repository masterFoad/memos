# pytest -q tests/test_integration_real.py
import os, json, tarfile, io, time, pathlib, shutil, subprocess
import jwt
import pytest
import docker

# we import AFTER configuring env in a fixture to ensure settings load correctly
# (but we also tweak app settings below for temp dirs)
import importlib

TEST_SECRET = "integration-secret"

def _have_docker():
    try:
        docker.from_env().ping()
        return True
    except Exception:
        return False

def _ensure_image(tag="onmemos/python-runner:3.11"):
    cli = docker.from_env()
    try:
        cli.images.get(tag)
        return True
    except docker.errors.ImageNotFound:
        # try building if Dockerfile exists in repo
        df = pathlib.Path("images/python-runner/Dockerfile")
        if not df.exists():
            return False
        print(f"[build] building {tag} ...")
        api = docker.APIClient()
        for chunk in api.build(path=str(df.parent), tag=tag, decode=True):
            if "stream" in chunk:
                line = chunk["stream"].strip()
                if line:
                    print(line)
        return True
    except Exception:
        return False

requires_docker = pytest.mark.skipif(not _have_docker(), reason="Docker not available")
requires_image  = pytest.mark.skipif(not _ensure_image(), reason="Runtime image missing and build failed")
requires_run    = pytest.mark.skipif(not os.access("/run", os.W_OK), reason="Need permission to create /run/onmemos/ws (run as root or create writable dir)")

@pytest.fixture(scope="session", autouse=True)
def ensure_run_dir():
    base = pathlib.Path("/run/onmemos/ws")
    try:
        base.mkdir(parents=True, exist_ok=True)
        os.chmod(base, 0o777)
    except PermissionError:
        pytest.skip("cannot create /run/onmemos/ws; run as root or pre-create with write perms")

@pytest.fixture(scope="session")
def cfg_tmp(tmp_path_factory):
    root = tmp_path_factory.mktemp("onmemos")
    persist = root / "persist"
    cas = root / "cas"
    persist.mkdir(parents=True, exist_ok=True)
    cas.mkdir(parents=True, exist_ok=True)
    cfg = root / "config.yaml"
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
    return {"root": root, "persist": persist, "cas": cas, "cfg": cfg}

@pytest.fixture(scope="session")
def app(cfg_tmp):
    os.environ["ONMEMOS_CONFIG"] = str(cfg_tmp["cfg"])
    # lazy import after env set
    import server.app as appmod
    # ensure template exists and points to our built tag
    tpath = pathlib.Path("server/templates/python.yaml")
    assert tpath.exists(), "server/templates/python.yaml missing"
    # tweak loaded template image at runtime (if you want a custom tag)
    appmod.TEMPLATES["python"]["image"] = "onmemos/python-runner:3.11"
    return appmod

@pytest.fixture
def token():
    return jwt.encode({"sub":"user:alice"}, TEST_SECRET, algorithm="HS256")

@pytest.fixture
def client(app, token):
    from fastapi.testclient import TestClient
    c = TestClient(app.app)
    c.headers.update({"Authorization": f"Bearer {token}"})
    return c

# ---------- A) Workspace lifecycle ----------

@requires_docker
@requires_image
def test_1_create_workspace(client, app):
    r = client.post("/v1/workspaces", json={"template":"python","namespace":"team-a","user":"alice","ttl_minutes":30})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["template"] == "python"
    assert data["namespace"] == "team-a"
    assert data["user"] == "alice"
    assert data["shell_ws"].endswith(f"/v1/workspaces/{data['id']}/shell")
    # keep id for next tests
    client.__dict__["_last_ws"] = data["id"]

@requires_docker
def test_2_run_python_ok(client, app):
    wid = client.__dict__.get("_last_ws")
    assert wid, "previous test didn't create a workspace"
    r = client.post(f"/v1/workspaces/{wid}/runpy", json={"code":"x=2+2; print(x)","timeout":5})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert isinstance(body["dt_ms"], int)

@requires_docker
def test_3_run_shell_echo(client, app):
    wid = client.__dict__["_last_ws"]
    r = client.post(f"/v1/workspaces/{wid}/runsh", json={"cmd":"bash -lc 'echo hi'","timeout":5})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "hi" in body.get("stdout","")

# ---------- B) Upload / Download ----------

def test_4_upload_persist_and_download(client, app, cfg_tmp):
    files = {"file": ("hello.txt", b"hi")}
    r = client.post("/v1/fs/persist/upload", params={"namespace":"team-a","user":"alice","dst":"docs"}, files=files)
    assert r.status_code == 200
    meta = r.json()
    assert meta["ok"] is True and meta["bytes"] == 2
    # round-trip
    r2 = client.get("/v1/fs/persist/download", params={"namespace":"team-a","user":"alice","path":"docs/hello.txt"})
    assert r2.status_code == 200
    assert r2.content == b"hi"

@requires_docker
def test_5_upload_work_and_download(client, app):
    wid = client.__dict__["_last_ws"]
    files = {"file": ("hello.txt", b"hi")}
    r = client.post(f"/v1/workspaces/{wid}/upload", params={"to":"/work/hello.txt"}, files=files)
    assert r.status_code == 200 and r.json()["ok"] is True
    r2 = client.get(f"/v1/workspaces/{wid}/download", params={"path":"/work/hello.txt"})
    assert r2.status_code == 200
    # validate tar
    buf = io.BytesIO(r2.content)
    with tarfile.open(fileobj=buf, mode="r:*") as tf:
        names = tf.getnames()
        assert any("hello.txt" in n for n in names)
        f = tf.extractfile(names[0])
        assert f.read() == b"hi"

# ---------- C) Snapshots / Share / Fork ----------

@requires_docker
def test_6_snapshot_metadata(client, app):
    wid = client.__dict__["_last_ws"]
    r = client.post(f"/v1/workspaces/{wid}/snapshot", json={"comment":"demo"})
    assert r.status_code == 200
    meta = r.json()
    assert meta["id"].startswith("sha256:")
    assert meta["bytes"] >= 0

@requires_docker
def test_7_fork_from_snapshot_restores_content(client, app):
    # write unique file, snapshot, fork, then read in new ws
    wid = client.__dict__["_last_ws"]
    uniq = f"forkme_{int(time.time())}.txt"
    files = {"file": (uniq, b"fork-data")}
    r0 = client.post(f"/v1/workspaces/{wid}/upload", params={"to":f"/work/{uniq}"}, files=files)
    assert r0.status_code == 200
    snap = client.post(f"/v1/workspaces/{wid}/snapshot", json={"comment":"forktest"}).json()
    r = client.post("/v1/workspaces/fork", json={"snapshot_id":snap["id"], "namespace":"team-a","user":"bob"})
    assert r.status_code == 200
    wid2 = r.json()["id"]
    tarresp = client.get(f"/v1/workspaces/{wid2}/download", params={"path":f"/work/{uniq}"})
    buf = io.BytesIO(tarresp.content)
    with tarfile.open(fileobj=buf, mode="r:*") as tf:
        f = tf.extractfile(tf.getnames()[0])
        assert f.read() == b"fork-data"

@requires_docker
def test_8_share_and_fork_from_share(client, app):
    wid = client.__dict__["_last_ws"]
    snap = client.post(f"/v1/workspaces/{wid}/snapshot", json={"comment":"share"}).json()
    share = client.post(f"/v1/snapshots/{snap['id']}/share", json={"ttl":3600,"scope":"fork"}).json()
    token = share["url"].split("/s/",1)[1]
    r = client.post("/v1/workspaces/from-share", json={"token": token})
    assert r.status_code == 200
    assert r.json()["id"].startswith("ws_")

# ---------- D) Shell & cleanup ----------

@requires_docker
def test_9_websocket_shell_echo(client, app):
    wid = client.__dict__["_last_ws"]
    from fastapi.testclient import TestClient
    c = TestClient(app.app)
    c.headers.update(client.headers)
    with c.websocket_connect(f"/v1/workspaces/{wid}/shell") as ws:
        ws.send_bytes(b"echo ping && echo DONE && exit\n")
        buf = b""
        t0 = time.time()
        while b"DONE" not in buf and time.time()-t0 < 5:
            buf += ws.receive_bytes()
        assert b"ping" in buf and b"DONE" in buf

@requires_docker
def test_10_delete_workspace_and_cleanup(client, app):
    wid = client.__dict__["_last_ws"]
    r = client.delete(f"/v1/workspaces/{wid}")
    assert r.status_code == 200 and r.json()["ok"] is True
    # verify container gone
    cli = docker.from_env()
    names = [c.name for c in cli.containers.list(all=True)]
    assert wid not in names
