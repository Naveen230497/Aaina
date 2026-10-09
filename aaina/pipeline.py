"""One function that runs a full sweep: engines -> fuse -> verify locally -> score."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from . import demo as demo_mod
from .cache import DiskCache
from .engines import EngineReport, SerpClient, plan_cost, run_engines
from .fusion import IgnoreRules, fuse
from .hashing import reference_signatures
from .models import ImageRef
from .quota import Quota
from .safety import safe_download, sanitize_upload, validate_public_url
from .scoring import score_all
from .verify import fetch_thumb, verify


@dataclass
class SweepResult:
    findings: list
    reports: list
    cost: int


def build_runtime(settings):
    """Returns (client, thumbnail_fetcher). Demo mode never touches the network."""
    if settings.demo:
        return demo_mod.DemoClient(), demo_mod.demo_fetch()
    cache = DiskCache(settings.home / "cache", settings.cache_ttl_hours)
    quota = Quota(settings.home / "quota.json", settings.monthly_cap)
    return SerpClient(settings.api_key, cache, quota), fetch_thumb


def prepare_inputs(client, public_urls, uploads):
    """Sanitise every photo and return (refs, original images, sha256 of sanitised files)."""
    refs, originals, shas = [], [], []
    for i, url in enumerate(public_urls, 1):
        jpeg, img = sanitize_upload(safe_download(validate_public_url(url)))
        refs.append(ImageRef(f"photo-{i} (public link)", url=url.strip()))
        originals.append(img)
        shas.append(hashlib.sha256(jpeg).hexdigest())
    for j, raw in enumerate(uploads, 1):
        jpeg, img = sanitize_upload(raw)
        sha = hashlib.sha256(jpeg).hexdigest()
        refs.append(ImageRef(f"photo-{len(public_urls) + j} (upload)", image_id=client.upload_image(jpeg, sha)))
        originals.append(img)
        shas.append(sha)
    return refs, originals, shas


def estimate_cost(refs, settings) -> int:
    return plan_cost(refs, settings.lens_exact)


def run_sweep(client, refs, originals, settings, ignore: IgnoreRules = IgnoreRules(),
              fetch=fetch_thumb) -> SweepResult:
    hits, reports = run_engines(client, refs, settings.lens_exact)
    findings = fuse(hits, ignore)
    
    # Extra engines: Domain Reputation & Ads Transparency
    from .engines_extra import domain_reputation_news, check_ads_transparency
    import concurrent.futures

    unique_domains_checked = set()
    target_findings = []
    
    for f in sorted(findings, key=lambda x: -len(x.engines)): # Prioritize those found on multiple engines
        if len(unique_domains_checked) >= 5 and f.domain not in unique_domains_checked:
            f.news_articles = []
            f.ads = []
            continue
        unique_domains_checked.add(f.domain)
        target_findings.append(f)
        
    def fetch_extra(f):
        news = domain_reputation_news(f.domain, settings, client)
        ads = check_ads_transparency(f.domain, settings, client) if len(f.engines) >= 1 else []
        return f, news, ads

    if target_findings:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_extra, f): f for f in target_findings}
            for future in concurrent.futures.as_completed(futures):
                try:
                    f, news, ads = future.result()
                    f.news_articles = news
                    f.ads = ads
                except Exception as e:
                    f = futures[future]
                    f.news_articles = []
                    f.ads = []
                    reports.append(EngineReport("extra_engines", False, error=f"Thread failed for {f.domain}: {str(e)}"))

    ref_sigs = [s for img in originals for s in reference_signatures(img)]
    verify(findings, ref_sigs, fetch, settings.max_verify)
    return SweepResult(score_all(findings), reports, estimate_cost(refs, settings))
