from __future__ import annotations

import unittest

from scraper.filter_articles import (
    filter_articles,
    make_entity_patterns,
    parse_publication_date,
    politically_relevant,
)


POLITICIANS = [
    {
        "name": "Mette Frederiksen",
        "party_name": "Socialdemokratiet",
    },
]


class FilterArticlesTests(unittest.TestCase):
    def test_inclusive_publication_dates_and_rejects_unknown(self):
        articles = [
            {"published_at": "2022-10-05", "content": ""},
            {"published_at": "2022-11-01", "content": ""},
            {"published_at": "2022-11-02", "content": ""},
            {"published_at": None, "url_date": "2022-10-10", "content": ""},
        ]
        _, stats = filter_articles(articles, POLITICIANS)

        self.assertEqual(stats["within_date_range"], 2)
        self.assertEqual(stats["outside_date_range"], 1)
        self.assertEqual(stats["unknown_publication_date"], 1)

    def test_requires_repeated_body_evidence_of_political_activity(self):
        article = {
            "title": "Mette Frederiksen",
            "content": (
                "Mette Frederiksen foreslår en ny skatteaftale under valgkampen. "
                "Mette Frederiksen siger, at regeringen vil fremlægge planen."
            ),
        }
        unrelated = {
            "title": "Mette Frederiksen",
            "content": "Mette Frederiksen deltog i arrangementet. Hun gik derefter hjem.",
        }

        patterns = make_entity_patterns(POLITICIANS)
        self.assertTrue(politically_relevant(article, patterns))
        self.assertFalse(politically_relevant(unrelated, patterns))

    def test_uses_unique_registered_surname_reference(self):
        article = {
            "content": (
                "Løkke siger, at Moderaterne vil støtte en ny regering. "
                "Løkke foreslår også ændringer til skattepolitikken."
            ),
        }
        patterns = make_entity_patterns(POLITICIANS + [
            {"name": "Lars Løkke Rasmussen", "party_name": "Moderaterne"},
        ])

        self.assertTrue(politically_relevant(article, patterns))

    def test_does_not_use_url_or_discovery_date_as_publication_date(self):
        self.assertIsNone(parse_publication_date({
            "url_date": "2022-10-05",
            "discovery": {"discovered_published": "2022-10-05"},
        }))


if __name__ == "__main__":
    unittest.main()
