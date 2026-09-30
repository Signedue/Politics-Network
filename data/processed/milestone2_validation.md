# Milestone 2 validation report

- Votes tested: `10/10`
- Votes passed: `9/10`
- Votes failed: `1/10`

## Selection method

All `Afstemning` records linked to period `20251` were sorted by meeting date, vote number, and `Afstemning` ID. Ten positions were selected evenly from the first through last record using `round(i * (n - 1) / 9)`.

## Selected votes

| Vote | Afstemning ID | Date | Afstemningstype |
|---:|---:|---|---|
| 2 | 10379 | 2025-10-09T08:00:00 | Forslag til vedtagelse |
| 23 | 10396 | 2025-12-04T10:00:00 | Endelig vedtagelse |
| 44 | 10453 | 2025-12-10T09:00:00 | Ændringsforslag |
| 68 | 10475 | 2025-12-10T09:00:00 | Ændringsforslag |
| 91 | 10496 | 2025-12-10T09:00:00 | Ændringsforslag |
| 112 | 10419 | 2025-12-11T10:00:00 | Endelig vedtagelse |
| 133 | 10506 | 2025-12-18T10:00:00 | Endelig vedtagelse |
| 155 | 10527 | 2025-12-19T09:00:00 | Endelig vedtagelse |
| 176 | 10549 | 2026-01-29T10:00:00 | Endelig vedtagelse |
| 212 | 10567 | 2026-02-26T10:20:00 | Endelig vedtagelse |

## Summary

| Vote | Afstemning ID | Rows | For | Imod | Hverken | Fravær | Missing | Duplicates | Official totals match | Status |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 2 | 10379 | 179 | 59 | 51 | 0 | 69 | 0 | 0 | PASS | PASS |
| 23 | 10396 | 179 | 84 | 23 | 1 | 71 | 0 | 0 | PASS | PASS |
| 44 | 10453 | 179 | 20 | 74 | 4 | 81 | 0 | 0 | PASS | PASS |
| 68 | 10475 | 179 | 20 | 79 | 0 | 80 | 0 | 0 | PASS | PASS |
| 91 | 10496 | 179 | 11 | 87 | 0 | 81 | 0 | 0 | PASS | PASS |
| 112 | 10419 | 179 | 85 | 13 | 2 | 79 | 0 | 0 | PASS | PASS |
| 133 | 10506 | 179 | 92 | 14 | 0 | 73 | 0 | 0 | PASS | PASS |
| 155 | 10527 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | FAIL | FAIL |
| 176 | 10549 | 179 | 45 | 60 | 0 | 74 | 0 | 0 | PASS | PASS |
| 212 | 10567 | 179 | 87 | 23 | 0 | 69 | 0 | 0 | PASS | PASS |

## Per-vote details

- Vote 2 (`10379`): 2 OData pages, unique politicians `179`, duplicates `0`, missing IDs `0`, missing names `0`, missing parties `0`, unexpected categories `[]`, official totals `{'For': 59, 'Imod': 51, 'Hverken for eller imod': 0}`, failure reason `none`.
- Vote 23 (`10396`): 2 OData pages, unique politicians `179`, duplicates `0`, missing IDs `0`, missing names `0`, missing parties `0`, unexpected categories `[]`, official totals `{'For': 84, 'Imod': 23, 'Hverken for eller imod': 1}`, failure reason `none`.
- Vote 44 (`10453`): 2 OData pages, unique politicians `179`, duplicates `0`, missing IDs `0`, missing names `0`, missing parties `0`, unexpected categories `[]`, official totals `{'For': 20, 'Imod': 74, 'Hverken for eller imod': 4}`, failure reason `none`.
- Vote 68 (`10475`): 2 OData pages, unique politicians `179`, duplicates `0`, missing IDs `0`, missing names `0`, missing parties `0`, unexpected categories `[]`, official totals `{'For': 20, 'Imod': 79, 'Hverken for eller imod': 0}`, failure reason `none`.
- Vote 91 (`10496`): 2 OData pages, unique politicians `179`, duplicates `0`, missing IDs `0`, missing names `0`, missing parties `0`, unexpected categories `[]`, official totals `{'For': 11, 'Imod': 87, 'Hverken for eller imod': 0}`, failure reason `none`.
- Vote 112 (`10419`): 2 OData pages, unique politicians `179`, duplicates `0`, missing IDs `0`, missing names `0`, missing parties `0`, unexpected categories `[]`, official totals `{'For': 85, 'Imod': 13, 'Hverken for eller imod': 2}`, failure reason `none`.
- Vote 133 (`10506`): 2 OData pages, unique politicians `179`, duplicates `0`, missing IDs `0`, missing names `0`, missing parties `0`, unexpected categories `[]`, official totals `{'For': 92, 'Imod': 14, 'Hverken for eller imod': 0}`, failure reason `none`.
- Vote 155 (`10527`): 1 OData pages, unique politicians `0`, duplicates `0`, missing IDs `0`, missing names `0`, missing parties `0`, unexpected categories `[]`, official totals `{'For': 99, 'Imod': 3, 'Hverken for eller imod': 0}`, failure reason `No Stemme rows returned; OData inline count is zero`.
- Vote 176 (`10549`): 2 OData pages, unique politicians `179`, duplicates `0`, missing IDs `0`, missing names `0`, missing parties `0`, unexpected categories `[]`, official totals `{'For': 45, 'Imod': 60, 'Hverken for eller imod': 0}`, failure reason `none`.
- Vote 212 (`10567`): 2 OData pages, unique politicians `179`, duplicates `0`, missing IDs `0`, missing names `0`, missing parties `0`, unexpected categories `[]`, official totals `{'For': 87, 'Imod': 23, 'Hverken for eller imod': 0}`, failure reason `none`.

## Overall result: `FAIL`
