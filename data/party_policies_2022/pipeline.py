from __future__ import annotations

import csv
import gzip
import hashlib
import json
import logging
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .config import (
    CDX_URL,
    DISCOVERY_TERMS,
    ELECTION_END,
    MAX_RETRIES,
    HISTORICAL_2022_PARTY_MAPPING,
    SOCIALDEMOCRATIET_HIGHLIGHTED_PRIORITIES,
    SOCIALDEMOCRATIET_2022_CAPTURE_OVERRIDES,
    ALTERNATIVET_HIGHLIGHTED_PRIORITIES,
    PARTIES,
    Party,
    PREFERRED_START,
    RADIKALE_VISION_THEMES,
    REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
    WAYBACK_URL,
)

TARGET_CAPTURE = datetime(2022, 10, 31)

PRESERVED_PARTY_SOURCE_METADATA = {
    "S": {
        "priority_section_url": "https://socialdemokratiet.dk/",
        "priority_section_heading": "Vores mærkesager",
        "manual_review_needed": False,
    },
    "V": {
        "priority_section_url": "https://www.venstre.dk/politik/maerkesager",
        "priority_section_heading": "Mærkesager",
        "manual_review_needed": False,
    },
}

def select_individual_snapshots(records: list[dict]) -> list[dict]:
    def distance(record: dict) -> tuple[float, str]:
        timestamp = str(record.get("timestamp", ""))
        try:
            captured = datetime.strptime(timestamp[:14], "%Y%m%d%H%M%S")
            seconds = abs((captured - TARGET_CAPTURE).total_seconds())
        except ValueError:
            seconds = float("inf")
        return seconds, timestamp

    return sorted(records, key=distance)

LOGGER = logging.getLogger("party_policies_2022")
ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "cache"
CDX_CACHE = CACHE_DIR / "cdx"
HTML_CACHE = CACHE_DIR / "html"
CHECKPOINT_DIR = CACHE_DIR / "checkpoints"
OUTPUT_DIR = ROOT / "output"

CSV_COLUMNS = (
    "party", "party_code", "document_type", "title", "original_url",
    "resolved_original_url",
    "archive_url", "snapshot_timestamp", "original_publication_date",
    "text", "text_length", "extraction_method", "validation_status",
    "review_status", "policy_relevance", "relevance_reason",
    "priority_category", "source_section_heading", "priority_order",
    "text_granularity",
    "priority_overview_archive_url", "priority_overview_snapshot_timestamp",
    "navigation_path", "homepage_archive_url",
    "homepage_snapshot_timestamp", "capture_gap_days", "capture_gap_status",
    "content_status",
)
SUPPLEMENTARY_COLUMNS = (
    "party", "party_code", "title", "text", "source_url",
    "archive_url", "snapshot_timestamp", "source_section_heading",
    "document_type",
)
EXCLUDED_COLUMNS = (
    "party", "party_code", "title", "original_url", "archive_url",
    "snapshot_timestamp", "text_length", "policy_relevance",
    "relevance_reason", "exclusion_reason", "text_excerpt",
    "navigation_path", "homepage_archive_url",
    "homepage_snapshot_timestamp", "capture_gap_days", "capture_gap_status",
)


def normalize_original_url(value: str, domain: str | None = None) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = unquote(value.strip())
    if value.startswith("//"):
        value = "https:" + value
    if value.startswith("/"):
        value = "https://" + (domain or "")
        value += value
    parsed = urlparse(value if "://" in value else "https://" + value)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if domain and host != domain.lower().removeprefix("www."):
        return None
    if parsed.scheme not in {"http", "https"} or not host:
        return None
    path = parsed.path or "/"
    if path.lower().endswith((
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".pdf",
        ".zip", ".mp4", ".mp3", ".css", ".js", ".xml",
    )):
        return None
    query = parsed.query
    return f"https://{host}{path.rstrip('/') or '/'}" + (f"?{query}" if query else "")


def timestamp_is_pre_election(timestamp: str) -> bool:
    return bool(timestamp and timestamp[:8] <= ELECTION_END)


def timestamp_is_preferred(timestamp: str) -> bool:
    return bool(timestamp and PREFERRED_START <= timestamp[:8] <= ELECTION_END)


def archive_url(timestamp: str, original_url: str) -> str:
    return WAYBACK_URL.format(
        timestamp=timestamp,
        original_url=quote(original_url, safe=":/?=&%#"),
    )


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def text_hash(value: str) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()


def page_type(title: str, url: str, text: str) -> tuple[str, str]:
    haystack = f"{title} {url} {text[:2500]}".casefold()
    if "valgprogram" in haystack or "valg 2022" in haystack or "valg2022" in haystack:
        return "election_programme", "programme_signal"
    if "partiprogram" in haystack:
        return "party_programme", "programme_signal"
    if "principprogram" in haystack:
        return "principle_programme", "programme_signal"
    if any(term in haystack for term in ("mærkesag", "maerkesag", "det-mener-vi")):
        return "policy_priorities", "priority_signal"
    if "udspil" in haystack:
        return "policy_proposal", "proposal_signal"
    return "general_policy_page", "content_review"


POLICY_TERMS = (
    "vi vil", "vi ønsker", "vi foreslår", "vores mål", "vores politik",
    "mærkesag", "maerkesag", "principprogram", "valgprogram", "partiprogram",
    "udspil", "forslag", "politik", "skal vi", "det mener vi",
)
POLICY_TOPIC_TERMS = (
    "klima", "sundhed", "skat", "uddannelse", "velfærd", "arbejde",
    "økonomi", "bolig", "energi", "forsvar", "integration", "retspolitik",
    "ældre", "landbrug", "miljø", "transport", "børn", "pension",
)
EXCLUSION_TERMS = (
    "rally", "valgmøde", "arrangement", "kontakt", "find politiker",
    "mød din politiker", "biografi", "kandidat", "pressemeddelelse",
    "nyhed", "kalender", "job", "bliv medlem", "log ind", "søg",
)


def classify_policy_relevance(title: str, url: str, text: str) -> tuple[str, str]:
    title_folded = normalize_text(title).casefold()
    url_folded = unquote(url).casefold()
    text_folded = normalize_text(text).casefold()
    combined = f"{title_folded} {url_folded}"
    content = text_folded[:5000]
    programme_signal = any(
        term in combined
        for term in ("valgprogram", "valg2022", "valg 2022", "partiprogram", "principprogram")
    )
    proposal_signal = "udspil" in combined or "forslag" in title_folded
    exclusion_hits = [term for term in EXCLUSION_TERMS if term in combined]
    policy_term_count = sum(term in combined or term in content for term in POLICY_TERMS)
    topic_count = sum(term in combined or term in content for term in POLICY_TOPIC_TERMS)
    substantial = len(text) >= 500 and (text.count("\n") >= 2 or len(text) >= 1200)

    if exclusion_hits and not programme_signal and not proposal_signal:
        return "low", f"non-policy page signal: {', '.join(exclusion_hits[:3])}"
    if programme_signal:
        return "high", "programme or manifesto signal"
    if proposal_signal and substantial:
        return "high", "concrete policy proposal with substantive text"
    if substantial and policy_term_count >= 2 and (topic_count >= 1 or len(text) >= 2500):
        return "high", "substantive policy language and issue/topic signals"
    if substantial and (policy_term_count >= 1 or topic_count >= 1):
        return "medium", "general or issue-specific policy content"
    if substantial:
        return "medium", "substantive page with uncertain policy classification"
    return "low", "short or unclear policy content"


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/json"})
    return session


def request_with_backoff(session: requests.Session, url: str, **kwargs) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
            if response.status_code in (403, 429):
                raise PermissionError(f"HTTP {response.status_code} access limit")
            response.raise_for_status()
            return response
        except (requests.RequestException, PermissionError) as exc:
            last_error = exc
            if isinstance(exc, PermissionError):
                raise
            if attempt < MAX_RETRIES:
                time.sleep(attempt * 2)
    raise RuntimeError(str(last_error))


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def cdx_records(session: requests.Session, party: Party, domain: str) -> list[dict]:
    cache_path = CDX_CACHE / f"{party.code}_{domain.replace('.', '_')}.json"
    cached = load_json(cache_path, None)
    if isinstance(cached, list):
        return cached
    params = {
        "url": f"{domain}/*",
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype,digest",
        "filter": "statuscode:200",
        "collapse": "urlkey",
        "filter": "statuscode:200",
    }
    response = request_with_backoff(session, CDX_URL, params=params)
    rows = response.json()
    if not rows:
        save_json(cache_path, [])
        return []
    headers, values = rows[0], rows[1:]
    records = [dict(zip(headers, row)) for row in values if len(row) == len(headers)]
    save_json(cache_path, records)
    time.sleep(REQUEST_DELAY_SECONDS)
    return records


def cdx_exact_records(
    session: requests.Session,
    party: Party,
    original_url: str,
) -> list[dict]:
    cache_path = CDX_CACHE / f"{party.code}_{hashlib.sha256(original_url.encode()).hexdigest()[:12]}.json"
    cached = load_json(cache_path, None)
    if isinstance(cached, list):
        return cached
    response = request_with_backoff(
        session,
        CDX_URL,
        params={
            "url": original_url,
            "output": "json",
            "fl": "timestamp,original,statuscode,mimetype,digest",
            "filter": "statuscode:200",
            "collapse": "timestamp:8",
        },
    )
    rows = response.json()
    if not rows:
        save_json(cache_path, [])
        return []
    headers, values = rows[0], rows[1:]
    records = [dict(zip(headers, row)) for row in values if len(row) == len(headers)]
    save_json(cache_path, records)
    time.sleep(REQUEST_DELAY_SECONDS)
    return records


def url_variants(original_url: str, aliases: tuple[str, ...] = ()) -> list[str]:
    if not aliases:
        return [original_url]
    parsed = urlparse(original_url)
    host = parsed.hostname or ""
    path = parsed.path or "/"
    base = f"https://{host}{path}"
    if parsed.query:
        base += f"?{parsed.query}"
    variants = [
        original_url,
        base.rstrip("/") or "https://" + host + "/",
        (base.rstrip("/") or "https://" + host) + "/",
        base.replace("https://", "http://", 1),
        base.replace("https://", "https://www.", 1),
        base.replace("https://", "http://www.", 1),
    ]
    for alias in aliases:
        variants.extend(url_variants(alias))
    return list(dict.fromkeys(variants))


