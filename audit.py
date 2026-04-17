"""Website fetching and heuristic scoring."""
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

HTTP_TIMEOUT = 5
WAYBACK_TIMEOUT = 3

TEMPLATE_MARKERS = [
    "wix.com", "jimdo", "squarespace", "/offix.ch", "localsearch", "mywebsite",
]
PLACEHOLDER_PHRASES = ["coming soon", "hier entsteht", "under construction"]
BOOKING_MARKERS = [
    "opentable", "resmio", "lunchgate", "booksy", "treatwell", "calendly",
]
BOOKING_FORM_REGEX = re.compile(r"<form[^>]*reserv", re.IGNORECASE)
YEAR_REGEX = re.compile(r"\b(19|20)\d{2}\b")

UA = "Mozilla/5.0 (compatible; sme-prospecting/1.0; +https://example.com)"


def _template_signal(marker):
    clean = marker.replace("/", "").replace(".com", "").replace(".ch", "")
    return f"template:{clean}"


def audit_live_site(url):
    """Fetch site and return (score, status, signals)."""
    try:
        r = requests.get(
            url,
            timeout=HTTP_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": UA},
        )
    except Exception:
        return 35, "broken", ["fetch_failed"]

    if r.status_code >= 400:
        return 35, "broken", [f"http_{r.status_code}"]

    final_url = r.url or url
    html = r.text or ""
    html_lower = html.lower()

    signals = []
    score = 0

    if not final_url.lower().startswith("https://"):
        score += 10
        signals.append("no_https")

    soup = BeautifulSoup(html, "html.parser")
    viewport = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
    if not viewport:
        score += 15
        signals.append("no_viewport")

    current_year = datetime.now().year
    years = [int(m.group(0)) for m in YEAR_REGEX.finditer(html)]
    valid_years = [y for y in years if 1995 <= y <= current_year]
    if not valid_years or max(valid_years) < current_year - 2:
        score += 10
        signals.append("stale_copyright")

    for marker in TEMPLATE_MARKERS:
        if marker in html_lower:
            score += 10
            signals.append(_template_signal(marker))
            break

    text_content = soup.get_text(" ", strip=True).lower()
    for phrase in PLACEHOLDER_PHRASES:
        if phrase in text_content:
            score += 30
            signals.append("placeholder")
            return score, "placeholder", signals

    has_booking = any(m in html_lower for m in BOOKING_MARKERS) or bool(
        BOOKING_FORM_REGEX.search(html)
    )
    if not has_booking:
        score += 5
        signals.append("no_booking")

    return score, "live", signals


def check_wayback(url):
    """Return (score_delta, signals). Silent on timeout/error."""
    try:
        r = requests.get(
            "http://archive.org/wayback/available",
            params={"url": url},
            timeout=WAYBACK_TIMEOUT,
            headers={"User-Agent": UA},
        )
        data = r.json()
        snap = (data.get("archived_snapshots") or {}).get("closest") or {}
        ts = snap.get("timestamp")  # YYYYMMDDhhmmss
        if ts and len(ts) >= 4:
            year = int(ts[:4])
            if year < datetime.now().year - 3:
                return 10, ["stale_wayback"]
    except Exception:
        pass
    return 0, []


def _normalize_url(url):
    url = url.strip()
    if not url:
        return ""
    if not url.lower().startswith(("http://", "https://")):
        url = "http://" + url
    return url


def score_business(business):
    """Enrich business with score/status/signals keys."""
    website = (business.get("website") or "").strip()

    if not website:
        business["score"] = 40
        business["website_status"] = "missing"
        business["signals"] = ["no_website"]
        return business

    url = _normalize_url(website)
    score, status, signals = audit_live_site(url)

    if status == "live":
        wb_score, wb_signals = check_wayback(url)
        score += wb_score
        signals.extend(wb_signals)

    business["score"] = min(score, 100)
    business["website_status"] = status
    business["signals"] = signals
    return business
