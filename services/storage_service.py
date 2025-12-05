# services/storage_service.py
# POC local storage helper (no PII saved)
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

BASE = Path("data")
BASE.mkdir(exist_ok=True)

def save_json(obj, fname):
    p = BASE / fname
    p.write_text(obj)
    logger.info("Saved JSON to %s", p)
    return str(p)
