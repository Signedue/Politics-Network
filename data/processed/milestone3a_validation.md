# Milestone 3A validation report

## Data

Ten valid votes were used. Nine came from the locally stored Milestone 2 dataset; vote 3 (`Afstemning` 10380) was retrieved once because it was a valid covered vote not already present locally.

- Matrix dimensions: `188 politicians x 10 votes`
- Category counts: `{'For': 559, 'Imod': 475, 'Hverken for eller imod': 7, 'Fravær': 749}`
- Missing matrix values: `90`

## Deterministic pair selection

Politicians were sorted by party then politician ID. Pair A is the first two politicians in the first party with at least two politicians. Pairs B and C are the first two lexicographic pairs with different non-null parties.

## Pair results

### A_same_party: Torsten Gejl (ALT) vs Franciska Rosenkilde (ALT)

- Shared participated votes: `1`
- Same-position votes: `1`
- Similarity: `1 / 1 = 1.0`
- Diagnostic: `shared participated votes < 5`

### B_different_party: Torsten Gejl (ALT) vs Søren Espersen (DD)

- Shared participated votes: `4`
- Same-position votes: `1`
- Similarity: `1 / 4 = 0.25`
- Diagnostic: `shared participated votes < 5`

### C_different_party: Torsten Gejl (ALT) vs Peter Skaarup (DD)

- Shared participated votes: `1`
- Same-position votes: `1`
- Similarity: `1 / 1 = 1.0`
- Diagnostic: `shared participated votes < 5`

## Manual verification

For A_same_party: shared participated votes = 1; same positions = 1; similarity = 1 / 1 = 1.0. The programmatic result matches this calculation.
