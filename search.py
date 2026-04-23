"""
Search layer.

Primary (free, no key): DuckDuckGo via duckduckgo-search library.
Optional fallbacks    : SerpAPI or Google Custom Search Engine.

Set SERPAPI_KEY **or** GOOGLE_CSE_KEY + GOOGLE_CSE_ID in .env to upgrade to
paid APIs for higher quotas / fewer rate-limits. If neither is set the app
works out of the box using DuckDuckGo.
"""

import os
import time
import random
from typing import Callable, Optional

import requests
from utils import logger, rate_limit

# ── Optional paid APIs ────────────────────────────────────────────────────────
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
GOOGLE_CSE_KEY = os.getenv("GOOGLE_CSE_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")

SERPAPI_ENDPOINT = "https://serpapi.com/search"
CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"


# ── Query builder ─────────────────────────────────────────────────────────────

def build_queries(sector: str, city: str) -> list[str]:
    s, c = sector.strip(), city.strip()
    return [
        f'"{s}" "{c}" instagram contact phone',
        f'"{s}" "{c}" site:instagram.com',
        f'"{s}" {c} whatsapp portfolio hire',
        f'"{s}" {c} -justdial -sulekha -indiamart',
        f'{s} {c} instagram bio booking',
    ]


# ── DuckDuckGo (free, default) ────────────────────────────────────────────────

def _ddg_search(query: str, num: int) -> list[dict]:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.error("duckduckgo-search not installed. Run: pip install duckduckgo-search")
        return []

    results: list[dict] = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=num, region="in-en"):
                if r.get("href"):
                    results.append(
                        {
                            "title": r.get("title", ""),
                            "url": r.get("href", ""),
                            "snippet": r.get("body", ""),
                            "source": "duckduckgo",
                        }
                    )
    except Exception as e:
        logger.warning(f"DDG search error for '{query[:60]}': {e}")
    return results


# ── SerpAPI (optional, paid) ──────────────────────────────────────────────────

def _serpapi(query: str, num: int) -> list[dict]:
    try:
        resp = requests.get(
            SERPAPI_ENDPOINT,
            params={"q": query, "api_key": SERPAPI_KEY, "num": num, "hl": "en", "gl": "in"},
            timeout=20,
        )
        resp.raise_for_status()
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("link", ""),
                "snippet": r.get("snippet", ""),
                "source": "serpapi",
            }
            for r in resp.json().get("organic_results", [])
            if r.get("link")
        ]
    except Exception as e:
        logger.error(f"SerpAPI error: {e}")
        return []


# ── Google CSE (optional, paid) ───────────────────────────────────────────────

def _cse(query: str, num: int) -> list[dict]:
    try:
        resp = requests.get(
            CSE_ENDPOINT,
            params={
                "key": GOOGLE_CSE_KEY,
                "cx": GOOGLE_CSE_ID,
                "q": query,
                "num": min(num, 10),
                "gl": "in",
            },
            timeout=20,
        )
        resp.raise_for_status()
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": "google_cse",
            }
            for item in resp.json().get("items", [])
            if item.get("link")
        ]
    except Exception as e:
        logger.error(f"Google CSE error: {e}")
        return []


# ── Router ────────────────────────────────────────────────────────────────────

def _search_one(query: str, num: int) -> list[dict]:
    if SERPAPI_KEY:
        return _serpapi(query, num)
    if GOOGLE_CSE_KEY and GOOGLE_CSE_ID:
        return _cse(query, num)
    return _ddg_search(query, num)          # free default


# ── Public API ────────────────────────────────────────────────────────────────

def run_search(
    sector: str,
    city: str,
    max_results: int = 50,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> list[dict]:
    queries = build_queries(sector, city)
    per_query = max(10, max_results // len(queries))
    seen_urls: set[str] = set()
    results: list[dict] = []

    for i, query in enumerate(queries):
        if len(results) >= max_results:
            break
        if progress_callback:
            progress_callback(
                i / len(queries),
                f"Query {i+1}/{len(queries)}: {query[:70]}",
            )
        for r in _search_one(query, per_query):
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                results.append(r)

        # Polite delay — DuckDuckGo rate-limits aggressive clients
        rate_limit(1.5, 3.0)

    if progress_callback:
        progress_callback(1.0, f"Done — {len(results)} URLs collected.")

    return results[:max_results]
