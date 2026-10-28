# Milestone 6A full electoral-period voting data audit

- Study period: `2022-11-01` inclusive to `2026-03-24` exclusive.
- Relevant session records inspected: `20222, 20231, 20241, 20251`.
- Votes after actual-date filtering: `1569`.
- Individual Stemme rows retrieved: `263114`.

## Session and year summary

session  year  total_votes  votes_with_individual_records  votes_without_individual_records  unique_politicians  for_count  against_count  neither_count  absent_count  unknown_vote_type_count
  20222  2022           16                             16                                 0                 182       1557            157             13          1138                        0
  20222  2023          339                            339                                 0                 188      17835          18631            314         23901                        0
  20231  2023          189                            189                                 0                 193      12150           8441            184         13043                        0
  20231  2024          367                            367                                 0                 194      18316          19968           1066         26337                        0
  20241  2024          192                            145                                47                 191       9608           5880            261         10208                        0
  20241  2025          274                            246                                28                 197      15773          10328            555         17378                        0
  20251  2025          165                            146                                19                 184       7750           6729            381         11274                        0
  20251  2026           27                             22                                 5                 183       1677            641             55          1565                        0

## Coverage and missingness

- Votes without individual Stemme rows remain distinct from votes containing recorded `Fravær` rows.
- Votes without individual records: `99`.
- Recorded absence rows: `104844`.

## Actor consistency and metadata

- Unique actor IDs in registry: `236`.
- Actor records with missing names: `0`.
- Actor records with missing party labels: `0`.
- Duplicate actor/vote rows: `0`.
- Actor IDs with multiple name variants in retrieved metadata: `0`.
- Actor IDs with multiple party variants in retrieved metadata: `0`.

### Alex Vanopslagh (actor ID 18703)

 actor_id            name party first_observed_vote_date last_observed_vote_date  recorded_vote_rows  for_count  against_count  neither_count  absent_count  unknown_vote_type_count  name_variant_count  party_variant_count
    18703 Alex Vanopslagh    LA      2022-11-16T13:00:00     2026-02-26T10:20:00                1295         14             56              0          1225                        0                   1                    1

## Validation checks

- date_lower_boundary: `PASS`
- date_upper_boundary: `PASS`
- unique_vote_ids: `PASS`
- unique_actor_ids: `PASS`
- no_missing_names: `PASS`
- no_missing_parties: `PASS`
- no_duplicate_stemme_rows: `PASS`
- no_unknown_vote_types: `PASS`

## Limitations

- Party labels are extracted from actor biography metadata via `partyShortname`; this audit does not reconstruct historical party membership by vote date.
- The registry counts recorded Stemme rows. A missing vote record is not converted into `Fravær`.
- No participation threshold, similarity calculation, network construction, or community detection was applied.
