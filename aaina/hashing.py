"""Local perceptual hashing: compare search-result thumbnails with the user's originals on-device."""
from __future__ import annotations

import io

from PIL import Image, ImageFilter, ImageOps

STRONG_MAX = 8      # near-identical
PARTIAL_MAX = 16    # same picture, but cropped/edited/recoloured


def _gray(img: Image.Image) -> Image.Image:
    return ImageOps.autocontrast(ImageOps.exif_transpose(img).convert("L"))


def _pixels(img: Image.Image) -> list:
    getter = getattr(img, "get_flattened_data", None) or img.getdata   # Pillow 14+ / older
    return list(getter())


def dhash(img: Image.Image, size: int = 8) -> int:
    px = _pixels(_gray(img).resize((size + 1, size), Image.LANCZOS))
    bits = 0
    for row in range(size):
        for col in range(size):
            i = row * (size + 1) + col
            bits = (bits << 1) | int(px[i] > px[i + 1])
    return bits


def ahash(img: Image.Image, size: int = 8) -> int:
    px = _pixels(_gray(img).resize((size, size), Image.LANCZOS))
    avg = sum(px) / len(px)
    bits = 0
    for p in px:
        bits = (bits << 1) | int(p > avg)
    return bits


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def signature(img: Image.Image) -> tuple:
    return (dhash(img), ahash(img))


def _center_crop(img: Image.Image, keep: float) -> Image.Image:
    w, h = img.size
    dx, dy = int(w * (1 - keep) / 2), int(h * (1 - keep) / 2)
    return img.crop((dx, dy, w - dx, h - dy))


def reference_signatures(original: Image.Image) -> list:
    """Hashes of the original plus the usual evasion edits: mirror and two centre crops."""
    variants = [original, ImageOps.mirror(original),
                _center_crop(original, 0.85), _center_crop(original, 0.7)]
    return [signature(v) for v in variants]


def distance(candidate_sig: tuple, refs: list) -> int:
    """Smallest average (dHash, aHash) Hamming distance to any reference. 0 = identical."""
    return min((hamming(candidate_sig[0], r[0]) + hamming(candidate_sig[1], r[1])) // 2
               for r in refs)


def classify_distance(d) -> str:
    if d is None:
        return "unchecked"
    return "strong" if d <= STRONG_MAX else "partial" if d <= PARTIAL_MAX else "none"


def blurred_png(data: bytes, radius: int = 14) -> bytes:
    """Thumbnails are blurred by default so users are not re-traumatised by what they find."""
    img = Image.open(io.BytesIO(data)).convert("RGB").filter(ImageFilter.GaussianBlur(radius))
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()
