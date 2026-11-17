import unittest

from data.party_policies_2022.pipeline import (
    archive_url,
    classify_policy_relevance,
    extract_structured_html,
    extract_radikale_visions,
    extract_nye_borgerlige_priorities,
    extract_moderaterne_proposals,
    extract_danmarksdemokraterne_programme,
    extract_enhedslisten_campaign_priority,
    extract_alternativet_programme,
    clean_socialdemokratiet_text,
    normalize_original_url,
    text_hash,
    timestamp_is_pre_election,
    timestamp_is_preferred,
)
from data.party_policies_2022.config import (
    RADIKALE_VISION_THEMES,
    SOCIALDEMOCRATIET_HIGHLIGHTED_PRIORITIES,
    SOCIALDEMOCRATIET_2022_CAPTURE_OVERRIDES,
)


class PipelineTests(unittest.TestCase):
    def test_normalizes_urls_and_rejects_assets(self):
        self.assertEqual(
            normalize_original_url("http://www.venstre.dk/politik/", "venstre.dk"),
            "https://venstre.dk/politik",
        )
        self.assertIsNone(normalize_original_url("https://venstre.dk/logo.png", "venstre.dk"))
        self.assertIsNone(normalize_original_url("https://example.org/politik", "venstre.dk"))

    def test_timestamp_validation(self):
        self.assertTrue(timestamp_is_pre_election("20221031120000"))
        self.assertTrue(timestamp_is_preferred("20221025120000"))
        self.assertFalse(timestamp_is_preferred("20221015120000"))
        self.assertFalse(timestamp_is_pre_election("20221101120000"))
        self.assertFalse(timestamp_is_preferred("20220930120000"))

    def test_archive_url_preserves_original_url(self):
        result = archive_url("20221015120000", "https://venstre.dk/valg?x=1")
        self.assertIn("/web/20221015120000id_/", result)
        self.assertIn("https://venstre.dk/valg?x=1", result)

    def test_extracts_structure_and_removes_boilerplate(self):
        title, text, method, links, publication_date = extract_structured_html("""
            <html><head><title>Politik</title></head><body>
            <nav>Menu</nav><main><h1>Klima</h1><p>Vi vil ændre klimaet.</p>
            <ul><li>Ren energi</li></ul><a href="/sundhed">Sundhed</a></main>
            <footer>Cookie policy</footer></body></html>
        """)
        self.assertEqual(title, "Politik")
        self.assertIn("# Klima", text)
        self.assertIn("Vi vil ændre klimaet.", text)
        self.assertIn("- Ren energi", text)
        self.assertNotIn("Cookie policy", text)
        self.assertEqual(method, "structured_headings_paragraphs_lists")
        self.assertEqual(links[0]["href"], "/sundhed")
        self.assertEqual(publication_date, "")

    def test_text_hash_is_stable_after_whitespace_normalization(self):
        self.assertEqual(text_hash("A  policy\ntext"), text_hash("A policy text"))

    def test_policy_relevance_prioritizes_proposals_and_excludes_events(self):
        relevance, reason = classify_policy_relevance(
            "Vores klimaudspil",
            "https://example.dk/politik/klimaudspil",
            "Vi vil gennemføre en konkret plan for klimaet.\n\n" * 30,
        )
        self.assertEqual(relevance, "high")
        self.assertIn("proposal", reason)
        relevance, reason = classify_policy_relevance(
            "Valgrally i Region Sjælland",
            "https://example.dk/valgkamp/valgrally",
            "Kom til valgrally og mød vores kandidater.",
        )
        self.assertEqual(relevance, "low")

    def test_extracts_radikale_visions_in_order_with_themes_and_proposals(self):
        first = RADIKALE_VISION_THEMES[0][1][0]
        second = RADIKALE_VISION_THEMES[0][1][1]
        html = f"""
            <main>
              <h2>{first}</h2><p>Problem description.</p>
              <h2>RADIKALE FORSLAG</h2><p>First proposal.</p>
              <h2>{second}</h2><p>Second description.</p>
              <h2>Vi mener</h2><p>General policy category.</p>
              <footer><h2>Kontakt</h2><p>Footer text.</p></footer>
            </main>
        """
        records = extract_radikale_visions(
            html,
            "https://www.radikale.dk/politik/sammen-om-en-ny-start",
            RADIKALE_VISION_THEMES,
        )
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["title"], first)
        self.assertEqual(records[0]["theme"], "TÆNK GRØNT")
        self.assertEqual(records[0]["order"], 1)
        self.assertIn("RADIKALE FORSLAG", records[0]["text"])
        self.assertIn("First proposal.", records[0]["text"])
        self.assertEqual(records[1]["title"], second)
        self.assertNotIn("General policy category.", records[1]["text"])
        self.assertNotIn("Footer text.", records[1]["text"])

    def test_radikale_theme_configuration_contains_exactly_16_visions(self):
        titles = [title for _, theme_titles in RADIKALE_VISION_THEMES for title in theme_titles]
        self.assertEqual(len(titles), 16)
        self.assertEqual(len(set(titles)), 16)

    def test_extracts_nye_numbered_priorities_and_deduplicates_headings(self):
        records = extract_nye_borgerlige_priorities(
            """
            <h6>Udlændingepolitikken</h6>
            <div class="fusion-panel"><h4>01. Første prioritet</h4>
              <div class="panel-body"><p>Forklarende tekst.</p></div></div>
            <div class="fusion-panel"><h4>01. Første prioritet</h4>
              <div class="panel-body"><p>Forklarende tekst.</p></div></div>
            <div class="fusion-panel"><span class="fusion-toggle-heading">
              100. Sidste prioritet
            </span><div class="panel-body"></div></div>
            """,
            "https://web.archive.org/web/20221014020140id_/https://nyeborgerlige.dk/politik/valgoplaeg",
        )
        self.assertEqual([record["number"] for record in records], [1, 100])
        self.assertEqual(records[0]["policy_area"], "Udlændingepolitikken")
        self.assertEqual(records[1]["text_granularity"], "title_only")

    def test_extracts_moderaterne_numbered_proposals_from_accordions(self):
        records = extract_moderaterne_proposals(
            """
            <h2>11 MODERATE FORSLAG</h2>
            <div class="eael-accordion-header" aria-controls="proposal-1">
              1. Første forslag
            </div>
            <div id="proposal-1" class="eael-accordion-content">
              <p>Original forklarende tekst.</p>
            </div>
            <div class="eael-accordion-header" aria-controls="proposal-2">
              2. Andet forslag
            </div>
            <div id="proposal-2" class="eael-accordion-content">
              <p>Anden original tekst.</p>
            </div>
            <div class="video-playlist">3. Videoindhold</div>
            """,
            "https://moderaterne.dk/politik",
            ("Første forslag", "Andet forslag"),
        )
        self.assertEqual([item["number"] for item in records], [1, 2])
        self.assertEqual(records[0]["text"], "Original forklarende tekst.")
        self.assertEqual(records[1]["title"], "Andet forslag")
        self.assertEqual(records[0]["text_granularity"], "substantive_explanatory_text")
        self.assertEqual(records[1]["text_granularity"], "substantive_explanatory_text")

    def test_extracts_dd_main_priorities_and_separate_supplement(self):
        main, supplementary = extract_danmarksdemokraterne_programme(
            """
            <main>
              <h2>Vores politik</h2>
              <h3>Danmark skal hænge sammen</h3><p>Første tekst.</p>
              <h3>Respekt for Produktionsdanmark</h3><p>Anden tekst.</p>
              <h3>En varm hånd, der griber de svageste</h3><p>Tredje tekst.</p>
              <h3>Udlændinge- og retspolitik</h3><p>Fjerde tekst.</p>
              <h2>Vores politiske forslag:</h2>
              <h4>Første forslag</h4><p>Supplerende tekst.</p>
              <h4>Andet forslag</h4><p>Anden supplerende tekst.</p>
              <footer><h4>Kontakt os</h4><p>Ikke politik.</p></footer>
            </main>
            """,
            "https://danmarksdemokraterne.dk/parti/program/",
            (
                "Danmark skal hænge sammen",
                "Respekt for Produktionsdanmark",
                "En varm hånd, der griber de svageste",
                "Udlændinge- og retspolitik",
            ),
        )
        self.assertEqual([item["title"] for item in main], [
            "Danmark skal hænge sammen",
            "Respekt for Produktionsdanmark",
            "En varm hånd, der griber de svageste",
            "Udlændinge- og retspolitik",
        ])
        self.assertEqual(len(supplementary), 2)
        self.assertEqual(main[0]["text"], "Første tekst.")
        self.assertEqual(supplementary[0]["text"], "Supplerende tekst.")
        self.assertNotIn("Ikke politik.", supplementary[-1]["text"])

    def test_extracts_enhedslisten_campaign_intro_and_proposals_only(self):
        title, text, method = extract_enhedslisten_campaign_priority(
            """
            <main class="c-main-valg">
              <h2>Gør valget til et klimavalg</h2>
              <div class="pol-content">
                <p>Original kampagneintroduktion.</p>
              </div>
              <h4>Det vil Enhedslisten:</h4>
              <ul><li>Første forslag</li><li>Andet forslag</li></ul>
              <h4>Download Enhedslistens udspil:</h4>
              <p>Urelateret dokument.</p>
              <h5>del denne side</h5>
              <p>Footer.</p>
            </main>
            """,
            "Gør valget til et klimavalg",
        )
        self.assertEqual(title, "Gør valget til et klimavalg")
        self.assertIn("Original kampagneintroduktion.", text)
        self.assertIn("- Første forslag", text)
        self.assertNotIn("Urelateret dokument.", text)
        self.assertNotIn("Footer.", text)
        self.assertEqual(method, "enhedslisten_campaign_priority")

    def test_extracts_alternativet_sections_and_programme_introduction(self):
        introduction, records = extract_alternativet_programme(
            """
            <section class="frontpage-politics">
              <div class="col-sm-6">
                <h2>Stien til det bæredygtige samfund</h2>
                <p>Programintroduktion.</p>
              </div>
              <div class="col-sm-6">
                <h1>Vores økonomi</h1>
                <p>Økonomisk introduktion.</p>
                <button class="accordion-politics">Første forslag</button>
                <div class="panel-politics"><p>Originalt forslag.</p></div>
              </div>
              <div class="col-sm-6">
                <h1>Vores planet</h1>
                <p>Planet-introduktion.</p>
                <button class="accordion-politics">Andet forslag</button>
                <div class="panel-politics"><p>Anden tekst.</p></div>
              </div>
              <div class="col-sm-6"><h1>Vores samfund</h1><p>Samfund.</p></div>
              <div class="col-sm-6"><h1>Vores liv</h1><p>Liv.</p></div>
            </section>
            """,
            (
                "Vores økonomi",
                "Vores planet",
                "Vores samfund",
                "Vores liv",
            ),
        )
        self.assertEqual(introduction, "Programintroduktion.")
        self.assertEqual([item["title"] for item in records], [
            "Vores økonomi", "Vores planet", "Vores samfund", "Vores liv"
        ])
        self.assertIn("Økonomisk introduktion.", records[0]["text"])
        self.assertIn("Originalt forslag.", records[0]["text"])
        self.assertEqual(records[0]["proposal_count"], 1)

    def test_extracts_alternativet_h2_sections_from_archived_structure(self):
        introduction, records = extract_alternativet_programme(
            """
            <section class="frontpage-politics">
              <h2>Nyheder</h2>
              <h3>Udenfor programmet.</h3>
            </section>
            <section class="frontpage-politics">
              <div class="col-sm-6">
                <h2>Stien til det bæredygtige samfund</h2>
                <p>Programintroduktion.</p>
              </div>
              <div class="col-sm-6">
                <h2>Vores økonomi</h2>
                <p>Økonomisk introduktion.</p>
                <button class="accordion-politics">Forslag økonomi</button>
                <div class="panel-politics"><p>Forslagstekst økonomi.</p></div>
              </div>
              <div class="col-sm-6">
                <h2>Vores planet</h2>
                <p>Planetintroduktion.</p>
                <button class="accordion-politics">Forslag planet</button>
                <div class="panel-politics"><p>Forslagstekst planet.</p></div>
              </div>
            </section>
            """,
            ("Vores økonomi", "Vores planet"),
        )
        self.assertEqual(introduction, "Programintroduktion.")
        self.assertEqual(
            [record["title"] for record in records],
            ["Vores økonomi", "Vores planet"],
        )
        self.assertEqual([record["proposal_count"] for record in records], [1, 1])
        self.assertIn("Forslagstekst økonomi.", records[0]["text"])
        self.assertIn("Forslagstekst planet.", records[1]["text"])

    def test_socialdemokratiet_13_priority_titles_and_order(self):
        self.assertEqual(
            SOCIALDEMOCRATIET_HIGHLIGHTED_PRIORITIES,
            (
                "Bedre vilkår. Bedre velfærd.",
                "Et faglært Danmark",
                "Ret til rent drikkevand",
                "Akutpakke til sygehusene",
                "Ny sygehusfond til moderne sygehuse i hele landet",
                "Ny inflationshjælp",
                "Tryghed for alle",
                "Et grønt landbrug der indfrier klimamålene",
                "Lavere skat på arbejde",
                "Trygt igennem usikre tider",
                "Værdig velfærd",
                "Hurtigere grøn omstilling",
                "En stram udlændingepolitik",
            ),
        )

    def test_socialdemokratiet_cleaner_removes_membership_and_duplicates(self):
        text = (
            "## Politik\n\nVi vil gøre noget konkret.\n\n"
            "- Vi vil gøre noget konkret.\n\n"
            "## Apropos...\n\n### Klima\n\nRelateret indhold.\n\n"
            "## Vil du være med i fællesskabet?\n\n"
            "Som intromedlem af Socialdemokratiet bliver du medlem."
        )
        cleaned = clean_socialdemokratiet_text(text)
        self.assertIn("Vi vil gøre noget konkret.", cleaned)
        self.assertNotIn("Relateret indhold.", cleaned)
        self.assertNotIn("Som intromedlem", cleaned)
        self.assertEqual(cleaned.count("Vi vil gøre noget konkret."), 1)

    def test_socialdemokratiet_climate_capture_is_post_election_near_capture(self):
        stamp, url, capture_kind = SOCIALDEMOCRATIET_2022_CAPTURE_OVERRIDES["12"]
        self.assertEqual(stamp, "20221108181631")
        self.assertEqual(
            url,
            "https://www.socialdemokratiet.dk/det-vil-vi/klima-og-miljoe/",
        )
        self.assertEqual(capture_kind, "post_election_near_capture")

    def test_socialdemokratiet_pre_election_capture_overrides(self):
        verified = {
            key
            for key, (_, _, capture_kind)
            in SOCIALDEMOCRATIET_2022_CAPTURE_OVERRIDES.items()
            if capture_kind == "pre_election_verified"
        }
        self.assertEqual(verified, {"1", "6", "7", "8", "9", "10", "11"})


if __name__ == "__main__":
    unittest.main()
