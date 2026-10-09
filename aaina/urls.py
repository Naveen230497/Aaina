"""URL canonicalisation, domain classification and text cues (all offline, all testable)."""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_KEYS = {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "ref", "ref_src",
                  "si", "feature", "srsltid"}
_SECOND_LEVEL = {"co", "com", "org", "net", "ac", "gov", "edu", "nic"}

SOCIAL = ("instagram.com", "facebook.com", "fb.com", "x.com", "twitter.com", "tiktok.com",
          "snapchat.com", "linkedin.com", "pinterest.com", "reddit.com", "t.me",
          "telegram.me", "threads.net", "vk.com", "tumblr.com", "youtube.com", "sharechat.com")
IMAGE_HOST = ("imgur.com", "ibb.co", "imgbb.com", "postimg.cc", "pinimg.com",
              "flickr.com", "500px.com", "pixhost.to")
DATING_MARKET = ("tinder.com", "bumble.com", "badoo.com", "okcupid.com", "hinge.co",
                 "trulymadly.com", "olx.in", "quikr.com")

# Whole-token matching avoids the "Scunthorpe problem" (e.g. "essex" must not match "sex").
ADULT_TOKENS = {"porn", "xxx", "nsfw", "nude", "nudes", "naked", "leak", "leaks",
                "leaked", "onlyfans", "fansly", "fappening", "sex"}
ADULT_SUBSTR = ("porn", "xvideo", "onlyfans", "fansly", "fappening")
IMPERSONATION_TOKENS = {"dating", "escort", "escorts", "hookup", "whatsapp", "chat",
                        "girls", "meet", "contact", "number", "telegram", "signal", "call", "email", "dm", "91"}


def tokens(text: str) -> list:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def host_of(url: str) -> str:
    try:
        host = (urlsplit(url if "://" in url else "https://" + url).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def registrable(host: str) -> str:
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in _SECOND_LEVEL and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def canonical_url(url: str) -> str:
    """Stable identity for a page: https, no www, no tracking params, no fragment."""
    url = (url or "").strip()
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    try:
        p = urlsplit(url)
        port = f":{p.port}" if p.port and p.port not in (80, 443) else ""
    except ValueError:
        return ""
    host = (p.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return ""
    path = re.sub(r"/{2,}", "/", p.path or "").rstrip("/")
    query = urlencode(sorted(
        (k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_KEYS and not k.lower().startswith("utm_")))
    return urlunsplit(("https", host + port, path, query, ""))


def _in(host: str, domains) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def classify_domain(host: str) -> str:
    if _in(host, SOCIAL):
        return "social"
    if _in(host, DATING_MARKET):
        return "dating"
    if _in(host, IMAGE_HOST):
        return "image_host"
    if set(tokens(host)) & ADULT_TOKENS or any(s in host for s in ADULT_SUBSTR):
        return "adult"
    return "unknown"


def text_cues(*texts: str):
    """Returns (adult_cue: bool, impersonation_cues: list[str])."""
    combined = " ".join(t for t in texts if t)
    toks = set(tokens(combined))
    adult = bool(toks & ADULT_TOKENS)
    imp = sorted(toks & IMPERSONATION_TOKENS)
    if re.search(r"\+?91[\-\s]?\d{10}\b|\b[6-9]\d{9}\b", combined):
        imp.append("indian_mobile")
    return adult, imp
