from urllib.parse import urlparse

LINKTREE_DOMAINS = {
    "linktr.ee", "linktree.com", "bio.link", "beacons.ai",
    "solo.to", "campsite.bio", "tap.bio", "hoo.be",
}

WEAK_BUILDERS = [
    "wix.com", "weebly.com", "wordpress.com", "blogspot.com",
    "sites.google.com", "godaddysites.com", "jimdo.com",
    "yolasite.com", "strikingly.com",
]

PORTFOLIO_SIGNALS = [
    "portfolio", "gallery", "work", "projects", "services",
    "pricing", "packages", "booking", "shoots",
]


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _is_linktree(url: str) -> bool:
    return _domain(url) in LINKTREE_DOMAINS


def _is_instagram_url(url: str) -> bool:
    return "instagram.com" in (url or "").lower()


def _is_weak_builder(url: str) -> bool:
    d = _domain(url)
    return any(b in d for b in WEAK_BUILDERS)


def _has_portfolio(url: str, bio: str) -> bool:
    text = ((url or "") + " " + (bio or "")).lower()
    return any(sig in text for sig in PORTFOLIO_SIGNALS)


def compute_digital_presence_score(lead: dict) -> int:
    """
    Higher score = weaker digital presence = better outreach candidate.
    Range: 0–10.
    """
    score = 0
    website = (lead.get("website") or "").strip()
    instagram = (lead.get("instagram_url") or "").strip()
    phone = (lead.get("phone") or "").strip()
    email = (lead.get("email") or "").strip()
    bio = (lead.get("bio") or "").lower()

    if not website:
        score += 3                              # No website at all
    elif _is_instagram_url(website):
        score += 2                              # Instagram as "website"
    elif _is_linktree(website):
        score += 2                              # Link-in-bio aggregator
    elif _is_weak_builder(website):
        score += 2                              # DIY builder site
    else:
        if _has_portfolio(website, bio):
            score -= 5                          # Strong professional presence
        else:
            score += 1                          # Generic / thin site

    # WhatsApp-only contact
    if phone and not email:
        score += 1

    # Short bio with no portfolio mention suggests low effort
    if bio and len(bio) < 150 and not any(sig in bio for sig in PORTFOLIO_SIGNALS):
        score += 2

    # Only social presence, no independent web identity
    if instagram and not website:
        score += 1

    return max(0, min(10, score))


def compute_lead_quality_score(lead: dict) -> float:
    """
    How complete and actionable the contact information is.
    Range: 0.0–10.0.
    """
    score = 0.0
    if lead.get("name"):
        score += 1.5
    if lead.get("instagram_url"):
        score += 2.0
    if lead.get("phone"):
        score += 2.5
    if lead.get("email"):
        score += 2.0
    if lead.get("website"):
        score += 1.0
    if lead.get("bio"):
        score += 1.0
    return round(min(10.0, score), 1)
