# Danish party policies, 2022

This independent pipeline discovers historical policy pages from official
Danish, Greenlandic, and Faroese party domains through the Internet Archive
Wayback Machine. It is
designed for policy priorities, election programmes, party programmes, and
related policy pages—not news articles.

The pipeline reconstructs the site immediately before the election. It only
accepts snapshots captured no later than **31 October 2022**, prefers captures
from **25–31 October 2022**, and labels earlier captures as temporally
uncertain. It starts from each party homepage, follows policy-section links,
and uses CDX wildcard discovery only as a fallback. The capture timestamp and
any original publication date are stored separately. A page is not
automatically interpreted as an election promise.

The scrape scope is the 12 Danish parties represented after the 2022 election
plus Inuit Ataqatigiit, Naleraq, Javnaðarflokkurin, Siumut, and
Sambandsflokkurin. `UFG` is a parliamentary status, not a party, and is not
scraped. The source politician labels remain unchanged. A separate historical
person-level party-affiliation mapping is required before policy pages can be
compared with individual voting behaviour; the generated
`output/historical_party_mapping.csv` documents this distinction.

For Socialdemokratiet, the linked `Værdig velfærd` path is resolved through a
historical URL alias when the `/det-vil-vi/` path has no usable pre-election
snapshot. The original linked URL remains in `original_url`, while the
recoverable historical URL is recorded in `resolved_original_url`.

Each linked policy record preserves the homepage archive URL, homepage capture
timestamp, navigation path, page capture timestamp, and a capture-gap status.
Gaps over 30 days are flagged as `substantial_gap` for manual review.

## Installation

The repository already uses `requests`, `beautifulsoup4`, and `pandas`-compatible
CSV outputs. Install missing dependencies with:

```powershell
python -m pip install requests beautifulsoup4
```

## Pilot execution

Run the requested three-party pilot, limited to three pages per party:

```powershell
python -m data.party_policies_2022.cli --party Venstre --max-pages 3
python -m data.party_policies_2022.cli --party Socialdemokratiet --max-pages 3
python -m data.party_policies_2022.cli --party Moderaterne --max-pages 3
```

Use `--dry-run` to discover candidates without downloading archived HTML.
Each party has a separate cache and checkpoint under `cache/`.

The output files are written to `output/`:

- `policy_pages.csv`
- `policy_pages.jsonl`
- `excluded_policy_pages.csv`
- `excluded_policy_pages.jsonl`
- `party_coverage.csv`
- `scrape_errors.json`
- `quality_report.md`

The main policy dataset contains only pages classified as high or medium
relevance. Low-relevance pages are preserved separately with exclusion reasons.
All discovered URLs, including internally followed URLs, are retained under
`cache/discovery_*.json` and the raw CDX cache.

Relevance classification uses URL, title, headings, and extracted content. It
is deliberately conservative but not absolute: pages with uncertain
classification remain in the main dataset with `review_status` set to
`manual_review_required`.

The current implementation is intentionally conservative: it retries ordinary
network failures, sleeps between requests, and stops on HTTP 403 or 429. It
does not bypass archive access controls.
