# Diagnostic Milestone 1B

## Conclusion

The target vote record exists and the filter field is correct. The OData `Stemme` entity is populated for older data, but the target vote and the checked current-period/nearby records return no individual rows. Within these minimal checks, the discrepancy is missing individual-vote rows in the API for this vote/current period, not an invalid target ID or malformed field filter.

## Diagnostic table

| Test | Expected | Observed | Pass/Fail | Interpretation |
|---|---|---|---|---|
| 1 | Full target Afstemning record exists | Afstemning(10530) returned fields ['id', 'kommentar', 'konklusion', 'mødeid', 'nummer', 'opdateringsdato', 'sagstrinid', 'typeid', 'vedtaget'] | Pass | The target vote record exists. |
| 2 | Small unfiltered Stemme sample returns rows and fields | 5 rows; fields ['afstemningid', 'aktørid', 'id', 'opdateringsdato', 'typeid'] | Pass | The Stemme endpoint and schema are populated. |
| 3 | afstemningid is exact numeric link field | metadata afstemningid=Edm.Int32; navigation=Afstemning, Akt?r, Stemmetype | Pass | The original field name and type are confirmed. |
| 4 | 20251 or nearby Afstemning IDs have Stemme rows | current-period meeting vote IDs [10543, 10542, 10541, 10540, 10539]; latest checked 10543: 0; nearby counts {'10529': 0, '10530': 0, '10531': 0} | Fail | Compares the target with current-period and adjacent vote IDs. |
| 5 | Older control vote has Stemme rows | control Afstemning 1: 1 row(s) | Pass | Confirms the endpoint/filter work for an older published vote. |

## Exact schema findings

- `Stemme.afstemningid`: `Edm.Int32`
- `Stemme.akt?rid`: `Edm.Int32`
- `Stemme.typeid`: `Edm.Int32`
- Navigation properties: `Afstemning`, `Akt?r`, `Stemmetype`

## Target record (all fields)

```json
{
  "odata.metadata": "https://oda.ft.dk/api/$metadata#Afstemning/@Element",
  "id": 10530,
  "nummer": 158,
  "konklusion": "Forslaget er vedtaget.\nFor stemte 74 (S, V, SF, M, KF, RV, ALT, Jeppe Søe (UFG) og Jon Stephensen (UFG)),\nimod stemte 4 (EL),\nhverken for eller imod stemte 23 (DD, LA, DF og Mike Villa Fonseca (UFG)).",
  "vedtaget": true,
  "kommentar": null,
  "mødeid": 15470,
  "typeid": 1,
  "sagstrinid": 269789,
  "opdateringsdato": "2025-12-19T09:32:16.467"
}
```

## Control record (all fields)

```json
{
  "odata.metadata": "https://oda.ft.dk/api/$metadata#Afstemning/@Element",
  "id": 1,
  "nummer": 411,
  "konklusion": "Vedtaget\n\n108 stemmer for forslaget (V, S, DF, RV, SF, EL, LA, KF, UFG)\n\n0 stemmer imod forslaget\n\n0 stemmer hverken for eller imod forslaget\n\n",
  "vedtaget": true,
  "kommentar": null,
  "mødeid": 17,
  "typeid": 2,
  "sagstrinid": null,
  "opdateringsdato": "2014-09-09T09:05:59.653"
}
```

