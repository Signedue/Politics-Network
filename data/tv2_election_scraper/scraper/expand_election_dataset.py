from __future__ import annotations

import argparse
import json
import logging
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_date

from scraper.config import (
    END_DATE,
    OUTPUT_DIR,
    REQUEST_DELAY_SECONDS,
    START_DATE,
)
from scraper.discover_articles import canonical_url
from scraper.scrape_articles import HEADERS, scrape_article_metadata

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / OUTPUT_DIR
DISCOVERY_PROGRESS_FILE = OUT / "discovery_progress.json"
EXISTING_URL_FILES = (
    OUT / "unfilteredArticles_urls.json",
    OUT / "article_urls.json",
)
EXISTING_METADATA_FILES = (
    OUT / "filteredArticleswithindate.json",
    OUT / "tv2_articles.json",
)
SEARCH_RESULTS_FILE = OUT / "tv2_election_search_results.json"
SEARCH_PROGRESS_FILE = OUT / "tv2_election_search_progress.json"
METADATA_CACHE_FILE = OUT / "tv2_election_metadata_cache.json"
SUMMARY_FILE = OUT / "tv2_election_search_summary.json"
RELEVANT_FILE = OUT / "tv2_election_articles.json"
UNCERTAIN_FILE = OUT / "tv2_election_uncertain.json"
REJECTED_FILE = OUT / "tv2_election_rejected.json"

SEARCH_URL = "https://search.tv2.dk/"
SEARCH_QUERIES = (
    "Folketingsvalg 2022",
    "Folketingsvalget 2022",
    "Folketingsvalg",
    "valgkamp 2022",
)
START = date.fromisoformat(START_DATE)
END = date.fromisoformat(END_DATE)
LOGGER = logging.getLogger("tv2_election_search")


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def article_url(value: str) -> str | None:
    return canonical_url(value)


def search_result_count(soup: BeautifulSoup) -> int | None:
    heading = soup.select_one(".tc_searchresults > h2")
    if not heading:
        return None
    match = re.search(r"([\d.]+)\s+resultater", heading.get_text(" ", strip=True))
    return int(match.group(1).replace(".", "")) if match else None


def parse_search_page(html: str) -> tuple[list[dict], str | None, int | None]:
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for link in soup.select(".tc_searchresults__item__link[href]"):
        url = article_url(link.get("href", ""))
        heading = link.select_one("h2, h3")
        if not url or not heading:
            continue

        snippet = link.select_one(".tc_searchresults__item__text")
        date_match = re.search(
            r"\b\d{1,2}\.\s*[a-zæøå]{3,}\.?\s*\d{4}\b",
            snippet.get_text(" ", strip=True) if snippet else "",
            flags=re.IGNORECASE,
        )
        results.append({
            "url": url,
            "search_result_title": heading.get_text(" ", strip=True),
            "search_result_date": date_match.group(0) if date_match else None,
        })

    next_link = soup.select_one("a.tc_pagination__next[href]")
    next_url = next_link.get("href") if next_link else None
    return results, next_url, search_result_count(soup)


def page_from_href(href: str) -> int:
    values = parse_qs(urlparse(href).query).get("page", [])
    if not values:
        raise ValueError(f"TV 2 next-page link has no page parameter: {href}")
    return int(values[0])


def merge_search_result(existing: dict, result: dict, query: str, page: int) -> dict:
    merged = dict(existing)
    merged["url"] = result["url"]
    if not merged.get("discovered_title"):
        merged["discovered_title"] = result["search_result_title"]
    discoveries = list(merged.get("search_discoveries", []))
    discovery = {
        "query": query,
        "page": page,
        "title": result["search_result_title"],
        "displayed_date": result["search_result_date"],
    }
    if discovery not in discoveries:
        discoveries.append(discovery)
    merged["search_discoveries"] = discoveries
    merged["discovery_source"] = "TV 2 search"
    return merged


