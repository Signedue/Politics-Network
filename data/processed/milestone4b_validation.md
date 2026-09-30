# Milestone 4B significance-based network audit

## Provisional node rule

This test uses `participated votes >= 40` provisionally. It retains `150` politicians, every retained politician has at least 16 eligible n_shared>=40 partners, and none has fewer than 5 eligible partners. This is not the only valid node definition.

## Pair eligibility and null precision

- Eligible pairs: `8794`
- Null simulations: `1000`
- Random seed: `20260930` using NumPy `default_rng`
- The vote-preserving shuffle fixed participation, absence, missingness, and the three participating-position counts within every vote.
- Marginal-count mismatches: `0`
- `n_shared` was verified unchanged in every simulation.

## Candidate edge rules

|   nodes_with_edges |   edges |   density |   isolates |   connected_components |   giant_component_size |   median_degree |   weight_min |   weight_p25 |   weight_median |   weight_mean |   weight_p75 |   weight_max |   same_party_fraction |   different_party_fraction | construction                         |   sign_stable_fraction |   sign_estimable_edges |
|-------------------:|--------:|----------:|-----------:|-----------------------:|-----------------------:|----------------:|-------------:|-------------:|----------------:|--------------:|-------------:|-------------:|----------------------:|---------------------------:|:-------------------------------------|-----------------------:|-----------------------:|
|                148 |    3188 |  0.28528  |          2 |                      4 |                    143 |            50.5 |    0.0668167 |     0.200996 |        0.257015 |      0.239625 |     0.279734 |     0.336164 |              0.392723 |                   0.607277 | A: excess > 0 and empirical p < 0.05 |               0.999165 |                   2396 |
|                147 |    3086 |  0.276152 |          3 |                      6 |                    117 |            50   |    0.088493  |     0.204098 |        0.258779 |      0.244359 |     0.280949 |     0.336164 |              0.405379 |                   0.594621 | B: excess > 0 and q < 0.05           |               1        |                   2349 |
|                146 |    3025 |  0.270694 |          4 |                     10 |                     88 |            50   |    0.121923  |     0.206659 |        0.259544 |      0.246771 |     0.281785 |     0.336164 |              0.412893 |                   0.587107 | C: excess > 0 and q < 0.01           |               1        |                   2330 |

## Excess-similarity effect sizes

- **A: excess > 0 and empirical p < 0.05**: `{'min': 0.06681666666666608, 'p25': 0.2009964788732339, 'median': 0.2570154761904757, 'mean': 0.23962453541926398, 'p75': 0.27973405253282846, 'max': 0.3361641791044784}`
- **B: excess > 0 and q < 0.05**: `{'min': 0.0884929577464807, 'p25': 0.20409838998211569, 'median': 0.2587789598108739, 'mean': 0.24435936662966848, 'p75': 0.28094876569810373, 'max': 0.3361641791044784}`
- **C: excess > 0 and q < 0.01**: `{'min': 0.1219230769230718, 'p25': 0.20665853658536837, 'median': 0.25954411764705787, 'mean': 0.24677115029325897, 'p75': 0.28178461538461097, 'max': 0.3361641791044784}`

## Half-session sign stability

- First and second halves contain `84` valid votes each.
- Half-level minimum n_shared for estimability: `20`.
- **A: excess > 0 and empirical p < 0.05**: `2396` estimable edges; stable-sign fraction `0.9991652754590985`
- **B: excess > 0 and q < 0.05**: `2349` estimable edges; stable-sign fraction `1.0`
- **C: excess > 0 and q < 0.01**: `2330` estimable edges; stable-sign fraction `1.0`

## Comparison with Milestone 4A

The significance rules are grounded in the vote-preserving null model, unlike arbitrary excess cutoffs. Rule A uses uncorrected empirical p-values and therefore does not control the false-discovery rate. Rules B and C apply Benjamini-Hochberg correction and should be compared with Milestone 4A's global thresholds and disparity backbones using the reported connectivity, effect sizes, and stability rather than visual density.

## Decision

Among these choices, FDR-adjusted rules are methodologically more defensible than the uncorrected rule because they account for the thousands of simultaneous pair tests. Rule B (q<0.05) appears to offer the clearest balance here: it retains substantial connectivity, has a minimum retained-edge excess of about 0.088, and has complete sign stability among estimable retained edges. Rule C (q<0.01) is more conservative but fragments the giant component further, while Rule A lacks FDR control. Relative to Milestone 4A, the significance rules are better null-grounded than global cutoffs or disparity filtering, but no final network was selected because node eligibility, effect-size adequacy, connectivity, and half-session sign stability remain separate empirical decisions.

Party labels were used only for descriptive validation and did not affect null simulations or edge construction.
