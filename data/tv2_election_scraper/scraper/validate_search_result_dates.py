from __future__ import annotations

import logging
from pathlib import Path

import requests

from scraper.expand_election_dataset import (
    END,
    SEARCH_RESULTS_FILE,
    START,
    fetch_metadata,
    load_json,
    load_metadata_cache,
    metadata_only,
    parse_publication_date,
    save_json,
)
from scraper.scrape_articles import HEADERS

ROOT = Path(__file__).resolve().parents[1]
DATE_CHECK_FILE = ROOT / "output" / "tv2_election_search_result_date_check.json"
SUMMARY_FILE = ROOT / "output" / "tv2_election_search_result_date_summary.json"
LOGGER = logging.getLogger("tv2_election_date_check")


def build_date_report(
    candidates: dict[str, dict],
    metadata: dict[str, dict],
    failures: dict[str, str],
    stopped_by_site: bool,
) -> tuple[list[dict], dict]:
    records = []
    counts = {
        "within_date_range": 0,
        "outside_date_range": 0,
        "missing_publication_date": 0,
        "retrieval_failed": 0,
        "not_checked": 0,
    }

    for url, candidate in candidates.items():
        article = metadata_only(candidate)
        article.update(metadata.get(url, {}))
        article["url"] = url

        if url not in metadata:
            if url in failures:
                status = "retrieval_failed"
                article["date_check_reason"] = failures[url]
            else:
                status = "not_checked"
                article["date_check_reason"] = (
                    "stopped_after_site_block"
                    if stopped_by_site else "metadata_not_retrieved"
                )
        else:
            published = parse_publication_date(article)
            if published is None:
                status = "missing_publication_date"
            elif START <= published <= END:
                status = "within_date_range"
            else:
                status = "outside_date_range"

        article["date_check_status"] = status
        counts[status] += 1
        records.append(article)

    summary = {
        "total_search_articles": len(candidates),
        "date_range_start_inclusive": START.isoformat(),
        "date_range_end_inclusive": END.isoformat(),
        **counts,
        "checked_with_publication_date": (
            counts["within_date_range"] + counts["outside_date_range"]
        ),
    }
    return records, summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if not SEARCH_RESULTS_FILE.exists():
        raise FileNotFoundError(f"Search results file not found: {SEARCH_RESULTS_FILE}")

    candidates = {
        item["url"]: item
        for item in load_json(SEARCH_RESULTS_FILE, [])
        if isinstance(item, dict) and item.get("url")
    }
    cache = load_metadata_cache()
    with requests.Session() as session:
        session.headers.update(HEADERS)
        metadata, failures, requests_made, stopped_by_site = fetch_metadata(
            session,
            candidates,
            cache,
            retry_failed=True,
            max_requests=None,
        )

    records, summary = build_date_report(
        candidates,
        metadata,
        failures,
        stopped_by_site,
    )
    save_json(DATE_CHECK_FILE, records)
    save_json(SUMMARY_FILE, summary)

    LOGGER.info(
        "Checked %d search-result articles; requested metadata for %d.",
        summary["total_search_articles"],
        requests_made,
    )
    LOGGER.info(
        "Date range %s through %s: %d within, %d outside.",
        START,
        END,
        summary["within_date_range"],
        summary["outside_date_range"],
    )
    LOGGER.info(
        "Missing dates: %d; failed retrievals: %d; not checked: %d.",
        summary["missing_publication_date"],
        summary["retrieval_failed"],
        summary["not_checked"],
    )
    LOGGER.info("Date report saved to %s", DATE_CHECK_FILE)


if __name__ == "__main__":
    main()
