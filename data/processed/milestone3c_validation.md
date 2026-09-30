# Milestone 3C validation report

## Data scope and retrieval

- Session: `20251`
- Valid votes included: `168`
- The 24 coverage-audit votes with zero Stemme rows were excluded.
- Existing local Stemme data were reused for `56` votes.
- New complete paginated Stemme retrievals: `112` votes.
- No missing vote was scraped or replaced.

## Session matrix

- Dimensions: `188 politicians x 168 votes`
- Unique politicians: `188`
- Votes represented: `168`
- Category counts: `{'For': 9427, 'Imod': 7370, 'Hverken for eller imod': 436, 'Fravær': 12839}`
- Missing matrix values: `1512`

## Participation diagnostics

- Participation-rate distribution: `{'count': 188.0, 'mean': 0.5456243667679838, 'std': 0.3101750119159772, 'min': 0.0, '25%': 0.31398809523809523, '50%': 0.5476190476190477, '75%': 0.8214285714285714, 'max': 1.0}`
- Ten politicians with the fewest recorded rows:

| Politician ID | Name | Party | Recorded rows | Participated | Absent | Rate |
|---:|---|---|---:|---:|---:|---:|
| 21083 | Thorkild Holmboe-Hay | S | 2 | 2 | 0 | 0.012 |
| 21186 | Mads Madsen Henriksen | S | 2 | 2 | 0 | 0.012 |
| 21206 | Elvira Kûitse | N | 2 | 0 | 2 | 0.000 |
| 20917 | Tina Cartey Hansen | KF | 5 | 4 | 1 | 0.024 |
| 20379 | Tobias Grotkjær Elmstrøm | M | 7 | 0 | 7 | 0.000 |
| 17628 | Carl Valentin | SF | 16 | 13 | 3 | 0.077 |
| 20361 | Fie Hækkerup | S | 16 | 15 | 1 | 0.089 |
| 20380 | Monika Rubin | M | 16 | 10 | 6 | 0.060 |
| 217 | Lars Christian Lilleholt | V | 36 | 18 | 18 | 0.107 |
| 18698 | Marlene Ambo-Rasmussen | V | 132 | 66 | 66 | 0.393 |

## Pairwise n_shared distribution

- Min: `0`
- 25th percentile: `10.0`
- Median: `40.0`
- 75th percentile: `80.0`
- Max: `166`
- Pairs with n_shared >= 10: `75.30%`
- Pairs with n_shared >= 20: `65.83%`
- Pairs with n_shared >= 40: `50.03%`
- Pairs with n_shared >= 60: `36.30%`
- Pairs with n_shared >= 80: `25.16%`
- Pairs with n_shared >= 100: `18.35%`
- Pairs with n_shared >= 120: `10.89%`

## Similarity for n_shared >= 40

- Eligible pairs: `8794`
- Min: `0.17391304347826086`
- 25th percentile: `0.5849056603773585`
- Median: `0.7333333333333333`
- Mean: `0.7407221052018973`
- 75th percentile: `1.0`
- Max: `1.0`

## Same-party / different-party descriptive check

- Same-party pairs: `1255`; mean `0.9977834966073986`; median `1.0`
- Different-party pairs: `7539`; mean `0.6979296862850777`; median `0.6842105263157895`

## Stability check

- Split: first `84` and second `84` valid votes in sorted session order.
- Minimum n_shared within each half: `20`.
- Pairs meeting the requirement in both halves: `5945`.
- Pearson correlation of first-half and second-half similarities: `0.8984225981163778`.

## Decision

The full valid session provides enough shared participation and stability to proceed toward constructing a network.
This is a descriptive diagnostic only. No similarity cutoff, edge threshold, community method, or network layout was selected.
