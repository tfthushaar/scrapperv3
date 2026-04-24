"""
Search layer.

Primary (free, no key): DuckDuckGo via duckduckgo-search.
Optional upgrades: SerpAPI or Google Custom Search Engine.
"""

from typing import Callable, Optional

import requests

from config import get_secret
from utils import logger, rate_limit

SERPAPI_KEY = str(get_secret("SERPAPI_KEY", "") or "")
GOOGLE_CSE_KEY = str(get_secret("GOOGLE_CSE_KEY", "") or "")
GOOGLE_CSE_ID = str(get_secret("GOOGLE_CSE_ID", "") or "")

SERPAPI_ENDPOINT = "https://serpapi.com/search"
CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"


def build_queries(sector: str, city: str) -> list[str]:
    sector = sector.strip()
    city = city.strip()
    return [
        f'"{sector}" "{city}" instagram contact phone',
        f'"{sector}" "{city}" site:instagram.com',
        f'"{sector}" {city} whatsapp portfolio hire',
        f'"{sector}" {city} -justdial -sulekha -indiamart',
        f"{sector} {city} instagram bio booking",
    ]


def _ddg_search(query: str, num: int) -> list[dict]:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.error("duckduckgo-search is missing. Run: pip install duckduckgo-search")
        return []

    results: list[dict] = []
    try:
        with DDGS() as ddgs:
            for result in ddgs.text(query, max_results=num, region="in-en"):
                if result.get("href"):
                    results.append(
                        {
                            "title": result.get("title", ""),
                            "url": result.get("href", ""),
                            "snippet": result.get("body", ""),
                            "source": "duckduckgo",
                        }
                    )
    except Exception as exc:
        logger.warning(f"DDG search error for '{query[:60]}': {exc}")
    return results


def _serpapi(query: str, num: int) -> list[dict]:
    try:
        response = requests.get(
            SERPAPI_ENDPOINT,
            params={"q": query, "api_key": SERPAPI_KEY, "num": num, "hl": "en", "gl": "in"},
            timeout=20,
        )
        response.raise_for_status()
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": "serpapi",
            }
            for item in response.json().get("organic_results", [])
            if item.get("link")
        ]
    except Exception as exc:
        logger.error(f"SerpAPI error: {exc}")
        return []


def _cse(query: str, num: int) -> list[dict]:
    try:
        response = requests.get(
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
        response.raise_for_status()
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": "google_cse",
            }
            for item in response.json().get("items", [])
            if item.get("link")
        ]
    except Exception as exc:
        logger.error(f"Google CSE error: {exc}")
        return []


def _search_one(query: str, num: int) -> list[dict]:
    if SERPAPI_KEY:
        return _serpapi(query, num)
    if GOOGLE_CSE_KEY and GOOGLE_CSE_ID:
        return _cse(query, num)
    return _ddg_search(query, num)


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

    for index, query in enumerate(queries):
        if len(results) >= max_results:
            break

        if progress_callback:
            progress_callback(
                index / len(queries),
                f"Query {index + 1}/{len(queries)}: {query[:70]}",
            )

        for result in _search_one(query, per_query):
            url = result.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                results.append(result)

        rate_limit(1.5, 3.0)

    if progress_callback:
        progress_callback(1.0, f"Done - {len(results)} URLs collected.")

    return results[:max_results]
