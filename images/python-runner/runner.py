import os, json, socket, time, traceback, subprocess, shlex, base64, binascii, pathlib

SOCK = os.environ.get("RUNNER_SOCK","/run/runner.sock")
os.makedirs(os.path.dirname(SOCK), exist_ok=True)
try: os.unlink(SOCK)
except FileNotFoundError: pass
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.bind(SOCK); os.chmod(SOCK,0o777); s.listen(64)

# optional warm imports
try:
    import numpy as _np  # noqa
except Exception:
    pass

def handle(req: dict) -> dict:
    op = req.get("op"); env = req.get("env") or {}; timeout = float(req.get("timeout",30))
    os.environ.update({str(k):str(v) for k,v in env.items()})
    if op == "py":
        code = req.get("code",""); start = time.time()
        glb = {"__name__":"__main__"}
        try:
            # Capture stdout and stderr
            import io
            import sys
            
            # Create string buffers to capture output
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()
            
            # Save original stdout/stderr
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            
            # Redirect to our buffers
            sys.stdout = stdout_buffer
            sys.stderr = stderr_buffer
            
            try:
                exec(compile(code, "<onmemos>", "exec"), glb)
                exit_code = 0
            except Exception as e:
                exit_code = 1
                stderr_buffer.write(f"Error: {str(e)}\n")
                stderr_buffer.write(traceback.format_exc())
            finally:
                # Restore original stdout/stderr
                sys.stdout = old_stdout
                sys.stderr = old_stderr
            
            # Get captured output
            stdout_content = stdout_buffer.getvalue()
            stderr_content = stderr_buffer.getvalue()
            
            return {
                "ok": exit_code == 0, 
                "stdout": stdout_content,
                "stderr": stderr_content,
                "exit_code": exit_code,
                "dt_ms": int((time.time()-start)*1000)
            }
        except Exception as e:
            return {"ok": False, "err": str(e), "trace": traceback.format_exc(), "dt_ms": int((time.time()-start)*1000)}
    if op == "sh":
        cmd = req.get("cmd")
        if not cmd: return {"ok": False, "err": "no cmd"}
        try:
            # Handle stdin properly - ensure it's a string
            stdin_data = req.get("stdin") or ""
            if isinstance(stdin_data, bytes):
                stdin_data = stdin_data.decode('utf-8')
            elif not isinstance(stdin_data, str):
                stdin_data = str(stdin_data)
            
            p = subprocess.run(cmd if isinstance(cmd, list) else shlex.split(cmd),
                               input=stdin_data,
                               capture_output=True, timeout=timeout, text=True)
            return {"ok": p.returncode==0, "rc": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
        except subprocess.TimeoutExpired:
            return {"ok": False, "err": "timeout"}
        except Exception as e:
            return {"ok": False, "err": str(e), "trace": traceback.format_exc()}
    if op == "put":
        path=req.get("path"); data=req.get("b64")
        if not path or not data: return {"ok":False,"err":"missing path/b64"}
        try:
            raw=base64.b64decode(data.encode()); pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
            open(path,"wb").write(raw); return {"ok":True,"bytes":len(raw)}
        except binascii.Error as e:
            return {"ok":False,"err":f"b64:{e}"}
    if op == "get":
        path=req.get("path"); 
        if not path or not os.path.exists(path): return {"ok":False,"err":"not found"}
        raw=open(path,"rb").read()
        return {"ok":True,"b64":base64.b64encode(raw).decode(),"bytes":len(raw)}
    return {"ok":False,"err":f"unknown op {op}"}

while True:
    c,_ = s.accept()
    try:
        data = c.recv(32*1024*1024)
        resp = handle(json.loads(data.decode()))
        c.sendall(json.dumps(resp).encode())
    except Exception as e:
        c.sendall(json.dumps({"ok":False,"err":str(e)}).encode())
    finally:
        c.close()
