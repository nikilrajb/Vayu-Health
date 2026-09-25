"""Shared local pacing across the API and monitor (not across other computers)."""
import sqlite3
import time
from app.config import get_settings


def pace_openaq():
    # One request every two seconds stays below 60/minute and 2,000/hour.
    path = get_settings().processed_dir / "provider-quota.sqlite3"
    with sqlite3.connect(path, timeout=15) as db:
        db.execute("CREATE TABLE IF NOT EXISTS quota (provider TEXT PRIMARY KEY, next_at REAL)")
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT next_at FROM quota WHERE provider='openaq'").fetchone()
        now = time.time()
        slot = max(now, row[0] if row else now)
        db.execute("INSERT OR REPLACE INTO quota VALUES ('openaq',?)", (slot + 2.0,))
    time.sleep(max(0, slot-time.time()))