def crawl_search(
    session: requests.Session,
    results_by_url: dict[str, dict],
    progress: dict,
) -> tuple[int, int]:
    raw_results = duplicate_results = 0
    query_state = progress.setdefault("queries", {})

    for query in SEARCH_QUERIES:
        state = query_state.setdefault(query, {
            "next_page": 1,
            "done": False,
            "pages_inspected": 0,
            "result_count": 0,
            "reported_total": None,
        })
        if state["done"]:
            continue

        seen_pages = set()
        while not state["done"]:
            page = int(state["next_page"])
            if page in seen_pages:
                raise RuntimeError(f"Pagination loop detected for {query!r} at page {page}")
            seen_pages.add(page)

            response = session.get(
                SEARCH_URL,
                params={"query": query, "sort": "relevance", "page": page},
                timeout=20,
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            page_results, next_href, reported_total = parse_search_page(response.text)
            state["pages_inspected"] += 1
            state["reported_total"] = reported_total or state["reported_total"]

            if not page_results:
                state["done"] = True
                state["next_page"] = None
                save_json(SEARCH_PROGRESS_FILE, progress)
                break

            state["result_count"] += len(page_results)
            raw_results += len(page_results)
            for result in page_results:
                url = result["url"]
                if url in results_by_url:
                    duplicate_results += 1
                    results_by_url[url] = merge_search_result(
                        results_by_url[url], result, query, page,
                    )
                else:
                    results_by_url[url] = merge_search_result(
                        result, result, query, page,
                    )

            if not next_href:
                state["done"] = True
                state["next_page"] = None
            else:
                next_page = page_from_href(next_href)
                if next_page <= page:
                    raise RuntimeError(
                        f"Non-increasing TV 2 pagination for {query!r}: "
                        f"{page} -> {next_page}"
                    )
                state["next_page"] = next_page

            save_json(SEARCH_RESULTS_FILE, list(results_by_url.values()))
            save_json(SEARCH_PROGRESS_FILE, progress)
            time.sleep(REQUEST_DELAY_SECONDS)

        LOGGER.info(
            "Search %r: %d pages inspected, %d result rows",
            query,
            state["pages_inspected"],
            state["result_count"],
        )

    return raw_results, duplicate_results


def load_existing_candidates() -> tuple[dict[str, dict], int, int]:
    candidates = {}
    duplicate_count = 0
    progress_items = load_json(DISCOVERY_PROGRESS_FILE, [])
    progress_article_count = 0
    if isinstance(progress_items, list):
        progress_article_count = sum(
            isinstance(item, dict) and bool(item.get("url"))
            for item in progress_items
        )

    for path in EXISTING_URL_FILES:
        items = load_json(path, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            url = article_url(item.get("url", ""))
            if not url:
                continue
            item = dict(item)
            item["url"] = url
            if url in candidates:
                duplicate_count += 1
                candidates[url].setdefault("existing_sources", []).append(path.name)
            else:
                item["existing_sources"] = [path.name]
                candidates[url] = item

    return candidates, duplicate_count, progress_article_count


def metadata_only(article: dict) -> dict:
    result = {
        key: value
        for key, value in article.items()
        if key not in {
            "content",
            "content_extraction_method",
            "live_entries",
            "politicians",
            "parties",
        }
    }
    discovery = result.get("discovery")
    if isinstance(discovery, dict):
        discovery = dict(discovery)
        discovery.pop("discovered_snippet", None)
        result["discovery"] = discovery
    result["politicians"] = None
    result["parties"] = None
    result["politician_match_status"] = "not_assessed_metadata_only"
    return result


def load_metadata_cache() -> dict[str, dict]:
    cache = {}
    for article in load_json(METADATA_CACHE_FILE, []):
        if (
            isinstance(article, dict)
            and article.get("url")
            and article.get("status") != "failed"
        ):
            url = article_url(article["url"])
            if url:
                cache[url] = metadata_only(article)

    for path in EXISTING_METADATA_FILES:
        for article in load_json(path, []):
            if not isinstance(article, dict) or not article.get("url"):
                continue
            url = article_url(article["url"])
            if url and url not in cache:
                cache[url] = metadata_only(article)
    return cache


def parse_publication_date(article: dict) -> date | None:
    value = article.get("published_at") or article.get("published_at_raw")
    if not value:
        return None
    try:
        return parse_date(str(value)).date()
    except (TypeError, ValueError, OverflowError):
        return None


def classify_metadata(
    candidates: dict[str, dict],
    metadata: dict[str, dict],
    failed: dict[str, str],
) -> tuple[list[dict], list[dict], list[dict], dict]:
    relevant = []
    uncertain = []
    rejected = []
    stats = {
        "within_date_range": 0,
        "outside_date_range": 0,
        "missing_publication_date": 0,
        "retrieval_failed": 0,
    }

    for url, candidate in candidates.items():
        article = dict(candidate)
        article.update(metadata.get(url, {}))
        article = metadata_only(article)
        article["url"] = url

        if url not in metadata:
            article["classification"] = "uncertain"
            article["classification_reason"] = (
                "article_metadata_retrieval_failed"
                if url in failed else "article_metadata_not_retrieved"
            )
            if url in failed:
                stats["retrieval_failed"] += 1
                article["rejection_reason"] = "metadata_retrieval_failed"
            else:
                article["rejection_reason"] = "metadata_not_retrieved"
            rejected.append(article)
            continue

        published = parse_publication_date(article)
        if published is None:
            stats["missing_publication_date"] += 1
            article["classification"] = "uncertain"
            article["classification_reason"] = "publication_date_missing"
            article["rejection_reason"] = "missing_publication_date"
            rejected.append(article)
            continue

        if not START <= published <= END:
            stats["outside_date_range"] += 1
            article["classification"] = "uncertain"
            article["classification_reason"] = "political_relevance_not_assessed_without_body"
            article["rejection_reason"] = "outside_date_range"
            rejected.append(article)
            continue

        stats["within_date_range"] += 1
        article["classification"] = "uncertain"
        article["classification_reason"] = (
            "article_body_not_collected; political relevance was not assessed"
        )
        uncertain.append(article)

    stats["relevant"] = len(relevant)
    stats["uncertain"] = len(uncertain)
    stats["irrelevant"] = 0
    stats["rejected"] = len(rejected)
    return relevant, uncertain, rejected, stats


def fetch_metadata(
    session: requests.Session,
    candidates: dict[str, dict],
    cache: dict[str, dict],
    retry_failed: bool,
    max_requests: int | None,
) -> tuple[dict[str, dict], dict[str, str], int, bool]:
    failures = {}
    for record in load_json(METADATA_CACHE_FILE, []):
        if isinstance(record, dict) and record.get("status") == "failed":
            failures[record.get("url", "")] = record.get("error", "unknown error")

    requests_made = 0
    stopped_by_site = False
    for url, candidate in candidates.items():
        cached = cache.get(url)
        if cached and parse_publication_date(cached) is not None:
            continue
        if url in failures and not retry_failed:
            continue
        if max_requests is not None and requests_made >= max_requests:
            LOGGER.warning("Reached --max-metadata-requests=%d; run again to resume.", max_requests)
            break

        requests_made += 1
        try:
            item = dict(candidate)
            item["url"] = url
            result, error = scrape_article_metadata(
                session,
                item,
            )
            if error or not result:
                failures[url] = error or "No metadata returned"
            else:
                cache[url] = metadata_only(result)
                failures.pop(url, None)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            failures[url] = str(exc)
            LOGGER.warning("Metadata request failed for %s: %s", url, exc)
            if status in (403, 429):
                LOGGER.warning("Stopping article requests after HTTP %s.", status)
                stopped_by_site = True
        except requests.RequestException as exc:
            failures[url] = str(exc)
            LOGGER.warning("Metadata request failed for %s: %s", url, exc)
        finally:
            cache_records = list(cache.values()) + [
                {"url": failed_url, "status": "failed", "error": reason}
                for failed_url, reason in failures.items()
            ]
            save_json(METADATA_CACHE_FILE, cache_records)

        if stopped_by_site:
            break
        time.sleep(REQUEST_DELAY_SECONDS)
        if requests_made % 25 == 0:
            LOGGER.info(
                "Metadata progress: %d requests, %d successful article records",
                requests_made,
                len(cache),
            )

    return cache, failures, requests_made, stopped_by_site


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Search TV 2 and collect article metadata only. Article bodies "
            "are deliberately not downloaded or stored."
        )
    )
    parser.add_argument(
        "--search-only",
        action="store_true",
        help="Crawl search pages and save candidate URLs without requesting article pages.",
    )
    parser.add_argument(
        "--skip-search",
        action="store_true",
        help="Use saved search results and existing URLs without crawling search pages.",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry URLs whose metadata requests previously failed.",
    )
    parser.add_argument(
        "--max-metadata-requests",
        type=int,
        help="Limit this run's article-page requests; cached progress remains resumable.",
    )
    args = parser.parse_args()
    if args.max_metadata_requests is not None and args.max_metadata_requests < 1:
        parser.error("--max-metadata-requests must be positive")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    session = requests.Session()
    session.headers.update(HEADERS)
    search_results = {
        item["url"]: item
        for item in load_json(SEARCH_RESULTS_FILE, [])
        if isinstance(item, dict) and item.get("url")
    }
    progress = load_json(SEARCH_PROGRESS_FILE, {"queries": {}})
    raw_search_results = duplicate_search_results = 0
    if not args.skip_search:
        raw_search_results, duplicate_search_results = crawl_search(
            session,
            search_results,
            progress,
        )
    save_json(SEARCH_RESULTS_FILE, list(search_results.values()))

    existing, existing_duplicates, progress_article_count = load_existing_candidates()
    candidates = dict(existing)
    for url, result in search_results.items():
        if url in candidates:
            discoveries = candidates[url].setdefault("search_discoveries", [])
            for discovery in result.get("search_discoveries", []):
                if discovery not in discoveries:
                    discoveries.append(discovery)
        else:
            candidates[url] = result

    new_unique = len(set(search_results) - set(existing))
    cache = load_metadata_cache()
    old_cache = {url: row for url, row in cache.items() if url in candidates}

    LOGGER.info(
        "Existing discovery_progress article records: %d",
        progress_article_count,
    )
    LOGGER.info("Existing unique article URLs: %d", len(existing))
    LOGGER.info("New unique TV 2 search URLs: %d", new_unique)
    LOGGER.info("Combined unique candidate URLs: %d", len(candidates))

    if args.search_only:
        LOGGER.info("Search rows encountered this run: %d", raw_search_results)
        LOGGER.info("Search duplicates removed this run: %d", duplicate_search_results)
        for query in SEARCH_QUERIES:
            state = progress.get("queries", {}).get(query, {})
            LOGGER.info(
                "Query %r: %d pages inspected, %d results",
                query,
                state.get("pages_inspected", 0),
                state.get("result_count", 0),
            )
        return

    cache, failures, requests_made, stopped = fetch_metadata(
        session,
        candidates,
        cache,
        args.retry_failed,
        args.max_metadata_requests,
    )
    relevant, uncertain, rejected, stats = classify_metadata(
        candidates,
        cache,
        failures,
    )
    for path, records in (
        (RELEVANT_FILE, relevant),
        (UNCERTAIN_FILE, uncertain),
        (REJECTED_FILE, rejected),
    ):
        save_json(path, records)

    query_summary = {
        query: {
            "pages_inspected": state.get("pages_inspected", 0),
            "result_rows": state.get("result_count", 0),
            "reported_total": state.get("reported_total"),
            "complete": state.get("done", False),
        }
        for query, state in progress.get("queries", {}).items()
    }
    successful_metadata_records = sum(
        url in cache for url in candidates
    )
    metadata_records_with_publication_date = sum(
        url in cache and parse_publication_date(cache[url]) is not None
        for url in candidates
    )
    summary = {
        "existing_discovery_progress_article_records": progress_article_count,
        "existing_unique_article_urls": len(existing),
        "existing_duplicates_removed": existing_duplicates,
        "search_queries": query_summary,
        "search_result_rows_this_run": raw_search_results,
        "search_duplicates_removed_this_run": duplicate_search_results,
        "new_unique_search_articles": new_unique,
        "combined_unique_candidates": len(candidates),
        "article_metadata_cached_before_run": len(old_cache),
        "article_metadata_requests_this_run": requests_made,
        "successful_article_metadata_records": successful_metadata_records,
        "metadata_records_with_publication_date": metadata_records_with_publication_date,
        "failed_article_metadata_requests": len(failures),
        "stopped_by_site": stopped,
        **stats,
        "article_bodies_collected": False,
    }
    save_json(SUMMARY_FILE, summary)

    LOGGER.info("TV 2 search page summary: %s", query_summary)
    LOGGER.info("Search result rows discovered: %d", raw_search_results)
    LOGGER.info("New unique search articles: %d", new_unique)
    LOGGER.info("Duplicate search results removed: %d", duplicate_search_results)
    LOGGER.info("Article metadata requests this run: %d", requests_made)
    LOGGER.info("Successfully retrieved article metadata: %d", successful_metadata_records)
    LOGGER.info("Metadata records with publication date: %d", metadata_records_with_publication_date)
    LOGGER.info("Articles within date range: %d", stats["within_date_range"])
    LOGGER.info("Relevant articles: 0 (body not assessed in metadata-only mode)")
    LOGGER.info("Uncertain articles: %d", stats["uncertain"])
    LOGGER.info("Irrelevant articles: 0 (body not assessed in metadata-only mode)")
    LOGGER.info("Outside date range: %d", stats["outside_date_range"])
    LOGGER.info("Articles missing publication date: %d", stats["missing_publication_date"])
    LOGGER.info("Results written to %s, %s, and %s", RELEVANT_FILE, UNCERTAIN_FILE, REJECTED_FILE)


if __name__ == "__main__":
    main()
