"""Central configuration, read from environment variables or a local .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Tiny .env loader so we need no extra dependency."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    api_key: str
    home: Path
    monthly_cap: int
    cache_ttl_hours: int
    demo: bool
    lens_exact: bool
    max_verify: int

    @staticmethod
    def load() -> "Settings":
        _load_dotenv()
        home = Path(os.environ.get("AAINA_HOME", str(Path.home() / ".aaina"))).expanduser()
        home.mkdir(parents=True, exist_ok=True)
        return Settings(
            api_key=os.environ.get("SERPAPI_API_KEY", ""),
            home=home,
            monthly_cap=int(os.environ.get("AAINA_MONTHLY_CAP", "200")),
            cache_ttl_hours=int(os.environ.get("AAINA_CACHE_TTL_HOURS", "24")),
            demo=os.environ.get("AAINA_DEMO", "0") == "1",
            lens_exact=os.environ.get("AAINA_LENS_EXACT", "1") == "1",
            max_verify=int(os.environ.get("AAINA_MAX_VERIFY", "40")),
        )
