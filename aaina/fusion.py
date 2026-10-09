"""Merge raw hits from all engines into one Finding per page."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .models import Finding
from .urls import canonical_url, classify_domain, host_of

_SEARCH_ENGINE_HOSTS = ("google.com", "bing.com", "yandex.com", "yandex.ru", "gstatic.com",
                        "googleusercontent.com", "serpapi.com")


@dataclass(frozen=True)
class IgnoreRules:
    """The user's own pages: domains (e.g. my-site.com) and handles (e.g. instagram.com/me)."""
    hosts: frozenset = frozenset()
    handles: frozenset = frozenset()

    @staticmethod
    def from_text(text: str) -> "IgnoreRules":
        items = [t.strip().lower() for t in (text or "").replace(",", "\n").splitlines() if t.strip()]
        hosts = frozenset(i for i in items if "/" not in i and "." in i)
        return IgnoreRules(hosts, frozenset(i for i in items if i not in hosts))

    def matches(self, url: str) -> bool:
        host, canon = host_of(url), canonical_url(url).lower()
        return (any(host == h or host.endswith("." + h) for h in self.hosts)
                or any(h in canon for h in self.handles))


def _add(lst: list, value: str, limit: int = 6) -> None:
    if value and value not in lst and len(lst) < limit:
        lst.append(value)


def fuse(hits, ignore: IgnoreRules = IgnoreRules()) -> list:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    groups: dict = {}
    for h in hits:
        key, host = canonical_url(h.page_url), host_of(h.page_url)
        if not key or not host or any(host == s or host.endswith("." + s) for s in _SEARCH_ENGINE_HOSTS):
            continue
        f = groups.get(key)
        if f is None:
            f = groups[key] = Finding(key=key, page_url=h.page_url, domain=host,
                                      domain_class=classify_domain(host), first_seen=now,
                                      mine=ignore.matches(h.page_url))
        f.engines.add(h.engine)
        f.kinds.add(h.kind)
        _add(f.titles, h.title)
        _add(f.snippets, h.snippet)
        _add(f.thumbs, h.thumb)
        _add(f.image_urls, h.image_url)
    return list(groups.values())
