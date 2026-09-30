"""Retrieve and validate one Folketinget vote from the official OData API."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
import requests


API_BASE = "https://oda.ft.dk/api"
SESSION_CODE = "20251"
VOTE_NUMBER = 2
EXPECTED_TOTALS = {
    "For": 59,
    "Imod": 51,
    "Hverken for eller imod": 0,
    "Fravær": 69,
}
OUTPUT_COLUMNS = [
    "politician_id",
    "politician_name",
    "party",
    "period",
    "vote_number",
    "afstemning_id",
    "vote_category",
]
ALLOWED_CATEGORIES = set(EXPECTED_TOTALS)
MAX_PAGES = 1000

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"


def fetch_odata(
    resource: str,
    params: dict[str, str | int] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Fetch all pages from an OData endpoint by following ``odata.nextLink``."""
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    url = f"{API_BASE}/{resource}"
    pages: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for page_number in range(1, MAX_PAGES + 1):
        if url in seen_urls:
            raise RuntimeError(f"Pagination loop detected while requesting {url}")
        seen_urls.add(url)
        try:
            response = session.get(
                url,
                params=params if page_number == 1 else None,
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"OData request failed for {url}: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"OData returned invalid JSON for {url}") from exc

        if not isinstance(payload.get("value"), list):
            raise RuntimeError(f"OData response has no list-valued 'value': {url}")
        pages.append(payload)
        rows.extend(payload["value"])

        next_url = payload.get("odata.nextLink")
        if not next_url:
            return rows, pages, page_number
        url = next_url

    raise RuntimeError(f"Exceeded pagination safety limit of {MAX_PAGES} pages")


def save_raw(filename: str, payload: Any) -> None:
    (RAW_DIR / filename).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def party_shortname(actor: dict[str, Any]) -> str | None:
    """Read the official party shortname from the actor record."""
    if actor.get("gruppenavnkort"):
        return actor["gruppenavnkort"]
    match = re.search(
        r"<partyShortname>(.*?)</partyShortname>",
        actor.get("biografi") or "",
    )
    return match.group(1) if match else None


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    periods, period_pages, _ = fetch_odata(
        "Periode",
        {"$filter": f"kode eq '{SESSION_CODE}' and type eq 'samling'"},
    )
    save_raw("periode_20251.json", {"value": periods, "pages": period_pages})
    if len(periods) != 1:
        raise RuntimeError(
            f"Expected one parliamentary period for {SESSION_CODE}, found {len(periods)}."
        )
    period_id = periods[0]["id"]

    votes, vote_pages, _ = fetch_odata(
        "Afstemning",
        {
            "$filter": f"nummer eq {VOTE_NUMBER} and Møde/Periode/id eq {period_id}",
            "$expand": "Møde",
        },
    )
    save_raw("afstemning_20251_2.json", {"value": votes, "pages": vote_pages})
    if len(votes) != 1:
        raise RuntimeError(f"Expected one vote {VOTE_NUMBER}, found {len(votes)}.")
    vote = votes[0]
    vote_id = vote["id"]

    stem_rows, stem_pages, stem_page_count = fetch_odata(
        "Stemme", {"$filter": f"afstemningid eq {vote_id}"}
    )
    save_raw(
        f"stemme_{vote_id}.json",
        {"value": stem_rows, "pages": stem_pages, "page_count": stem_page_count},
    )

    vote_types, type_pages, _ = fetch_odata("Stemmetype", {"$top": 20})
    save_raw("stemmetype.json", {"value": vote_types, "pages": type_pages})
    vote_type_by_id = {item["id"]: item["type"] for item in vote_types}

    actor_ids = sorted({row["aktørid"] for row in stem_rows})
    actors: list[dict[str, Any]] = []
    for start in range(0, len(actor_ids), 10):
        actor_batch = actor_ids[start : start + 10]
        batch, _, _ = fetch_odata(
            "Aktør",
            {"$filter": " or ".join(f"id eq {actor_id}" for actor_id in actor_batch)},
        )
        actors.extend(batch)
    save_raw(f"aktør_{vote_id}.json", {"value": actors})

    actor_by_id = {item["id"]: item for item in actors}
    rows = [
        {
            "politician_id": stem["aktørid"],
            "politician_name": actor_by_id.get(stem["aktørid"], {}).get("navn"),
            "party": party_shortname(actor_by_id.get(stem["aktørid"], {})),
            "period": SESSION_CODE,
            "vote_number": vote["nummer"],
            "afstemning_id": vote_id,
            "vote_category": vote_type_by_id.get(stem["typeid"]),
        }
        for stem in stem_rows
    ]
    result = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    result.to_csv(PROCESSED_DIR / "vote_20251_2.csv", index=False)

    observed_counts = result["vote_category"].value_counts().to_dict()
    counts = {category: observed_counts.get(category, 0) for category in EXPECTED_TOTALS}
    duplicate_count = result.duplicated(["politician_id", "afstemning_id"]).sum()
    missing_ids = result["politician_id"].isna().sum()
    missing_names = result["politician_name"].isna().sum()
    missing_parties = result["party"].isna().sum()
    unexpected = sorted(set(result["vote_category"].dropna()) - ALLOWED_CATEGORIES)
    checks = {
        "total_rows": len(result) == 179,
        "unique_politicians": result["politician_id"].nunique() == 179,
        "duplicate_politician_vote_rows": duplicate_count == 0,
        "missing_politician_ids": missing_ids == 0,
        "missing_names": missing_names == 0,
        "missing_parties": missing_parties == 0,
        "category_counts": counts == EXPECTED_TOTALS,
        "unexpected_categories": not unexpected,
    }
    passed = all(checks.values())

    report = [
        "# Milestone 1 validation report",
        "",
        f"- Period: `{SESSION_CODE}`",
        f"- Vote number: `{VOTE_NUMBER}`",
        f"- Afstemning ID: `{vote_id}`",
        f"- OData Stemme pages followed: `{stem_page_count}`",
        "",
        "## Validation",
        "",
        f"- Total individual rows: `{len(result)}` (expected `179`)",
        f"- Unique politicians: `{result['politician_id'].nunique()}` (expected `179`)",
        f"- Duplicate politician/vote combinations: `{duplicate_count}`",
        f"- Missing politician IDs: `{missing_ids}`",
        f"- Missing names: `{missing_names}`",
        f"- Missing parties: `{missing_parties}`",
        f"- Counts by vote category: `{counts}`",
        f"- Unexpected vote categories: `{unexpected}`",
        "",
        "## Check results",
        "",
    ]
    report.extend(f"- {name}: `{'PASS' if value else 'FAIL'}`" for name, value in checks.items())
    report.extend(["", f"## Overall result: `{'PASS' if passed else 'FAIL'}`", ""])
    (PROCESSED_DIR / "vote_20251_2_validation.md").write_text(
        "\n".join(report), encoding="utf-8"
    )

    print(f"OData Stemme pages followed: {stem_page_count}")
    print(json.dumps(
        {
            "total_rows": len(result),
            "unique_politicians": int(result["politician_id"].nunique()),
            "duplicate_politician_vote_rows": int(duplicate_count),
            "missing_politician_ids": int(missing_ids),
            "missing_names": int(missing_names),
            "missing_parties": int(missing_parties),
            "counts_by_vote_category": counts,
            "unexpected_categories": unexpected,
        },
        ensure_ascii=False,
        indent=2,
    ))
    if not passed:
        raise RuntimeError("Milestone 1 validation failed; see the validation report.")
    print("MILESTONE 1: PASS")


if __name__ == "__main__":
    main()
