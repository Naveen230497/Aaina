"""Offline demo: synthetic (non-human) images + canned API responses in the REAL response shapes,
so the real parsers, hashing, fusion and scoring all run. No network, no personal photos."""
from __future__ import annotations

import io
import random

from PIL import Image, ImageDraw, ImageOps

from .models import ImageRef

DEMO_URL = "https://photos-demo.example/original.jpg"


def synthetic_image(seed: int, size=(480, 640)) -> Image.Image:
    rnd = random.Random(seed)
    w, h = size
    c1 = tuple(rnd.randint(30, 220) for _ in range(3))
    c2 = tuple(rnd.randint(30, 220) for _ in range(3))
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3)))
    for _ in range(14):
        x0, y0 = rnd.randint(0, w - 80), rnd.randint(0, h - 80)
        box = [x0, y0, x0 + rnd.randint(40, 200), y0 + rnd.randint(40, 200)]
        col = tuple(rnd.randint(0, 255) for _ in range(3))
        (d.ellipse if rnd.random() < 0.5 else d.rectangle)(box, fill=col)
    return img


def _jpeg(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def demo_original() -> Image.Image:
    return synthetic_image(7)


def demo_thumbs() -> dict:
    orig = demo_original()
    edited = orig.copy()
    ImageDraw.Draw(edited).rectangle([120, 180, 360, 420], fill=(20, 20, 20))
    return {
        "copy": _jpeg(orig.resize((240, 320)), 35),                 # re-compressed repost
        "mirrored": _jpeg(ImageOps.mirror(orig).resize((200, 266)), 50),
        "edited": _jpeg(edited.resize((240, 320)), 60),             # altered version
        "unrelated": _jpeg(synthetic_image(99).resize((240, 320)), 60),
    }


def demo_fetch():
    thumbs = demo_thumbs()
    return lambda url: thumbs.get((url or "").replace("demo://", "", 1))


def demo_inputs():
    return [ImageRef("demo-photo", url=DEMO_URL)], [demo_original()], ["demo-sha256"]


class DemoClient:
    """Same interface as SerpClient, but answers from fixtures."""

    def search(self, params: dict) -> dict:
        engine, kind = params["engine"], params.get("type")
        if engine == "google_lens" and kind == "exact_matches":
            return {"exact_matches": [
                {"title": "Demo gallery 1", "link": "https://leaks-demo.example/gallery/1",
                 "thumbnail": "demo://copy"}]}
        if engine == "google_lens":
            return {"exact_matches": True, "visual_matches": [
                {"title": "Demo profile - chat and contact number",
                 "link": "https://www.instagram.com/demo_profile_0001/", "thumbnail": "demo://mirrored"},
                {"title": "Demo gallery 1",
                 "link": "https://leaks-demo.example/gallery/1?utm_source=x", "thumbnail": "demo://copy"},
                {"title": "Holiday blog post", "link": "https://blog-demo.example/post/9",
                 "thumbnail": "demo://unrelated"}]}
        if engine == "google_reverse_image":
            return {"image_results": [
                {"position": 1, "title": "Demo gallery 1", "link": "https://leaks-demo.example/gallery/1",
                 "snippet": "Demo gallery"},
                {"position": 2, "title": "Demo profile - chat and contact number",
                 "link": "https://instagram.com/demo_profile_0001", "snippet": "chat contact"}]}
        if engine == "bing_reverse_image":
            return {"pages_with_this_image": [
                {"title": "Demo profile", "link": "https://www.bing.com/images/search?demo=1",
                 "source": "https://www.instagram.com/demo_profile_0001/", "thumbnail": "demo://mirrored"}],
                "related_content": [
                {"title": "Photo dump 3", "source": "https://photo-dump-demo.example/a/3",
                 "thumbnail": "demo://edited"}],
                "looks_like": {"title": "IGNORED identity guess"}}
        if engine == "yandex_images":
            return {"image_results": [
                {"title": "Photo dump 3", "link": "https://photo-dump-demo.example/a/3",
                 "source": "photo-dump-demo.example", "thumbnail": {"link": "demo://edited"},
                 "original_image": {"link": "https://photo-dump-demo.example/img/3.jpg"}}],
                "knowledge_graph": [{"title": "IGNORED identity guess"}]}
        return {"_empty": True}

    def upload_image(self, jpeg: bytes, sha: str) -> str:
        return "demo-image-id"
