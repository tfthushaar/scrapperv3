from urllib.parse import urlparse

LINKTREE_DOMAINS = {
    "beacons.ai",
    "bio.link",
    "campsite.bio",
    "hoo.be",
    "linktr.ee",
    "linktree.com",
    "solo.to",
    "tap.bio",
}

SOCIAL_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "tiktok.com",
    "twitter.com",
    "wa.me",
    "whatsapp.com",
    "x.com",
    "youtube.com",
}

DIRECTORY_DOMAINS = {
    "indiamart.com",
    "justdial.com",
    "practo.com",
    "sulekha.com",
    "urbancompany.com",
    "wedmegood.com",
    "weddingwire.in",
}

WEAK_BUILDERS = {
    "blogspot.com",
    "godaddysites.com",
    "jimdo.com",
    "sites.google.com",
    "strikingly.com",
    "weebly.com",
    "wix.com",
    "wordpress.com",
    "yolasite.com",
}

PROFESSIONAL_SIGNALS = {
    "about",
    "book",
    "booking",
    "contact",
    "gallery",
    "packages",
    "portfolio",
    "pricing",
    "projects",
    "reviews",
    "services",
    "testimonials",
    "work",
}

TRUST_SIGNALS = {
    "award",
    "certified",
    "clients",
    "est.",
    "experience",
    "featured",
    "founded",
    "since",
    "studio",
    "team",
    "trusted",
    "years",
}

GENERIC_EMAIL_DOMAINS = {
    "aol.com",
    "gmail.com",
    "hotmail.com",
    "icloud.com",
    "outlook.com",
    "proton.me",
    "yahoo.com",
}


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _matches_domain(url: str, domains: set[str]) -> bool:
    domain = _domain(url)
    return any(domain == item or domain.endswith(f".{item}") for item in domains)


def _text_blob(lead: dict) -> str:
    parts = [
        lead.get("name", ""),
        lead.get("website", ""),
        lead.get("bio", ""),
        lead.get("snippet", ""),
        lead.get("source_url", ""),
    ]
    return " ".join(str(part or "") for part in parts).lower()


def _keyword_hits(text: str, keywords: set[str]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def _is_social_or_link_hub(url: str) -> bool:
    return _matches_domain(url, SOCIAL_DOMAINS | LINKTREE_DOMAINS)


def _is_directory(url: str) -> bool:
    return _matches_domain(url, DIRECTORY_DOMAINS)


def _is_weak_builder(url: str) -> bool:
    return _matches_domain(url, WEAK_BUILDERS)


def _email_domain(email: str) -> str:
    email = (email or "").strip().lower()
    if "@" not in email:
        return ""
    return email.split("@", 1)[1]


def _has_domain_matched_email(email: str, website: str) -> bool:
    email_domain = _email_domain(email)
    website_domain = _domain(website)
    if not email_domain or not website_domain:
        return False
    return email_domain == website_domain or email_domain.endswith(f".{website_domain}")


def _is_generic_email(email: str) -> bool:
    return _email_domain(email) in GENERIC_EMAIL_DOMAINS


def analyze_digital_presence(lead: dict) -> dict:
    """
    Higher score = weaker digital presence = better outreach candidate.
    Returns a score plus short human-readable notes.
    """
    website = (lead.get("website") or "").strip()
    instagram = (lead.get("instagram_url") or "").strip()
    phone = (lead.get("phone") or "").strip()
    email = (lead.get("email") or "").strip()
    bio = (lead.get("bio") or "").strip()
    source_url = (lead.get("source_url") or "").strip()
    text = _text_blob(lead)

    score = 5.0
    reasons: list[str] = []

    owned_website = bool(website) and not _is_social_or_link_hub(website) and not _is_directory(website)
    professional_hits = _keyword_hits(text, PROFESSIONAL_SIGNALS)
    trust_hits = _keyword_hits(text, TRUST_SIGNALS)
    contact_channels = sum(bool(value) for value in [instagram, phone, email, owned_website])

    if not website:
        score += 2.5
        reasons.append("No owned website found")
    elif _is_social_or_link_hub(website):
        score += 2.0
        reasons.append("Uses social or link-in-bio as primary web presence")
    elif _is_weak_builder(website):
        score += 1.0
        reasons.append("Website appears to be on a DIY site builder")
    else:
        score -= 1.5
        reasons.append("Own website found")

    if instagram and not owned_website:
        score += 1.0
        reasons.append("Relies heavily on Instagram without a strong site")

    if _is_directory(source_url) and not owned_website:
        score += 1.0
        reasons.append("Mostly surfaced through a directory listing")

    if not email:
        score += 1.0
        reasons.append("No email discovered")
    elif _has_domain_matched_email(email, website):
        score -= 1.25
        reasons.append("Uses a domain-matched business email")
    elif _is_generic_email(email):
        score += 0.5
        reasons.append("Uses a generic email provider")

    if phone and not email:
        score += 0.5
        reasons.append("Phone or WhatsApp is the main contact path")

    if contact_channels <= 1:
        score += 1.0
        reasons.append("Very few public contact channels")
    elif contact_channels >= 3:
        score -= 0.75
        reasons.append("Multiple public contact paths are available")

    if not bio:
        score += 0.75
        reasons.append("Little descriptive business copy")
    elif len(bio) < 80:
        score += 1.0
        reasons.append("Bio is very short")
    elif len(bio) >= 220:
        score -= 0.5
        reasons.append("Bio is detailed")

    if professional_hits >= 4:
        score -= 2.0
        reasons.append("Strong portfolio or conversion signals")
    elif professional_hits >= 2:
        score -= 1.0
        reasons.append("Some service or portfolio signals are present")
    elif not owned_website:
        score += 0.5
        reasons.append("Few portfolio or service signals found")

    if trust_hits >= 2:
        score -= 1.0
        reasons.append("Brand trust signals are visible")

    clamped = max(0.0, min(10.0, score))
    ordered_reasons = []
    seen_reasons = set()
    for reason in reasons:
        if reason not in seen_reasons:
            seen_reasons.add(reason)
            ordered_reasons.append(reason)

    return {
        "score": int(round(clamped)),
        "notes": " | ".join(ordered_reasons[:4]),
        "owned_website": owned_website,
    }


def compute_digital_presence_score(lead: dict) -> int:
    return analyze_digital_presence(lead)["score"]


def compute_digital_presence_notes(lead: dict) -> str:
    return analyze_digital_presence(lead)["notes"]


def compute_lead_quality_score(lead: dict) -> float:
    """
    How complete and actionable the contact information is.
    Range: 0.0-10.0.
    """
    website = (lead.get("website") or "").strip()
    email = (lead.get("email") or "").strip()
    bio = (lead.get("bio") or "").strip()
    instagram = (lead.get("instagram_url") or "").strip()
    phone = (lead.get("phone") or "").strip()

    score = 0.0

    if lead.get("name"):
        score += 1.5
    if instagram:
        score += 1.5
    if phone:
        score += 2.25
    if email:
        score += 2.0
    if website:
        score += 1.25
    if bio:
        score += 0.75 if len(bio) < 80 else 1.25
    if email and website and _has_domain_matched_email(email, website):
        score += 0.75
    if lead.get("all_phones") and len(lead.get("all_phones") or []) > 1:
        score += 0.25
    if lead.get("all_emails") and len(lead.get("all_emails") or []) > 1:
        score += 0.25

    return round(min(10.0, score), 1)
