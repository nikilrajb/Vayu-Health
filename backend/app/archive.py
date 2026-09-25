"""Atomic, inspectable collection records; observations retain their provenance."""
import json
import os
from datetime import datetime, timezone
from uuid import uuid4
from fastapi.encoders import jsonable_encoder
from app.config import get_settings


def save_collection(city, snapshot, root=None):
    root = root or get_settings().processed_dir
    directory = root / "collections" / city
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    filename = f"{stamp}-{uuid4().hex[:8]}.json"
    payload = json.dumps(jsonable_encoder(snapshot), ensure_ascii=False, allow_nan=False, indent=2)
    temporary = directory / (filename + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, directory / filename)
    return f"collections/{city}/{filename}"