def alias_urls(party: Party, original_url: str) -> tuple[str, ...]:
    normalized = normalize_original_url(original_url)
    for source, aliases in party.url_aliases:
        if normalize_original_url(source) == normalized:
            return aliases
    return ()


def candidate_urls(records: list[dict], domain: str) -> dict[str, list[dict]]:
    candidates: dict[str, list[dict]] = {}
    for record in records:
        original = normalize_original_url(record.get("original", ""), domain)
        timestamp = str(record.get("timestamp", ""))
        if not original or not timestamp_is_pre_election(timestamp):
            continue
        parsed = urlparse(original)
        path_terms = unquote(parsed.path).casefold()
        if any(term.casefold() in path_terms for term in DISCOVERY_TERMS):
            candidates.setdefault(original, []).append(record)
    return candidates


def homepage_records(records: list[dict], domain: str) -> list[dict]:
    homepage = normalize_original_url(f"https://{domain}/", domain)
    return [
        record for record in records
        if normalize_original_url(record.get("original", ""), domain) == homepage
        and timestamp_is_pre_election(str(record.get("timestamp", "")))
    ]


def candidate_score(url: str, snapshots: list[dict]) -> tuple[int, int, int, int]:
    path = unquote(urlparse(url).path).casefold()
    full_url = unquote(url).casefold()
    current_election_signal = int(any(
        term in full_url
        for term in ("2022", "valgprogram", "valgkamp", "valgudspil", "valg-politik")
    ))
    preferred = sum(
        timestamp_is_preferred(str(record.get("timestamp", "")))
        for record in snapshots
    )
    term_matches = sum(term.casefold() in path for term in DISCOVERY_TERMS)
    return current_election_signal, term_matches, preferred, -len(path)


def select_snapshots(records: list[dict], end_date: str = ELECTION_END) -> list[dict]:
    return sorted(
        (
            record for record in records
            if str(record.get("timestamp", ""))[:8] <= end_date
        ),
        key=lambda record: (
            timestamp_is_preferred(str(record.get("timestamp", ""))),
            str(record.get("timestamp", "")),
        ),
        reverse=True,
    )


def extract_structured_html(html: str) -> tuple[str, str, str, list[dict], str]:
    soup = BeautifulSoup(html, "html.parser")
    for selector in (
        "script", "style", "noscript", "nav", "footer", "header",
        "form", ".wayback-toolbar", "#wm-ipp", ".cookie", "[id*='cookie']",
        "[class*='cookie']", "[class*='navigation']", "[class*='menu']",
    ):
        for node in soup.select(selector):
            node.decompose()
    title = normalize_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    publication_date = ""
    for selector in (
        'meta[property="article:published_time"]',
        'meta[name="date"]',
        'meta[name="pubdate"]',
        'time[datetime]',
    ):
        node = soup.select_one(selector)
        value = (node.get("content") or node.get("datetime") or "").strip() if node else ""
        match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", value)
        if match:
            publication_date = match.group(1)
            break
    root = soup.select_one("main, article, [role='main']") or soup.body or soup
    blocks: list[str] = []
    links: list[dict] = []
    for node in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
        text = normalize_text(node.get_text(" ", strip=True))
        if text and len(text) > 1:
            prefix = f"{'#' * int(node.name[1:])} " if node.name.startswith("h") else "- " if node.name == "li" else ""
            blocks.append(prefix + text)
    for anchor in root.select("a[href]"):
        links.append({
            "href": anchor.get("href", ""),
            "text": normalize_text(anchor.get_text(" ", strip=True)),
            "title": normalize_text(anchor.get("title", "")),
        })
    text = "\n\n".join(blocks)
    method = "structured_headings_paragraphs_lists" if blocks else "empty"
    return title, text, method, links, publication_date


def clean_socialdemokratiet_text(text: str) -> str:
    """Remove repeated and shared webpage boilerplate while retaining policy text."""
    stop_markers = (
        "## apropos",
        "## vil du være med i fællesskabet",
        "### bliv gratis intromedlem",
        "som intromedlem af socialdemokratiet",
        "meld dig ind i dag",
        "gå til indmeldelse",
    )
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw_block in text.split("\n\n"):
        block = normalize_text(raw_block)
        if not block:
            continue
        block_fold = block.casefold()
        if any(marker in block_fold for marker in stop_markers):
            break
        if block_fold.startswith(("bliv medlem", "nyhedsbrev", "følg os", "kontakt", "cookie")):
            continue
        duplicate_key = normalize_text(re.sub(r"^[-*]\s*", "", block)).casefold()
        if duplicate_key in seen:
            continue
        seen.add(duplicate_key)
        cleaned.append(block)
    return "\n\n".join(cleaned)


def extract_socialdemokratiet_priority(html: str) -> tuple[str, str, str, str]:
    title, text, method, _, publication_date = extract_structured_html(html)
    cleaned = clean_socialdemokratiet_text(text)
    return title, cleaned, method, publication_date


def linked_internal_urls(
    original_url: str,
    hrefs: list[dict],
    domain: str,
) -> dict[str, str]:
    found: dict[str, str] = {}
    for link in hrefs:
        href = link.get("href", "")
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        candidate = normalize_original_url(urljoin(original_url, href), domain)
        if candidate:
            label = link.get("text") or link.get("title") or ""
            found.setdefault(candidate, label)
    return found


def _title_key(value: str) -> str:
    return re.sub(r"[^a-z0-9æøå]+", "", normalize_text(value).casefold())


def highlighted_priority_links(
    hrefs: list[dict],
    domain: str,
    expected_titles: tuple[str, ...] | None = None,
) -> list[dict]:
    """Return ordered links from an explicitly labelled priority section.

    The Socialdemokratiet ground-truth list is used only as a validation
    constraint for that party; other parties will require manual section
    identification rather than inferred inclusion.
    """
    expected = {_title_key(title): (index, title) for index, title in enumerate(expected_titles or ())}
    found = []
    for link in hrefs:
        label = normalize_text(link.get("text") or link.get("title") or "")
        key = _title_key(label)
        if expected and key in expected:
            order, title = expected[key]
            url = normalize_original_url(urljoin(f"https://{domain}/", link.get("href", "")), domain)
            if url:
                found.append({
                    "url": url,
                    "title": title,
                    "order": order + 1,
                    "section_heading": "Vores mærkesager",
                })
    return sorted(found, key=lambda item: item["order"])


def configured_priority_links(
    hrefs: list[dict],
    domain: str,
    titles: tuple[str, ...],
    urls: tuple[str, ...],
    section_heading: str = "Mærkesager",
) -> list[dict]:
    configured = {
        normalize_original_url(url, domain): (index, title)
        for index, (title, url) in enumerate(zip(titles, urls))
    }
    found = []
    for link in hrefs:
        url = normalize_original_url(
            urljoin(f"https://{domain}/", link.get("href", "")),
            domain,
        )
        if url not in configured:
            continue
        order, title = configured[url]
        found.append({
            "url": url,
            "title": title,
            "order": order + 1,
            "section_heading": section_heading,
        })
    return sorted(found, key=lambda item: item["order"])


def extract_df_main_content(html: str) -> tuple[str, str, str, list[dict]]:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main, #main, .post-content")
    if not main:
        return "", "", "df_main_content", []
    for selector in (
        "script", "style", "noscript", "nav", "footer", "header",
        ".wayback-toolbar", "#wm-ipp",
    ):
        for node in main.select(selector):
            node.decompose()
    title = normalize_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    text = normalize_text(main.get_text(" ", strip=True))
    hrefs = [
        {
            "href": link.get("href", ""),
            "text": normalize_text(link.get_text(" ", strip=True)),
            "title": normalize_text(link.get("title", "")),
        }
        for link in main.find_all("a", href=True)
    ]
    return title, text, "df_main_content", hrefs


def extract_enhedslisten_campaign_priority(
    html: str,
    priority_title: str,
) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("main.c-main-valg, main") or soup
    heading = next(
        (
            element for element in root.find_all(["h1", "h2"])
            if _title_key(element.get_text(" ", strip=True))
            == _title_key(priority_title)
        ),
        None,
    )
    if heading is None:
        return "", "", "enhedslisten_campaign_priority_missing_heading"
    elements = root.find_all(["h1", "h2", "h3", "h4", "h5", "p", "li"])
    start = elements.index(heading)
    blocks = []
    first_proposal_heading = next(
        (
            element for element in elements[start + 1:]
            if element.name == "h4"
            and element.get_text(" ", strip=True).casefold()
            == "det vil enhedslisten:"
        ),
        None,
    )
    if first_proposal_heading is not None:
        for intro in root.select("div.pol-content"):
            if heading in intro.find_all_previous(["h1", "h2"]) and (
                first_proposal_heading in intro.find_all_next(["h1", "h2", "h3", "h4", "h5"])
            ):
                intro_text = normalize_text(intro.get_text(" ", strip=True))
                if intro_text:
                    blocks.append(intro_text)
    skip_downloads = False
    for element in elements[start + 1:]:
        text = normalize_text(element.get_text(" ", strip=True))
        if element.name == "h5" and "del denne side" in text.casefold():
            break
        if not text:
            continue
        if element.name == "h4":
            skip_downloads = "download" in text.casefold()
            if skip_downloads:
                continue
            if text.casefold() == "det vil enhedslisten:":
                blocks.append("### " + text)
            continue
        if skip_downloads:
            continue
        if element.name == "p" and (
            text.startswith("http://")
            or text.startswith("https://")
            or text.casefold().startswith("læs mere")
        ):
            continue
        if element.name == "li":
            blocks.append("- " + text)
        elif element.name not in {"h1", "h2", "h3", "h5"}:
            blocks.append(text)
    text = "\n\n".join(dict.fromkeys(blocks))
    return (
        normalize_text(heading.get_text(" ", strip=True)),
        text,
        "enhedslisten_campaign_priority",
    )


