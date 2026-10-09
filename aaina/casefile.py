"""Evidence case file: JSON (machine-readable) + PDF (human-readable), with an integrity fingerprint.

The SHA-256 manifest makes later edits detectable. It is tamper-evident, not tamper-proof."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

IST = timezone(timedelta(hours=5, minutes=30))


def _manifest(items: list) -> str:
    return hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()


def make_case(findings, originals_sha, public_urls, reports, previous=None) -> dict:
    now = datetime.now(timezone.utc)
    items = sorted((f.to_dict() for f in findings), key=lambda d: d["key"])
    case = {
        "case_id": previous["case_id"] if previous else
        f"AAINA-{now:%Y%m%d}-{uuid.uuid4().hex[:6].upper()}",
        "created_utc": previous["created_utc"] if previous else now.isoformat(timespec="seconds"),
        "updated_utc": now.isoformat(timespec="seconds"),
        "updated_ist": now.astimezone(IST).strftime("%d %b %Y %H:%M IST"),
        "originals_sha256": list(originals_sha),   # fingerprints only, never the photos
        "public_urls": list(public_urls),
        "engine_reports": [r.__dict__ for r in reports],
        "items": items,
        "manifest_sha256": _manifest(items),
        "history": (previous or {}).get("history", []),
    }
    return case


def verify_manifest(case: dict) -> bool:
    return case.get("manifest_sha256") == _manifest(case.get("items", []))


def save_case(case: dict, home: Path) -> Path:
    folder = Path(home) / "cases"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{case['case_id']}.json"
    path.write_text(json.dumps(case, indent=2), encoding="utf-8")
    return path


def load_case(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def render_pdf(case: dict, path) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    st = getSampleStyleSheet()
    small = st["BodyText"].clone("small", fontSize=7.5, leading=9.5)
    P = lambda text, style=small: Paragraph(escape(str(text)), style)  # noqa: E731
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"Aaina case file {case['case_id']}")
    items = [i for i in case["items"] if not i["mine"]]
    counts = {b: sum(1 for i in items if i["bucket"] == b) for b in ("Urgent", "Review", "Low")}
    story = [Paragraph("Aaina: Image Misuse Case File", st["Title"]),
             P(f"Case {case['case_id']}   |   generated {case['updated_ist']}", st["BodyText"]),
             Spacer(1, 4 * mm),
             P(f"Possible matches found: {len(items)}   (Urgent {counts['Urgent']}, "
               f"Review {counts['Review']}, Low {counts['Low']})", st["BodyText"]),
             P("These are possible matches found by reverse-image search on the user's own photographs. "
               "They are not proof of wrongdoing and were reviewed by the user.", st["BodyText"]),
             Spacer(1, 4 * mm)]
    rows = [[P("#"), P("Page"), P("Risk"), P("Engines"), P("Why")]]
    for n, it in enumerate(items, 1):
        rows.append([P(n), P(it["page_url"]), P(f"{it['bucket']} ({it['score']})"),
                     P(", ".join(it["engines"])),
                     P("; ".join(r["text"] for r in it["reasons"]))])
    table = Table(rows, colWidths=[8 * mm, 62 * mm, 20 * mm, 30 * mm, 62 * mm], repeatRows=1)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [table, Spacer(1, 5 * mm),
              Paragraph("Integrity fingerprint (SHA-256)", st["Heading4"]),
              P(case["manifest_sha256"]),
              P("Recompute this value from the JSON case file to confirm the list above was not changed.")]
    doc.build(story)
    return Path(path)
