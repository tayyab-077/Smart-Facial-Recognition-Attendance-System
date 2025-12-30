# utils/file_utils.py
# Safe filesystem helpers and name sanitizer.


import re
from pathlib import Path
import shutil

def sanitize_name(name: str) -> str:
    s = (name or "").strip()
    s = re.sub(r"[^A-Za-z0-9 _\-\.]", "", s)
    s = s.replace(" ", "_")
    return s[:100]  # limit length

def ensure_dir(path):
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

def remove_dir(path):
    p = Path(path)
    if p.exists() and p.is_dir():
        shutil.rmtree(path, ignore_errors=True)
