"""Command-line sweep. Day-one milestone and a handy demo:  python -m aaina.cli --demo"""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from . import demo as demo_mod
from .casefile import make_case, render_pdf, save_case
from .config import Settings
from .fusion import IgnoreRules
from .pipeline import build_runtime, estimate_cost, prepare_inputs, run_sweep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Aaina: find where your photos are misused online.")
    ap.add_argument("--demo", action="store_true", help="offline demo with synthetic images")
    ap.add_argument("--url", action="append", default=[], help="public link to YOUR photo (repeatable)")
    ap.add_argument("--image", action="append", default=[], help="path to YOUR photo (Lens only; repeatable)")
    ap.add_argument("--ignore", default="", help="your own domains/handles, comma separated")
    ap.add_argument("--pdf", action="store_true", help="also write the PDF case file")
    args = ap.parse_args(argv)

    settings = Settings.load()
    if args.demo:
        settings = replace(settings, demo=True)
    client, fetch = build_runtime(settings)
    if settings.demo:
        refs, originals, shas = demo_mod.demo_inputs()
    else:
        if not (args.url or args.image):
            ap.error("give at least one --url or --image (or use --demo)")
        refs, originals, shas = prepare_inputs(client, args.url, [Path(p).read_bytes() for p in args.image])
    print(f"Planned searches: {estimate_cost(refs, settings)}")
    result = run_sweep(client, refs, originals, settings, IgnoreRules.from_text(args.ignore), fetch)

    for rep in result.reports:
        print(f"  engine {rep.engine:22} {'ok ' if rep.ok else 'ERR'} hits={rep.hits} {rep.error}")
    for f in result.findings:
        print(f"[{f.bucket:6}] {f.score:3}  {f.page_url}")
        for text, pts in f.reasons:
            print(f"           {pts:+d}  {text}")
    case = make_case(result.findings, shas, args.url, result.reports)
    path = save_case(case, settings.home)
    print(f"\nCase saved: {path}")
    if args.pdf:
        print(f"PDF: {render_pdf(case, path.with_suffix('.pdf'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
