import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from aaina import demo
from aaina.cache import DiskCache
from aaina.casefile import make_case, render_pdf, verify_manifest
from aaina.config import Settings
from aaina.engines import (SerpClient, parse_bing, parse_google_reverse, parse_lens, parse_yandex,
                           plan_cost, plan_tasks)
from aaina.fusion import IgnoreRules, fuse
from aaina.hashing import blurred_png, classify_distance, distance, reference_signatures, signature
from aaina.models import ImageRef
from aaina.pipeline import run_sweep
from aaina.quota import Quota, QuotaExceeded
from aaina.safety import (Attestation, UnsafeInput, attestation_ok, sanitize_upload,
                          validate_public_url)
from aaina.takedown import Applicant, build_kit, find_abuse_email, kit_zip
from aaina.urls import canonical_url, classify_domain, host_of, registrable, text_cues
from aaina.verify import is_allowed_thumb


def settings(**kw):
    base = dict(api_key="k", home=Path(tempfile.mkdtemp()), monthly_cap=50, cache_ttl_hours=1,
                demo=True, lens_exact=True, max_verify=40)
    base.update(kw)
    return Settings(**base)


class UrlTests(unittest.TestCase):
    def test_canonical_merges_variants(self):
        a = canonical_url("http://www.Example.com/a/b/?utm_source=x&b=2&a=1#frag")
        b = canonical_url("https://example.com/a/b?a=1&b=2")
        self.assertEqual(a, b)

    def test_registrable(self):
        self.assertEqual(registrable("img.site.co.in"), "site.co.in")
        self.assertEqual(registrable("a.b.example.com"), "example.com")

    def test_scunthorpe_problem(self):
        self.assertEqual(classify_domain("essex-council.gov.uk"), "unknown")
        self.assertEqual(classify_domain("leaks-demo.example"), "adult")
        self.assertEqual(classify_domain("m.instagram.com"), "social")
        adult, _ = text_cues("Visit Essex and Sussex")
        self.assertFalse(adult)


class HashTests(unittest.TestCase):
    def setUp(self):
        self.refs = reference_signatures(demo.demo_original())

    def dist(self, name):
        data = demo.demo_thumbs()[name]
        return distance(signature(Image.open(io.BytesIO(data))), self.refs)

    def test_copy_and_mirror_are_strong(self):
        self.assertEqual(classify_distance(self.dist("copy")), "strong")
        self.assertEqual(classify_distance(self.dist("mirrored")), "strong")

    def test_edit_is_partial_and_unrelated_is_none(self):
        self.assertEqual(classify_distance(self.dist("edited")), "partial")
        self.assertEqual(classify_distance(self.dist("unrelated")), "none")

    def test_blur_returns_png(self):
        self.assertTrue(blurred_png(demo.demo_thumbs()["copy"]).startswith(b"\x89PNG"))


class ParserTests(unittest.TestCase):
    def test_lens_ignores_boolean_flag(self):
        hits = parse_lens({"exact_matches": True,
                           "visual_matches": [{"link": "https://a.example/x", "title": "t"}]})
        self.assertEqual([h.kind for h in hits], ["visual"])

    def test_bing_uses_source_not_bing_link_and_ignores_looks_like(self):
        hits = parse_bing({"pages_with_this_image": [{"link": "https://www.bing.com/x", "source": "https://p.example/1"}],
                           "looks_like": {"title": "Some Person"}})
        self.assertEqual(hits[0].page_url, "https://p.example/1")
        self.assertFalse(any("Some Person" in h.title for h in hits))

    def test_yandex_and_google(self):
        y = parse_yandex({"image_results": [{"link": "https://y.example/1", "thumbnail": {"link": "https://avatars.mds.yandex.net/i"}}],
                          "knowledge_graph": [{"title": "Some Person"}]})
        self.assertEqual(y[0].thumb, "https://avatars.mds.yandex.net/i")
        g = parse_google_reverse({"image_results": [{"link": "https://g.example/1", "title": "T"}]})
        self.assertEqual(g[0].engine, "google_reverse_image")


class PlanTests(unittest.TestCase):
    def test_cost(self):
        url_ref, id_ref = ImageRef("a", url="https://x.example/a.jpg"), ImageRef("b", image_id="abc")
        self.assertEqual(plan_cost([url_ref], True), 5)
        self.assertEqual(plan_cost([url_ref], False), 4)
        self.assertEqual(plan_cost([id_ref], True), 2)   # upload mode: Lens only
        self.assertEqual(plan_tasks(id_ref, False)[0][1], {"engine": "google_lens", "image_id": "abc"})


class PipelineTests(unittest.TestCase):
    def test_demo_sweep_buckets(self):
        s = settings()
        refs, originals, _ = demo.demo_inputs()
        res = run_sweep(demo.DemoClient(), refs, originals, s, fetch=demo.demo_fetch())
        buckets = {f.domain: f.bucket for f in res.findings}
        self.assertEqual(buckets["leaks-demo.example"], "Urgent")
        self.assertEqual(buckets["instagram.com"], "Urgent")
        self.assertEqual(buckets["photo-dump-demo.example"], "Review")
        self.assertEqual(buckets["blog-demo.example"], "Low")
        self.assertEqual(len(res.findings), 4)           # duplicates were merged

    def test_ignore_rules_mark_own_pages(self):
        s = settings()
        refs, originals, _ = demo.demo_inputs()
        res = run_sweep(demo.DemoClient(), refs, originals, s,
                        IgnoreRules.from_text("instagram.com/demo_profile_0001"), demo.demo_fetch())
        self.assertEqual({f.domain: f.bucket for f in res.findings}["instagram.com"], "Yours")

    def test_one_engine_failing_does_not_sink_the_sweep(self):
        class Flaky(demo.DemoClient):
            def search(self, params):
                if params["engine"] == "bing_reverse_image":
                    raise RuntimeError("boom")
                return super().search(params)
        s = settings()
        refs, originals, _ = demo.demo_inputs()
        res = run_sweep(Flaky(), refs, originals, s, fetch=demo.demo_fetch())
        self.assertTrue(any(not r.ok for r in res.reports))
        self.assertGreater(len(res.findings), 0)


