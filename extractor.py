import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import phonenumbers

from utils import logger, rate_limit, is_valid_url

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
FETCH_TIMEOUT = 10

# Patterns
INSTAGRAM_RE = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9._]{2,30})/?",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)
WHATSAPP_RE = re.compile(r"(?:wa\.me|api\.whatsapp\.com/send[^\"']*phone=)\+?(\d{7,15})")

# Instagram paths that are not usernames
_IG_NON_USERS = {
    "p", "reel", "reels", "stories", "explore", "accounts",
    "direct", "tv", "ar", "about", "press", "api", "privacy",
    "legal", "directory", "hashtag", "sharedfiles",
}

# Email domains that are almost always false positives
_EMAIL_NOISE = {
    "example.com", "test.com", "domain.com", "email.com",
    "sentry.io", "wixpress.com", "squarespace.com",
}

_NON_OWNED_WEBSITE_DOMAINS = {
    "beacons.ai",
    "bio.link",
    "facebook.com",
    "hoo.be",
    "indiamart.com",
    "instagram.com",
    "justdial.com",
    "linktr.ee",
    "linktree.com",
    "linkedin.com",
    "practo.com",
    "solo.to",
    "sulekha.com",
    "tap.bio",
    "tiktok.com",
    "urbancompany.com",
    "wa.me",
    "wedmegood.com",
    "weddingwire.in",
    "whatsapp.com",
    "x.com",
    "youtube.com",
}


# ─── Low-level helpers ────────────────────────────────────────────────────────

def _fetch_html(url: str) -> Optional[str]:
    try:
        resp = requests.get(
            url, headers=HEADERS, timeout=FETCH_TIMEOUT, allow_redirects=True
        )
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        logger.debug(f"Fetch failed {url}: {e}")
    return None


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _domain_matches(url: str, domains: set[str]) -> bool:
    domain = _domain(url)
    return any(domain == item or domain.endswith(f".{item}") for item in domains)


def _extract_instagram_urls(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for handle in INSTAGRAM_RE.findall(text):
        if handle.lower() not in _IG_NON_USERS and len(handle) >= 2:
            key = f"https://www.instagram.com/{handle}/"
            seen[key] = None
    return list(seen)


def _extract_emails(text: str) -> list[str]:
    found: dict[str, None] = {}
    for email in EMAIL_RE.findall(text):
        domain = email.split("@")[-1].lower()
        if domain not in _EMAIL_NOISE:
            found[email.lower()] = None
    return list(found)


def _extract_phones(text: str, region: str = "IN") -> list[str]:
    seen: dict[str, None] = {}

    # WhatsApp deep-links carry reliable numbers
    for digits in WHATSAPP_RE.findall(text):
        num = digits if digits.startswith("+") else f"+{digits}"
        seen[num] = None

    # phonenumbers library for everything else
    try:
        for match in phonenumbers.PhoneNumberMatcher(text, region):
            formatted = phonenumbers.format_number(
                match.number, phonenumbers.PhoneNumberFormat.E164
            )
            seen[formatted] = None
    except Exception:
        pass

    return list(seen)[:5]


def _extract_website_candidates(links: list[str], base_url: str) -> list[str]:
    base_domain = _domain(base_url)
    base_is_non_owned = _domain_matches(base_url, _NON_OWNED_WEBSITE_DOMAINS)
    seen: dict[str, None] = {}

    for raw_link in links:
        if not raw_link:
            continue
        absolute = urljoin(base_url, raw_link)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if not is_valid_url(absolute):
            continue
        if _domain_matches(absolute, _NON_OWNED_WEBSITE_DOMAINS):
            continue

        candidate_domain = _domain(absolute)
        if not candidate_domain:
            continue
        if candidate_domain == base_domain and base_is_non_owned:
            continue

        canonical = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        seen[canonical] = None

    return list(seen)


# ─── HTML parser ─────────────────────────────────────────────────────────────

def _parse_html(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    all_links = [a.get("href", "") for a in soup.find_all("a", href=True)]
    combined = text + " " + " ".join(str(l) for l in all_links)

    # Name: og:title > <title>
    name = ""
    og_title = soup.find("meta", property="og:title")
    if og_title:
        name = og_title.get("content", "")
    if not name:
        title_tag = soup.find("title")
        if title_tag:
            name = title_tag.get_text(strip=True)

    # Bio: og:description > meta description > first <p>
    bio = ""
    og_desc = soup.find("meta", property="og:description")
    if og_desc:
        bio = og_desc.get("content", "")
    if not bio:
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            bio = meta_desc.get("content", "")
    if not bio:
        first_p = soup.find("p")
        if first_p:
            bio = first_p.get_text(strip=True)

    return {
        "name": name,
        "bio": bio[:500],
        "instagram_urls": _extract_instagram_urls(combined),
        "emails": _extract_emails(combined),
        "phones": _extract_phones(combined),
        "website_candidates": _extract_website_candidates(all_links, url),
    }


# ─── Public API ──────────────────────────────────────────────────────────────

def extract_lead(search_result: dict, sector: str, city: str) -> dict:
    """
    Turn a raw search result into a structured lead dict.
    Combines snippet-level data (free) with page-level data (1 HTTP req).
    Instagram pages are not fetched — they block bots.
    """
    url = search_result.get("url", "")
    title = search_result.get("title", "")
    snippet = search_result.get("snippet", "") or ""

    is_instagram = "instagram.com" in url.lower()

    # Always parse snippet (no network cost)
    snippet_data = {
        "name": title,
        "bio": snippet,
        "instagram_urls": _extract_instagram_urls(snippet + " " + url),
        "emails": _extract_emails(snippet),
        "phones": _extract_phones(snippet),
    }

    # Fetch the page only if it's not Instagram and the URL looks valid
    html_data: dict = {}
    if not is_instagram and is_valid_url(url):
        rate_limit(0.5, 1.5)
        html = _fetch_html(url)
        if html:
            try:
                html_data = _parse_html(html, url)
            except Exception as e:
                logger.warning(f"Parse error {url}: {e}")

    # Merge: html_data takes priority; snippet fills gaps
    name = html_data.get("name") or snippet_data["name"] or title

    insta_urls = _dedup_list(
        (snippet_data["instagram_urls"] or []) + (html_data.get("instagram_urls") or [])
    )
    if is_instagram and url not in insta_urls:
        insta_urls.insert(0, url)

    emails = _dedup_list(
        (snippet_data["emails"] or []) + (html_data.get("emails") or [])
    )
    phones = _dedup_list(
        (snippet_data["phones"] or []) + (html_data.get("phones") or [])
    )

    bio = html_data.get("bio") or snippet_data["bio"] or ""
    source_is_non_owned = _domain_matches(url, _NON_OWNED_WEBSITE_DOMAINS)
    website_candidates = html_data.get("website_candidates") or []
    website = ""
    if not is_instagram and is_valid_url(url) and not source_is_non_owned:
        website = url
    elif website_candidates:
        website = website_candidates[0]

    return {
        "name": name,
        "sector": sector,
        "city": city,
        "instagram_url": insta_urls[0] if insta_urls else "",
        "all_instagram_urls": insta_urls,
        "website": website,
        "phone": phones[0] if phones else "",
        "all_phones": phones,
        "email": emails[0] if emails else "",
        "all_emails": emails,
        "bio": bio,
        "source_url": url,
        "source": search_result.get("source", ""),
        "snippet": snippet[:300],
    }


def _dedup_list(items: list) -> list:
    seen: dict = {}
    for x in items:
        if x:
            seen[x] = None
    return list(seen)
