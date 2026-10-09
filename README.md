# Aaina 🪞 (mirror)

**Find where your photos are being misused online, understand the risk, and get a takedown kit.**

Aaina runs your *own original photos* through four reverse-image engines via
[SerpApi](https://serpapi.com), merges the results, checks result thumbnails against your photo
**locally on your device**, scores each match with explainable reasons, and builds ready-to-send
takedown notices plus an evidence case file. A weekly watch mode reports only *new* matches.

> Aaina cannot delete content from other websites. It finds, prioritises and prepares.

## Why SerpApi
| Need | Engine |
|---|---|
| Visual + exact matches | `google_lens` (url or uploaded `image_id`; `type=exact_matches`) |
| Pages containing the image | `google_reverse_image`, `bing_reverse_image` (`pages_with_this_image`) |
| Cross-check | `yandex_images` (reverse image via `url`) |
| Uploads without hosting | SerpApi Image API (`POST /image`, ≤ 500 KB) |

Deliberately ignored: Bing `looks_like` and Yandex `knowledge_graph`. They are identity guesses, and Aaina never shows those.

## Safety by design
- Consent gate (18+, own photos, no minors, limits understood) before anything runs
- No face recognition, no people search. Only photos you attest are yours
- Search with clean originals, **never** the harmful image
- EXIF/GPS stripped; nothing stored; case files hold fingerprints, not images
- Thumbnails fetched only from search-engine CDNs (allow-list), never from the suspect site
- Thumbnails blurred by default; result links shown as text, not clickable
- Language is "possible match", never "guilty"

## Setup
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # add SERPAPI_API_KEY (never commit .env)
streamlit run app.py
```
**Offline demo (no key, no network, synthetic images):** `AAINA_DEMO=1 streamlit run app.py` or `python -m aaina.cli --demo --pdf`

## CLI and watch mode
```bash
python -m aaina.cli --url https://example.org/my-profile-photo.jpg --pdf
python -m aaina.watch --case ~/.aaina/cases/AAINA-YYYYMMDD-XXXXXX.json
# cron (weekly, Mondays 09:00):  0 9 * * 1  cd /path/to/aaina && .venv/bin/python -m aaina.watch --case ...
```

## Budget (free plan = 250 searches/month)
~5 searches per public-link photo (4 without `AAINA_LENS_EXACT`), 2 per uploaded photo.
`AAINA_MONTHLY_CAP` is a hard local stop; responses are cached on disk (24 h).

## Tests
`python -m unittest discover -s tests -v`

## Limitations (please read)
- Reverse image search finds copies and near-copies reliably; a heavily morphed image may not match.
- Results are possible matches, not proof. Search engines can be wrong or miss pages.
- Risk scores are heuristics, shown with reasons. Domain/word cues are judged from names only.
- Legal references in the kit are pointers, not legal advice. Verify before sending.

## Hackathon disclosures
Built for the SerpApi India Hackathon 2026. AI tools used: *(list here)*. Demo images are synthetic; no real person's photos are in this repo.
