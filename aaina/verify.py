"""Check each result thumbnail against the user's originals, locally.

Privacy design: we only ever download thumbnails from the search engines' own CDNs.
Your machine never contacts the (possibly abusive) site itself."""
from __future__ import annotations

import io
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import requests
from PIL import Image

from .hashing import distance, signature

CDN_SUFFIXES = ("gstatic.com", "bing.net", "bing.com", "yandex.net", "serpapi.com")


def is_allowed_thumb(url: str) -> bool:
    p = urlsplit(url or "")
    host = (p.hostname or "").lower()
    return p.scheme == "https" and any(host == s or host.endswith("." + s) for s in CDN_SUFFIXES)


def fetch_thumb(url: str, timeout: int = 8, max_bytes: int = 1_500_000):
    if not is_allowed_thumb(url):
        return None
    try:
        with requests.get(url, stream=True, timeout=timeout, allow_redirects=False) as r:
            if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
                return None
            buf = bytearray()
            for chunk in r.iter_content(65536):
                buf += chunk
                if len(buf) > max_bytes:
                    return None
            return bytes(buf)
    except requests.RequestException:
        return None


def verify(findings, ref_sigs, fetch=fetch_thumb, max_checks: int = 40, workers: int = 6) -> int:
    pool_items = sorted((f for f in findings if not f.mine and f.thumbs),
                        key=lambda f: (-len(f.engines), f.key))[:max_checks]

    def work(f):
        best = None
        for url in f.thumbs[:2]:
            data = fetch(url)
            if not data:
                continue
            try:
                img = Image.open(io.BytesIO(data))
                img.load()
            except Exception:  # noqa: BLE001
                continue
            d = distance(signature(img), ref_sigs)
            if f.thumb_bytes is None:
                f.thumb_bytes = data
            best = d if best is None else min(best, d)
        f.hash_distance = best

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(work, pool_items))
    return len(pool_items)
