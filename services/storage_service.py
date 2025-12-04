# services/storage_service.py
# POC local storage helper (no PII saved)
import os
from pathlib import Path

BASE = Path("data")
BASE.mkdir(exist_ok=True)

def save_json(obj, fname):
    p = BASE / fname
    p.write_text(obj)
    return str(p)
