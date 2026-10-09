"""Weekly re-check: python -m aaina.watch --case ~/.aaina/cases/AAINA-....json [--image photo.jpg]

Schedule it with cron (Linux/macOS) or Task Scheduler (Windows). It reports only NEW matches."""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from . import demo as demo_mod
from .casefile import load_case, make_case, save_case
from .config import Settings
from .fusion import IgnoreRules
from .pipeline import build_runtime, prepare_inputs, run_sweep


def new_since(case: dict, findings) -> list:
    known = {i["key"] for i in case["items"]}
    return [f for f in findings if f.key not in known and not f.mine]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Re-run an Aaina case and list new matches only.")
    ap.add_argument("--case", required=True, help="path to a saved case JSON")
    ap.add_argument("--image", action="append", default=[], help="re-supply an uploaded photo (repeatable)")
    ap.add_argument("--ignore", default="", help="your own domains/handles, comma separated")
    ap.add_argument("--dry-run", action="store_true", help="estimate searches needed, do not run")
    args = ap.parse_args(argv)

    settings = Settings.load()
    case = load_case(args.case)
    client, fetch = build_runtime(settings)
    
    if args.dry_run:
        if settings.demo:
            print("Dry run: Demo mode uses 0 API quota.")
        else:
            # We don't upload images on dry run, we just count
            from .pipeline import estimate_cost
            from .models import ImageRef
            refs = [ImageRef(f"photo-url", url=u) for u in case["public_urls"]]
            # for images, it takes 1 for lens + 1 if lens_exact
            img_cost = len(args.image) * (1 + int(settings.lens_exact))
            print(f"Dry run: Next sweep will consume ~{estimate_cost(refs, settings) + img_cost} searches.")
        return 0

    if settings.demo:
        refs, originals, shas = demo_mod.demo_inputs()
    else:
        uploads = [Path(p).read_bytes() for p in args.image]
        refs, originals, shas = prepare_inputs(client, case["public_urls"], uploads)
    result = run_sweep(client, refs, originals, settings, IgnoreRules.from_text(args.ignore), fetch)

    fresh = new_since(case, result.findings)
    updated = make_case(result.findings, shas, case["public_urls"], result.reports, previous=case)
    updated["history"].append({"checked_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "new": [f.key for f in fresh]})
    save_case(updated, settings.home)
    if not fresh:
        print("No new matches since the last check.")
        return 0
    print(f"{len(fresh)} NEW possible match(es):")
    urgent_domains = []
    for f in fresh:
        print(f"  [{f.bucket:6}] {f.score:3}  {f.page_url}")
        if f.bucket == "Urgent":
            urgent_domains.append(f.domain)
            
    if urgent_domains:
        from app import make_whatsapp_card
        print("\n--- NEW URGENT MISUSE DETECTED ---")
        msg = make_whatsapp_card(len(urgent_domains), list(set(urgent_domains)))
        print(msg)
        
        # Next-Level Feature: Enterprise Webhook Alerts (Slack/Discord)
        webhook_url = getattr(settings, "webhook_url", None) or os.environ.get("AAINA_WEBHOOK_URL")
        if webhook_url:
            try:
                import requests
                payload = {"text": f"🚨 *Aaina Alert: Urgent Photo Misuse Detected!*\n\n{len(fresh)} new matches found.\n\n" + msg}
                requests.post(webhook_url, json=payload, timeout=5)
                print("[+] Webhook alert sent successfully.")
            except Exception as e:
                print(f"[-] Failed to send webhook alert: {e}")
        
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
