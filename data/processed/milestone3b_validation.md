# Milestone 3B validation report

## Selection

The Milestone 2B audit was filtered to votes with individual Stemme data, sorted by date, vote number, and Afstemning ID, and positions `round(i * (n - 1) / 49)` were selected. Exactly 50 valid votes were used.
Individual-vote data were already local for `4` votes; only `46` selected votes were retrieved.

## Matrix

- Dimensions: `188 politicians x 50 votes`
- Unique politicians: `188`
- Category counts: `{'For': 2924, 'Imod': 2077, 'Hverken for eller imod': 145, 'Fravær': 3804}`
- Missing values: `450`

## n_shared distribution

- Min: `0`
- 25th percentile: `3.0`
- Median: `12.0`
- 75th percentile: `24.0`
- Max: `50`
- Pair percentage with n_shared >= 5: `70.82%`
- Pair percentage with n_shared >= 10: `56.34%`
- Pair percentage with n_shared >= 20: `33.27%`
- Pair percentage with n_shared >= 30: `17.88%`
- Pair percentage with n_shared >= 40: `5.71%`

## Similarity for n_shared >= 20

- Eligible pairs: `5848`
- Min: `0.05`
- 25th percentile: `0.5277777777777778`
- Median: `0.7333333333333333`
- 75th percentile: `1.0`
- Max: `1.0`
- Mean: `0.7332349063551902`

## Same-party vs different-party

- Same-party pairs: `874`; mean `0.9984676386381865`; median `1.0`
- Same-party distribution: `{'count': 874.0, 'mean': 0.9984676386381865, 'std': 0.006905729214147652, 'min': 0.95, '25%': 1.0, '50%': 1.0, '75%': 1.0, 'max': 1.0}`
- Different-party pairs: `4974`; mean `0.6866298786078361`; median `0.6923076923076923`
- Different-party distribution: `{'count': 4974.0, 'mean': 0.6866298786078361, 'std': 0.2210276667283637, 'min': 0.05, '25%': 0.5, '50%': 0.6923076923076923, '75%': 0.8857142857142857, 'max': 1.0}`

## High similarity / low information

- Pairs with similarity >= 0.90 and n_shared < 5: `1775`
- Example: `12` vs `38`, n_shared `1`, similarity `1.0`
- Example: `12` vs `43`, n_shared `1`, similarity `1.0`
- Example: `12` vs `57`, n_shared `1`, similarity `1.0`
- Example: `12` vs `109`, n_shared `1`, similarity `1.0`
- Example: `12` vs `118`, n_shared `2`, similarity `1.0`

## Decision

50 votes still leave shared participation too sparse for most politician pairs to estimate voting similarity robustly: the median n_shared is 12 and only 33.27% of pairs reach n_shared >= 20. A larger valid sample would be required; this is a descriptive result, not a causal claim or a network-threshold recommendation.
