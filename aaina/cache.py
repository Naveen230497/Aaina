"""On-disk response cache. The API key is never part of a cache key or a cached value."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path


class DiskCache:
    def __init__(self, folder: Path, ttl_hours: int = 24):
        self.folder, self.ttl = Path(folder), ttl_hours * 3600
        self.folder.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(namespace: str, params: dict) -> str:
        clean = {k: v for k, v in sorted(params.items()) if k != "api_key"}
        raw = json.dumps([namespace, clean], sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, key: str):
        path = self.folder / f"{key}.json"
        try:
            if time.time() - path.stat().st_mtime > self.ttl:
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def put(self, key: str, value) -> None:
        path = self.folder / f"{key}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(value), encoding="utf-8")
        os.replace(tmp, path)
