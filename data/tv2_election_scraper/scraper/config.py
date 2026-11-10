"""Configuration for the TV 2 election-period scraper."""
START_DATE = "2022-10-05"
END_DATE = "2022-11-01"  # inclusive
BASE_DOMAIN = "https://nyheder.tv2.dk"
POLITICIANS_FILE = "data/politicians.json"
OUTPUT_DIR = "output"

# Conservative pacing. Increase only if permitted by the site's policies.
REQUEST_DELAY_SECONDS = 2.0
REQUEST_TIMEOUT_SECONDS = 30
MAX_ARTICLE_PAGES = 200

# These searches complement politician-name searches. They are deliberately broad.
ELECTION_QUERIES = [
    '"folketingsvalg" site:nyheder.tv2.dk after:2022-10-04 before:2022-11-02',
    '"valgkamp" site:nyheder.tv2.dk after:2022-10-04 before:2022-11-02',
    '"valgdebat" site:nyheder.tv2.dk after:2022-10-04 before:2022-11-02',
    '"meningsmåling" site:nyheder.tv2.dk after:2022-10-04 before:2022-11-02',
    '"partilederdebat" site:nyheder.tv2.dk after:2022-10-04 before:2022-11-02',
    '"valgløfte" site:nyheder.tv2.dk after:2022-10-04 before:2022-11-02',
    '"regeringsgrundlag" site:nyheder.tv2.dk after:2022-10-04 before:2022-11-02',
    '"valgresultat" site:nyheder.tv2.dk after:2022-10-04 before:2022-11-02',
    '"Christiansborg" site:nyheder.tv2.dk after:2022-10-04 before:2022-11-02',
]
