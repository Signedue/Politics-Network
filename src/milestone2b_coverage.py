"""Audit individual-vote coverage across all Afstemning records in 20251."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from milestone1_retrieve_vote import fetch_odata


SESSION_CODE = "20251"
API_BASE = "https://oda.ft.dk/api"
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "milestone2b"
PROCESSED_DIR = ROOT / "data" / "processed"


def count_stemme(afstemning_id: int) -> tuple[int, dict[str, Any]]:
    """Return the server-reported Stemme count without retrieving rows."""
    response = requests.get(
        f"{API_BASE}/Stemme",
        params={
            "$filter": f"afstemningid eq {afstemning_id}",
            "$top": 0,
            "$inlinecount": "allpages",
        },
        headers={"Accept": "application/json"},
        timeout=30,
    )
    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Stemme count request failed for Afstemning {afstemning_id}: {exc}"
        ) from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Stemme count response was not valid JSON for Afstemning {afstemning_id}"
        ) from exc
    if "odata.count" not in payload:
        raise RuntimeError(
            f"Stemme count response lacked odata.count for Afstemning {afstemning_id}"
        )
    return int(payload["odata.count"]), payload


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    periods, period_pages, _ = fetch_odata(
        "Periode",
        {"$filter": f"kode eq '{SESSION_CODE}' and type eq 'samling'"},
    )
    if len(periods) != 1:
        raise RuntimeError(f"Expected one session period, found {len(periods)}")
    period_id = periods[0]["id"]
    save_json(RAW_DIR / "period.json", {"value": periods, "pages": period_pages})

    votes, vote_pages, _ = fetch_odata(
        "Afstemning",
        {
            "$filter": f"Møde/Periode/id eq {period_id}",
            "$expand": "Møde,Afstemningstype",
        },
    )
    save_json(
        RAW_DIR / "afstemning_metadata.json",
        {"value": votes, "pages": vote_pages},
    )

    records: list[dict[str, Any]] = []
    count_responses: list[dict[str, Any]] = []
    for vote in votes:
        meeting = vote.get("Møde") or {}
        vote_type = vote.get("Afstemningstype") or {}
        count, raw_count = count_stemme(vote["id"])
        count_responses.append(
            {"afstemning_id": vote["id"], "response": raw_count}
        )
        records.append(
            {
                "vote_number": vote.get("nummer"),
                "afstemning_id": vote["id"],
                "date": meeting.get("dato"),
                "afstemningstype": vote_type.get("type"),
                "meeting_id": vote.get("mødeid"),
                "meeting_number": meeting.get("nummer"),
                "stemme_count": count,
                "has_individual_votes": count > 0,
            }
        )

    audit = pd.DataFrame(records).sort_values(
        ["date", "vote_number", "afstemning_id"]
    )
    audit.to_csv(PROCESSED_DIR / "milestone2b_coverage.csv", index=False)
    save_json(RAW_DIR / "stemme_count_responses.json", count_responses)

    total = len(audit)
    with_data = int(audit["has_individual_votes"].sum())
    without_data = total - with_data
    coverage = (with_data / total * 100) if total else 0
    if coverage >= 95:
        classification = "HIGH COVERAGE"
    elif coverage >= 80:
        classification = "PARTIAL COVERAGE"
    else:
        classification = "LOW COVERAGE"

    missing = audit[~audit["has_individual_votes"]]
    date_counts = Counter(missing["date"].str[:10].fillna("missing date"))
    meeting_counts = Counter(missing["meeting_id"])
    type_counts = Counter(missing["afstemningstype"].fillna("missing type"))
    report = [
        "# Milestone 2B session coverage audit",
        "",
        "## Method",
        "",
        f"All `{total}` `Afstemning` records linked to session `{SESSION_CODE}` "
        "were retrieved as metadata. For each record, the API was queried with "
        "`Stemme?$top=0&$inlinecount=allpages`; no individual `Stemme` rows were "
        "downloaded.",
        "",
        "## Coverage summary",
        "",
        f"- Total Afstemning records: `{total}`",
        f"- Records with Stemme data: `{with_data}`",
        f"- Records with zero Stemme rows: `{without_data}`",
        f"- Percentage with individual-vote data: `{coverage:.2f}%`",
        f"- Classification: **{classification}**",
        "",
        "## Votes with zero Stemme rows",
        "",
        "| Vote | Afstemning ID | Date | Afstemningstype | Meeting ID |",
        "|---:|---:|---|---|---:|",
    ]
    for row in missing.itertuples(index=False):
        report.append(
            f"| {row.vote_number} | {row.afstemning_id} | {row.date or ''} | "
            f"{row.afstemningstype or ''} | {row.meeting_id} |"
        )
    report.extend(
        [
            "",
            "## Metadata pattern check",
            "",
            f"- Missing votes by date: `{dict(date_counts)}`",
            f"- Missing votes by meeting: `{dict(meeting_counts)}`",
            f"- Missing votes by Afstemningstype: `{dict(type_counts)}`",
            "",
            "The audit identifies clustering only through the metadata above. "
            "It does not infer a cause or replace missing records.",
            "",
            "## Decision",
            "",
            f"Session `20251` is classified as **{classification}** under the "
            "specified threshold rule.",
            "The session is suitable for the project only with the documented "
            "missing votes excluded from any later analysis; missing votes must "
            "not be silently replaced or treated as observed individual votes.",
        ]
    )
    (PROCESSED_DIR / "milestone2b_coverage_report.md").write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
    )

    print(f"Total Afstemning records: {total}")
    print(f"Records with Stemme data: {with_data}")
    print(f"Records with zero Stemme rows: {without_data}")
    print(f"Percentage with individual-vote data: {coverage:.2f}%")
    print(f"Classification: {classification}")
    print("Votes with zero Stemme rows:")
    print(missing[["vote_number", "afstemning_id", "date", "afstemningstype", "meeting_id"]].to_string(index=False))


if __name__ == "__main__":
    main()
