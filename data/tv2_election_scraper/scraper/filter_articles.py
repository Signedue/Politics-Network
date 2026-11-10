from __future__ import annotations

import argparse
import json
import logging
import re
import time
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests
from dateutil.parser import parse as parse_date

from scraper.config import (
    END_DATE,
    OUTPUT_DIR,
    REQUEST_DELAY_SECONDS,
    START_DATE,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / OUTPUT_DIR
URLS_FILE = OUT / "article_urls.json"
SCRAPED_FILE = OUT / "tv2_articles.json"
POLITICIANS_FILE = ROOT / "data" / "politicians.json"
FILTERED_FILE = OUT / "tv2_politics_2022-10-05_2022-11-01.json"

START = date.fromisoformat(START_DATE)
END = date.fromisoformat(END_DATE)

POLITICAL_TOPICS = (
    "politik", "politisk", "valg", "valgkamp", "folketingsvalg",
    "folketing", "regering", "statsminister", "minister", "partileder",
    "opposition", "lovforslag", "forhandling", "parlamentarisk",
    "mandat", "valgprogram", "regeringsgrundlag", "finanslov",
    "meningsmåling", "måling", "kandidat", "vælgermøde",
    "skat", "økonomi", "klima", "energi", "sundhed", "velfærd",
    "uddannelse", "skole", "indvandring", "integration", "forsvar",
    "arbejdsmarked", "pension", "bolig", "landbrug", "politi",
    "udlænding", "eu",
)

POLITICAL_ACTIONS = (
    "siger", "sagde", "mener", "mente", "foreslår", "foreslog",
    "fremlægger", "fremlagde", "kritiserer", "kritiserede", "lover",
    "lovede", "beslutter", "besluttede", "vedtager", "vedtog",
    "afviser", "afviste", "kræver", "krævede", "ønsker", "ønskede",
    "stemmer", "stemte", "stiller op", "stiller sig", "forhandler",
    "forhandlede", "går til valg", "går ind for", "peger på",
    "indgår", "indgik", "tilslutter", "tilsluttede", "vil",
    "fører", "står til", "erkender", "melder sig", "åbner for",
    "begyndte", "deltager", "deltog", "debatterer", "kæmper",
    "kritiseret", "anklager", "afslår",
)

LOGGER = logging.getLogger("tv2_filter")


def load_json(path: Path, default):
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def canonical_url(value: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None

    parsed = urlparse(value.strip())
    if parsed.hostname not in {"nyheder.tv2.dk", "www.nyheder.tv2.dk"}:
        return None
    return f"https://nyheder.tv2.dk{parsed.path.rstrip('/')}"


def repair_mojibake(value: str) -> str:
    if not re.search(r"Ã.|Â.|â€", value):
        return value
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def fold(value: str) -> str:
    value = repair_mojibake(value).casefold()
    return "".join(
        char for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )


def phrase_pattern(value: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?<!\w){re.escape(fold(value))}(?!\w)",
        flags=re.IGNORECASE,
    )


def make_entity_patterns(politicians: list[dict]) -> list[re.Pattern[str]]:
    phrases = set()
    surname_counts = {}
    for person in politicians:
        name = person.get("name")
        if isinstance(name, str):
            for token in name.split()[-2:]:
                normalized = fold(token.strip(".,-"))
                if len(normalized) >= 5:
                    surname_counts[normalized] = surname_counts.get(normalized, 0) + 1

    for person in politicians:
        name = person.get("name")
        if isinstance(name, str) and name.strip():
            phrases.add(name.strip())
            for token in name.split()[-2:]:
                normalized = fold(token.strip(".,-"))
                if len(normalized) >= 5 and surname_counts.get(normalized) == 1:
                    phrases.add(token.strip(".,-"))
        aliases = person.get("aliases", [])
        if isinstance(aliases, list):
            phrases.update(
                alias.strip()
                for alias in aliases
                if isinstance(alias, str) and alias.strip()
            )

        party_name = person.get("party_name")
        if isinstance(party_name, str) and party_name.strip():
            phrases.add(party_name.strip())
            # Some registry names include a descriptive suffix after a comma.
            phrases.add(party_name.split(",", 1)[0].strip())
            party_short = party_name.split(",", 1)[0].strip()
            if party_short.startswith("Det "):
                party_short = party_short[4:]
                phrases.add(party_short)
                phrases.add(f"De {party_short.split()[0]}")
            if party_short.endswith(" Folkeparti"):
                phrases.add(party_short.removesuffix(" Folkeparti"))

    return [phrase_pattern(phrase) for phrase in sorted(phrases, key=len, reverse=True)]


def parse_publication_date(article: dict) -> date | None:
    # Only the article's publication metadata is authoritative; URL and
    # discovery dates are deliberately not used as fallbacks.
    value = article.get("published_at") or article.get("published_at_raw")
    if not value:
        return None
    try:
        return parse_date(str(value)).date()
    except (TypeError, ValueError, OverflowError):
        return None


def politically_relevant(
    article: dict,
    entity_patterns: list[re.Pattern[str]],
) -> bool:
    body = article.get("content")
    if not isinstance(body, str) or not body.strip():
        return False

    text = fold(body)
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    entity_sentences = set()
    political_sentences = set()
    corroborating_sentences = set()
    for sentence in sentences:
        sentence = sentence.strip()
        has_entity = any(pattern.search(sentence) for pattern in entity_patterns)
        if has_entity:
            entity_sentences.add(sentence)
        has_political_topic = any(term in sentence for term in map(fold, POLITICAL_TOPICS))
        has_political_action = any(term in sentence for term in map(fold, POLITICAL_ACTIONS))
        if has_political_topic and has_political_action:
            political_sentences.add(sentence)
            if has_entity:
                corroborating_sentences.add(sentence)

    # Require repeated body references and repeated political context, with at
    # least one sentence connecting the two; a title or single passing mention
    # cannot qualify an article on its own.
    return (
        len(entity_sentences) >= 2
        and len(political_sentences) >= 2
        and bool(corroborating_sentences)
    )


def merge_records(primary: dict, secondary: dict) -> dict:
    merged = dict(primary)
    for key, value in secondary.items():
        if key not in merged or merged[key] in (None, "", [], {}):
            merged[key] = value
    return merged


def load_candidates() -> tuple[list[dict], int]:
    candidate_items = load_json(URLS_FILE, [])
    cached_articles = load_json(SCRAPED_FILE, [])

    unique_candidates = {}
    duplicate_count = 0
    for item in candidate_items:
        if not isinstance(item, dict):
            continue
        url = canonical_url(item.get("url", ""))
        if not url:
            continue
        item = dict(item)
        item["url"] = url
        if url in unique_candidates:
            duplicate_count += 1
            unique_candidates[url] = merge_records(unique_candidates[url], item)
        else:
            unique_candidates[url] = item

    records = {}
    for article in cached_articles:
        if not isinstance(article, dict):
            continue
        url = canonical_url(article.get("url", ""))
        if not url:
            continue
        article = dict(article)
        article["url"] = url
        if url in records:
            duplicate_count += 1
            records[url] = merge_records(records[url], article)
        else:
            records[url] = article

    for url, candidate in unique_candidates.items():
        if url in records:
            records[url] = merge_records(records[url], {"discovery": candidate})
        else:
            records[url] = candidate

    return list(records.values()), duplicate_count


def refresh_incomplete(records: list[dict], politicians: list[dict]) -> tuple[int, int]:
    from scraper.scrape_articles import HEADERS, scrape_article

    session = requests.Session()
    session.headers.update(HEADERS)
    refreshed = failed = 0

    for article in records:
        if parse_publication_date(article) and article.get("content"):
            continue
        try:
            discovery_item = article.get("discovery")
            item = discovery_item if isinstance(discovery_item, dict) else article
            result, error = scrape_article(session, item, politicians)
            if error or not result:
                failed += 1
                LOGGER.warning("Could not retrieve %s: %s", article.get("url"), error)
                continue
            article.update(result)
            refreshed += 1
        except requests.HTTPError as exc:
            failed += 1
            status = exc.response.status_code if exc.response is not None else None
            LOGGER.warning("Could not retrieve %s: %s", article.get("url"), exc)
            if status in (403, 429):
                LOGGER.warning("Stopping retries after HTTP %d.", status)
                break
        except requests.RequestException as exc:
            failed += 1
            LOGGER.warning("Could not retrieve %s: %s", article.get("url"), exc)
        except Exception as exc:
            failed += 1
            LOGGER.exception("Unexpected retrieval failure for %s: %s", article.get("url"), exc)
        finally:
            time.sleep(REQUEST_DELAY_SECONDS)

    return refreshed, failed


def filter_articles(records: list[dict], politicians: list[dict]) -> tuple[list[dict], dict]:
    entity_patterns = make_entity_patterns(politicians)
    stats = {
        "total_discovered": len(records),
        "within_date_range": 0,
        "outside_date_range": 0,
        "unknown_publication_date": 0,
        "irrelevant": 0,
        "missing_body": 0,
        "included": 0,
    }
    included = []

    for article in records:
        published = parse_publication_date(article)
        if published is None:
            stats["unknown_publication_date"] += 1
            continue
        if not START <= published <= END:
            stats["outside_date_range"] += 1
            continue
        stats["within_date_range"] += 1

        if not isinstance(article.get("content"), str) or not article["content"].strip():
            stats["missing_body"] += 1
            continue
        if not politically_relevant(article, entity_patterns):
            stats["irrelevant"] += 1
            continue
        included.append(article)

    stats["included"] = len(included)
    return included, stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Filter scraped TV 2 articles for substantive Danish political coverage."
    )
    parser.add_argument(
        "--retry-incomplete",
        action="store_true",
        help="Fetch records missing an actual publication date or article body.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=FILTERED_FILE,
        help=f"Filtered JSON output (default: {FILTERED_FILE}).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    records, duplicate_count = load_candidates()
    politicians = load_json(POLITICIANS_FILE, [])

    LOGGER.info("Discovered unique articles: %d", len(records))
    LOGGER.info("Duplicate article records removed: %d", duplicate_count)
    if args.retry_incomplete:
        refreshed, failed = refresh_incomplete(records, politicians)
        LOGGER.info("Incomplete articles refreshed: %d", refreshed)
        LOGGER.info("Failed article retrievals: %d", failed)

    included, stats = filter_articles(records, politicians)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(included, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    LOGGER.info("Articles within date range: %d", stats["within_date_range"])
    LOGGER.info("Rejected outside date range: %d", stats["outside_date_range"])
    LOGGER.info("Unknown publication dates (not guessed): %d", stats["unknown_publication_date"])
    LOGGER.info("Rejected as politically irrelevant: %d", stats["irrelevant"])
    LOGGER.info("In-range articles with missing bodies: %d", stats["missing_body"])
    LOGGER.info("Successfully included: %d", stats["included"])
    LOGGER.info("Filtered dataset written to %s", args.output)


if __name__ == "__main__":
    main()
