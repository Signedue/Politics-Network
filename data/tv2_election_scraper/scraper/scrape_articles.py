from __future__ import annotations

import json
import re
import time
import hashlib
from pathlib import Path
from datetime import date
from urllib.parse import urlparse


import requests
from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_date
from tqdm import tqdm

from scraper.config import (
    START_DATE,
    END_DATE,
    OUTPUT_DIR,
    REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    MAX_ARTICLE_PAGES,
)
from scraper.discover_articles import (
    canonical_url,
    load_politicians,
    HEADERS,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / OUTPUT_DIR
OUT.mkdir(parents=True, exist_ok=True)

ARTICLES_FILE = OUT / "tv2_articles.json"
ERRORS_FILE = OUT / "scrape_errors.json"

START = date.fromisoformat(START_DATE)
END = date.fromisoformat(END_DATE)


def normalize_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def load_json(path, default):
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def extract_url_date(url):
    match = re.search(r"/(20\d{2}-\d{2}-\d{2})(?:/|-)", url)
    if not match:
        return None

    try:
        return date.fromisoformat(match.group(1)).isoformat()
    except ValueError:
        return None


def parse_jsonld(soup):
    objects = []

    for node in soup.select('script[type="application/ld+json"]'):
        raw = node.string or node.get_text()

        if not raw:
            continue

        try:
            data = json.loads(raw)
            objects.extend(data if isinstance(data, list) else [data])
        except Exception:
            continue

    flat = []

    for obj in objects:
        if not isinstance(obj, dict):
            continue

        if isinstance(obj.get("@graph"), list):
            flat.extend(
                item for item in obj["@graph"]
                if isinstance(item, dict)
            )
        else:
            flat.append(obj)

    return flat


def find_article_object(objects):
    for obj in objects:
        typ = obj.get("@type", [])
        types = typ if isinstance(typ, list) else [typ]

        if any("Article" in str(value) for value in types):
            return obj

    return {}


def parse_date_safe(value):
    if not value:
        return None

    try:
        return parse_date(str(value)).date().isoformat()
    except Exception:
        return None


def get_meta(soup, selectors):
    for selector in selectors:
        node = soup.select_one(selector)

        if node:
            value = node.get("content")

            if value:
                return value

    return None


def collect_body(soup, article_obj):
    body = article_obj.get("articleBody")

    if isinstance(body, str) and len(body) > 100:
        return normalize_text(body), "jsonld_articleBody"

    selectors = [
        '[itemprop="articleBody"]',
        '[data-testid*="article-body"]',
        '[class*="article-body"]',
        '[class*="ArticleBody"]',
        "article",
        "main",
    ]

    candidates = []

    for selector in selectors:
        for original in soup.select(selector):
            node = BeautifulSoup(str(original), "html.parser")

            for el in node.select(
                "script, style, nav, footer, aside, button"
            ):
                el.decompose()

            text = normalize_text(node.get_text(" ", strip=True))

            if len(text) > 100:
                candidates.append((len(text), text))

    if candidates:
        return max(candidates, key=lambda item: item[0])[1], "html_visible_text"

    return "", "not_found"


def collect_live_entries(soup):
    """
    Best-effort extraction of timestamped live-blog elements.
    These are candidates, not guaranteed complete live entries.
    """
    entries = []

    selectors = [
        "time",
        "[datetime]",
        '[class*="live"]',
        '[class*="Live"]',
    ]

    seen = set()

    for selector in selectors:
        for node in soup.select(selector):
            timestamp = (
                node.get("datetime")
                or node.get("content")
                or node.get("data-timestamp")
            )

            text = normalize_text(node.get_text(" ", strip=True))

            if not text or len(text) < 20:
                continue

            parsed = parse_date_safe(timestamp)

            if not parsed:
                continue

            key = (parsed, text[:200])

            if key in seen:
                continue

            seen.add(key)

            entries.append({
                "timestamp": timestamp,
                "date": parsed,
                "text": text,
            })

    return entries


def politician_matches(text, politicians):
    folded = text.casefold()
    matches = []

    for person in politicians:
        terms = [person.get("name", "")]
        terms += person.get("aliases", [])

        found = []

        for term in terms:
            if not isinstance(term, str):
                continue

            term = normalize_text(term)

            if len(term) >= 5 and term.casefold() in folded:
                found.append(term)

        if found:
            matches.append({
                "actor_id": person.get("actor_id"),
                "name": person.get("name"),
                "party": person.get("party"),
                "party_name": person.get("party_name"),
                "matched_terms": sorted(set(found)),
            })

    return matches


def validate_date(published):
    if not published:
        return "unknown"

    article_date = date.fromisoformat(published)

    if START <= article_date <= END:
        return "inside_range"

    return "outside_range"


def scrape_article(session, item, politicians):
    url = canonical_url(item.get("url", ""))

    if not url:
        return None, "Invalid or non-TV2 URL"

    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    objects = parse_jsonld(soup)
    obj = find_article_object(objects)

    title = normalize_text(
        obj.get("headline")
        or get_meta(soup, ['meta[property="og:title"]'])
        or (soup.title.get_text() if soup.title else "")
    )

    published_raw = (
        obj.get("datePublished")
        or get_meta(soup, [
            'meta[property="article:published_time"]',
            'meta[name="date"]',
            'meta[itemprop="datePublished"]',
        ])
    )

    updated_raw = (
        obj.get("dateModified")
        or get_meta(soup, [
            'meta[property="article:modified_time"]',
            'meta[itemprop="dateModified"]',
        ])
    )

    published = parse_date_safe(published_raw)
    updated = parse_date_safe(updated_raw)

    body, body_source = collect_body(soup, obj)
    live_entries = collect_live_entries(soup)

    author = obj.get("author")

    if isinstance(author, dict):
        author = author.get("name")
    elif isinstance(author, list):
        author = ", ".join(
            value.get("name", "") if isinstance(value, dict)
            else str(value)
            for value in author
        )

    text = title + " " + body

    matches = politician_matches(text, politicians)

    article_id = hashlib.sha1(
        url.encode("utf-8")
    ).hexdigest()[:16]

    return {
        "article_id": article_id,
        "title": title,
        "url": url,
        "url_date": extract_url_date(url),
        "published_at": published,
        "published_at_raw": published_raw,
        "updated_at": updated,
        "updated_at_raw": updated_raw,
        "date_validation": validate_date(published),
        "author": author,
        "content": body,
        "content_extraction_method": body_source,
        "politicians": matches,
        "parties": sorted({
            match["party_name"]
            for match in matches
            if match.get("party_name")
        }),
        "live_entries": live_entries,
        "discovery": item,
        "http_status": response.status_code,
    }, None


def main():
    urls_file = OUT / "article_urls.json"

    if not urls_file.exists():
        raise SystemExit(
            "Run first: python -m scraper.discover_articles"
        )

    candidates = load_json(urls_file, [])
    politicians = load_politicians()

    # Resume previously scraped articles.
    articles = load_json(ARTICLES_FILE, [])
    errors = load_json(ERRORS_FILE, [])

    scraped_urls = {
        article.get("url")
        for article in articles
        if article.get("url")
    }

    failed_urls = {
        error.get("url")
        for error in errors
        if error.get("url")
    }

    session = requests.Session()
    session.headers.update(HEADERS)

    remaining = [
        item for item in candidates
        if item.get("url") not in scraped_urls
        and item.get("url") not in failed_urls
    ]

    remaining = remaining[:MAX_ARTICLE_PAGES]

    print(f"Candidate URLs: {len(candidates)}")
    print(f"Already scraped: {len(scraped_urls)}")
    print(f"Remaining: {len(remaining)}")

    for item in tqdm(remaining, desc="Scraping TV2"):
        url = item.get("url", "")

        try:
            article, error = scrape_article(
                session,
                item,
                politicians,
            )

            if error:
                errors.append({
                    "url": url,
                    "error": error,
                })
            elif article:
                articles.append(article)

        except requests.HTTPError as exc:
            status = (
                exc.response.status_code
                if exc.response is not None else None
            )

            errors.append({
                "url": url,
                "error": str(exc),
                "http_status": status,
            })

            if status in (403, 429):
                print(
                    f"\n[STOP] HTTP {status}. "
                    "Stopping to avoid repeated requests."
                )
                break

        except Exception as exc:
            errors.append({
                "url": url,
                "error": str(exc),
            })

        # Save after every article.
        save_json(ARTICLES_FILE, articles)
        save_json(ERRORS_FILE, errors)

        time.sleep(REQUEST_DELAY_SECONDS)

    articles.sort(
        key=lambda article: (
            article.get("published_at") or "9999-99-99",
            article.get("title") or "",
        )
    )

    save_json(ARTICLES_FILE, articles)
    save_json(ERRORS_FILE, errors)

    in_range = sum(
        article["date_validation"] == "inside_range"
        for article in articles
    )

    outside_range = sum(
        article["date_validation"] == "outside_range"
        for article in articles
    )

    unknown = sum(
        article["date_validation"] == "unknown"
        for article in articles
    )

    print("\n----------------------------------------")
    print("SCRAPING SUMMARY")
    print("----------------------------------------")
    print(f"Scraped articles: {len(articles)}")
    print(f"Inside requested date range: {in_range}")
    print(f"Outside requested date range: {outside_range}")
    print(f"Unknown publication date: {unknown}")
    print(f"Errors: {len(errors)}")
    print(f"Saved to: {ARTICLES_FILE}")
    print("----------------------------------------")


if __name__ == "__main__":
    main()