from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

from scraper.expand_election_dataset import (
    classify_metadata,
    metadata_only,
    page_from_href,
    parse_search_page,
)
from scraper.scrape_articles import extract_article_metadata
from scraper.validate_search_result_dates import build_date_report


class ExpandElectionDatasetTests(unittest.TestCase):
    def test_extracts_tv2_results_and_next_page(self):
        html = """
        <section class="tc_searchresults">
          <h2>120 resultater på <strong>Folketingsvalg 2022</strong></h2>
          <ul class="tc_searchresults__list">
            <li><a class="tc_searchresults__item__link"
              href="https://nyheder.tv2.dk/politik/2022-10-05-valg">
              <h3>Valg i Danmark</h3>
              <p class="tc_searchresults__item__text">5. okt. 2022 ...</p>
            </a></li>
          </ul>
          <a class="tc_pagination__next"
             href="https://search.tv2.dk/?query=valg&amp;page=2">Næste</a>
        </section>
        """

        results, next_href, result_count = parse_search_page(html)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["search_result_title"], "Valg i Danmark")
        self.assertEqual(results[0]["search_result_date"], "5. okt. 2022")
        self.assertEqual(result_count, 120)
        self.assertEqual(page_from_href(next_href), 2)

    def test_metadata_only_output_drops_article_text(self):
        article = metadata_only({
            "url": "https://nyheder.tv2.dk/politik/2022-10-05-valg",
            "content": "full article text",
            "live_entries": [{"text": "live text"}],
            "discovery": {"discovered_snippet": "search excerpt"},
        })

        self.assertNotIn("content", article)
        self.assertNotIn("live_entries", article)
        self.assertNotIn("discovered_snippet", article["discovery"])
        self.assertEqual(article["politician_match_status"], "not_assessed_metadata_only")

    def test_only_actual_in_range_publication_dates_are_uncertain(self):
        candidates = {
            "https://nyheder.tv2.dk/politik/2022-10-05-a": {
                "url": "https://nyheder.tv2.dk/politik/2022-10-05-a",
            },
            "https://nyheder.tv2.dk/politik/2022-11-02-b": {
                "url": "https://nyheder.tv2.dk/politik/2022-11-02-b",
            },
        }
        metadata = {
            "https://nyheder.tv2.dk/politik/2022-10-05-a": {
                "url": "https://nyheder.tv2.dk/politik/2022-10-05-a",
                "published_at": "2022-10-05",
            },
            "https://nyheder.tv2.dk/politik/2022-11-02-b": {
                "url": "https://nyheder.tv2.dk/politik/2022-11-02-b",
                "published_at": "2022-11-02",
            },
        }

        relevant, uncertain, rejected, stats = classify_metadata(
            candidates, metadata, {},
        )

        self.assertEqual(relevant, [])
        self.assertEqual(len(uncertain), 1)
        self.assertEqual(rejected[0]["rejection_reason"], "outside_date_range")
        self.assertEqual(stats["within_date_range"], 1)
        self.assertEqual(stats["outside_date_range"], 1)

    def test_date_report_uses_inclusive_boundaries_and_marks_unchecked(self):
        candidates = {
            "https://nyheder.tv2.dk/politik/2022-10-05-start": {
                "url": "https://nyheder.tv2.dk/politik/2022-10-05-start",
            },
            "https://nyheder.tv2.dk/politik/2022-11-01-end": {
                "url": "https://nyheder.tv2.dk/politik/2022-11-01-end",
            },
            "https://nyheder.tv2.dk/politik/missing": {
                "url": "https://nyheder.tv2.dk/politik/missing",
            },
            "https://nyheder.tv2.dk/politik/not-checked": {
                "url": "https://nyheder.tv2.dk/politik/not-checked",
            },
        }
        metadata = {
            candidates[url]["url"]: {
                "url": candidates[url]["url"],
                "published_at": published,
            }
            for url, published in (
                ("https://nyheder.tv2.dk/politik/2022-10-05-start", "2022-10-05"),
                ("https://nyheder.tv2.dk/politik/2022-11-01-end", "2022-11-01"),
            )
        }

        records, summary = build_date_report(
            candidates,
            metadata,
            {"https://nyheder.tv2.dk/politik/missing": "timeout"},
            stopped_by_site=True,
        )
        statuses = {record["url"]: record["date_check_status"] for record in records}

        self.assertEqual(statuses[candidates["https://nyheder.tv2.dk/politik/2022-10-05-start"]["url"]], "within_date_range")
        self.assertEqual(statuses[candidates["https://nyheder.tv2.dk/politik/2022-11-01-end"]["url"]], "within_date_range")
        self.assertEqual(statuses[candidates["https://nyheder.tv2.dk/politik/missing"]["url"]], "retrieval_failed")
        self.assertEqual(statuses[candidates["https://nyheder.tv2.dk/politik/not-checked"]["url"]], "not_checked")
        self.assertEqual(summary["within_date_range"], 2)

    def test_extracts_visible_publication_time_separately_from_update_time(self):
        soup = BeautifulSoup("""
            <article>
              <time datetime="2022-10-05T11:01:51.000Z">5. okt 2022 kl. 13.01</time>
              <time datetime="2022-10-05T11:59:16.000Z">Opdateret 5. okt 2022 kl. 13.59</time>
            </article>
        """, "html.parser")
        metadata = extract_article_metadata(
            soup,
            "https://nyheder.tv2.dk/politik/2022-10-05-example",
            200,
            {"url": "https://nyheder.tv2.dk/politik/2022-10-05-example"},
        )

        self.assertEqual(metadata["published_at"], "2022-10-05")
        self.assertEqual(metadata["published_at_raw"], "2022-10-05T11:01:51.000Z")
        self.assertEqual(metadata["updated_at"], "2022-10-05")
        self.assertEqual(metadata["updated_at_raw"], "2022-10-05T11:59:16.000Z")


if __name__ == "__main__":
    unittest.main()
