"""Plain data containers shared by every module."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ImageRef:
    """How a search engine can reach one of the user's original photos."""
    label: str
    url: Optional[str] = None        # public URL (works with all four engines)
    image_id: Optional[str] = None   # SerpApi Image API id (Google Lens only)


@dataclass(frozen=True)
class Hit:
    """One raw result from one engine, normalised."""
    engine: str
    kind: str            # "exact" | "visual" | "page"
    page_url: str
    title: str = ""
    snippet: str = ""
    thumb: str = ""
    image_url: str = ""


@dataclass
class Finding:
    """All hits that point at the same page, merged."""
    key: str
    page_url: str
    domain: str
    domain_class: str = "unknown"
    titles: list = field(default_factory=list)
    snippets: list = field(default_factory=list)
    engines: set = field(default_factory=set)
    kinds: set = field(default_factory=set)
    thumbs: list = field(default_factory=list)
    image_urls: list = field(default_factory=list)
    hash_distance: Optional[int] = None
    thumb_bytes: Optional[bytes] = field(default=None, repr=False)  # memory only, never saved
    score: int = 0
    bucket: str = "Low"
    reasons: list = field(default_factory=list)  # [(text, points)]
    first_seen: str = ""
    mine: bool = False

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "page_url": self.page_url,
            "domain": self.domain,
            "domain_class": self.domain_class,
            "titles": self.titles[:3],
            "engines": sorted(self.engines),
            "kinds": sorted(self.kinds),
            "hash_distance": self.hash_distance,
            "score": self.score,
            "bucket": self.bucket,
            "reasons": [{"text": t, "points": p} for t, p in self.reasons],
            "first_seen": self.first_seen,
            "mine": self.mine,
        }
