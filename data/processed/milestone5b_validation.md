# Milestone 5B descriptive validation

## Scope and denominator definitions

- Reused only `milestone3c_session_matrix.csv`, `milestone4b_null_pairwise.csv`, `milestone4c_nodes.csv`, `milestone4c_edges.csv`, and `milestone5a_community_party_table.csv`.
- No new data were retrieved, no thresholds were changed, and no community detection was rerun.
- Observed population: all 188 politicians in the Milestone 3C session matrix.
- Participation count: number of `For`, `Imod`, or `Hverken for eller imod` values across 168 valid votes; `Fravær` is not participation.
- Inclusion denominator: 188 observed politicians; inclusion requires participation count >= 40.
- Eligible pair denominator: unordered pairs among included politicians with `n_shared >= 40` (8,794 pairs).
- Rule B edge denominator: the same eligible pairs; an edge additionally requires positive excess similarity and q < 0.05.

## Population reconciliation

- Observed politicians: `188` (expected 188)
- Included politicians: `150` (expected 150)
- Excluded politicians: `38` (expected 38)
- Included + excluded: `188`
- Participation rule: `participation_count >= 40`

## Party metadata quality

- Party labels are the official short labels carried into Milestone 3C from the actor biography `partyShortname` field.
- They are biography metadata values available in the retrieved actor records, not a reconstructed historical party-membership series for each vote.
- No historical party label was assigned silently; labels were reused exactly as stored in the validated matrix.
- Missing party labels: `0`
- Unknown/blank party labels by token check: `0`
- UFG labels: `6`
- Labels outside the documented known-label set: `[]`

## Overall participation distribution

- Participation count: min `0`, Q1 `52.75`, median `92.00`, Q3 `138.00`, max `168`, mean `91.66`.
- Participation rate: min `0.0000`, Q1 `0.3140`, median `0.5476`, Q3 `0.8214`, max `1.0000`, mean `0.5456`.

## Participation and inclusion by party

The following party-level inclusion rates are descriptive only. They identify how the >=40 rule changes representation; they do not interpret the cause of participation differences.
| party | observed_count | included_count | excluded_count | inclusion_rate | participation_count_min | participation_count_median | participation_count_max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ALT | 6 | 5 | 1 | 0.8333333333333334 | 1 | 78.0 | 149 |
| DD | 16 | 15 | 1 | 0.9375 | 38 | 80.5 | 159 |
| DF | 7 | 5 | 2 | 0.7142857142857143 | 7 | 89.0 | 144 |
| EL | 9 | 8 | 1 | 0.8888888888888888 | 32 | 76.0 | 163 |
| IA | 1 | 0 | 1 | 0.0 | 0 | 0.0 | 0 |
| JF | 1 | 0 | 1 | 0.0 | 1 | 1.0 | 1 |
| KF | 11 | 10 | 1 | 0.9090909090909091 | 4 | 92.0 | 158 |
| LA | 15 | 14 | 1 | 0.9333333333333333 | 1 | 126.0 | 162 |
| M | 14 | 9 | 5 | 0.6428571428571429 | 0 | 85.0 | 166 |
| N | 2 | 0 | 2 | 0.0 | 0 | 0.0 | 0 |
| RV | 6 | 5 | 1 | 0.8333333333333334 | 16 | 103.5 | 139 |
| S | 53 | 44 | 9 | 0.8301886792452831 | 1 | 127.0 | 168 |
| SF | 16 | 12 | 4 | 0.75 | 3 | 95.5 | 161 |
| SP | 1 | 1 | 0 | 1.0 | 72 | 72.0 | 72 |
| UFG | 6 | 4 | 2 | 0.6666666666666666 | 0 | 46.5 | 87 |
| V | 24 | 18 | 6 | 0.75 | 1 | 102.0 | 161 |

## Milestone 4C and 5A reconciliation

- Rule B nodes: `150` (expected 150)
- Rule B edges: `3086` (expected 3,086)
- Representative communities: `9` (expected 9)
- Representative community members: `150` (expected 150)
- Eligible pair rows used for party-pair summaries: `8794` (expected 8,794)
- Rule B edges represented in party-pair summaries: `3086` (expected 3,086)

## Community sizes and party diversity

| community | community_size | party_diversity |
| --- | --- | --- |
| 0 | 46 | 6 |
| 1 | 5 | 1 |
| 2 | 14 | 1 |
| 3 | 39 | 4 |
| 4 | 18 | 3 |
| 5 | 25 | 3 |
| 6 | 1 | 1 |
| 7 | 1 | 1 |
| 8 | 1 | 1 |

## Exclusion interpretation

- All `38` exclusions have the exact rule-based reason: participation count below `40`.
- Exclusion is descriptive and does not interpret why participation differs.

## Party-pair agreement interpretation

- Mean and median excess similarity summarize pairwise agreement relative to the existing vote-preserving null.
- Positive-excess fraction counts eligible politician pairs with excess similarity > 0.
- Rule B edge fraction counts only graph edges under the already validated Rule B definition; it is not the same quantity as positive excess fraction.
