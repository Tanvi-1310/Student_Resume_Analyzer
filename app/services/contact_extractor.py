"""Conservative contact information extraction service.

Extracts candidate email, telephone, LinkedIn, GitHub, and personal portfolio links.
Follows strict safety principles:
- Zero logging or printing of candidate personal details.
- Avoids false-positive digit matching for phone numbers.
- Does not infer names via unreliable first-line heuristics.
"""

import re
from typing import Optional

from app.schemas.parser import ContactInfo

# Regex patterns for contact fields
EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Phone: requires 10 to 13 digits with standard delimiters (+, -, ., spaces, parens)
PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}\b"
)

LINKEDIN_PATTERN = re.compile(
    r"(?:https?:\/\/)?(?:www\.)?linkedin\.com\/(?:in|pub)\/([A-Za-z0-9_\-\.]+)\/?",
    re.IGNORECASE,
)

GITHUB_PATTERN = re.compile(
    r"(?:https?:\/\/)?(?:www\.)?github\.com\/([A-Za-z0-9_\-]+)\/?",
    re.IGNORECASE,
)

PORTFOLIO_EXPLICIT_PATTERN = re.compile(
    r"(?:portfolio|website|site|homepage)\s*[:\-]\s*(https?:\/\/[^\s,]+|[A-Za-z0-9_\-\.]+\.(?:dev|me|io|com|org|net)(?:\/[^\s,]*)?)",
    re.IGNORECASE,
)

GENERIC_URL_PATTERN = re.compile(
    r"\bhttps?:\/\/(?!(?:www\.)?(?:linkedin\.com|github\.com|twitter\.com|facebook\.com|instagram\.com))[a-zA-Z0-9_\-\.]+\.[a-zA-Z]{2,}(?:\/[^\s,)]*)?",
    re.IGNORECASE,
)


def extract_email(text: str) -> Optional[str]:
    """Extract email address using conservative regex pattern."""
    matches = EMAIL_PATTERN.findall(text)
    if matches:
        # Return first valid email stripped of surrounding punctuation
        return matches[0].strip().rstrip(".")
    return None


def extract_phone(text: str) -> Optional[str]:
    """Extract telephone number with digit-count and repetition safeguards."""
    candidates = PHONE_PATTERN.findall(text)
    for candidate in candidates:
        digits = re.sub(r"\D", "", candidate)
        # Valid phone numbers typically have 10 to 13 digits
        if 10 <= len(digits) <= 13:
            # Reject sequences of identical digits (e.g., 0000000000)
            if len(set(digits)) <= 2:
                continue
            return candidate.strip()
    return None


def extract_linkedin(text: str) -> Optional[str]:
    """Extract and normalize LinkedIn URL."""
    match = LINKEDIN_PATTERN.search(text)
    if match:
        username = match.group(1).rstrip("/")
        # Filter out generic words
        if username.lower() not in {"in", "pub", "feed", "posts"}:
            return f"https://linkedin.com/in/{username}"
    return None


def extract_github(text: str) -> Optional[str]:
    """Extract and normalize GitHub profile URL."""
    match = GITHUB_PATTERN.search(text)
    if match:
        username = match.group(1).rstrip("/")
        # Filter out common GitHub top-level site pages
        if username.lower() not in {"topics", "features", "explore", "pricing", "login", "signup"}:
            return f"https://github.com/{username}"
    return None


def extract_portfolio(text: str) -> Optional[str]:
    """Extract personal website or portfolio URL."""
    # 1. Check explicit 'Portfolio: ...' prefix
    explicit_match = PORTFOLIO_EXPLICIT_PATTERN.search(text)
    if explicit_match:
        url = explicit_match.group(1).strip().rstrip(".,)")
        if not url.startswith("http"):
            url = f"https://{url}"
        return url

    # 2. Check general personal URLs that aren't social media
    generic_match = GENERIC_URL_PATTERN.search(text)
    if generic_match:
        return generic_match.group(0).strip().rstrip(".,)")

    return None


def extract_contact_info(text: str) -> ContactInfo:
    """Analyze text and extract structured contact details without logging PII."""
    return ContactInfo(
        email=extract_email(text),
        phone=extract_phone(text),
        linkedin_url=extract_linkedin(text),
        github_url=extract_github(text),
        portfolio_url=extract_portfolio(text),
    )