class InfraTests(unittest.TestCase):
    def test_quota_blocks_and_persists(self):
        d = Path(tempfile.mkdtemp())
        q = Quota(d / "q.json", 3)
        q.reserve(3)
        with self.assertRaises(QuotaExceeded):
            q.reserve(1)
        self.assertEqual(Quota(d / "q.json", 3).remaining(), 0)

    def test_cache_key_ignores_api_key_and_roundtrips(self):
        c = DiskCache(Path(tempfile.mkdtemp()), 1)
        self.assertEqual(c.key("e", {"url": "u", "api_key": "A"}), c.key("e", {"url": "u", "api_key": "B"}))
        c.put("k", {"x": 1})
        self.assertEqual(c.get("k"), {"x": 1})

    def test_client_serves_second_call_from_cache(self):
        calls = []

        class Sess:
            def get(self, url, **kw):
                calls.append(url)
                class R:
                    status_code = 200
                    def json(self_inner): return {"visual_matches": []}
                return R()
        d = Path(tempfile.mkdtemp())
        client = SerpClient("k", DiskCache(d / "c", 1), Quota(d / "q.json", 10), Sess())
        client.search({"engine": "google_lens", "url": "https://x.example/a.jpg"})
        client.search({"engine": "google_lens", "url": "https://x.example/a.jpg"})
        self.assertEqual(len(calls), 1)


class SafetyTests(unittest.TestCase):
    def test_attestation(self):
        ok, missing = attestation_ok(Attestation(adult=True))
        self.assertFalse(ok)
        self.assertEqual(len(missing), 3)
        self.assertTrue(attestation_ok(Attestation(True, True, True, True))[0])

    def test_sanitize_strips_exif_and_fits_limit(self):
        img = demo.synthetic_image(3, (2400, 3200))
        exif = Image.Exif()
        exif[0x010F] = "SecretCamera"
        buf = io.BytesIO()
        img.save(buf, "JPEG", exif=exif)
        jpeg, out = sanitize_upload(buf.getvalue())
        self.assertLessEqual(len(jpeg), 480_000)
        self.assertEqual(len(Image.open(io.BytesIO(jpeg)).getexif()), 0)
        self.assertLessEqual(max(out.size), 1024)

    def test_rejects_non_images_and_private_urls(self):
        with self.assertRaises(UnsafeInput):
            sanitize_upload(b"not an image")
        for bad in ("http://localhost/a.jpg", "http://192.168.1.5/a.jpg", "ftp://x.example/a.jpg",
                    "https://user:pw@x.example/a.jpg", "http://127.0.0.1/a"):
            with self.assertRaises(UnsafeInput):
                validate_public_url(bad)
        self.assertEqual(validate_public_url("https://example.org/me.jpg"), "https://example.org/me.jpg")

    def test_thumbnail_allowlist(self):
        self.assertTrue(is_allowed_thumb("https://encrypted-tbn0.gstatic.com/images?q=1"))
        self.assertTrue(is_allowed_thumb("https://tse1.mm.bing.net/th?id=1"))
        self.assertFalse(is_allowed_thumb("https://evil.example/a.jpg"))
        self.assertFalse(is_allowed_thumb("http://encrypted-tbn0.gstatic.com/a"))
        self.assertFalse(is_allowed_thumb("https://gstatic.com.evil.example/a"))


class OutputTests(unittest.TestCase):
    def setUp(self):
        s = settings()
        refs, originals, self.shas = demo.demo_inputs()
        self.res = run_sweep(demo.DemoClient(), refs, originals, s, fetch=demo.demo_fetch())

    def test_case_manifest_detects_tampering_and_pdf_renders(self):
        case = make_case(self.res.findings, self.shas, [], self.res.reports)
        self.assertTrue(verify_manifest(case))
        pdf = render_pdf(case, Path(tempfile.mkdtemp()) / "c.pdf")
        self.assertTrue(pdf.read_bytes().startswith(b"%PDF"))
        case["items"][0]["score"] = 1
        self.assertFalse(verify_manifest(case))
        json.dumps(case)  # serialisable, and contains no image bytes
        self.assertNotIn("thumb_bytes", json.dumps(case))

    def test_kit_contents(self):
        sel = [f for f in self.res.findings if f.bucket == "Urgent"]
        kit = build_kit(sel, Applicant("Test User", "t@example.org"), "copyright", "AAINA-X", "abc",
                        lookup_abuse=lambda d: "abuse@host.example")
        self.assertIn("00_READ_ME_FIRST.txt", kit)
        text = "\n".join(kit.values())
        self.assertIn(sel[0].page_url, text)
        self.assertIn("cybercrime.gov.in", text)
        self.assertIn("DMCA", text)
        self.assertIn("abuse@host.example", text)
        self.assertTrue(kit_zip(kit).startswith(b"PK"))

    def test_find_abuse_email(self):
        rdap = {"entities": [{"roles": ["registrar"], "entities": [
            {"roles": ["abuse"], "vcardArray": ["vcard", [["version", {}, "text", "4.0"],
                                                          ["email", {}, "text", "abuse@reg.example"]]]}]}]}
        self.assertEqual(find_abuse_email(rdap), "abuse@reg.example")
        self.assertIsNone(find_abuse_email({"entities": []}))


if __name__ == "__main__":
    unittest.main()
