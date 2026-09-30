"""Diagnose pairwise voting similarity across all valid votes in period 20251."""

from __future__ import annotations

import itertools
import json
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from milestone1_retrieve_vote import fetch_odata, party_shortname


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "milestone3c"
PROCESSED_DIR = ROOT / "data" / "processed"
FIGURES_DIR = ROOT / "outputs" / "figures"
COVERAGE_PATH = PROCESSED_DIR / "milestone2b_coverage.csv"
LOCAL_DATASETS = [
    PROCESSED_DIR / "milestone2_votes.csv",
    PROCESSED_DIR / "milestone3a_pair_tests.csv",
]
LOCAL_RAW_DIRS = [
    ROOT / "data" / "raw" / "milestone2",
    ROOT / "data" / "raw" / "milestone3a",
    ROOT / "data" / "raw" / "milestone3b",
]
SESSION_CODE = "20251"
PARTICIPATED = {"For", "Imod", "Hverken for eller imod"}
ALL_CATEGORIES = ["For", "Imod", "Hverken for eller imod", "Fravær"]
HALF_MIN_SHARED = 20


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def raw_rows(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path)
    return payload.get("value", [])


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def find_raw_file(filename: str) -> Path | None:
    for directory in LOCAL_RAW_DIRS:
        candidate = directory / filename
        if candidate.exists():
            return candidate
    return None


def load_local_rows() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in LOCAL_DATASETS:
        if path.exists():
            frame = pd.read_csv(path)
            if {"afstemning_id", "politician_id", "vote_category"}.issubset(frame.columns):
                frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates(
        ["politician_id", "afstemning_id"]
    )


def load_local_stemme(vote_id: int) -> list[dict[str, Any]] | None:
    path = find_raw_file(f"stemme_{vote_id}.json")
    if path is None:
        return None
    return raw_rows(path)


def load_local_actors() -> dict[int, dict[str, Any]]:
    actors: dict[int, dict[str, Any]] = {}
    for directory in LOCAL_RAW_DIRS:
        for path in directory.glob("aktør*.json"):
            for actor in raw_rows(path):
                if "id" in actor:
                    actors[actor["id"]] = actor
    return actors


def load_local_stemmetype() -> dict[int, str]:
    for directory in LOCAL_RAW_DIRS:
        path = directory / "stemmetype.json"
        if path.exists():
            return {row["id"]: row["type"] for row in raw_rows(path)}
    return {}


def percentile_summary(values: pd.Series) -> dict[str, float | int]:
    return {
        "min": int(values.min()),
        "p25": float(values.quantile(0.25)),
        "median": float(values.median()),
        "p75": float(values.quantile(0.75)),
        "max": int(values.max()),
    }


