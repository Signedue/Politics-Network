# TV 2 election-period scraper (5 October – 1 November 2022)

This project is a **candidate collection pipeline**, not a guarantee that every TV 2 article is found.

## What it does

1. Reads `data/politicians.json` (your supplied politician list).
2. Searches Google News RSS for:
   - election-related phrases, and
   - each politician's full name and supplied aliases.
3. Keeps candidate links on `nyheder.tv2.dk`.
4. Fetches publicly accessible article pages and extracts structured metadata / visible text.
5. Filters by publication date (inclusive: 2022-10-05 through 2022-11-01).
6. Matches politician names/aliases in the title and extracted text.
7. Writes three JSON outputs.

## Setup

Use Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\activate        # Windows

pip install -r requirements.txt
```

## Run

From the project root:

```bash
python -m scraper.discover_articles
python -m scraper.scrape_articles
```

Outputs are saved in `output/`:

- `article_urls.json`
- `tv2_articles.json`
- `politician_mentions.json`

## Important research and technical limitations

- Search-engine RSS results are incomplete and can change over time. Historical indexing is not exhaustive.
- A politician's name search will miss articles that discuss them without naming them. Broad election-topic queries help, but do not solve this completely.
- Google News may return duplicate, redirected, or non-TV2 links; the script filters to the TV2 Nyheder host.
- TV 2's HTML and structured metadata can change. Inspect a sample of scraped records before relying on the corpus.
- `content` contains only text exposed on the publicly accessible page. The script does not log in, bypass a paywall, or circumvent access controls. Some articles may have incomplete or no extracted body text.
- The politician list may represent a particular parliamentary composition; verify that it corresponds to the 2022 election candidates/members before treating mentions as a complete election-candidate dataset.
- The script intentionally stores articles in the date window even when no politician is matched, to support high-recall analysis.
- This pipeline does not scrape comments, user data, or video/audio transcripts.

## Responsible use

Before running, review TV 2's current `robots.txt`, terms of use, and any applicable research permissions. The scraper uses a descriptive User-Agent and a two-second delay, but you should stop if the site's rules prohibit the planned access. Do not attempt to bypass technical restrictions. Replace the example contact email in `scraper/discover_articles.py` with your own valid research contact.

## Recommended quality checks

1. Manually inspect 20–30 articles from `tv2_articles.json`.
2. Check date parsing against the article page.
3. Check whether extracted `content` includes the full visible article and not navigation/recommendations.
4. Measure duplicates and missing articles against a manually assembled reference sample.
5. Keep the original raw output and document any later cleaning decisions.

## Suggested next improvement

Add a second discovery source (for example, a licensed media archive such as Infomedia, if you have access). This is likely to improve historical coverage more than increasing the number of name-based web searches.
