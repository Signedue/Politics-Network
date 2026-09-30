# Diagnostic Milestone 1C

## Scope

Only period metadata and bounded `Afstemning`/`Stemme?$top=1` existence checks were retrieved. No full session or voting history was downloaded.

## Diagnostic table

| Period | Sampled vote | Afstemning ID | Stemme rows | Status |
|---|---:|---:|---:|---|
| 20261 (2026-27) | ? | ? | ? | no Afstemning records in bounded sample |
| 20252 | 3 | 10571 | 1 | populated (at least 1) |
| 20252 | 43 | 10604 | 1 | populated (at least 1) |
| 20252 | 4 | 10572 | 1 | populated (at least 1) |
| 20251 | 2 | 10379 | 1 | populated (at least 1) |
| 20251 | 207 | 10570 | 1 | populated (at least 1) |
| 20251 | 3 | 10380 | 1 | populated (at least 1) |
| 20241 | 1 | 9913 | 1 | populated (at least 1) |
| 20241 | 533 | 10378 | 1 | populated (at least 1) |
| 20241 | 3 | 9914 | 1 | populated (at least 1) |
| 20231 | 1 | 9357 | 1 | populated (at least 1) |
| 20231 | 576 | 9912 | 1 | populated (at least 1) |
| 20231 | 4 | 9358 | 1 | populated (at least 1) |
| 20252 | 5 | 10573 | 1 | populated (at least 1) |
| 20252 | 6 | 10574 | 1 | populated (at least 1) |
| 20252 | 7 | 10575 | 1 | populated (at least 1) |
| 20251 | 5 | 10381 | 1 | populated (at least 1) |
| 20251 | 6 | 10382 | 1 | populated (at least 1) |
| 20251 | 7 | 10383 | 1 | populated (at least 1) |

## Conclusion

- Newest tested period with individual-vote data: `20252`.
- Newest tested period without individual-vote data: `none among periods with sampled Afstemning records`.
- `20261` had no sampled Afstemning records, so it was not classified as an empty Stemme period.
- Clear cutoff: `no`. Both `20252` and `20251` contain populated Stemme samples.
- The missing `Stemme` rows for target vote `Afstemning.id=10530` are a vote-level anomaly, not evidence that period `20251` lacks individual-vote data.
- Evidence sufficient to choose a historical session: `yes; 20251 is a viable historical session based on multiple populated samples, although vote 158 itself remains unusable through OData.`

A populated value means the top-1 existence query returned one row; it is not a full row count.
