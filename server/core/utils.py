import os, pathlib, re

# Accepts: "123", "10k", "1.5M", "2G", "4T", "512b",
#          "10 KB", "1.5GiB", "2_000k", "3,000 m"
_SIZE_RE = re.compile(r"""
    ^\s*
    (?P<num>[+-]?(?:\d+(?:[,_ ]\d{3})+|\d+)(?:\.\d+)?)
    \s*
    (?P<unit>[a-zA-Z]{0,3})?
    \s*$
""", re.VERBOSE)

# Keep original decimal behavior for k/m/g (×1000)
_DECIMAL = {
    '': 1, 'b': 1,
    'k': 1000, 'kb': 1000,
    'm': 1000**2, 'mb': 1000**2,
    'g': 1000**3, 'gb': 1000**3,
    't': 1000**4, 'tb': 1000**4,
}

# Binary variants (×1024)
_BINARY = {
    'ki': 1024, 'kib': 1024,
    'mi': 1024**2, 'mib': 1024**2,
    'gi': 1024**3, 'gib': 1024**3,
    'ti': 1024**4, 'tib': 1024**4,
}

def human_to_bytes(s: str) -> int:
    """
    Parse human-friendly byte sizes.
    k/m/g/t map to decimal (×1000) to preserve existing behavior.
    'ki/mi/gi/ti' map to binary (×1024).
    """
    m = _SIZE_RE.match(s)
    if not m:
        raise ValueError(f"invalid size: {s!r}")
    num = m.group('num').replace(',', '').replace('_', '').replace(' ', '')
    unit = (m.group('unit') or '').lower()

    # Normalize units; accept trailing 'b' forms like 'kb', 'gib'
    if unit in _DECIMAL:
        factor = _DECIMAL[unit]
    elif unit in _BINARY:
        factor = _BINARY[unit]
    elif unit.endswith('b') and unit[:-1] in _DECIMAL:
        factor = _DECIMAL[unit[:-1]]
    elif unit.endswith('b') and unit[:-1] in _BINARY:
        factor = _BINARY[unit[:-1]]
    else:
        raise ValueError(f"unknown unit: {unit!r}")

    return int(float(num) * factor)

def safe_join(root: str, *parts: str) -> str:
    """
    Join under a fixed root, preventing escape via '..', absolute parts, or
    (to the extent resolvable) symlinks. Returns an absolute path string.

    Drop-in upgrade: same signature and raises ValueError('unsafe path').
    """
    base = pathlib.Path(root).resolve(strict=False)
    target = base.joinpath(*parts).resolve(strict=False)

    # Extra guard for Windows drive/anchor mismatches.
    if getattr(base, "drive", "") and base.drive.lower() != target.drive.lower():
        raise ValueError("unsafe path")

    # Proper containment check (doesn't have the '/tmp/a' vs '/tmp/ab' pitfall).
    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError("unsafe path")

    return str(target)
