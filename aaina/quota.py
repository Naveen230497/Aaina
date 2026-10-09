"""Monthly search budget, persisted locally, so a bug can never burn the whole free plan."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class QuotaExceeded(RuntimeError):
    pass


class Quota:
    def __init__(self, path: Path, cap: int):
        self.path, self.cap, self._lock = Path(path), cap, threading.Lock()

    @staticmethod
    def _month() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text())
            if data.get("month") == self._month():
                return data
        except (OSError, ValueError):
            pass
        return {"month": self._month(), "used": 0}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data))

    def used(self) -> int:
        with self._lock:
            return self._load()["used"]

    def remaining(self) -> int:
        return max(0, self.cap - self.used())

    def reserve(self, n: int = 1) -> None:
        with self._lock:
            data = self._load()
            if data["used"] + n > self.cap:
                raise QuotaExceeded(
                    f"Monthly search cap reached ({data['used']}/{self.cap}). "
                    "Raise AAINA_MONTHLY_CAP or wait until next month.")
            data["used"] += n
            self._save(data)

    def refund(self, n: int = 1) -> None:
        with self._lock:
            data = self._load()
            data["used"] = max(0, data["used"] - n)
            self._save(data)
