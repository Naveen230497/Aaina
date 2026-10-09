import os
import json
from aaina.config import Settings
from aaina.engines import PARSERS

# I will write a simpler script to just check if `engines.py` parses a dummy JSON or we actually run a live request.
# But `engines.py` has no `search_google_lens` functions. It has `PARSERS` and `run_engines` taking a `SerpClient`.
from aaina.engines import SerpClient
from aaina.models import ImageRef

class DummyCache:
    def key(self, engine, params): return "dummy"
    def get(self, key): return None
    def put(self, key, val): pass

class DummyQuota:
    def reserve(self, n): pass
    def refund(self, n): pass

s = Settings.load()
# If no api key, print warning
if not s.api_key:
    print("NO API KEY SET!")

TEST_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/240px-PNG_transparency_demonstration_1.png"
client = SerpClient(s.api_key, DummyCache(), DummyQuota())

params_list = [
    ("google_lens", {"engine": "google_lens", "url": TEST_URL}),
    ("google_reverse_image", {"engine": "google_reverse_image", "image_url": TEST_URL}),
    ("bing_reverse_image", {"engine": "bing_reverse_image", "image_url": TEST_URL}),
    ("yandex_images", {"engine": "yandex_images", "url": TEST_URL}),
]

for name, params in params_list:
    try:
        data = client.search(params)
        hits = PARSERS[name](data)
        print(f"OK {name}: {len(hits)} hits, first={hits[0].page_url if hits else 'none'}")
    except Exception as e:
        print(f"FAILED {name}: {e}")
