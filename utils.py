import time
import random
import logging
import re
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("lead_research")


def rate_limit(min_delay: float = 1.0, max_delay: float = 2.5):
    time.sleep(random.uniform(min_delay, max_delay))


def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def deduplicate_leads(leads: list) -> list:
    seen = set()
    unique = []
    for lead in leads:
        key = (
            lead.get("instagram_url")
            or lead.get("phone")
            or lead.get("source_url")
            or lead.get("name", "")
        ).strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(lead)
    return unique


TITLE_SUFFIXES = [
    " | Instagram",
    " - Instagram",
    " • Instagram",
    " (@",
    " | Facebook",
    " - Facebook",
    " | LinkedIn",
    " - LinkedIn",
    " | YouTube",
    " - YouTube",
    " - Google",
    " | Google",
    " – ",
]


def clean_name(name: str) -> str:
    if not name:
        return ""
    for suffix in TITLE_SUFFIXES:
        if suffix in name:
            name = name[: name.index(suffix)]
    return name.strip()


def extract_instagram_handle(url: str) -> str:
    m = re.search(r"instagram\.com/([A-Za-z0-9._]+)/?", url)
    return f"@{m.group(1)}" if m else ""
