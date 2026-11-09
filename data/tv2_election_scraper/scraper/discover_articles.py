
from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlparse

from ddgs import DDGS

from scraper.config import (
    BASE_DOMAIN,
    POLITICIANS_FILE,
    OUTPUT_DIR,
    REQUEST_DELAY_SECONDS,
    ELECTION_QUERIES,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / OUTPUT_DIR
OUT.mkdir(parents=True, exist_ok=True)

ARTICLES_FILE = OUT / "article_urls.json"
PROGRESS_FILE = OUT / "discovery_progress.json"

DATE_FILTER = "after:2022-10-04 before:2022-11-02"
SITE_FILTER = "site:nyheder.tv2.dk"


# Broad topics to find political statements beyond campaign promises.
POLITICAL_TOPICS = [
    "politik",
    "folketingsvalg",
    "valgkamp",
    "partilederdebat",
    "politisk debat",
    "interview politiker",
    "politisk udspil",
    "regering",
    "opposition",
    "sundhed",
    "sygehus",
    "ældrepleje",
    "velfærd",
    "skat",
    "økonomi",
    "inflation",
    "klima",
    "energi",
    "uddannelse",
    "folkeskole",
    "indvandring",
    "integration",
    "forsvar",
    "politi",
    "retspolitik",
    "arbejdsmarked",
    "bolig",
    "landbrug",
    "ulighed",
    "pension",
    "udenrigspolitik",
]


def load_json(path: Path, default):
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def load_politicians():
    path = ROOT / POLITICIANS_FILE
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_url(url: str) -> str | None:
    if not url:
        return None

    url = url.strip()

    if url.startswith("//"):
        url = "https:" + url

    if url.startswith("/"):
        url = BASE_DOMAIN + url

    parsed = urlparse(url)

    if parsed.hostname not in {
        "nyheder.tv2.dk",
        "www.nyheder.tv2.dk",
    }:
        return None

    return f"https://nyheder.tv2.dk{parsed.path.rstrip('/')}"


def build_queries(politicians):
    queries = list(ELECTION_QUERIES)

    # Search for every politician by full name and aliases.
    for person in politicians:
        name = person.get("name", "").strip()

        if name:
            queries.append(
                f'"{name}" {SITE_FILTER} {DATE_FILTER}'
            )

        for alias in person.get("aliases", []):
            if isinstance(alias, str) and len(alias.strip()) >= 5:
                queries.append(
                    f'"{alias.strip()}" {SITE_FILTER} {DATE_FILTER}'
                )

    # Search for each party by its full name.
    parties = {}

    for person in politicians:
        code = str(person.get("party", "")).strip()
        party_name = str(person.get("party_name", "")).strip()

        if code and party_name:
            parties[code] = party_name

    for code, party_name in sorted(parties.items()):
        queries.append(
            f'"{party_name}" {SITE_FILTER} {DATE_FILTER}'
        )

        # Short party abbreviations are searched together with election terms
        # to reduce irrelevant results.
        if len(code) <= 3:
            queries.append(
                f'"{code}" folketingsvalg {SITE_FILTER} {DATE_FILTER}'
            )

    # General political topics.
    for topic in POLITICAL_TOPICS:
        queries.append(
            f'"{topic}" {SITE_FILTER} {DATE_FILTER}'
        )

    # Remove duplicate queries while preserving order.
    return list(dict.fromkeys(queries))


def save_results(discovered):
    ARTICLES_FILE.write_text(
        json.dumps(
            list(discovered.values()),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def save_progress(completed_queries):
    PROGRESS_FILE.write_text(
        json.dumps(
            sorted(completed_queries),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def duckduckgo_search(query: str, max_retries: int = 3):
    for attempt in range(1, max_retries + 1):
        try:
            results = []

            with DDGS() as ddgs:
                search_results = list(
                    ddgs.text(query, max_results=30)
                )

            for entry in search_results:
                article_url = canonical_url(entry.get("href", ""))

                if not article_url:
                    continue

                results.append({
                    "url": article_url,
                    "discovery_query": query,
                    "discovery_queries": [query],
                    "discovery_source": "DuckDuckGo",
                    "discovered_title": entry.get("title", ""),
                    "discovered_published": "",
                    "discovered_snippet": entry.get("body", ""),
                })

            return results

        except Exception as exc:
            print(
                f"[WARN] Attempt {attempt}/{max_retries} failed: {exc}"
            )

            if attempt < max_retries:
                wait_time = attempt * 10
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

    print(f"[ERROR] Search failed after all retries: {query}")
    return None


def main():
    politicians = load_politicians()
    queries = build_queries(politicians)

    # Load existing results so previous work is preserved.
    existing_articles = load_json(ARTICLES_FILE, [])
    discovered = {
        item["url"]: item
        for item in existing_articles
        if isinstance(item, dict) and item.get("url")
    }

    # Load completed searches to support resuming.
    completed_queries = set(load_json(PROGRESS_FILE, []))

    remaining = [
        query for query in queries
        if query not in completed_queries
    ]

    print("----------------------------------------")
    print("TV 2 ELECTION ARTICLE DISCOVERY")
    print("----------------------------------------")
    print(f"Politicians: {len(politicians)}")
    print(f"Unique searches: {len(queries)}")
    print(f"Already completed: {len(completed_queries)}")
    print(f"Remaining searches: {len(remaining)}")
    print(f"Existing candidate articles: {len(discovered)}")
    print("----------------------------------------")

    for i, query in enumerate(remaining, 1):
        print(f"\n[{i}/{len(remaining)}] Searching:")
        print(query)

        articles = duckduckgo_search(query)

        # Do not mark a failed search as completed.
        if articles is None:
            print("[INFO] Search will be retried next time.")
            continue

        new_count = 0

        for item in articles:
            url = item["url"]

            if url not in discovered:
                discovered[url] = item
                new_count += 1
            else:
                existing = discovered[url]

                if query not in existing["discovery_queries"]:
                    existing["discovery_queries"].append(query)
                    existing["discovery_query"] += " | " + query

        completed_queries.add(query)

        save_results(discovered)
        save_progress(completed_queries)

        print(f"New articles: {new_count}")
        print(f"Total unique articles: {len(discovered)}")
        print("Progress saved.")

        time.sleep(REQUEST_DELAY_SECONDS)

    print("\n----------------------------------------")
    print("DISCOVERY FINISHED")
    print("----------------------------------------")
    print(f"Completed searches: {len(completed_queries)}")
    print(f"Total candidate articles: {len(discovered)}")
    print(f"Articles saved to: {ARTICLES_FILE}")
    print(f"Progress saved to: {PROGRESS_FILE}")
    print("----------------------------------------")

    print(
        "\nIMPORTANT: These are candidate articles discovered "
        "through search engines, not a complete TV 2 archive. "
        "Article publication dates and actual political statements "
        "must be validated during scraping."
    )


if __name__ == "__main__":
    main()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Safari/605.1.15"
    )
}
