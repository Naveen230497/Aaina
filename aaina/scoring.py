"""Transparent risk scoring. Every point comes with a human-readable reason."""
from __future__ import annotations

from .hashing import classify_distance
from .urls import text_cues

URGENT_AT, REVIEW_AT = 60, 30
BUCKET_ORDER = {"Urgent": 0, "Review": 1, "Low": 2, "Yours": 3}
_ENGINE_POINTS = {1: 5, 2: 15, 3: 25}
_DOMAIN_POINTS = {
    "adult": (35, "Appears on a site that looks adult/leak-oriented (judged from its name)"),
    "dating": (20, "Appears on a dating or classifieds site"),
    "social": (12, "Appears on a social/profile platform, where impersonation happens"),
    "image_host": (4, "Appears on a public image-hosting site"),
}


def score_finding(f) -> None:
    if f.mine:
        f.score, f.bucket, f.reasons = 0, "Yours", [("Matches a page or handle you marked as yours", 0)]
        return
    reasons = []

    n = len(f.engines)
    pts = 30 if n >= 4 else _ENGINE_POINTS.get(n, 0)
    reasons.append((f"Found by {n} search engine{'s' if n != 1 else ''}", pts))
    if "exact" in f.kinds:
        reasons.append(("Google Lens reports an exact image match", 10))

    verdict = classify_distance(f.hash_distance)
    if verdict == "strong":
        reasons.append(("Result thumbnail is almost identical to your photo (local check)", 25))
    elif verdict == "partial":
        reasons.append(("Thumbnail resembles your photo but differs: possible crop or edit (local check)", 20))
    elif verdict == "none":
        reasons.append(("Thumbnail does not resemble your photo (may be a different image)", -10))

    if f.domain_class in _DOMAIN_POINTS:
        p, why = _DOMAIN_POINTS[f.domain_class]
        reasons.append((why, p))

    adult, imp = text_cues(" ".join(f.titles), " ".join(f.snippets))
    if adult and f.domain_class != "adult":
        reasons.append(("Page title or text contains adult/leak wording", 15))
    if len(imp) >= 2:
        reasons.append((f"Text suggests a contact/dating-style page ({', '.join(imp[:3])})", 15))
    elif len(imp) == 1:
        reasons.append((f"Text contains a contact-style word ({imp[0]})", 6))

    import re
    PROFILE_TITLE_PATTERNS = [
        r"^meet\s+\w+", r"\bprofile\b", r"\babout\s+me\b", r"\bpersonal\s+details\b", r"\bescort\b"
    ]
    if any(re.search(p, " ".join(f.titles).lower()) for p in PROFILE_TITLE_PATTERNS):
        reasons.append(("Page title suggests a personal profile using your photo", 15))

    news = getattr(f, "news_articles", [])
    if len(news) >= 2:
        reasons.append(("Domain has 2+ news reports mentioning fraud/complaints", 30))
    elif len(news) == 1:
        reasons.append(("Domain mentioned in a complaint/scam news article", 15))

    ads = getattr(f, "ads", [])
    if ads:
        reasons.append(("Domain is running active Google Ads — photo may be used commercially", 25))

    f.reasons = [(t, p) for t, p in reasons if p != 0 or t.startswith("Found")]
    f.score = max(0, min(100, sum(p for _, p in reasons)))

    if len(f.engines) >= 3 and f.score < 30:
        f.score = 30
        f.reasons.append(("Found by 3+ engines — promoted to Review despite no hash match", 0))

    f.bucket = "Urgent" if f.score >= URGENT_AT else "Review" if f.score >= REVIEW_AT else "Low"


def score_all(findings) -> list:
    for f in findings:
        score_finding(f)
    return sorted(findings, key=lambda f: (BUCKET_ORDER[f.bucket], -f.score, f.key))
