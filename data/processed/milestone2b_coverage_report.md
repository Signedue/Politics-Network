# Milestone 2B session coverage audit

## Method

All `192` `Afstemning` records linked to session `20251` were retrieved as metadata. For each record, the API was queried with `Stemme?$top=0&$inlinecount=allpages`; no individual `Stemme` rows were downloaded.

## Coverage summary

- Total Afstemning records: `192`
- Records with Stemme data: `168`
- Records with zero Stemme rows: `24`
- Percentage with individual-vote data: `87.50%`
- Classification: **PARTIAL COVERAGE**

## Votes with zero Stemme rows

| Vote | Afstemning ID | Date | Afstemningstype | Meeting ID |
|---:|---:|---|---|---:|
| 152 | 10533 | 2025-12-19T09:00:00 | Forslag til vedtagelse | 15470 |
| 153 | 10525 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 154 | 10526 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 155 | 10527 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 156 | 10528 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 157 | 10529 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 158 | 10530 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 159 | 10531 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 160 | 10532 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 161 | 10534 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 162 | 10535 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 163 | 10536 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 164 | 10537 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 165 | 10538 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 166 | 10539 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 167 | 10540 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 168 | 10541 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 169 | 10542 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 170 | 10543 | 2025-12-19T09:00:00 | Endelig vedtagelse | 15470 |
| 177 | 10554 | 2026-02-05T10:00:00 | Forslag til vedtagelse | 15489 |
| 178 | 10550 | 2026-02-05T10:00:00 | Endelig vedtagelse | 15489 |
| 179 | 10551 | 2026-02-05T10:00:00 | Endelig vedtagelse | 15489 |
| 180 | 10552 | 2026-02-05T10:00:00 | Endelig vedtagelse | 15489 |
| 181 | 10553 | 2026-02-05T10:00:00 | Endelig vedtagelse | 15489 |

## Metadata pattern check

- Missing votes by date: `{'2025-12-19': 19, '2026-02-05': 5}`
- Missing votes by meeting: `{15470: 19, 15489: 5}`
- Missing votes by Afstemningstype: `{'Forslag til vedtagelse': 2, 'Endelig vedtagelse': 22}`

The audit identifies clustering only through the metadata above. It does not infer a cause or replace missing records.

## Decision

Session `20251` is classified as **PARTIAL COVERAGE** under the specified threshold rule.
The session is suitable for the project only with the documented missing votes excluded from any later analysis; missing votes must not be silently replaced or treated as observed individual votes.
