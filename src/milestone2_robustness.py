"""Test the paginated individual-vote pipeline on ten 20251 votes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from milestone1_retrieve_vote import fetch_odata, party_shortname


SESSION_CODE = "20251"
SAMPLE_SIZE = 10
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "milestone2"
PROCESSED_DIR = ROOT / "data" / "processed"

CATEGORIES = ("For", "Imod", "Hverken for eller imod", "Fravær")
OUTPUT_COLUMNS = [
    "politician_id",
    "politician_name",
    "party",
    "period",
    "vote_number",
    "afstemning_id",
    "vote_category",
]


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_official_totals(conclusion: str | None) -> dict[str, int] | None:
    if not conclusion:
        return None
    patterns = {
        "For": r"for\s+stemte\s+(\d+)",
        "Imod": r"imod\s+stemte\s+(\d+)",
        "Hverken for eller imod": r"hverken\s+for\s+eller\s+imod\s+stemte\s+(\d+)",
    }
    totals: dict[str, int] = {}
    for category, pattern in patterns.items():
        match = re.search(pattern, conclusion, flags=re.IGNORECASE)
        if match:
            totals[category] = int(match.group(1))
    return totals if len(totals) == 3 else None


def meeting_date(vote: dict[str, Any]) -> str:
    meeting = vote.get("Møde") or {}
    return meeting.get("dato") or ""


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    periods, period_pages, _ = fetch_odata(
        "Periode",
        {"$filter": f"kode eq '{SESSION_CODE}' and type eq 'samling'"},
    )
    if len(periods) != 1:
        raise RuntimeError(f"Expected one {SESSION_CODE} session period, found {len(periods)}")
    period_id = periods[0]["id"]
    save_json(RAW_DIR / "period.json", {"value": periods, "pages": period_pages})

    votes, vote_pages, _ = fetch_odata(
        "Afstemning",
        {
            "$filter": f"Møde/Periode/id eq {period_id}",
            "$expand": "Møde,Afstemningstype",
        },
    )
    save_json(RAW_DIR / "all_vote_metadata.json", {"value": votes, "pages": vote_pages})
    if len(votes) < SAMPLE_SIZE:
        raise RuntimeError(f"Expected at least {SAMPLE_SIZE} votes, found {len(votes)}")

    ordered_votes = sorted(
        votes,
        key=lambda vote: (meeting_date(vote), vote.get("nummer", 0), vote["id"]),
    )
    selected_positions = [
        round(index * (len(ordered_votes) - 1) / (SAMPLE_SIZE - 1))
        for index in range(SAMPLE_SIZE)
    ]
    selected_votes = [ordered_votes[position] for position in selected_positions]
    save_json(
        RAW_DIR / "selected_votes.json",
        {
            "method": (
                "Sort all 20251 Afstemning records by meeting date, vote number, "
                "and Afstemning ID; select ten positions evenly spaced from first "
                "through last using round(i * (n - 1) / 9)."
            ),
            "positions": selected_positions,
            "votes": selected_votes,
        },
    )

    vote_types, type_pages, _ = fetch_odata("Stemmetype", {"$top": 20})
    save_json(RAW_DIR / "stemmetype.json", {"value": vote_types, "pages": type_pages})
    vote_type_by_id = {item["id"]: item["type"] for item in vote_types}

    all_rows: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    for vote in selected_votes:
        vote_id = vote["id"]
        stems, stem_pages, stem_page_count = fetch_odata(
            "Stemme",
            {"$filter": f"afstemningid eq {vote_id}"},
        )
        save_json(
            RAW_DIR / f"stemme_{vote_id}.json",
            {"value": stems, "pages": stem_pages, "page_count": stem_page_count},
        )

        actor_ids = sorted({row["aktørid"] for row in stems})
        actors: list[dict[str, Any]] = []
        for start in range(0, len(actor_ids), 10):
            batch_ids = actor_ids[start : start + 10]
            batch, _, _ = fetch_odata(
                "Aktør",
                {"$filter": " or ".join(f"id eq {actor_id}" for actor_id in batch_ids)},
            )
            actors.extend(batch)
        save_json(RAW_DIR / f"aktør_{vote_id}.json", {"value": actors})
        actor_by_id = {actor["id"]: actor for actor in actors}

        vote_rows = [
            {
                "politician_id": stem["aktørid"],
                "politician_name": actor_by_id.get(stem["aktørid"], {}).get("navn"),
                "party": party_shortname(actor_by_id.get(stem["aktørid"], {})),
                "period": SESSION_CODE,
                "vote_number": vote["nummer"],
                "afstemning_id": vote_id,
                "vote_category": vote_type_by_id.get(stem["typeid"]),
            }
            for stem in stems
        ]
        all_rows.extend(vote_rows)

        frame = pd.DataFrame(vote_rows, columns=OUTPUT_COLUMNS)
        observed_counts = frame["vote_category"].value_counts().to_dict()
        counts = {category: observed_counts.get(category, 0) for category in CATEGORIES}
        official_totals = parse_official_totals(vote.get("konklusion"))
        cast_totals = {category: counts[category] for category in CATEGORIES[:3]}
        unexpected = sorted(set(frame["vote_category"].dropna()) - set(CATEGORIES))
        official_match = (
            official_totals is None or cast_totals == official_totals
        )
        retrieval_ok = (
            len(frame) > 0
            and len(frame["politician_id"].unique()) == len(frame)
            and frame["politician_id"].notna().all()
            and frame["politician_name"].notna().all()
            and frame["party"].notna().all()
            and not unexpected
        )
        passed = retrieval_ok and official_match
        validations.append(
            {
                "vote": vote["nummer"],
                "afstemning_id": vote_id,
                "date": meeting_date(vote),
                "afstemningstype": (vote.get("Afstemningstype") or {}).get("type"),
                "rows": len(frame),
                "unique_politicians": frame["politician_id"].nunique(),
                "pages": stem_page_count,
                "duplicates": int(frame.duplicated(["politician_id", "afstemning_id"]).sum()),
                "missing": int(
                    frame[["politician_id", "politician_name", "party"]].isna().any(axis=1).sum()
                ),
                "missing_politician_ids": int(frame["politician_id"].isna().sum()),
                "missing_names": int(frame["politician_name"].isna().sum()),
                "missing_parties": int(frame["party"].isna().sum()),
                "for": counts["For"],
                "imod": counts["Imod"],
                "hverken": counts["Hverken for eller imod"],
                "fravær": counts["Fravær"],
                "unexpected": unexpected,
                "official_totals": official_totals,
                "official_totals_match": official_match,
                "status": "PASS" if passed else "FAIL",
                "failure_reason": (
                    "No Stemme rows returned; OData inline count is zero"
                    if not stems
                    else ""
                ),
            }
        )

    combined = pd.DataFrame(all_rows, columns=OUTPUT_COLUMNS)
    combined.to_csv(PROCESSED_DIR / "milestone2_votes.csv", index=False)
    save_json(RAW_DIR / "validation.json", validations)

    passed_count = sum(item["status"] == "PASS" for item in validations)
    failed_count = len(validations) - passed_count
    report = [
        "# Milestone 2 validation report",
        "",
        f"- Votes tested: `{len(validations)}/10`",
        f"- Votes passed: `{passed_count}/10`",
        f"- Votes failed: `{failed_count}/10`",
        "",
        "## Selection method",
        "",
        "All `Afstemning` records linked to period `20251` were sorted by meeting date, "
        "vote number, and `Afstemning` ID. Ten positions were selected evenly from the "
        "first through last record using `round(i * (n - 1) / 9)`.",
        "",
        "## Selected votes",
        "",
        "| Vote | Afstemning ID | Date | Afstemningstype |",
        "|---:|---:|---|---|",
    ]
    for item in validations:
        report.append(
            f"| {item['vote']} | {item['afstemning_id']} | {item['date']} | "
            f"{item['afstemningstype'] or 'not available'} |"
        )
    report.extend(
        [
            "",
        "## Summary",
        "",
        "| Vote | Afstemning ID | Rows | For | Imod | Hverken | Fravær | Missing | Duplicates | Official totals match | Status |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for item in validations:
        report.append(
            f"| {item['vote']} | {item['afstemning_id']} | {item['rows']} | "
            f"{item['for']} | {item['imod']} | {item['hverken']} | {item['fravær']} | "
            f"{item['missing']} | {item['duplicates']} | "
            f"{'PASS' if item['official_totals_match'] else 'FAIL'} | {item['status']} |"
        )
    report.extend(["", "## Per-vote details", ""])
    for item in validations:
        report.append(
            f"- Vote {item['vote']} (`{item['afstemning_id']}`): "
            f"{item['pages']} OData pages, unique politicians `{item['unique_politicians']}`, "
            f"duplicates `{item['duplicates']}`, missing IDs `{item['missing_politician_ids']}`, "
            f"missing names `{item['missing_names']}`, missing parties `{item['missing_parties']}`, "
            f"unexpected categories `{item['unexpected']}`, official totals `{item['official_totals']}`, "
            f"failure reason `{item['failure_reason'] or 'none'}`."
        )
    report.extend(
        [
            "",
            f"## Overall result: `{'PASS' if failed_count == 0 else 'FAIL'}`",
        ]
    )
    (PROCESSED_DIR / "milestone2_validation.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )

    print(f"Votes tested: {len(validations)}/10")
    print(f"Votes passed: {passed_count}/10")
    print(f"Votes failed: {failed_count}/10")
    print(pd.DataFrame(validations).to_string(index=False))
    if failed_count == 0:
        print("MILESTONE 2: PASS")
    else:
        print("MILESTONE 2: FAIL")


if __name__ == "__main__":
    main()
