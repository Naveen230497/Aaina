"""Extra SerpApi engines for domain reputation and commercial misuse."""
from __future__ import annotations

def domain_reputation_news(domain: str, settings, client) -> list[dict]:
    if not settings.api_key or settings.demo:
        return []

    query = f'"{domain}" ("scam" OR "fake profile" OR "leaked" OR "fraud" OR "complaint")'
    params = {
        "engine": "google_news",
        "q": query,
        "num": 5,
    }
    
    try:
        data = client.search(params)
        articles = [
            {
                "title":   a.get("title", ""),
                "link":    a.get("link", ""),
                "snippet": a.get("snippet", ""),
                "date":    a.get("date", ""),
            }
            for a in data.get("news_results", [])[:5]
        ]
        return articles
    except Exception:
        return []

def check_ads_transparency(domain: str, settings, client) -> list[dict]:
    if not settings.api_key or settings.demo:
        return []

    params = {
        "engine": "google_ads_transparency_center",
        "advertiser_id": domain,
    }
    try:
        data = client.search(params)
        ads = [
            {
                "advertiser": a.get("advertiser_name", ""),
                "format":     a.get("format", ""),
                "first_shown": a.get("first_shown", ""),
                "last_shown":  a.get("last_shown", ""),
            }
            for a in data.get("ads", [])[:3]
        ]
        return ads
    except Exception:
        return []
