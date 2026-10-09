"""SerpApi client and one parser per reverse-image engine.

Engines (all verified against SerpApi's docs):
  google_lens          params: url | image_id, optional type=exact_matches
                       results: visual_matches / exact_matches
  google_reverse_image params: image_url              results: image_results
  bing_reverse_image   params: image_url              results: pages_with_this_image, related_content
  yandex_images        params: url                    results: image_results

Deliberately IGNORED: Bing `looks_like` and Yandex `knowledge_graph`. They are engine guesses
about who a face "looks like". Aaina never surfaces identity guesses.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import requests

from .models import Hit, ImageRef

API = "https://serpapi.com"


class SerpError(RuntimeError):
    pass


class SerpClient:
    def __init__(self, api_key, cache, quota, session=None):
        if not api_key:
            raise SerpError("SERPAPI_API_KEY is not set. Add it to your .env file.")
        self.api_key, self.cache, self.quota = api_key, cache, quota
        self.session = session or requests.Session()

    def search(self, params: dict) -> dict:
        key = self.cache.key(params["engine"], params)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        self.quota.reserve(1)
        last = None
        for attempt in range(3):
            try:
                r = self.session.get(f"{API}/search.json", timeout=90,
                                     params={**params, "api_key": self.api_key})
                if r.status_code >= 500:
                    raise requests.RequestException(f"HTTP {r.status_code}")
                data = r.json()
            except (requests.RequestException, ValueError) as exc:
                last = exc
                time.sleep(1.5 * (attempt + 1))
                continue
            err = str(data.get("error", ""))
            if err:
                if "hasn't returned any results" in err or "no results" in err.lower():
                    data = {"_empty": True}
                else:
                    raise SerpError(err)
            self.cache.put(key, data)
            return data
        self.quota.refund(1)  # network failure: very likely not billed
        raise SerpError(f"Network error talking to SerpApi: {last}")

    def upload_image(self, jpeg: bytes, sha: str) -> str:
        """SerpApi Image API (max 500 KB) -> image_id usable by Google Lens."""
        key = self.cache.key("upload", {"sha": sha})
        cached = self.cache.get(key)
        if cached and cached.get("image_id"):
            return cached["image_id"]
        last = None
        for attempt in range(3):
            try:
                r = self.session.post(f"{API}/image", timeout=60, data={"api_key": self.api_key},
                                      files={"image": ("photo.jpg", jpeg, "image/jpeg")})
                if r.status_code >= 500:
                    raise requests.RequestException(f"HTTP {r.status_code}")
                data = r.json()
                if "image_id" not in data:
                    raise SerpError(f"Image upload failed: {data.get('error', data)}")
                self.cache.put(key, data)
                return data["image_id"]
            except (requests.RequestException, ValueError) as exc:
                last = exc
                time.sleep(1.5 * (attempt + 1))
                continue
        raise SerpError(f"Network error uploading to SerpApi: {last}")


# ----------------------------------------------------------------- parsers (pure functions)
def _text(v) -> str:
    return v.strip() if isinstance(v, str) else ""


def _thumb(v) -> str:
    if isinstance(v, str):
        return v
    return _text(v.get("link")) if isinstance(v, dict) else ""


def parse_lens(data: dict) -> list:
    hits = []
    for key, kind in (("exact_matches", "exact"), ("visual_matches", "visual")):
        items = data.get(key)
        if not isinstance(items, list):      # in type=all, "exact_matches" is just a boolean flag
            continue
        for it in items:
            if isinstance(it, dict) and _text(it.get("link")):
                hits.append(Hit("google_lens", kind, _text(it["link"]), _text(it.get("title")),
                                _text(it.get("snippet")), _thumb(it.get("thumbnail")),
                                _text(it.get("image"))))
    return hits


def parse_google_reverse(data: dict) -> list:
    return [Hit("google_reverse_image", "page", _text(it["link"]), _text(it.get("title")),
                _text(it.get("snippet")), _thumb(it.get("thumbnail")))
            for it in data.get("image_results") or []
            if isinstance(it, dict) and _text(it.get("link"))]


def parse_bing(data: dict) -> list:
    hits = []
    for key, kind in (("pages_with_this_image", "page"), ("related_content", "visual")):
        for it in data.get(key) or []:
            if not isinstance(it, dict):
                continue
            page = _text(it.get("source")) or _text(it.get("link"))  # `link` is a bing.com page
            if page:
                hits.append(Hit("bing_reverse_image", kind, page, _text(it.get("title")), "",
                                _thumb(it.get("thumbnail")),
                                _text(it.get("original")) or _text(it.get("cdn_original"))))
    return hits


def parse_yandex(data: dict) -> list:
    hits = []
    for key in ("image_results", "images_results"):
        for it in data.get(key) or []:
            if isinstance(it, dict) and _text(it.get("link")):
                orig = _thumb(it.get("original_image")) or _text(it.get("original"))
                hits.append(Hit("yandex_images", "page", _text(it["link"]), _text(it.get("title")),
                                _text(it.get("snippet")), _thumb(it.get("thumbnail")), orig))
    return hits


PARSERS = {"google_lens": parse_lens, "google_reverse_image": parse_google_reverse,
           "bing_reverse_image": parse_bing, "yandex_images": parse_yandex}


# ----------------------------------------------------------------- orchestration
def plan_tasks(ref: ImageRef, lens_exact: bool) -> list:
    lens = {"engine": "google_lens"}
    lens.update({"image_id": ref.image_id} if ref.image_id else {"url": ref.url})
    tasks = [("google_lens", dict(lens))]
    if lens_exact:
        tasks.append(("google_lens", {**lens, "type": "exact_matches"}))
    if ref.url:   # the other three engines need a public image URL
        tasks += [("google_reverse_image", {"engine": "google_reverse_image", "image_url": ref.url}),
                  ("bing_reverse_image", {"engine": "bing_reverse_image", "image_url": ref.url}),
                  ("yandex_images", {"engine": "yandex_images", "url": ref.url})]
    return tasks


def plan_cost(refs, lens_exact: bool) -> int:
    return sum(len(plan_tasks(r, lens_exact)) for r in refs)


@dataclass
class EngineReport:
    engine: str
    label: str
    ok: bool
    hits: int = 0
    error: str = ""


def run_engines(client, refs, lens_exact: bool = True, workers: int = 4):
    jobs = [(ref.label, name, params) for ref in refs for name, params in plan_tasks(ref, lens_exact)]

    def work(job):
        label, name, params = job
        try:
            hits = PARSERS[name](client.search(params))
            return hits, EngineReport(name, label, True, len(hits))
        except Exception as exc:  # noqa: BLE001 - one failing engine must not sink the sweep
            return [], EngineReport(name, label, False, 0, str(exc))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(work, jobs))
    return [h for hits, _ in results for h in hits], [rep for _, rep in results]