def extract_alternativet_programme(
    html: str,
    expected_titles: tuple[str, ...],
) -> tuple[str, list[dict]]:
    soup = BeautifulSoup(html, "html.parser")
    expected = {
        _title_key(title): (index + 1, title)
        for index, title in enumerate(expected_titles)
    }
    programme_key = _title_key("Stien til det bæredygtige samfund")
    root = soup
    programme_heading = next(
        (
            heading for heading in root.find_all(["h1", "h2"])
            if (
                _title_key(heading.get_text(" ", strip=True)) == programme_key
                or _title_key(heading.get_text(" ", strip=True)).startswith(
                    "stientildet"
                )
            )
        ),
        None,
    )
    introduction = ""
    if programme_heading is not None:
        intro_container = programme_heading.find_parent(class_="col-sm-6")
        if intro_container:
            paragraphs = [
                normalize_text(node.get_text(" ", strip=True))
                for node in intro_container.find_all("p")
                if normalize_text(node.get_text(" ", strip=True))
            ]
            introduction = "\n\n".join(paragraphs)

    headings = [
        heading for heading in root.find_all(["h1", "h2"])
        if _title_key(heading.get_text(" ", strip=True)) in expected
    ]
    ordered_elements = root.find_all(["h1", "h2", "button"])
    records = []
    for position, heading in enumerate(headings):
        title = expected[_title_key(heading.get_text(" ", strip=True))][1]
        start = ordered_elements.index(heading)
        end = (
            ordered_elements.index(headings[position + 1])
            if position + 1 < len(headings)
            else len(ordered_elements)
        )
        section_elements = ordered_elements[start + 1:end]
        intro_container = heading.find_parent(class_="col-sm-6")
        blocks = []
        if intro_container:
            blocks.extend(
                normalize_text(node.get_text(" ", strip=True))
                for node in intro_container.find_all("p")
                if normalize_text(node.get_text(" ", strip=True))
            )
        missing_proposals = []
        proposal_count = 0
        for element in section_elements:
            if element.name != "button":
                continue
            proposal_count += 1
            proposal_title = normalize_text(element.get_text(" ", strip=True))
            panel = element.find_next_sibling(class_="panel-politics")
            blocks.append(f"## {proposal_title}")
            if not panel:
                missing_proposals.append(proposal_title)
                continue
            proposal_blocks = []
            for node in panel.find_all(["h2", "h3", "h4", "h5", "p", "li"]):
                text = normalize_text(node.get_text(" ", strip=True))
                if text:
                    proposal_blocks.append(("- " if node.name == "li" else "") + text)
            if proposal_blocks:
                blocks.append("\n\n".join(dict.fromkeys(proposal_blocks)))
            else:
                missing_proposals.append(proposal_title)
        records.append({
            "number": expected[_title_key(title)][0],
            "title": title,
            "text": "\n\n".join(dict.fromkeys(blocks)),
            "proposal_count": proposal_count,
            "missing_proposals": missing_proposals,
        })
    return introduction, sorted(records, key=lambda record: record["number"])


def extract_radikale_visions(
    html: str,
    source_url: str,
    expected_themes: tuple[tuple[str, tuple[str, ...]], ...],
) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    expected = []
    theme_by_title = {}
    for theme, titles in expected_themes:
        for title in titles:
            expected.append(title)
            theme_by_title[_title_key(title)] = theme
    expected_keys = {_title_key(title) for title in expected}
    headings = soup.find_all("h2")
    starts = []
    for index, heading in enumerate(headings):
        key = _title_key(heading.get_text(" ", strip=True))
        if key in expected_keys:
            starts.append((index, heading, heading.get_text(" ", strip=True)))
    records = []
    for position, (heading_index, heading, raw_title) in enumerate(starts):
        next_index = starts[position + 1][0] if position + 1 < len(starts) else len(headings)
        stop_heading = headings[next_index] if next_index < len(headings) else None
        blocks = [f"# {normalize_text(raw_title)}"]
        elements = soup.find_all(["h2", "h3", "h4", "p", "li"])
        start = elements.index(heading)
        end = len(elements)
        if stop_heading is not None:
            end = elements.index(stop_heading)
        for element in elements[start + 1:end]:
            if element.name == "h2" and normalize_text(element.get_text(" ", strip=True)).casefold() in {
                "vi mener", "kontakt", "følg os", "om radikale venstre",
            }:
                break
            text = normalize_text(element.get_text(" ", strip=True))
            if text and len(text) > 1:
                prefix = (
                    "### " if element.name == "h3"
                    else "#### " if element.name == "h4"
                    else "- " if element.name == "li"
                    else ""
                )
                blocks.append(prefix + text)
        title = next(title for title in expected if _title_key(title) == _title_key(raw_title))
        order = expected.index(title) + 1
        records.append({
            "title": title,
            "theme": theme_by_title[_title_key(title)],
            "order": order,
            "text": "\n\n".join(dict.fromkeys(blocks)),
            "original_url": f"{source_url}?vision={order}",
        })
    return records


def extract_nye_borgerlige_priorities(
    html: str,
    source_url: str,
) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    records_by_number = {}
    current_area = ""
    for heading in soup.find_all(["h6", "h4", "span"]):
        heading_text = normalize_text(heading.get_text(" ", strip=True))
        priority_match = re.match(r"^(\d{1,3})\.\s+(.+)$", heading_text)
        if heading.name == "h6":
            current_area = heading_text
            continue
        if heading.name == "span" and "fusion-toggle-heading" not in (heading.get("class") or []):
            continue
        if not priority_match:
            continue
        number = int(priority_match.group(1))
        panel = heading.find_parent(class_="fusion-panel")
        body = panel.find(class_="panel-body") if panel else None
        text_blocks = []
        if body:
            for node in body.find_all(["h5", "h6", "p", "li"]):
                text = normalize_text(node.get_text(" ", strip=True))
                if text:
                    text_blocks.append(("#" if node.name in {"h5", "h6"} else "- " if node.name == "li" else "") + text)
        explanatory_text = "\n\n".join(text_blocks)
        text = explanatory_text or priority_match.group(2)
        records_by_number[number] = {
            "number": number,
            "title": priority_match.group(2),
            "policy_area": current_area,
            "text": text,
            "text_granularity": (
                "substantive_explanatory_text" if explanatory_text else "title_only"
            ),
            "source_url": source_url,
        }
    return sorted(records_by_number.values(), key=lambda record: record["number"])


def extract_moderaterne_proposals(
    html: str,
    source_url: str,
    expected_titles: tuple[str, ...],
) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    expected = {_title_key(title): (index + 1, title) for index, title in enumerate(expected_titles)}
    records = []
    for header in soup.select(".eael-accordion-header"):
        raw_header = normalize_text(header.get_text(" ", strip=True))
        match = re.match(r"^(\d{1,2})\.\s+(.+)$", raw_header)
        if not match:
            continue
        number = int(match.group(1))
        key = _title_key(match.group(2))
        configured = expected.get(key)
        if configured is None or configured[0] != number:
            continue
        content_id = header.get("aria-controls")
        content = soup.find(id=content_id) if content_id else None
        text = normalize_text(content.get_text(" ", strip=True)) if content else ""
        records.append({
            "number": number,
            "title": configured[1],
            "text": text,
            "source_url": source_url,
            "text_granularity": "substantive_explanatory_text" if text else "missing",
        })
    return sorted(records, key=lambda record: record["number"])


def extract_danmarksdemokraterne_programme(
    html: str,
    source_url: str,
    expected_titles: tuple[str, ...],
) -> tuple[list[dict], list[dict]]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("main, #main, .post-content") or soup
    for selector in ("script", "style", "noscript", "nav", "footer", "header", ".wayback-toolbar", "#wm-ipp"):
        for node in root.select(selector):
            node.decompose()
    expected = {_title_key(title): (index + 1, title) for index, title in enumerate(expected_titles)}
    elements = root.find_all(["h2", "h3", "h4", "p", "li"])
    mains = []
    supplements = []
    main_headers = [
        (index, element)
        for index, element in enumerate(elements)
        if element.name == "h3" and _title_key(element.get_text(" ", strip=True)) in expected
    ]
    for position, (start, heading) in enumerate(main_headers):
        end = main_headers[position + 1][0] if position + 1 < len(main_headers) else len(elements)
        blocks = []
        for element in elements[start + 1:end]:
            if element.name in {"h2", "h3", "h4"}:
                continue
            text = normalize_text(element.get_text(" ", strip=True))
            if text:
                blocks.append(text)
        title = expected[_title_key(heading.get_text(" ", strip=True))][1]
        mains.append({
            "number": expected[_title_key(title)][0],
            "title": title,
            "text": "\n\n".join(dict.fromkeys(blocks)),
            "source_url": source_url,
        })
    supplement_heading = next(
        (
            index for index, element in enumerate(elements)
            if element.name == "h2"
            and _title_key(element.get_text(" ", strip=True)).startswith(
                _title_key("Vores politiske forslag")
            )
        ),
        None,
    )
    if supplement_heading is not None:
        proposal_headers = [
            (index, element)
            for index, element in enumerate(elements[supplement_heading + 1:], supplement_heading + 1)
            if element.name == "h4"
        ]
        for position, (start, heading) in enumerate(proposal_headers):
            end = proposal_headers[position + 1][0] if position + 1 < len(proposal_headers) else len(elements)
            blocks = []
            for element in elements[start + 1:end]:
                if element.name in {"h2", "h3", "h4"}:
                    continue
                text = normalize_text(element.get_text(" ", strip=True))
                if text:
                    blocks.append(text)
            supplements.append({
                "title": normalize_text(heading.get_text(" ", strip=True)),
                "text": "\n\n".join(dict.fromkeys(blocks)),
                "source_url": source_url,
                "source_section_heading": "Vores politiske forslag",
            })
    return sorted(mains, key=lambda record: record["number"]), supplements


