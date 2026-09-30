# Milestone 4C candidate Rule B network audit

## Provisional graph definition

- Nodes: politicians with at least 40 participated votes.
- Pair eligibility: n_shared >= 40.
- Edge rule: excess_similarity > 0 and Benjamini-Hochberg q < 0.05.
- Edge weight: excess_similarity.
- Party labels were retained as metadata only and did not affect construction.

## Basic validation

- Eligible politicians: `150` (expected `150`)
- Edges: `3086` (expected `3086`)
- Nodes with at least one edge: `147` (expected `147`)
- Isolates: `3` (expected `3`)
- Components: `6` (expected `6`)
- Giant component: `117` nodes (expected `117`)
- Validation status: **PASS**

## Basic network statistics

- Nodes: `150`
- Edges: `3086`
- Density: `0.276152`
- Connected components: `6`
- Isolates: `3`
- Giant-component size: `117`
- Mean degree: `41.14666666666667`
- Median degree: `50.0`
- Minimum degree: `0`
- Maximum degree: `82`
- Mean node strength: `10.054573405588759`
- Median node strength: `9.80438161128135`
- Minimum node strength: `0.0`
- Maximum node strength: `20.725283489450057`

## Distribution descriptions

- Degree summary: `{'min': 0.0, 'p25': 8.0, 'median': 50.0, 'mean': 41.14666666666667, 'p75': 75.75, 'max': 82.0}`; skewness `-0.011982942784660817`; descriptively **narrow**.
- Strength summary: `{'min': 0.0, 'p25': 1.8106433443938448, 'median': 9.80438161128135, 'mean': 10.054573405588759, 'p75': 19.606533963079286, 'max': 20.725283489450057}`; skewness `0.11367956182655882`; descriptively **narrow**.
These descriptions are not claims of a power-law or heavy-tail mechanism.

## Component audit

|   component |   nodes |   edges | party_composition                                                                    |
|------------:|--------:|--------:|:-------------------------------------------------------------------------------------|
|           1 |     117 |    2993 | {'DD': 15, 'KF': 10, 'LA': 14, 'M': 9, 'RV': 5, 'S': 44, 'SP': 1, 'UFG': 1, 'V': 18} |
|           2 |      25 |      85 | {'ALT': 5, 'EL': 8, 'SF': 12}                                                        |
|           3 |       5 |       8 | {'DF': 5}                                                                            |
|           4 |       1 |       0 | {'UFG': 1}                                                                           |
|           5 |       1 |       0 | {'UFG': 1}                                                                           |
|           6 |       1 |       0 | {'UFG': 1}                                                                           |

## Isolates

|   politician_id | politician_name     | party   |   participation_count |   eligible_n_shared_ge_40_partners |
|----------------:|:--------------------|:--------|----------------------:|-----------------------------------:|
|           18724 | Lars Boje Mathiesen | UFG     |                    87 |                                126 |
|           20383 | Jeppe Søe           | UFG     |                    43 |                                 33 |
|           20390 | Mike Villa Fonseca  | UFG     |                    73 |                                110 |

## Edge-weight audit

- Excess-similarity distribution: `{'min': 0.0884929577464807, 'p25': 0.2040983899821156, 'median': 0.2587789598108739, 'mean': 0.24435936662966848, 'p75': 0.2809487656981037, 'max': 0.3361641791044784}`
- Same-party edge fraction: `0.4053791315618924`
- Different-party edge fraction: `0.5946208684381076`

## Rule C robustness comparison

- Rule C edges: `3025`
- Eligible-node overlap: `1.0`
- Active-node overlap: `0.9931972789115646`
- Edge overlap: `3025`
- Edge-set Jaccard similarity: `0.9802333117303953`
- Giant-component sizes: Rule B `117`, Rule C `88`
- Giant-component membership overlap (Jaccard): `0.7521367521367521`

## Decision

The Rule B graph reproduces the Milestone 4B validation counts exactly. Rule C has a smaller edge set and giant component, so the broad topology should be checked for sensitivity to q=0.05 versus q=0.01 before any higher-level network method is applied. This milestone is descriptive; no centrality ranking, community detection, modularity, ideology inference, or final network claim was made.
