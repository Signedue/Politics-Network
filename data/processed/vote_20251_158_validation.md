# Milestone 1 validation report

- OData vote ID: `10530`
- Session code: `20251`
- Vote number: `158`

## OData model

Afstemning -> Stemme -> Aktør and Stemmetype; Afstemning -> Møde -> Periode. Aktør.gruppenavnkort is the party abbreviation.

## Validation

- Number of rows: `0`
- Number of unique politicians: `0`
- Duplicate politician/vote combinations: `0`
- Missing politician IDs: `0`
- Missing politician names: `0`
- Missing party values: `0`
- Vote category counts: `{}`
- Unexpected vote categories: `[]`
- Official totals: `{'For': 74, 'Imod': 4, 'Hverken for eller imod': 23, 'Fravær': 79}`
- Totals match official page: `False`

## Discrepancy

The official OData `Stemme` response contains zero rows for this vote.
Therefore no politician-level records or five-politician manual sample
can be produced from the permitted data source.
