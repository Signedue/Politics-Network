"""Audit Folketinget voting coverage for the post-2022 electoral period.

This is a new audit namespace. It does not modify Milestones 3C-5B, apply a
participation threshold, build a network, or calculate similarity.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests


API_BASE = "https://oda.ft.dk/api"
START_DATE = "2022-11-01"
END_DATE = "2026-03-24"
MAX_PAGES = 1000
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "post2022"
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
PARTICIPATED = {"For", "Imod", "Hverken for eller imod"}
EXPECTED_TYPES = ["For", "Imod", "Hverken for eller imod", "Fravær"]
PERIOD_FIELD = "M\u00f8de"


def fetch_odata(
    resource: str,
    params: dict[str, str | int] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    url = f"{API_BASE}/{resource}"
    rows: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page_number in range(1, MAX_PAGES + 1):
        if url in seen:
            raise RuntimeError(f"Pagination loop detected: {url}")
        seen.add(url)
        response = session.get(
            url,
            params=params if page_number == 1 else None,
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload.get("value"), list):
            raise RuntimeError(f"Missing list-valued OData value for {url}")
        pages.append(payload)
        rows.extend(payload["value"])
        next_url = payload.get("odata.nextLink")
        if not next_url:
            return rows, pages, page_number
        url = next_url
    raise RuntimeError(f"Exceeded pagination limit: {MAX_PAGES}")


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value[:19])


def party_shortname(actor: dict[str, Any]) -> str | None:
    if actor.get("gruppenavnkort"):
        return actor["gruppenavnkort"]
    match = re.search(
        r"<partyShortname>(.*?)</partyShortname>",
        actor.get("biografi") or "",
    )
    return match.group(1) if match else None


def in_study_period(value: str) -> bool:
    day = value[:10]
    return START_DATE <= day < END_DATE


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    periods, period_pages, period_page_count = fetch_odata(
        "Periode",
        {"$filter": "type eq 'samling'", "$top": 100},
    )
    save_json(
        RAW_DIR / "periods.json",
        {"value": periods, "pages": period_pages, "page_count": period_page_count},
    )

    relevant_periods = []
    for period in periods:
        if period.get("slutdato", "")[:10] > START_DATE and period.get(
            "startdato", ""
        )[:10] < END_DATE:
            relevant_periods.append(period)

    all_votes: list[dict[str, Any]] = []
    for period in relevant_periods:
        code = period["kode"]
        votes, pages, page_count = fetch_odata(
            "Afstemning",
            {
                "$filter": f"{PERIOD_FIELD}/Periode/id eq {period['id']}",
                "$expand": PERIOD_FIELD,
            },
        )
        save_json(
            RAW_DIR / f"afstemning_{code}.json",
            {"value": votes, "pages": pages, "page_count": page_count},
        )
        for vote in votes:
            meeting = vote.get(PERIOD_FIELD) or {}
            vote_date = meeting.get("dato")
            if vote_date and in_study_period(vote_date):
                all_votes.append(
                    {
                        "afstemning_id": int(vote["id"]),
                        "vote_number": vote.get("nummer"),
                        "date": vote_date,
                        "year": int(vote_date[:4]),
                        "session": code,
                        "period_id": period["id"],
                        "meeting_id": meeting.get("id"),
                        "meeting_number": meeting.get("nummer"),
                        "vote_type": vote.get("type"),
                        "title": vote.get("titel"),
                    }
                )

    vote_frame = pd.DataFrame(all_votes).drop_duplicates("afstemning_id")
    vote_frame = vote_frame.sort_values(["date", "session", "vote_number", "afstemning_id"])
    vote_frame.to_csv(
        PROCESSED_DIR / "post2022_vote_audit.csv", index=False, encoding="utf-8"
    )

    vote_types, type_pages, type_page_count = fetch_odata(
        "Stemmetype", {"$top": 100}
    )
    save_json(
        RAW_DIR / "stemmetype.json",
        {"value": vote_types, "pages": type_pages, "page_count": type_page_count},
    )
    type_by_id = {int(row["id"]): row.get("type") for row in vote_types}

    actor_ids: set[int] = set()
    registry_rows: list[dict[str, Any]] = []
    vote_summary_rows: list[dict[str, Any]] = []
    duplicate_rows: list[dict[str, Any]] = []
    raw_stemme_count = 0

    for vote in vote_frame.to_dict("records"):
        stems, pages, page_count = fetch_odata(
            "Stemme",
            {"$filter": f"afstemningid eq {vote['afstemning_id']}"},
        )
        save_json(
            RAW_DIR / f"stemme_{vote['afstemning_id']}.json",
            {"value": stems, "pages": pages, "page_count": page_count},
        )
        raw_stemme_count += len(stems)
        actor_ids.update(int(row["aktørid"]) for row in stems if row.get("aktørid") is not None)
        categories = Counter(type_by_id.get(int(row["typeid"]), "UNKNOWN") for row in stems)
        vote_summary_rows.append(
            {
                **vote,
                "stemme_count": len(stems),
                "has_individual_records": bool(stems),
                **{f"count_{category}": categories.get(category, 0) for category in EXPECTED_TYPES},
                "count_unknown": categories.get("UNKNOWN", 0),
                "duplicate_actor_rows": len(stems)
                - len({row.get("aktørid") for row in stems}),
                "odata_page_count": page_count,
            }
        )
        seen_actors: set[int] = set()
        for row in stems:
            actor_id = int(row["aktørid"])
            if actor_id in seen_actors:
                duplicate_rows.append(
                    {
                        "afstemning_id": vote["afstemning_id"],
                        "actor_id": actor_id,
                        "date": vote["date"],
                    }
                )
            seen_actors.add(actor_id)

    vote_summary = pd.DataFrame(vote_summary_rows)
    vote_summary.to_csv(
        PROCESSED_DIR / "post2022_vote_summary.csv", index=False, encoding="utf-8"
    )
    pd.DataFrame(duplicate_rows).to_csv(
        PROCESSED_DIR / "post2022_duplicate_stemme_rows.csv",
        index=False,
        encoding="utf-8",
    )

    actors: dict[int, dict[str, Any]] = {}
    actor_ids_sorted = sorted(actor_ids)
    for start in range(0, len(actor_ids_sorted), 20):
        batch_ids = actor_ids_sorted[start : start + 20]
        batch, pages, page_count = fetch_odata(
            "Aktør",
            {"$filter": " or ".join(f"id eq {actor_id}" for actor_id in batch_ids), "$top": 100},
        )
        for actor in batch:
            actors[int(actor["id"])] = actor
        save_json(
            RAW_DIR / f"actor_batch_{start // 20 + 1}.json",
            {"value": batch, "pages": pages, "page_count": page_count},
        )

    observations: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for vote in vote_frame.to_dict("records"):
        stem_payload = json.loads(
            (RAW_DIR / f"stemme_{vote['afstemning_id']}.json").read_text(
                encoding="utf-8"
            )
        )
        for row in stem_payload["value"]:
            actor_id = int(row["aktørid"])
            category = type_by_id.get(int(row["typeid"]), "UNKNOWN")
            observations[actor_id].append(
                {
                    "date": vote["date"],
                    "category": category,
                    "vote_id": vote["afstemning_id"],
                }
            )

    registry_rows = []
    for actor_id in sorted(observations):
        actor = actors.get(actor_id, {})
        obs = observations[actor_id]
        categories = Counter(item["category"] for item in obs)
        names = sorted({str(actor.get("navn") or "")})
        parties = sorted({party_shortname(actor) or ""})
        registry_rows.append(
            {
                "actor_id": actor_id,
                "name": actor.get("navn"),
                "party": party_shortname(actor),
                "first_observed_vote_date": min(item["date"] for item in obs),
                "last_observed_vote_date": max(item["date"] for item in obs),
                "recorded_vote_rows": len(obs),
                "for_count": categories.get("For", 0),
                "against_count": categories.get("Imod", 0),
                "neither_count": categories.get("Hverken for eller imod", 0),
                "absent_count": categories.get("Fravær", 0),
                "unknown_vote_type_count": categories.get("UNKNOWN", 0),
                "name_variant_count": len(names),
                "party_variant_count": len(parties),
            }
        )

    registry = pd.DataFrame(registry_rows).sort_values(["name", "actor_id"])
    registry.to_csv(
        PROCESSED_DIR / "post2022_politician_registry.csv",
        index=False,
        encoding="utf-8",
    )
    registry[["actor_id", "name", "party"]].to_csv(
        PROCESSED_DIR / "post2022_politicians.csv",
        index=False,
        encoding="utf-8",
    )

    vote_summary["session"] = vote_summary["session"].astype(str)
    group_columns = ["session", "year"]
    summary_rows = []
    for (session, year), group in vote_summary.groupby(group_columns, sort=True):
        ids = set()
        for vote_id in group["afstemning_id"]:
            payload = json.loads(
                (RAW_DIR / f"stemme_{vote_id}.json").read_text(encoding="utf-8")
            )
            ids.update(int(row["aktørid"]) for row in payload["value"])
        summary_rows.append(
            {
                "session": session,
                "year": int(year),
                "total_votes": len(group),
                "votes_with_individual_records": int(group["has_individual_records"].sum()),
                "votes_without_individual_records": int((~group["has_individual_records"]).sum()),
                "unique_politicians": len(ids),
                **{
                    f"{prefix}_count": int(group[f"count_{category}"].sum())
                    for category, prefix in [
                        ("For", "for"),
                        ("Imod", "against"),
                        ("Hverken for eller imod", "neither"),
                        ("Fravær", "absent"),
                    ]
                },
                "unknown_vote_type_count": int(group["count_unknown"].sum()),
            }
        )
    session_summary = pd.DataFrame(summary_rows)
    session_summary.to_csv(
        PROCESSED_DIR / "post2022_session_year_summary.csv",
        index=False,
        encoding="utf-8",
    )

    name_variants = []
    party_variants = []
    for actor_id, actor in actors.items():
        if actor_id not in observations:
            continue
        if not actor.get("navn"):
            name_variants.append(actor_id)
        if not party_shortname(actor):
            party_variants.append(actor_id)

    alex = registry[registry["actor_id"] == 18703]
    checks = {
        "date_lower_boundary": bool((vote_frame["date"].str[:10] >= START_DATE).all()),
        "date_upper_boundary": bool((vote_frame["date"].str[:10] < END_DATE).all()),
        "unique_vote_ids": vote_frame["afstemning_id"].is_unique,
        "unique_actor_ids": registry["actor_id"].is_unique,
        "no_missing_names": bool(registry["name"].notna().all()),
        "no_missing_parties": bool(registry["party"].notna().all()),
        "no_duplicate_stemme_rows": len(duplicate_rows) == 0,
        "no_unknown_vote_types": int(vote_summary["count_unknown"].sum()) == 0,
    }

    report = [
        "# Milestone 6A full electoral-period voting data audit",
        "",
        f"- Study period: `{START_DATE}` inclusive to `{END_DATE}` exclusive.",
        f"- Relevant session records inspected: `{', '.join(p['kode'] for p in relevant_periods)}`.",
        f"- Votes after actual-date filtering: `{len(vote_frame)}`.",
        f"- Individual Stemme rows retrieved: `{raw_stemme_count}`.",
        "",
        "## Session and year summary",
        "",
        session_summary.to_string(index=False),
        "",
        "## Coverage and missingness",
        "",
        "- Votes without individual Stemme rows remain distinct from votes containing recorded `Fravær` rows.",
        f"- Votes without individual records: `{int(vote_summary['has_individual_records'].eq(False).sum())}`.",
        f"- Recorded absence rows: `{int(vote_summary['count_Fravær'].sum())}`.",
        "",
        "## Actor consistency and metadata",
        "",
        f"- Unique actor IDs in registry: `{registry['actor_id'].nunique()}`.",
        f"- Actor records with missing names: `{len(name_variants)}`.",
        f"- Actor records with missing party labels: `{len(party_variants)}`.",
        f"- Duplicate actor/vote rows: `{len(duplicate_rows)}`.",
        f"- Actor IDs with multiple name variants in retrieved metadata: `{int((registry['name_variant_count'] > 1).sum())}`.",
        f"- Actor IDs with multiple party variants in retrieved metadata: `{int((registry['party_variant_count'] > 1).sum())}`.",
        "",
        "### Alex Vanopslagh (actor ID 18703)",
        "",
        alex.to_string(index=False) if not alex.empty else "Actor ID 18703 was not observed.",
        "",
        "## Validation checks",
        "",
    ]
    report.extend(
        f"- {name}: `{'PASS' if value else 'FAIL'}`" for name, value in checks.items()
    )
    report.extend(
        [
            "",
            "## Limitations",
            "",
            "- Party labels are extracted from actor biography metadata via `partyShortname`; this audit does not reconstruct historical party membership by vote date.",
            "- The registry counts recorded Stemme rows. A missing vote record is not converted into `Fravær`.",
            "- No participation threshold, similarity calculation, network construction, or community detection was applied.",
            "",
        ]
    )
    (PROCESSED_DIR / "post2022_validation.md").write_text(
        "\n".join(report), encoding="utf-8"
    )

    print(f"Sessions: {[p['kode'] for p in relevant_periods]}")
    print(f"Votes after date filter: {len(vote_frame)}")
    print(f"Individual Stemme rows: {raw_stemme_count}")
    print(f"Unique actors: {registry['actor_id'].nunique()}")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