def build_pairs(matrix: pd.DataFrame, info: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for left_id, right_id in itertools.combinations(matrix.index, 2):
        left = matrix.loc[left_id]
        right = matrix.loc[right_id]
        shared = left.isin(PARTICIPATED) & right.isin(PARTICIPATED)
        n_shared = int(shared.sum())
        n_same = int((left[shared] == right[shared]).sum())
        party_left = info.loc[left_id, "party"]
        party_right = info.loc[right_id, "party"]
        records.append(
            {
                "politician_A_id": left_id,
                "politician_B_id": right_id,
                "party_A": party_left,
                "party_B": party_right,
                "n_shared": n_shared,
                "n_same": n_same,
                "similarity": n_same / n_shared if n_shared else np.nan,
                "party_relation": (
                    "same-party" if party_left == party_right else "different-party"
                ),
            }
        )
    return pd.DataFrame(records)


def main() -> None:
    for directory in (RAW_DIR, PROCESSED_DIR, FIGURES_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    coverage = pd.read_csv(COVERAGE_PATH)
    valid = coverage[coverage["has_individual_votes"]].copy()
    valid = valid.sort_values(["date", "vote_number", "afstemning_id"]).reset_index(drop=True)
    if len(valid) != 168:
        raise RuntimeError(f"Expected 168 valid votes, found {len(valid)}")
    valid_ids = set(valid["afstemning_id"].astype(int))

    local = load_local_rows()
    local = local[local["afstemning_id"].isin(valid_ids)].copy()
    local_ids = set(local["afstemning_id"].astype(int))
    actors = load_local_actors()
    vote_type_by_id = load_local_stemmetype()
    fetched_ids: list[int] = []
    page_counts: dict[int, int] = {}
    stems_by_vote: dict[int, list[dict[str, Any]]] = {}

    for vote_id in sorted(valid_ids):
        local_stems = load_local_stemme(vote_id)
        if local_stems is not None:
            stems_by_vote[vote_id] = local_stems
            continue
        stems, pages, page_count = fetch_odata(
            "Stemme", {"$filter": f"afstemningid eq {vote_id}"}
        )
        if not stems:
            raise RuntimeError(f"Valid vote {vote_id} unexpectedly returned zero Stemme rows")
        save_json(
            RAW_DIR / f"stemme_{vote_id}.json",
            {"value": stems, "pages": pages, "page_count": page_count},
        )
        stems_by_vote[vote_id] = stems
        fetched_ids.append(vote_id)
        page_counts[vote_id] = page_count

    all_actor_ids = sorted(
        {int(row["aktørid"]) for stems in stems_by_vote.values() for row in stems}
    )
    missing_actor_ids = [actor_id for actor_id in all_actor_ids if actor_id not in actors]
    for start in range(0, len(missing_actor_ids), 10):
        batch_ids = missing_actor_ids[start : start + 10]
        batch, pages, page_count = fetch_odata(
            "Aktør",
            {"$filter": " or ".join(f"id eq {actor_id}" for actor_id in batch_ids)},
        )
        for actor in batch:
            actors[actor["id"]] = actor
        save_json(
            RAW_DIR / f"aktør_batch_{start // 10 + 1}.json",
            {"value": batch, "pages": pages, "page_count": page_count},
        )

    if not vote_type_by_id:
        type_rows, pages, page_count = fetch_odata("Stemmetype", {"$top": 20})
        vote_type_by_id = {row["id"]: row["type"] for row in type_rows}
        save_json(
            RAW_DIR / "stemmetype.json",
            {"value": type_rows, "pages": pages, "page_count": page_count},
        )

    rows: list[dict[str, Any]] = []
    vote_metadata = valid.set_index("afstemning_id")
    for vote_id, stems in stems_by_vote.items():
        vote = vote_metadata.loc[vote_id]
        for stem in stems:
            actor = actors.get(stem["aktørid"], {})
            rows.append(
                {
                    "politician_id": stem["aktørid"],
                    "politician_name": actor.get("navn"),
                    "party": party_shortname(actor),
                    "period": SESSION_CODE,
                    "vote_number": int(vote["vote_number"]),
                    "afstemning_id": vote_id,
                    "vote_category": vote_type_by_id.get(stem["typeid"]),
                }
            )

    data = pd.DataFrame(rows)
    duplicate_count = int(data.duplicated(["politician_id", "afstemning_id"]).sum())
    if duplicate_count:
        raise RuntimeError(f"Found {duplicate_count} duplicate politician/vote rows")
    unexpected = sorted(set(data["vote_category"].dropna()) - set(ALL_CATEGORIES))
    if unexpected:
        raise RuntimeError(f"Unexpected vote categories: {unexpected}")

    matrix = data.pivot(index="politician_id", columns="vote_number", values="vote_category")
    info = (
        data.sort_values(["politician_id", "vote_number"])
        [["politician_id", "politician_name", "party"]]
        .drop_duplicates("politician_id")
        .set_index("politician_id")
    )
    matrix_out = info.join(matrix)
    matrix_out.to_csv(PROCESSED_DIR / "milestone3c_session_matrix.csv")

    pairs = build_pairs(matrix, info)
    pairs.to_csv(PROCESSED_DIR / "milestone3c_pairwise.csv", index=False)

    participation = data.assign(
        participated=data["vote_category"].isin(PARTICIPATED),
        recorded=True,
    ).groupby("politician_id").agg(
        votes_with_recorded_row=("recorded", "sum"),
        votes_participated_in=("participated", "sum"),
    )
    participation["votes_absent"] = (
        data[data["vote_category"] == "Fravær"]
        .groupby("politician_id").size()
        .reindex(participation.index, fill_value=0)
    )
    participation["participation_rate"] = (
        participation["votes_participated_in"] / len(valid)
    )
    participation = info.join(participation).fillna({"votes_absent": 0})
    participation.to_csv(RAW_DIR / "politician_participation.csv")

    eligible = pairs[pairs["n_shared"] >= 40].copy()
    thresholds = {
        threshold: float((pairs["n_shared"] >= threshold).mean() * 100)
        for threshold in (10, 20, 40, 60, 80, 100, 120)
    }
    n_shared_stats = percentile_summary(pairs["n_shared"])

    first_votes = list(matrix.columns[: len(matrix.columns) // 2])
    second_votes = list(matrix.columns[len(matrix.columns) // 2 :])
    first_pairs = build_pairs(matrix[first_votes], info).rename(
        columns={"n_shared": "n_shared_first", "similarity": "similarity_first"}
    )
    second_pairs = build_pairs(matrix[second_votes], info).rename(
        columns={"n_shared": "n_shared_second", "similarity": "similarity_second"}
    )
    stability = first_pairs.merge(
        second_pairs[
            ["politician_A_id", "politician_B_id", "n_shared_second", "similarity_second"]
        ],
        on=["politician_A_id", "politician_B_id"],
    )
    stability = stability[
        (stability["n_shared_first"] >= HALF_MIN_SHARED)
        & (stability["n_shared_second"] >= HALF_MIN_SHARED)
    ].dropna(subset=["similarity_first", "similarity_second"])
    correlation = (
        float(stability["similarity_first"].corr(stability["similarity_second"]))
        if len(stability) >= 2
        else float("nan")
    )

    plt.figure(figsize=(7, 4.5))
    plt.hist(eligible["similarity"], bins=20, edgecolor="white")
    plt.xlabel("Similarity")
    plt.ylabel("Number of politician pairs")
    plt.title("Voting similarity for pairs with n_shared >= 40")
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "milestone3c_similarity_distribution.png", dpi=150)
    plt.close()

    rate_summary = participation["participation_rate"].describe()
    low_recorded = participation.sort_values(
        ["votes_with_recorded_row", "politician_id"]
    ).head(10)
    same = eligible[eligible["party_relation"] == "same-party"]["similarity"]
    different = eligible[eligible["party_relation"] == "different-party"]["similarity"]
    decision = (
        "The full valid session provides enough shared participation and stability "
        "to proceed toward constructing a network."
        if len(eligible) > 0 and not np.isnan(correlation) and correlation >= 0.5
        else
        "The full valid session does not yet provide sufficient evidence of shared "
        "participation and stability to proceed toward constructing a network."
    )
    report = [
        "# Milestone 3C validation report",
        "",
        "## Data scope and retrieval",
        "",
        f"- Session: `{SESSION_CODE}`",
        f"- Valid votes included: `{len(valid)}`",
        "- The 24 coverage-audit votes with zero Stemme rows were excluded.",
        f"- Existing local Stemme data were reused for `{len(valid_ids - set(fetched_ids))}` votes.",
        f"- New complete paginated Stemme retrievals: `{len(fetched_ids)}` votes.",
        "- No missing vote was scraped or replaced.",
        "",
        "## Session matrix",
        "",
        f"- Dimensions: `{matrix.shape[0]} politicians x {matrix.shape[1]} votes`",
        f"- Unique politicians: `{matrix.shape[0]}`",
        f"- Votes represented: `{matrix.shape[1]}`",
        f"- Category counts: `{data['vote_category'].value_counts().reindex(ALL_CATEGORIES, fill_value=0).to_dict()}`",
        f"- Missing matrix values: `{int(matrix.isna().sum().sum())}`",
        "",
        "## Participation diagnostics",
        "",
        f"- Participation-rate distribution: `{rate_summary.to_dict()}`",
        "- Ten politicians with the fewest recorded rows:",
        "",
        "| Politician ID | Name | Party | Recorded rows | Participated | Absent | Rate |",
        "|---:|---|---|---:|---:|---:|---:|",
    ]
    for row in low_recorded.itertuples():
        report.append(
            f"| {row.Index} | {row.politician_name} | {row.party} | "
            f"{row.votes_with_recorded_row} | {row.votes_participated_in} | "
            f"{row.votes_absent} | {row.participation_rate:.3f} |"
        )
    report.extend(
        [
            "",
            "## Pairwise n_shared distribution",
            "",
            f"- Min: `{n_shared_stats['min']}`",
            f"- 25th percentile: `{n_shared_stats['p25']}`",
            f"- Median: `{n_shared_stats['median']}`",
            f"- 75th percentile: `{n_shared_stats['p75']}`",
            f"- Max: `{n_shared_stats['max']}`",
        ]
    )
    report.extend(
        f"- Pairs with n_shared >= {threshold}: `{percentage:.2f}%`"
        for threshold, percentage in thresholds.items()
    )
    report.extend(
        [
            "",
            "## Similarity for n_shared >= 40",
            "",
            f"- Eligible pairs: `{len(eligible)}`",
            f"- Min: `{eligible['similarity'].min()}`",
            f"- 25th percentile: `{eligible['similarity'].quantile(0.25)}`",
            f"- Median: `{eligible['similarity'].median()}`",
            f"- Mean: `{eligible['similarity'].mean()}`",
            f"- 75th percentile: `{eligible['similarity'].quantile(0.75)}`",
            f"- Max: `{eligible['similarity'].max()}`",
            "",
            "## Same-party / different-party descriptive check",
            "",
            f"- Same-party pairs: `{len(same)}`; mean `{same.mean()}`; median `{same.median()}`",
            f"- Different-party pairs: `{len(different)}`; mean `{different.mean()}`; median `{different.median()}`",
            "",
            "## Stability check",
            "",
            f"- Split: first `{len(first_votes)}` and second `{len(second_votes)}` valid votes in sorted session order.",
            f"- Minimum n_shared within each half: `{HALF_MIN_SHARED}`.",
            f"- Pairs meeting the requirement in both halves: `{len(stability)}`.",
            f"- Pearson correlation of first-half and second-half similarities: `{correlation}`.",
            "",
            "## Decision",
            "",
            decision,
            "This is a descriptive diagnostic only. No similarity cutoff, edge "
            "threshold, community method, or network layout was selected.",
        ]
    )
    (PROCESSED_DIR / "milestone3c_validation.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )

    print(f"Valid votes: {len(valid)}")
    print(f"Matrix dimensions: {matrix.shape}")
    print(f"Category counts: {data['vote_category'].value_counts().to_dict()}")
    print(f"Missing values: {int(matrix.isna().sum().sum())}")
    print(f"n_shared distribution: {n_shared_stats}")
    print(f"Threshold percentages: {thresholds}")
    print(f"Eligible pairs (n_shared >= 40): {len(eligible)}")
    print(f"Stability pairs: {len(stability)}")
    print(f"Stability correlation: {correlation}")
    print(f"Decision: {decision}")


if __name__ == "__main__":
    main()