def read_cached_html(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\x1f\x8b"):
        data = gzip.decompress(data)
    return data.decode("utf-8", errors="replace")


def load_cached_html_for_page(page: dict) -> str:
    archive = str(page["archive_url"])
    cache_path = HTML_CACHE / f"{hashlib.sha256((archive + '|utf8-v2').encode()).hexdigest()}.html"
    return read_cached_html(cache_path)


def policy_link_score(url: str, label: str) -> tuple[int, str]:
    signal = normalize_text(f"{label} {url}").casefold()
    path = unquote(urlparse(url).path).casefold()
    if any(term in path for term in (
        "politikere", "politiker", "kontakt", "om-os", "om-partiet",
        "presse", "nyheder", "arrangement", "kalender",
    )):
        return 0, "non-policy internal page"
    strong = (
        ("mærkesag" in signal or "maerkesag" in signal, "mærkesager"),
        ("vores politik" in signal or "vores-politik" in signal, "vores politik"),
        ("valgprogram" in signal or "valgprogram" in signal, "valgprogram"),
        ("partiprogram" in signal, "partiprogram"),
        ("principprogram" in signal, "principprogram"),
        ("politik" in signal, "politik"),
        ("udspil" in signal, "udspil"),
    )
    for matched, reason in strong:
        if matched:
            return 2, reason
    if any(term in signal for term in ("klima", "sundhed", "skat", "uddannelse", "velfærd")):
        return 1, "issue-specific policy link"
    return 0, "other internal link"


def overview_link_score(url: str, label: str) -> tuple[int, str]:
    signal = normalize_text(f"{label} {url}").casefold()
    path = unquote(urlparse(url).path).casefold()
    if any(term in path for term in (
        "politikere", "politiker", "kontakt", "presse", "nyheder",
        "arrangement", "kalender",
    )):
        return 0, "non-policy overview candidate"
    if any(term in signal for term in (
        "mærkesag", "maerkesag", "vores politik", "vores-politik",
        "det vil vi", "politik", "valgprogram", "partiprogram",
        "principprogram",
    )):
        return 2, "policy overview"
    return 0, "other link"


def explicit_priority_section(title: str, text: str, url: str) -> tuple[bool, str]:
    signal = normalize_text(f"{title} {url} {text[:5000]}").casefold()
    terms = (
        ("mærkesag", "explicit mærkesager section"),
        ("maerkesag", "explicit mærkesager section"),
        ("valgprogram", "explicit election programme section"),
        ("valgprogram", "explicit election programme section"),
        ("vores vigtigste", "explicit key-priorities section"),
        ("det vil vi", "explicit policy-priorities section"),
        ("key issues", "explicit key-issues section"),
    )
    for term, reason in terms:
        if term in signal:
            return True, reason
    return False, "no explicit priority-section signal"


def capture_gap_days(homepage_timestamp: str, page_timestamp: str) -> int | None:
    try:
        home = datetime.strptime(homepage_timestamp[:14], "%Y%m%d%H%M%S")
        page = datetime.strptime(page_timestamp[:14], "%Y%m%d%H%M%S")
    except (TypeError, ValueError):
        return None
    return abs((page.date() - home.date()).days)


def capture_gap_status(gap_days: int | None) -> str:
    if gap_days is None:
        return "unknown"
    if gap_days > 30:
        return "substantial_gap"
    return "small_gap"


def fetch_snapshot(
    session: requests.Session,
    original_url: str,
    records: list[dict],
    aliases: tuple[str, ...] = (),
    allow_any_capture_date: bool = False,
    capture_end: str = ELECTION_END,
) -> tuple[dict | None, str | None]:
    reasons = []
    candidate_records = list(records)
    known_originals = {str(record.get("original", "")) for record in candidate_records}
    for variant in url_variants(original_url, aliases):
        if variant in known_originals:
            continue
        try:
            variant_records = cdx_exact_records(
                session,
                Party("URL variant", "VAR", (urlparse(variant).hostname or "",)),
                variant,
            )
            candidate_records.extend(
                record for record in variant_records
                if allow_any_capture_date or str(record.get("timestamp", ""))[:8] <= capture_end
            )
        except Exception as exc:
            reasons.append(f"{variant}: {exc}")
    selected_records = (
        select_individual_snapshots(candidate_records)
        if allow_any_capture_date
        else select_snapshots(candidate_records, capture_end)
    )
    for record in selected_records:
        timestamp = str(record.get("timestamp", ""))
        resolved_original_url = normalize_original_url(str(record.get("original", ""))) or original_url
        url = archive_url(timestamp, resolved_original_url)
        cache_path = HTML_CACHE / f"{hashlib.sha256((url + '|utf8-v2').encode()).hexdigest()}.html"
        try:
            if cache_path.exists():
                html = read_cached_html(cache_path)
            else:
                response = request_with_backoff(session, url)
                response.encoding = "utf-8"
                html = response.text
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(html, encoding="utf-8")
                time.sleep(REQUEST_DELAY_SECONDS)
            title, text, method, hrefs, publication_date = extract_structured_html(html)
            if len(text) < 120 and "danskfolkeparti.dk" in original_url:
                title, text, method, hrefs = extract_df_main_content(html)
            if len(text) < 120 and "danmarksdemokraterne.dk" in original_url:
                raw_soup = BeautifulSoup(html, "html.parser")
                title = normalize_text(
                    raw_soup.title.get_text(" ", strip=True)
                    if raw_soup.title else ""
                )
                text = normalize_text(raw_soup.get_text(" ", strip=True))
                method = "raw_page_snapshot"
                hrefs = [
                    {
                        "href": link.get("href", ""),
                        "text": normalize_text(link.get_text(" ", strip=True)),
                        "title": normalize_text(link.get("title", "")),
                    }
                    for link in raw_soup.find_all("a", href=True)
                ]
            if len(text) < 120:
                reasons.append(f"{timestamp}: insufficient text ({len(text)} chars)")
                continue
            if "wayback machine" in text.casefold() and len(text) < 500:
                reasons.append(f"{timestamp}: archive boilerplate")
                continue
            return ({
                "timestamp": timestamp,
                "archive_url": url,
                "resolved_original_url": resolved_original_url,
                "title": title,
                "text": text,
                "text_length": len(text),
                "extraction_method": method,
                "hrefs": hrefs,
                "original_publication_date": publication_date,
                "temporal_status": (
                    "preferred_pre_election"
                    if timestamp_is_preferred(timestamp)
                    else (
                        "individual_policy_capture_any_date"
                        if allow_any_capture_date
                        else "earlier_pre_election_uncertain"
                    )
                ),
            }, None)
        except (OSError, RuntimeError, requests.RequestException, PermissionError) as exc:
            reasons.append(f"{timestamp}: {exc}")
    return None, "; ".join(reasons) or "no usable pre-election snapshot"


def add_navigation_links(
    source_url: str,
    source_page: dict,
    domain: str,
    discovered: dict[str, list[dict]],
    navigation: dict[str, dict],
    reason: str,
) -> None:
    for linked_url, label in linked_internal_urls(
        source_url,
        source_page["hrefs"],
        domain,
    ).items():
        score, link_reason = policy_link_score(linked_url, label)
        if score:
            discovered.setdefault(linked_url, [])
            navigation.setdefault(linked_url, {
                "path": f"{source_page.get('original_url', source_url)} -> {label or linked_url}",
                "homepage_archive_url": navigation.get(source_url, {}).get(
                    "homepage_archive_url",
                    source_page.get("archive_url", ""),
                ),
                "homepage_snapshot_timestamp": navigation.get(source_url, {}).get(
                    "homepage_snapshot_timestamp",
                    source_page.get("timestamp", ""),
                ),
                "link_reason": f"{reason}: {link_reason}",
                "overview_source_url": source_url,
            })


def run_party(session: requests.Session, party: Party, max_pages: int | None, dry_run: bool) -> tuple[list[dict], list[dict], list[dict], dict]:
    discovered: dict[str, list[dict]] = {}
    navigation: dict[str, dict] = {}
    errors: list[dict] = []
    all_records_by_domain: dict[str, list[dict]] = {}
    direct_pages: dict[str, dict] = {}
    coverage = {
        "homepage_archive_url": "",
        "homepage_snapshot_timestamp": "",
        "priority_section_url": "",
        "priority_section_heading": "",
        "manual_review_needed": bool(not party.highlighted_priorities),
    }
    for domain in party.domains:
        try:
            homepage_url = normalize_original_url(
                f"https://{domain}/parti/" if party.code == "DD" else f"https://{domain}/",
                domain,
            )
            home_records = []
            homepage_candidates = (
                (
                    f"https://{domain}/parti/",
                    f"http://{domain}/parti/",
                    f"https://www.{domain}/parti/",
                    f"http://www.{domain}/parti/",
                )
                if party.code == "DD"
                else (
                    f"https://{domain}/",
                    f"http://{domain}/",
                    f"https://www.{domain}/",
                    f"http://www.{domain}/",
                )
            )
            for homepage_candidate in homepage_candidates:
                exact = cdx_exact_records(session, party, homepage_candidate)
                home_records.extend(
                    record for record in exact
                    if str(record.get("timestamp", ""))[:8] <= party.homepage_capture_end
                )
            home_records = list({
                (record.get("timestamp"), record.get("original")): record
                for record in home_records
            }.values())
        except Exception as exc:
            errors.append({"party": party.name, "stage": "cdx", "domain": domain, "error": str(exc)})
            continue
        home_page = None
        if home_records and not dry_run:
            home_page, reason = fetch_snapshot(
                session,
                homepage_url,
                home_records,
                capture_end=party.homepage_capture_end,
            )
            if not home_page and party.code not in {"NB", "DD"}:
                errors.append({
                    "party": party.name,
                    "original_url": homepage_url,
                    "stage": "homepage",
                    "error": reason,
                })
        if party.code == "NB" and not home_page and home_records and not dry_run:
            homepage_record = sorted(
                home_records,
                key=lambda record: str(record.get("timestamp", "")),
                reverse=True,
            )[0]
            homepage_timestamp = str(homepage_record.get("timestamp", ""))
            homepage_original = normalize_original_url(
                str(homepage_record.get("original", "")),
                domain,
            ) or homepage_url
            home_page = {
                "timestamp": homepage_timestamp,
                "archive_url": archive_url(homepage_timestamp, homepage_original),
                "resolved_original_url": homepage_original,
                "title": "Nye Borgerlige homepage",
                "text": "",
                "text_length": 0,
                "extraction_method": "homepage_metadata_only",
                "hrefs": [],
                "original_publication_date": "",
                "temporal_status": "homepage_metadata_only",
            }
        if party.code == "DF" and home_records and not dry_run:
            homepage_record = next(
                (
                    record for record in home_records
                    if str(record.get("timestamp", "")).startswith("20221102")
                ),
                select_snapshots(home_records, party.homepage_capture_end)[0],
            )
            homepage_timestamp = str(homepage_record.get("timestamp", ""))
            homepage_original = normalize_original_url(
                str(homepage_record.get("original", "")),
                domain,
            ) or homepage_url
            raw_archive_url = archive_url(homepage_timestamp, homepage_original)
            cache_path = HTML_CACHE / (
                f"{hashlib.sha256((raw_archive_url + '|utf8-v2').encode()).hexdigest()}.html"
            )
            if cache_path.exists():
                raw_html = cache_path.read_text(encoding="utf-8")
            else:
                response = request_with_backoff(session, raw_archive_url)
                response.encoding = "utf-8"
                raw_html = response.text
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(raw_html, encoding="utf-8")
            raw_soup = BeautifulSoup(raw_html, "html.parser")
            home_page = {
                "timestamp": homepage_timestamp,
                "archive_url": raw_archive_url,
                "resolved_original_url": homepage_original,
                "title": "Dansk Folkeparti – Mærkesager",
                "text": normalize_text(raw_soup.get_text(" ", strip=True)),
                "text_length": len(raw_soup.get_text(" ", strip=True)),
                "extraction_method": "raw_homepage_snapshot",
                "hrefs": [
                    {
                        "href": link.get("href", ""),
                        "text": normalize_text(link.get_text(" ", strip=True)),
                        "title": normalize_text(link.get("title", "")),
                    }
                    for link in raw_soup.find_all("a", href=True)
                ],
                "original_publication_date": "",
                "temporal_status": "preferred_pre_election",
            }
        if party.code == "DD" and home_records and not dry_run:
            homepage_record = sorted(
                home_records,
                key=lambda record: str(record.get("timestamp", "")),
                reverse=True,
            )[0]
            homepage_timestamp = str(homepage_record.get("timestamp", ""))
            homepage_original = normalize_original_url(
                str(homepage_record.get("original", "")),
                domain,
            ) or homepage_url
            raw_archive_url = archive_url(homepage_timestamp, homepage_original)
            cache_path = HTML_CACHE / (
                f"{hashlib.sha256((raw_archive_url + '|utf8-v2').encode()).hexdigest()}.html"
            )
            if cache_path.exists():
                raw_html = cache_path.read_text(encoding="utf-8")
            else:
                response = request_with_backoff(session, raw_archive_url)
                response.encoding = "utf-8"
                raw_html = response.text
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(raw_html, encoding="utf-8")
            raw_soup = BeautifulSoup(raw_html, "html.parser")
            raw_text = normalize_text(raw_soup.get_text(" ", strip=True))
            home_page = {
                "timestamp": homepage_timestamp,
                "archive_url": raw_archive_url,
                "resolved_original_url": homepage_original,
                "title": "Danmarksdemokraterne – Parti",
                "text": raw_text,
                "text_length": len(raw_text),
                "extraction_method": "raw_homepage_snapshot",
                "hrefs": [
                    {
                        "href": link.get("href", ""),
                        "text": normalize_text(link.get_text(" ", strip=True)),
                        "title": normalize_text(link.get("title", "")),
                    }
                    for link in raw_soup.find_all("a", href=True)
                ],
                "original_publication_date": "",
                "temporal_status": "preferred_pre_election",
            }
        if home_page:
            home_archive = home_page["archive_url"]
            home_timestamp = home_page["timestamp"]
            coverage["homepage_archive_url"] = home_archive
            coverage["homepage_snapshot_timestamp"] = home_timestamp
            if party.code == "S":
                checkpoint = load_json(CHECKPOINT_DIR / "S.json", {})
                existing_rows = {
                    str(row["priority_order"]): row
                    for row in checkpoint.get("rows", [])
                }
                discovered = {}
                direct_pages = {}
                for index, title in enumerate(
                    SOCIALDEMOCRATIET_HIGHLIGHTED_PRIORITIES,
                    start=1,
                ):
                    key = str(index)
                    existing = existing_rows.get(key, {})
                    original_url = str(existing.get("original_url", "")).strip()
                    if not original_url:
                        original_url = normalize_original_url(
                            f"https://socialdemokratiet.dk/det-vil-vi/{'klima-og-miljoe' if index == 12 else 'priority'}",
                            domain,
                        )
                    override = SOCIALDEMOCRATIET_2022_CAPTURE_OVERRIDES.get(key)
                    archive = str(existing.get("archive_url", "")).strip()
                    timestamp = str(existing.get("snapshot_timestamp", "")).strip()
                    text = str(existing.get("text", "")).strip()
                    validation_status = "post_election_capture_unverified"
                    review_status = "historical_text_unverified"
                    source_kind = "existing_post_election_capture"
                    if override:
                        stamp, override_url, capture_kind = override
                        override_archive = archive_url(stamp, override_url)
                        cache_path = HTML_CACHE / (
                            f"{hashlib.sha256((override_archive + '|utf8-v2').encode()).hexdigest()}.html"
                        )
                        if cache_path.exists():
                            html = read_cached_html(cache_path)
                            _, cleaned, _, _ = extract_socialdemokratiet_priority(html)
                            if cleaned:
                                archive = override_archive
                                timestamp = stamp
                                text = cleaned
                                source_kind = capture_kind
                                if capture_kind == "pre_election_verified":
                                    validation_status = "preferred_pre_election"
                                    review_status = "historical_text_verified_pre_election"
                                else:
                                    validation_status = "post_election_near_capture"
                                    review_status = "historical_text_supported_post_election"
                    if not override or not text:
                        existing_cache = None
                        if archive:
                            existing_cache = HTML_CACHE / (
                                f"{hashlib.sha256((archive + '|utf8-v2').encode()).hexdigest()}.html"
                            )
                        if existing_cache and existing_cache.exists():
                            html = read_cached_html(existing_cache)
                            _, cleaned, _, _ = extract_socialdemokratiet_priority(html)
                            if cleaned:
                                text = cleaned
                    text = clean_socialdemokratiet_text(text)
                    discovered[original_url] = [home_page]
                    navigation[original_url] = {
                        "path": f"{homepage_url} -> Vores mærkesager -> {title}",
                        "homepage_archive_url": home_archive,
                        "homepage_snapshot_timestamp": home_timestamp,
                        "link_reason": "manually verified 2022 homepage priority",
                        "overview_source_url": homepage_url,
                        "link_label": title,
                        "priority_category": "highlighted_priority",
                        "source_section_heading": "Vores mærkesager",
                        "priority_order": index,
                        "text_granularity": "substantive_explanatory_text",
                        "historical_source_kind": source_kind,
                    }
                    direct_pages[original_url] = {
                        **home_page,
                        "title": title,
                        "text": text,
                        "text_length": len(text),
                        "extraction_method": "socialdemokratiet_homepage_priority",
                        "archive_url": archive,
                        "timestamp": timestamp,
                        "resolved_original_url": (
                            override[1] if override and override[2] != "post_election_near_capture"
                            else str(existing.get("resolved_original_url", original_url))
                        ),
                        "temporal_status": validation_status,
                        "review_status": review_status,
                        "document_type": "general_policy_page",
                        "content_status": "extracted" if text else "missing",
                    }
                coverage["priority_section_url"] = homepage_url
                coverage["priority_section_heading"] = "Vores mærkesager"
                coverage["manual_review_needed"] = any(
                    navigation[url].get("historical_source_kind")
                    not in {"pre_election_verified", "post_election_near_capture"}
                    for url in discovered
                )
            homepage_links = linked_internal_urls(
                homepage_url,
                home_page["hrefs"],
                domain,
            )
            highlighted = highlighted_priority_links(
                home_page["hrefs"],
                domain,
                party.highlighted_priorities,
            )
            if party.highlighted_priority_urls:
                highlighted = configured_priority_links(
                    home_page["hrefs"],
                    domain,
                    party.highlighted_priorities,
                    party.highlighted_priority_urls,
                    "Læs hvad SF kæmper for" if party.code == "SF" else "Mærkesager",
                )
                if party.code == "SF":
                    coverage["priority_section_url"] = homepage_url
                    coverage["priority_section_heading"] = "Læs hvad SF kæmper for"
                    coverage["manual_review_needed"] = False
                elif party.code == "DF":
                    coverage["priority_section_url"] = homepage_url
                    coverage["priority_section_heading"] = "Mærkesager"
                    coverage["manual_review_needed"] = False
                elif party.code == "EL":
                    coverage["priority_section_url"] = homepage_url
                    coverage["priority_section_heading"] = "Enhedslisten valgkamp 2022"
                    coverage["manual_review_needed"] = len(highlighted) != 4
            priority_source_url = homepage_url
            priority_source_archive = home_archive
            if party.code == "ALT":
                highlighted = [
                    {
                        "url": normalize_original_url(
                            f"{homepage_url}?priority={index}",
                            domain,
                        ),
                        "title": title,
                        "order": index,
                        "section_heading": "Stien til det bæredygtige samfund",
                    }
                    for index, title in enumerate(
                        ALTERNATIVET_HIGHLIGHTED_PRIORITIES,
                        start=1,
                    )
                ]
                introduction, programme_records = extract_alternativet_programme(
                    load_cached_html_for_page(home_page),
                    ALTERNATIVET_HIGHLIGHTED_PRIORITIES,
                )
                coverage["priority_section_url"] = homepage_url
                coverage["priority_section_heading"] = (
                    "Stien til det bæredygtige samfund"
                )
                coverage["manual_review_needed"] = (
                    len(programme_records) != 4
                    or any(
                        not record["text"] or record["missing_proposals"]
                        for record in programme_records
                    )
                )
                coverage["supplementary_records"] = [{
                    "party": party.name,
                    "party_code": party.code,
                    "title": "Stien til det bæredygtige samfund",
                    "text": introduction,
                    "source_url": homepage_url,
                    "archive_url": home_archive,
                    "snapshot_timestamp": home_timestamp,
                    "source_section_heading": "Stien til det bæredygtige samfund",
                    "document_type": "contextual_election_programme",
                }]
                for record in programme_records:
                    synthetic_url = normalize_original_url(
                        f"{homepage_url}?priority={record['number']}",
                        domain,
                    )
                    discovered[synthetic_url] = [home_page]
                    navigation[synthetic_url] = {
                        "path": (
                            f"{homepage_url} -> Stien til det bæredygtige samfund"
                            f" -> {record['number']}. {record['title']}"
                        ),
                        "homepage_archive_url": home_archive,
                        "homepage_snapshot_timestamp": home_timestamp,
                        "link_reason": "section in archived election programme",
                        "overview_source_url": homepage_url,
                        "link_label": record["title"],
                        "priority_category": "highlighted_priority",
                        "source_section_heading": (
                            "Stien til det bæredygtige samfund"
                        ),
                        "priority_order": record["number"],
                        "text_granularity": "substantive_explanatory_text",
                    }
                    direct_pages[synthetic_url] = {
                        **home_page,
                        "title": record["title"],
                        "text": record["text"],
                        "text_length": len(record["text"]),
                        "extraction_method": "alternativet_election_programme_section",
                        "resolved_original_url": homepage_url,
                        "document_type": "election_campaign_priority",
                    }
            if party.priority_overview_paths:
                for overview_path in party.priority_overview_paths:
                    overview_url = normalize_original_url(overview_path, domain)
                    if not overview_url:
                        continue
                    overview_records = [
                        record for record in cdx_exact_records(session, party, overview_url)
                        if timestamp_is_pre_election(str(record.get("timestamp", "")))
                    ]
                    overview_page, overview_reason = fetch_snapshot(
                        session, overview_url, overview_records,
                    )
                    if not overview_page and party.code == "NB" and overview_records:
                        record = select_snapshots(overview_records)[0]
                        timestamp = str(record.get("timestamp", ""))
                        resolved_url = normalize_original_url(
                            str(record.get("original", "")),
                            domain,
                        ) or overview_url
                        raw_archive_url = archive_url(timestamp, resolved_url)
                        cache_path = HTML_CACHE / (
                            f"{hashlib.sha256((raw_archive_url + '|utf8-v2').encode()).hexdigest()}.html"
                        )
                        if cache_path.exists():
                            raw_html = cache_path.read_text(encoding="utf-8")
                        else:
                            response = request_with_backoff(session, raw_archive_url)
                            response.encoding = "utf-8"
                            raw_html = response.text
                            cache_path.parent.mkdir(parents=True, exist_ok=True)
                            cache_path.write_text(raw_html, encoding="utf-8")
                        overview_page = {
                            "timestamp": timestamp,
                            "archive_url": raw_archive_url,
                            "resolved_original_url": resolved_url,
                            "title": "Valgoplæg - 100 borgerlige mærkesager",
                            "text": "",
                            "text_length": 0,
                            "extraction_method": "raw_programme_snapshot",
                            "hrefs": [],
                            "original_publication_date": "",
                            "temporal_status": "preferred_pre_election",
                            "raw_html": raw_html,
                        }
                    if overview_page:
                        highlighted = highlighted_priority_links(
                            overview_page["hrefs"],
                            domain,
                            party.highlighted_priorities,
                        )
                        if party.highlighted_priority_urls:
                            highlighted = configured_priority_links(
                                overview_page["hrefs"],
                                domain,
                                party.highlighted_priorities,
                                party.highlighted_priority_urls,
                            )
                        priority_source_url = overview_url
                        priority_source_archive = overview_page["archive_url"]
                        coverage["priority_section_url"] = overview_url
                        coverage["priority_section_heading"] = overview_page["title"]
                        break
                    errors.append({
                        "party": party.name,
                        "original_url": overview_url,
                        "stage": "highlighted_priority_overview",
                        "error": overview_reason,
                    })
            if party.code == "RV" and overview_page:
                # The programme is the complete priority source; do not
                # treat its incidental links as separate policy pages.
                highlighted = []
                vision_records = extract_radikale_visions(
                    load_cached_html_for_page(overview_page),
                    priority_source_url,
                    RADIKALE_VISION_THEMES,
                )
                for vision in vision_records:
                    synthetic_url = normalize_original_url(vision["original_url"], domain)
                    discovered[synthetic_url] = [overview_page]
                    navigation[synthetic_url] = {
                        "path": (
                            f"{homepage_url} -> {priority_source_url} -> "
                            f"{vision['theme']} -> {vision['title']}"
                        ),
                        "homepage_archive_url": home_archive,
                        "homepage_snapshot_timestamp": home_timestamp,
                        "link_reason": "vision section in election programme",
                        "overview_source_url": priority_source_url,
                        "overview_title": overview_page["title"],
                        "link_label": vision["title"],
                        "priority_category": "highlighted_priority",
                        "source_section_heading": vision["theme"],
                        "priority_order": vision["order"],
                    }
                    direct_pages[synthetic_url] = {
                        **overview_page,
                        "title": vision["title"],
                        "text": vision["text"],
                        "text_length": len(vision["text"]),
                        "extraction_method": "programme_vision_section",
                        "resolved_original_url": priority_source_url,
                        "archive_url": overview_page["archive_url"],
                        "timestamp": overview_page["timestamp"],
                        "temporal_status": "preferred_pre_election",
                        "document_type": "election_programme",
                    }
                coverage["manual_review_needed"] = len(vision_records) != sum(
                    len(titles) for _, titles in RADIKALE_VISION_THEMES
                )
            if party.code == "NB" and overview_page:
                highlighted = []
                priority_records = extract_nye_borgerlige_priorities(
                    load_cached_html_for_page(overview_page),
                    priority_source_url,
                )
                for priority in priority_records:
                    synthetic_url = normalize_original_url(
                        f"{priority_source_url}?priority={priority['number']}",
                        domain,
                    )
                    discovered[synthetic_url] = [overview_page]
                    navigation[synthetic_url] = {
                        "path": (
                            f"{homepage_url} -> {priority_source_url} -> "
                            f"{priority['policy_area']} -> {priority['number']:02d}. "
                            f"{priority['title']}"
                        ),
                        "homepage_archive_url": home_archive,
                        "homepage_snapshot_timestamp": home_timestamp,
                        "link_reason": "numbered priority in election programme",
                        "overview_source_url": priority_source_url,
                        "overview_archive_url": overview_page["archive_url"],
                        "link_label": priority["title"],
                        "priority_category": "highlighted_priority",
                        "source_section_heading": priority["policy_area"],
                        "priority_order": priority["number"],
                        "text_granularity": priority["text_granularity"],
                    }
                    direct_pages[synthetic_url] = {
                        **overview_page,
                        "title": priority["title"],
                        "text": priority["text"],
                        "text_length": len(priority["text"]),
                        "extraction_method": "numbered_programme_priority",
                        "resolved_original_url": priority_source_url,
                        "document_type": "election_programme",
                    }
                coverage["manual_review_needed"] = len(priority_records) != 100
            if party.code == "M" and overview_page:
                highlighted = []
                proposal_records = extract_moderaterne_proposals(
                    load_cached_html_for_page(overview_page),
                    priority_source_url,
                    party.highlighted_priorities,
                )
                for proposal in proposal_records:
                    synthetic_url = normalize_original_url(
                        f"{priority_source_url}?proposal={proposal['number']}",
                        domain,
                    )
                    discovered[synthetic_url] = [overview_page]
                    navigation[synthetic_url] = {
                        "path": (
                            f"{homepage_url} -> {priority_source_url} -> "
                            f"{proposal['number']}. {proposal['title']}"
                        ),
                        "homepage_archive_url": home_archive,
                        "homepage_snapshot_timestamp": home_timestamp,
                        "link_reason": "numbered proposal section in policy overview",
                        "overview_source_url": priority_source_url,
                        "overview_archive_url": overview_page["archive_url"],
                        "overview_snapshot_timestamp": overview_page["timestamp"],
                        "link_label": proposal["title"],
                        "priority_category": "highlighted_priority",
                        "source_section_heading": "11 MODERATE FORSLAG",
                        "priority_order": proposal["number"],
                        "text_granularity": proposal["text_granularity"],
                    }
                    direct_pages[synthetic_url] = {
                        **overview_page,
                        "title": proposal["title"],
                        "text": proposal["text"],
                        "text_length": len(proposal["text"]),
                        "extraction_method": "moderaterne_numbered_proposal",
                        "resolved_original_url": priority_source_url,
                        "document_type": "policy_proposals",
                    }
                coverage["priority_section_url"] = priority_source_url
                coverage["priority_section_heading"] = "11 MODERATE FORSLAG"
                coverage["manual_review_needed"] = len(proposal_records) != 11
            if party.code == "DD" and overview_page:
                highlighted = []
                main_records, supplementary_records = extract_danmarksdemokraterne_programme(
                    load_cached_html_for_page(overview_page),
                    priority_source_url,
                    party.highlighted_priorities,
                )
                coverage["priority_section_url"] = priority_source_url
                coverage["priority_section_heading"] = "Vores politik"
                coverage["manual_review_needed"] = len(main_records) != 4 or any(
                    not record["text"] for record in main_records
                )
                for main in main_records:
                    synthetic_url = normalize_original_url(
                        f"{priority_source_url}?priority={main['number']}",
                        domain,
                    )
                    discovered[synthetic_url] = [overview_page]
                    navigation[synthetic_url] = {
                        "path": (
                            f"{homepage_url} -> {priority_source_url} -> "
                            f"{main['number']}. {main['title']}"
                        ),
                        "homepage_archive_url": home_archive,
                        "homepage_snapshot_timestamp": home_timestamp,
                        "link_reason": "main priority section in political programme",
                        "overview_source_url": priority_source_url,
                        "overview_archive_url": overview_page["archive_url"],
                        "overview_snapshot_timestamp": overview_page["timestamp"],
                        "link_label": main["title"],
                        "priority_category": "highlighted_priority",
                        "source_section_heading": "Vores politik",
                        "priority_order": main["number"],
                        "text_granularity": "substantive_explanatory_text" if main["text"] else "missing",
                    }
                    direct_pages[synthetic_url] = {
                        **overview_page,
                        "title": main["title"],
                        "text": main["text"],
                        "text_length": len(main["text"]),
                        "extraction_method": "dd_programme_main_priority",
                        "resolved_original_url": priority_source_url,
                        "document_type": "political_programme",
                    }
                coverage["supplementary_records"] = [
                    {
                        "party": party.name,
                        "party_code": party.code,
                        "title": item["title"],
                        "text": item["text"],
                        "source_url": item["source_url"],
                        "archive_url": overview_page["archive_url"],
                        "snapshot_timestamp": overview_page["timestamp"],
                        "source_section_heading": item["source_section_heading"],
                        "document_type": "supplementary_political_proposal",
                    }
                    for item in supplementary_records
                ]
            if party.code == "EL":
                for item in highlighted:
                    discovered[item["url"]] = []
                    navigation[item["url"]] = {
                        "path": f"{homepage_url} -> {item['title']}",
                        "homepage_archive_url": home_archive,
                        "homepage_snapshot_timestamp": home_timestamp,
                        "link_reason": "explicit election priority on archived homepage",
                        "overview_source_url": homepage_url,
                        "link_label": item["title"],
                        "priority_category": "highlighted_priority",
                        "source_section_heading": "Enhedslisten valgkamp 2022",
                        "priority_order": item["order"],
                        "text_granularity": "substantive_explanatory_text",
                    }
            if party.code == "LA":
                for item in highlighted:
                    item["section_heading"] = (
                        "MÆRKESAGER" if item["order"] == 5 else "Det kæmper vi for"
                    )
                coverage["manual_review_needed"] = len(highlighted) != 5
            for item in highlighted:
                discovered.setdefault(item["url"], [])
                navigation.setdefault(item["url"], {
                    "path": f"{homepage_url} -> {priority_source_url} -> {item['title']}",
                    "homepage_archive_url": home_archive,
                    "homepage_snapshot_timestamp": home_timestamp,
                    "link_reason": "explicit highlighted priority",
                    "overview_source_url": priority_source_url,
                    "overview_archive_url": priority_source_archive,
                    "overview_snapshot_timestamp": (
                        overview_page.get("timestamp", "")
                        if priority_source_url != homepage_url and overview_page
                        else ""
                    ),
                    "link_label": item["title"],
                    "priority_category": "highlighted_priority",
                    "source_section_heading": item["section_heading"],
                    "priority_order": item["order"],
                })

            # Fetch the archived policy overview itself and follow every
            # policy link it displays. Its links define the inclusion scope.
            overview_candidates = [] if (
                party.code == "DD"
                or (party.highlighted_priorities and party.code != "DD")
                or party.code in {"RV", "NB"}
            ) else [
                (url, label)
                for url, label in linked_internal_urls(
                    homepage_url,
                    home_page["hrefs"],
                    domain,
                ).items()
                if overview_link_score(url, label)[0]
            ]
            for overview_url, overview_label in overview_candidates:
                overview_records = [
                    record for record in cdx_exact_records(
                        session,
                        party,
                        overview_url,
                    )
                    if timestamp_is_pre_election(str(record.get("timestamp", "")))
                ]
                overview_page, overview_reason = fetch_snapshot(
                    session,
                    overview_url,
                    overview_records,
                )
                if not overview_page:
                    errors.append({
                        "party": party.name,
                        "original_url": overview_url,
                        "stage": "policy_overview",
                        "error": overview_reason,
                    })
                    continue
                overview_page["original_url"] = overview_url
                is_explicit, section_reason = explicit_priority_section(
                    overview_page["title"], overview_page["text"], overview_url,
                )
                if not is_explicit:
                    errors.append({
                        "party": party.name,
                        "original_url": overview_url,
                        "stage": "manual_review",
                        "error": section_reason,
                    })
                    continue
                coverage["priority_section_url"] = overview_url
                coverage["priority_section_heading"] = overview_page["title"]
                coverage["manual_review_needed"] = False
                navigation.setdefault(overview_url, {
                    "path": f"{homepage_url} -> {overview_label or overview_url}",
                    "homepage_archive_url": home_archive,
                    "homepage_snapshot_timestamp": home_timestamp,
                    "link_reason": "policy overview",
                })
                for policy_url, policy_label in linked_internal_urls(
                    overview_url,
                    overview_page["hrefs"],
                    domain,
                ).items():
                    score, policy_reason = policy_link_score(policy_url, policy_label)
                    if not score:
                        continue
                    discovered.setdefault(policy_url, [])
                    navigation.setdefault(policy_url, {
                        "path": (
                            f"{homepage_url} -> {overview_label or overview_url}"
                            f" -> {policy_label or policy_url}"
                        ),
                        "homepage_archive_url": home_archive,
                        "homepage_snapshot_timestamp": home_timestamp,
                        "link_reason": f"overview: {policy_reason}",
                        "overview_source_url": overview_url,
                        "overview_title": overview_page["title"],
                        "link_label": policy_label,
                    })
        if not discovered and not party.highlighted_priorities:
            errors.append({
                "party": party.name,
                "domain": domain,
                "stage": "manual_review",
                "error": "No explicit highlighted-priority section identified; broad policy discovery not used.",
            })

        if domain not in all_records_by_domain:
            all_records_by_domain[domain] = cdx_records(session, party, domain)
        by_url: dict[str, list[dict]] = {}
        for record in all_records_by_domain[domain]:
            url = normalize_original_url(record.get("original", ""), domain)
            if url:
                by_url.setdefault(url, []).append(record)
        for url in discovered:
            discovered[url] = by_url.get(url, [])

    for url in discovered:
        if party.code in {"DF", "EL"}:
            discovered[url] = cdx_exact_records(session, party, url)
        elif not discovered[url] and url not in direct_pages:
            discovered[url] = [
                record for record in cdx_exact_records(session, party, url)
            ]

    rows = []
    excluded = []
    seen_hashes = set()
    if party.code == "DD":
        ordered = sorted(
            discovered.items(),
            key=lambda item: navigation.get(item[0], {}).get(
                "priority_order", 999
            ),
        )
    else:
        ordered = sorted(
            discovered.items(),
            key=lambda item: (
                policy_link_score(
                    item[0],
                    navigation.get(item[0], {}).get("path", ""),
                )[0],
                candidate_score(item[0], item[1]),
            ),
            reverse=True,
        )
    if max_pages is not None:
        ordered = ordered[:max_pages]
    save_json(
        CACHE_DIR / f"discovery_{party.code}.json",
        [
            {"original_url": url, "snapshots": snapshots}
            for url, snapshots in discovered.items()
        ],
    )
    for original_url, snapshots in ordered:
        if dry_run:
            rows.append({
                "party": party.name, "party_code": party.code,
                "original_url": original_url, "validation_status": "dry_run_candidate",
                "review_status": "not_reviewed",
                "policy_relevance": "unassessed",
                "relevance_reason": "dry-run candidate",
                "navigation_path": navigation.get(original_url, {}).get("path", ""),
                "homepage_archive_url": navigation.get(original_url, {}).get("homepage_archive_url", ""),
                "homepage_snapshot_timestamp": navigation.get(original_url, {}).get("homepage_snapshot_timestamp", ""),
                "capture_gap_days": "",
            })
            continue
        page = direct_pages.get(original_url)
        reason = None
        if page is None:
            page, reason = fetch_snapshot(
                session,
                original_url,
                snapshots,
                alias_urls(party, original_url),
                allow_any_capture_date=True,
            )
            if page is not None and party.code == "EL":
                campaign_title, campaign_text, extraction_method = (
                    extract_enhedslisten_campaign_priority(
                        load_cached_html_for_page(page),
                        navigation.get(original_url, {}).get("link_label", ""),
                    )
                )
                if not campaign_text:
                    page = None
                    reason = "campaign priority text could not be extracted"
                else:
                    page["title"] = campaign_title or page["title"]
                    page["text"] = campaign_text
                    page["text_length"] = len(campaign_text)
                    page["extraction_method"] = extraction_method
                    page["document_type"] = "election_campaign_priority"
        if not page:
            nav = navigation.get(original_url, {})
            rows.append({
                "party": party.name,
                "party_code": party.code,
                "document_type": "policy_page",
                "title": nav.get("link_label", ""),
                "original_url": original_url,
                "resolved_original_url": "",
                "archive_url": "",
                "snapshot_timestamp": "",
                "original_publication_date": "",
                "text": "",
                "text_length": 0,
                "extraction_method": "",
                "validation_status": "linked_page_unavailable",
                "review_status": "manual_review_required",
                "policy_relevance": "medium",
                "relevance_reason": "included from archived policy overview",
                "priority_category": "highlighted_priority" if nav.get("priority_category") else "unclassified",
                "source_section_heading": nav.get("source_section_heading", ""),
                "priority_order": nav.get("priority_order", ""),
                "text_granularity": nav.get("text_granularity", ""),
                "priority_overview_archive_url": nav.get("overview_archive_url", ""),
                "priority_overview_snapshot_timestamp": nav.get(
                    "overview_snapshot_timestamp", ""
                ),
                "navigation_path": nav.get("path", ""),
                "homepage_archive_url": nav.get("homepage_archive_url", ""),
                "homepage_snapshot_timestamp": nav.get("homepage_snapshot_timestamp", ""),
                "capture_gap_days": "",
                "capture_gap_status": "unknown",
                "content_status": "missing",
            })
            errors.append({
                "party": party.name,
                "original_url": original_url,
                "stage": "extract",
                "error": reason,
                "retained_in_dataset": True,
            })
            continue
        digest = text_hash(page["text"])
        if digest in seen_hashes:
            errors.append({"party": party.name, "original_url": original_url, "stage": "deduplicate", "error": "duplicate normalized text"})
            continue
        seen_hashes.add(digest)
        document_type, classification_method = page_type(page["title"], original_url, page["text"])
        if page.get("document_type"):
            document_type = page["document_type"]
        relevance, relevance_reason = classify_policy_relevance(
            page["title"], original_url, page["text"],
        )
        navigation_record = navigation.get(original_url, {})
        output_title = navigation_record.get("link_label") or page["title"]
        base = {
            "party": party.name,
            "party_code": party.code,
            "title": output_title,
            "original_url": original_url,
            "resolved_original_url": page.get("resolved_original_url", original_url),
            "archive_url": page["archive_url"],
            "snapshot_timestamp": page["timestamp"],
            "text_length": page["text_length"],
            "policy_relevance": relevance,
            "relevance_reason": relevance_reason,
        }
        if relevance == "low":
            if navigation.get(original_url, {}).get("overview_source_url"):
                relevance = "medium"
                relevance_reason = "included from archived policy overview"
            else:
                gap_days = capture_gap_days(
                    navigation.get(original_url, {}).get("homepage_snapshot_timestamp", ""),
                    page["timestamp"],
                )
                excluded.append({
                    **base,
                    "exclusion_reason": relevance_reason,
                    "text_excerpt": page["text"][:500],
                    "navigation_path": navigation.get(original_url, {}).get("path", ""),
                    "homepage_archive_url": navigation.get(original_url, {}).get("homepage_archive_url", ""),
                    "homepage_snapshot_timestamp": navigation.get(original_url, {}).get("homepage_snapshot_timestamp", ""),
                    "capture_gap_days": gap_days,
                    "capture_gap_status": capture_gap_status(gap_days),
                })
                continue
        rows.append({
            "party": party.name, "party_code": party.code,
            "document_type": document_type, "title": output_title,
            "original_url": original_url, "archive_url": page["archive_url"],
            "snapshot_timestamp": page["timestamp"],
            "original_publication_date": page.get("original_publication_date", ""),
            "text": page["text"], "text_length": page["text_length"],
            "extraction_method": f"{page['extraction_method']};classification={classification_method}",
            "validation_status": page["temporal_status"],
            "review_status": page.get("review_status", "manual_review_required"),
            "policy_relevance": relevance, "relevance_reason": relevance_reason,
            "priority_category": navigation.get(original_url, {}).get("priority_category", "unclassified"),
            "source_section_heading": navigation.get(original_url, {}).get("source_section_heading", ""),
            "priority_order": navigation.get(original_url, {}).get("priority_order", ""),
            "text_granularity": navigation.get(original_url, {}).get("text_granularity", ""),
            "priority_overview_archive_url": navigation.get(
                original_url, {}
            ).get("overview_archive_url", ""),
            "priority_overview_snapshot_timestamp": navigation.get(
                original_url, {}
            ).get("overview_snapshot_timestamp", ""),
            "navigation_path": navigation.get(original_url, {}).get("path", ""),
            "homepage_archive_url": navigation.get(original_url, {}).get("homepage_archive_url", ""),
            "homepage_snapshot_timestamp": navigation.get(original_url, {}).get("homepage_snapshot_timestamp", ""),
            "capture_gap_days": capture_gap_days(
                navigation.get(original_url, {}).get("homepage_snapshot_timestamp", ""),
                page["timestamp"],
            ),
            "capture_gap_status": capture_gap_status(capture_gap_days(
                navigation.get(original_url, {}).get("homepage_snapshot_timestamp", ""),
                page["timestamp"],
            )),
            "content_status": "extracted",
        })
    return rows, errors, excluded, {
        "discovered_urls": len(discovered),
        "keyword_urls": len(discovered),
        **coverage,
    }


def write_outputs(
    rows: list[dict],
    excluded: list[dict],
    errors: list[dict],
    summaries: list[dict],
    supplementary: list[dict],
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUTPUT_DIR / "policy_pages.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    with (OUTPUT_DIR / "policy_pages.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (OUTPUT_DIR / "supplementary_proposals.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUPPLEMENTARY_COLUMNS)
        writer.writeheader()
        writer.writerows(supplementary)
    with (OUTPUT_DIR / "supplementary_proposals.jsonl").open("w", encoding="utf-8") as handle:
        for row in supplementary:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (OUTPUT_DIR / "excluded_policy_pages.jsonl").open("w", encoding="utf-8") as handle:
        for row in excluded:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (OUTPUT_DIR / "excluded_policy_pages.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXCLUDED_COLUMNS)
        writer.writeheader()
        writer.writerows(excluded)
    with (OUTPUT_DIR / "party_coverage.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = (
            "party", "party_code", "discovered_urls", "keyword_urls",
            "extracted_pages", "high_relevance", "medium_relevance",
            "low_relevance", "missing_pages", "rejected_pages",
            "homepage_archive_url", "homepage_snapshot_timestamp",
            "priority_section_url", "priority_section_heading",
            "manual_review_needed",
        )
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summaries)
    with (OUTPUT_DIR / "historical_party_mapping.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("policy_party_code", "dataset_label", "historical_party", "scope_note"))
        writer.writerows(HISTORICAL_2022_PARTY_MAPPING)
    (OUTPUT_DIR / "historical_party_mapping.md").write_text(
        "# Historical 2022 party-affiliation mapping\n\n"
        "The policy corpus uses historical parties represented after the 2022 election. "
        "The politician registry retains current/observed labels unchanged; a separate "
        "person-level historical affiliation mapping is required before comparing policy "
        "texts with individual voting behaviour. UFG is a parliamentary status, not a party "
        "and is intentionally excluded from the scrape.\n\n"
        "| Policy code | Dataset label | Historical party | Scope |\n"
        "|---|---|---|---|\n"
        + "\n".join(
            f"| {code} | {label} | {name} | {note} |"
            for code, label, name, note in HISTORICAL_2022_PARTY_MAPPING
        ) + "\n",
        encoding="utf-8",
    )
    save_json(OUTPUT_DIR / "scrape_errors.json", errors)
    by_party = Counter(row["party"] for row in rows)
    lines = [
        "# Party-policy collection quality report",
        "",
        "This report records Wayback discovery and extraction results. A policy page is not automatically a political promise.",
        "",
        "| Party | Discovered | Main dataset | High | Medium | Low | Missing | Rejected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        lines.append(
            f"| {summary['party']} | {summary['discovered_urls']} | "
            f"{summary['extracted_pages']} | {summary['high_relevance']} | "
            f"{summary['medium_relevance']} | {summary['low_relevance']} | "
            f"{summary['missing_pages']} | "
            f"{summary['rejected_pages']} |"
        )
        lines.append(
            f"\n**{summary['party']} source:** homepage `{summary.get('homepage_archive_url', '')}` "
            f"({summary.get('homepage_snapshot_timestamp', '')}); priority section "
            f"`{summary.get('priority_section_url', '')}` — "
            f"{summary.get('priority_section_heading', '')}; manual review: "
            f"`{summary.get('manual_review_needed', '')}`."
        )
    lines.extend([
        "", f"Total main-dataset pages: {len(rows)}",
        f"Total excluded low-relevance pages: {len(excluded)}",
        f"Total errors/rejections: {len(errors)}", "",
    ])
    for error in errors[:100]:
        lines.append(f"- **{error.get('party', '')}** `{error.get('original_url', '')}`: {error.get('error', '')}")
    (OUTPUT_DIR / "quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(parties: list[Party], max_pages: int | None, dry_run: bool) -> tuple[list[dict], list[dict], list[dict]]:
    session = make_session()
    all_rows: list[dict] = []
    all_excluded: list[dict] = []
    all_errors: list[dict] = []
    all_supplementary: list[dict] = []
    summaries = []
    selected_codes = {party.code for party in parties}
    for preserved_code in (
        "S", "V", "RV", "KF", "NB", "SF", "LA", "M", "DF", "DD", "EL", "ALT"
    ):
        if preserved_code in selected_codes:
            continue
        checkpoint = load_json(CHECKPOINT_DIR / f"{preserved_code}.json", None)
        if not checkpoint:
            continue
        all_rows.extend(checkpoint.get("rows", []))
        all_excluded.extend(checkpoint.get("excluded", []))
        all_errors.extend(checkpoint.get("errors", []))
        all_supplementary.extend(checkpoint.get("supplementary_records", []))
        if checkpoint.get("summary"):
            summary = dict(checkpoint["summary"])
            preserved_rows = checkpoint.get("rows", [])
            if preserved_rows:
                if not summary.get("homepage_archive_url"):
                    summary["homepage_archive_url"] = preserved_rows[0].get(
                        "homepage_archive_url", ""
                    )
                if not summary.get("homepage_snapshot_timestamp"):
                    summary["homepage_snapshot_timestamp"] = preserved_rows[0].get(
                        "homepage_snapshot_timestamp", ""
                    )
            summary.update({
                key: value
                for key, value in PRESERVED_PARTY_SOURCE_METADATA.get(
                    preserved_code, {}
                ).items()
                if not summary.get(key)
            })
            summaries.append(summary)
    for party in parties:
        LOGGER.info("Processing %s", party.name)
        rows, errors, excluded, stats = run_party(session, party, max_pages, dry_run)
        all_rows.extend(rows)
        all_excluded.extend(excluded)
        all_errors.extend(errors)
        all_supplementary.extend(stats.get("supplementary_records", []))
        relevance_counts = Counter(row.get("policy_relevance") for row in rows + excluded)
        summaries.append({
            "party": party.name,
            "party_code": party.code,
            "discovered_urls": stats["discovered_urls"],
            "keyword_urls": stats["keyword_urls"],
            "extracted_pages": len(rows),
            "high_relevance": relevance_counts["high"],
            "medium_relevance": relevance_counts["medium"],
            "low_relevance": relevance_counts["low"],
            "missing_pages": sum(row.get("content_status") == "missing" for row in rows),
            "rejected_pages": len(errors),
            "homepage_archive_url": stats.get("homepage_archive_url", ""),
            "homepage_snapshot_timestamp": stats.get("homepage_snapshot_timestamp", ""),
            "priority_section_url": stats.get("priority_section_url", ""),
            "priority_section_heading": stats.get("priority_section_heading", ""),
            "manual_review_needed": stats.get("manual_review_needed", False),
        })
        save_json(
            CHECKPOINT_DIR / f"{party.code}.json",
            {
                "summary": summaries[-1],
                "rows": rows,
                "excluded": excluded,
                "errors": errors,
                "supplementary_records": stats.get("supplementary_records", []),
            },
        )
    write_outputs(all_rows, all_excluded, all_errors, summaries, all_supplementary)
    return all_rows, all_errors, summaries
