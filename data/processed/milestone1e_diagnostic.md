# Diagnostic Milestone 1E

## Test | Observation | Interpretation | Confidence

| Test | Observation | Interpretation | Confidence |
|---|---|---|---|
| 1. Target Afstemning | `Afstemning(10379)` has `nummer=2`, `typeid=3`, `m?deid=15443`, `sagstrinid=268868`, and `vedtaget=true`; `Afstemningstype(3)` is `Forslag til vedtagelse`; the meeting is a plenary meeting in period `20251`. | The record identifies a formal adoption proposal in a plenary meeting. No field states that individual votes are absent; this requires checking the `Stemme` relation. | High |
| 2. Raw Stemme response | Initial response returned 100 rows, all unique by `id` and `akt?rid`, with type IDs 1, 2, and 3. It included `odata.nextLink`. `$inlinecount=allpages` returned `odata.count=179`; `$skip=100` returned 79 more rows. | Exactly 100 was the first server page, not the complete result. The retrieval was truncated by OData pagination. | High |
| 3. Actors | The first 100 rows join to 100 actors, all `Akt?rtype.id=5` (`Person`). | The rows represent individual persons, not groups or committees. | High |
| 4. Population | The complete target-vote result has 179 `Stemme` rows. The official aggregate reports 110 votes cast. `Frav?r` is an explicit `Stemmetype` category in the official lookup. | The `Stemme` entity includes both cast votes and absent persons; it is not limited to the 110 votes cast. | High |
| 5. Arithmetic | Complete category counts after following pagination: `{'Fravær': 69, 'Imod': 51, 'For': 59}`. | `59 For + 51 Imod + 0 Neither + 69 Frav?r = 179`; the 110 cast votes match the official aggregate, and the remaining 69 rows are absences. | High |

## Conclusion

**A. discrepancy explained and pipeline can be corrected.** The 100-row discrepancy was caused by server-side OData pagination. The initial response was only page one. The complete target-vote population is 179 individual person actors: 59 `For`, 51 `Imod`, 0 `Hverken for eller imod`, and 69 `Frav?r`. The 110 cast votes now reproduce the official aggregate exactly; `Frav?r` represents the additional persons with a `Stemme` row but no cast vote.
