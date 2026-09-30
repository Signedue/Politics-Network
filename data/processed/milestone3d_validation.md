# Milestone 3D validation report

## Null-model specification

- Source matrix: `milestone3c_session_matrix.csv`
- Valid votes: `168`
- Politicians: `188`
- Eligible pairs: `8794` with original n_shared >= `40`
- Simulations: `100`
- Random seed: `20260930` using NumPy `default_rng`
- For each vote, participation, absence, and missingness were held fixed; participating political positions were permuted independently.

## One-shuffle validation

- Marginal count mismatches: `0`
- One-shuffle validation: `PASS`
- n_shared mismatches across all simulations: `0`
- n_shared invariant validation: `PASS`

## Pair-level distributions

- Observed similarity: `{'count': 8794, 'min': 0.17391304347826086, 'p25': 0.5849056603773585, 'median': 0.7333333333333333, 'mean': 0.7407221052018973, 'p75': 1.0, 'max': 1.0}`
- Null mean similarity: `{'count': 8794, 'min': 0.6500000000000006, 'p25': 0.7109367836360431, 'median': 0.7364852941176467, 'mean': 0.746882417577012, 'p75': 0.7907207401032704, 'max': 0.8514285714285712}`
- Excess similarity: `{'count': 8794, 'min': -0.5004878048780486, 'p25': -0.1731297169811324, 'median': -0.04348333333333343, 'mean': -0.006160312375114653, 'p75': 0.20982742681047764, 'max': 0.3406060606060608}`
- z-scores: `{'count': 8794, 'min': -13.333315101148303, 'p25': -3.6022624496305666, 'median': -0.9441722286403578, 'mean': -0.056779660607993235, 'p75': 4.4318597496983365, 'max': 9.594218964360383}`

## Sanity-check examples

### High raw similarity, small excess

| A | B | Party A | Party B | n_shared | Observed | Null mean | Excess | z-score | Empirical p |
|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| 20385 | 20930 | M | S | 42 | 1.0000 | 0.8514 | 0.1486 | 3.2895 | 0.0099 |
| 18696 | 18715 | V | S | 43 | 1.0000 | 0.8416 | 0.1584 | 3.3326 | 0.0099 |
| 38 | 18715 | S | S | 44 | 1.0000 | 0.8416 | 0.1584 | 2.9601 | 0.0099 |

### High excess similarity

| A | B | Party A | Party B | n_shared | Observed | Null mean | Excess | z-score | Empirical p |
|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| 125 | 20349 | V | SP | 66 | 1.0000 | 0.6594 | 0.3406 | 6.5477 | 0.0099 |
| 208 | 20349 | S | SP | 66 | 1.0000 | 0.6600 | 0.3400 | 5.5292 | 0.0099 |
| 12 | 208 | S | S | 67 | 1.0000 | 0.6601 | 0.3399 | 5.7257 | 0.0099 |

### Observed similarity close to null expectation

| A | B | Party A | Party B | n_shared | Observed | Null mean | Excess | z-score | Empirical p |
|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1454 | 19000 | KF | SF | 56 | 0.7857 | 0.7859 | -0.0002 | -0.0036 | 0.4950 |
| 15760 | 20962 | S | SF | 51 | 0.7647 | 0.7645 | 0.0002 | 0.0038 | 0.5545 |
| 191 | 244 | RV | S | 50 | 0.7800 | 0.7798 | 0.0002 | 0.0038 | 0.5743 |

## Same-party / different-party excess similarity

- Same-party pairs: `1255`; mean `0.2536118611134912`; median `0.2634586466165413`
- Different-party pairs: `7539`; mean `-0.04940398895399784`; median `-0.06565789473684192`

## Decision

Yes, but not as a uniform upward shift in all pairwise similarities. The overall observed similarity distribution is close to the vote-preserving null expectation, while the positive same-party excess and negative different-party excess indicate that the mapping of positions to politicians contains structure beyond vote-level marginals. This supports proceeding to network construction as a separate, explicitly thresholded step.
This is descriptive only. No edge threshold, graph, community method, or causal interpretation was introduced.
