import os, pathlib

def human_to_bytes(s: str) -> int:
    s = s.strip().lower()
    if s.endswith("g"): return int(float(s[:-1]) * 1_000_000_000)
    if s.endswith("m"): return int(float(s[:-1]) * 1_000_000)
    if s.endswith("k"): return int(float(s[:-1]) * 1_000)
    return int(s)

def safe_join(root: str, *parts: str) -> str:
    base = pathlib.Path(root).resolve()
    target = base.joinpath(*parts).resolve()
    if not str(target).startswith(str(base)):
        raise ValueError("unsafe path")
    return str(target)
