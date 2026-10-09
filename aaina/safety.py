"""Safety gates: consent, input hygiene, SSRF-safe downloads, EXIF stripping."""
from __future__ import annotations

import io
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import requests
from PIL import Image, ImageOps

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
SERPAPI_UPLOAD_LIMIT = 480_000        # SerpApi's Image API accepts up to 500 KB
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class UnsafeInput(ValueError):
    """Raised when input fails a safety check. The message is safe to show the user."""


@dataclass
class Attestation:
    adult: bool = False
    own_photos: bool = False
    no_minors: bool = False
    understands_limits: bool = False


_LABELS = {
    "adult": "I am 18 or older.",
    "own_photos": "Every photo I add shows me, or I own the copyright and have the right to act on it.",
    "no_minors": "None of the photos shows a person under 18.",
    "understands_limits": "I understand results are possible matches to review, not proof, "
                          "and that Aaina cannot delete content from other websites.",
}


def attestation_labels() -> dict:
    return dict(_LABELS)


def attestation_ok(a: Attestation):
    missing = [lbl for k, lbl in _LABELS.items() if not getattr(a, k)]
    return (not missing), missing


def sanitize_upload(raw: bytes):
    """Validate, strip EXIF/GPS (by re-encoding) and shrink to fit SerpApi's upload limit."""
    if len(raw) > MAX_UPLOAD_BYTES:
        raise UnsafeInput("That file is larger than 8 MB.")
    try:
        img = Image.open(io.BytesIO(raw))
        fmt = img.format
        img.load()
    except Exception as exc:  # noqa: BLE001 - any decoder failure means "not a usable image"
        raise UnsafeInput("That file could not be read as an image.") from exc
    if fmt not in ALLOWED_FORMATS:
        raise UnsafeInput("Only JPEG, PNG or WebP images are accepted.")
    if getattr(img, "is_animated", False):
        raise UnsafeInput("Animated images are not supported.")
    img = ImageOps.exif_transpose(img).convert("RGB")
    if min(img.size) < 64:
        raise UnsafeInput("The image is too small to search with.")
    base = img
    for scale in (1.0, 0.8, 0.64, 0.5, 0.4):
        side = 1024 * scale
        k = min(1.0, side / max(base.size))
        cand = base.resize((max(1, int(base.width * k)), max(1, int(base.height * k))), Image.LANCZOS) if k < 1 else base
        for q in (88, 78, 68, 58, 48):
            buf = io.BytesIO()
            cand.save(buf, "JPEG", quality=q, optimize=True)   # no exif= argument: metadata dropped
            if buf.tell() <= SERPAPI_UPLOAD_LIMIT:
                return buf.getvalue(), cand
    raise UnsafeInput("Could not shrink that image enough to upload.")


def _is_public_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False


def validate_public_url(url: str) -> str:
    """Accept only plain http(s) URLs that point at the public internet."""
    url = (url or "").strip()
    p = urlsplit(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise UnsafeInput("Enter a full http(s) link to your photo.")
    if p.username or p.password:
        raise UnsafeInput("Links with embedded credentials are not accepted.")
    host = p.hostname.lower()
    if host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        raise UnsafeInput("That address is not on the public internet.")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None          # a hostname: resolved and re-checked at download time
    if literal is not None and not literal.is_global:
        raise UnsafeInput("That address is not on the public internet.")
    return url


def safe_download(url: str, max_bytes: int = MAX_UPLOAD_BYTES, hops: int = 3) -> bytes:
    """Download the user's own public photo, refusing private addresses on every redirect."""
    current = validate_public_url(url)
    for _ in range(hops + 1):
        host = urlsplit(current).hostname
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror as exc:
            raise UnsafeInput("That address could not be resolved.") from exc
        if not infos or not all(_is_public_ip(i[4][0]) for i in infos):
            raise UnsafeInput("That address is not on the public internet.")
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AainaBot/1.0"}
        r = requests.get(current, stream=True, timeout=10, allow_redirects=False, headers=headers)
        if r.is_redirect or r.status_code in (301, 302, 303, 307, 308):
            current = validate_public_url(urljoin(current, r.headers.get("Location", "")))
            continue
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
            raise UnsafeInput("That link did not return an image.")
        buf = bytearray()
        for chunk in r.iter_content(65536):
            buf += chunk
            if len(buf) > max_bytes:
                raise UnsafeInput("That image is larger than 8 MB.")
        return bytes(buf)
    raise UnsafeInput("Too many redirects.")
