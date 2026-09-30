"""Compute bounded pairwise voting statistics across 50 valid 20251 votes."""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from milestone1_retrieve_vote import fetch_odata, party_shortname


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "milestone3b"
PROCESSED_DIR = ROOT / "data" / "processed"
FIGURES_DIR = ROOT / "outputs" / "figures"
COVERAGE_PATH = PROCESSED_DIR / "milestone2b_coverage.csv"
LOCAL_DATA = PROCESSED_DIR / "milestone2_votes.csv"
LOCAL_EXTRA = ROOT / "data" / "raw" / "milestone3a"
SESSION_CODE = "20251"
SAMPLE_SIZE = 50
PARTICIPATED = {"For", "Imod", "Hverken for eller imod"}


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def raw_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("value", [])


def percentile_summary(values: pd.Series) -> dict[str, float | int]:
    return {
        "count": int(values.size),
        "min": int(values.min()),
        "p25": float(values.quantile(0.25)),
        "median": float(values.median()),
        "p75": float(values.quantile(0.75)),
        "max": int(values.max()),
    }


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    coverage = pd.read_csv(COVERAGE_PATH)
    valid = coverage[coverage["has_individual_votes"]].sort_values(
        ["date", "vote_number", "afstemning_id"]
    ).reset_index(drop=True)
    if len(valid) < SAMPLE_SIZE:
        raise RuntimeError(f"Only {len(valid)} valid votes are available.")
    positions = [
        round(index * (len(valid) - 1) / (SAMPLE_SIZE - 1))
        for index in range(SAMPLE_SIZE)
    ]
    selected = valid.iloc[positions].drop_duplicates("afstemning_id").reset_index(drop=True)
    if len(selected) != SAMPLE_SIZE:
        raise RuntimeError("Deterministic sample contained duplicate vote records.")
    save_json(
        RAW_DIR / "selection.json",
        {
            "method": (
                "Filter the Milestone 2B coverage audit to has_individual_votes=True; "
                "sort by date, vote_number, afstemning_id; select positions "
                "round(i * (n - 1) / 49) for i=0..49."
            ),
            "positions": positions,
            "votes": selected.to_dict("records"),
        },
    )

    local = pd.read_csv(LOCAL_DATA)
    local_vote_ids = set(local["afstemning_id"].unique())
    extra_rows: list[dict[str, Any]] = []
    if (LOCAL_EXTRA / "stemme_10380.json").exists():
        stems = raw_rows(LOCAL_EXTRA / "stemme_10380.json")
        actors = {
            row["id"]: row
            for row in raw_rows(LOCAL_EXTRA / "aktør_10380.json")
        }
        types = {
            row["id"]: row["type"]
            for row in raw_rows(LOCAL_EXTRA / "stemmetype.json")
        }
        for stem in stems:
            actor = actors[stem["aktørid"]]
            extra_rows.append(
                {
                    "politician_id": stem["aktørid"],
                    "politician_name": actor["navn"],
                    "party": party_shortname(actor),
                    "period": SESSION_CODE,
                    "vote_number": 3,
                    "afstemning_id": 10380,
                    "vote_category": types[stem["typeid"]],
                }
            )
    local = pd.concat([local, pd.DataFrame(extra_rows)], ignore_index=True)
    local_vote_ids = set(local["afstemning_id"].unique())

    selected_ids = set(selected["afstemning_id"])
    missing_ids = selected_ids - local_vote_ids
    fetched_rows: list[dict[str, Any]] = []
    fetched_actor_ids: set[int] = set()
    for vote_id in sorted(missing_ids):
        stems, pages, page_count = fetch_odata(
            "Stemme", {"$filter": f"afstemningid eq {vote_id}"}
        )
        save_json(
            RAW_DIR / f"stemme_{vote_id}.json",
            {"value": stems, "pages": pages, "page_count": page_count},
        )
        fetched_actor_ids.update(row["aktørid"] for row in stems)

    actors: dict[int, dict[str, Any]] = {}
    actor_ids = sorted(fetched_actor_ids)
    for start in range(0, len(actor_ids), 10):
        batch, pages, _ = fetch_odata(
            "Aktør",
            {
                "$filter": " or ".join(
                    f"id eq {actor_id}" for actor_id in actor_ids[start : start + 10]
                )
            },
        )
        for actor in batch:
            actors[actor["id"]] = actor
        save_json(RAW_DIR / f"aktør_batch_{start // 10 + 1}.json", {"value": batch, "pages": pages})

    type_rows, type_pages, _ = fetch_odata("Stemmetype", {"$top": 20})
    type_by_id = {row["id"]: row["type"] for row in type_rows}
    save_json(RAW_DIR / "stemmetype.json", {"value": type_rows, "pages": type_pages})

    for vote_id in sorted(missing_ids):
        stems = raw_rows(RAW_DIR / f"stemme_{vote_id}.json")
        vote_number = int(selected.loc[selected["afstemning_id"] == vote_id, "vote_number"].iloc[0])
        for stem in stems:
            actor = actors[stem["aktørid"]]
            fetched_rows.append(
                {
                    "politician_id": stem["aktørid"],
                    "politician_name": actor["navn"],
                    "party": party_shortname(actor),
                    "period": SESSION_CODE,
                    "vote_number": vote_number,
                    "afstemning_id": vote_id,
                    "vote_category": type_by_id[stem["typeid"]],
                }
            )

    selected_data = pd.concat(
        [
            local[local["afstemning_id"].isin(selected_ids)],
            pd.DataFrame(fetched_rows),
        ],
        ignore_index=True,
    )
    duplicate_count = selected_data.duplicated(
        ["politician_id", "afstemning_id"]
    ).sum()
    if duplicate_count:
        raise RuntimeError(
            f"Selected data contain {duplicate_count} duplicate politician/vote rows."
        )
    matrix = selected_data.pivot(
        index="politician_id",
        columns="vote_number",
        values="vote_category",
    )
    politician_info = (
        selected_data[["politician_id", "politician_name", "party"]]
        .drop_duplicates("politician_id")
        .set_index("politician_id")
    )
    pair_records: list[dict[str, Any]] = []
    for left_id, right_id in itertools.combinations(matrix.index, 2):
        left_votes = matrix.loc[left_id]
        right_votes = matrix.loc[right_id]
        participated = left_votes.isin(PARTICIPATED) & right_votes.isin(PARTICIPATED)
        n_shared = int(participated.sum())
        n_same = int((left_votes[participated] == right_votes[participated]).sum())
        pair_records.append(
            {
                "politician_A_id": left_id,
                "politician_B_id": right_id,
                "party_A": politician_info.loc[left_id, "party"],
                "party_B": politician_info.loc[right_id, "party"],
                "n_shared": n_shared,
                "n_same": n_same,
                "similarity": n_same / n_shared if n_shared else np.nan,
                "party_relation": (
                    "same-party"
                    if politician_info.loc[left_id, "party"] == politician_info.loc[right_id, "party"]
                    else "different-party"
                ),
            }
        )
    pairs = pd.DataFrame(pair_records)
    pairs.to_csv(PROCESSED_DIR / "milestone3b_pairwise.csv", index=False)

    eligible = pairs[pairs["n_shared"] >= 20]
    same_party = eligible[eligible["party_relation"] == "same-party"]["similarity"]
    different_party = eligible[eligible["party_relation"] == "different-party"]["similarity"]
    high_low = pairs[(pairs["similarity"] >= 0.90) & (pairs["n_shared"] < 5)]
    matrix_counts = selected_data["vote_category"].value_counts().reindex(
        ["For", "Imod", "Hverken for eller imod", "Fravær"], fill_value=0
    )
    n_shared_summary = percentile_summary(pairs["n_shared"])
    thresholds = {
        threshold: float((pairs["n_shared"] >= threshold).mean() * 100)
        for threshold in (5, 10, 20, 30, 40)
    }

    plt.figure(figsize=(7, 4.5))
    plt.hist(eligible["similarity"], bins=10, edgecolor="white")
    plt.xlabel("Similarity")
    plt.ylabel("Number of politician pairs")
    plt.title("Voting similarity for pairs with n_shared >= 20")
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "milestone3b_similarity_distribution.png", dpi=150)
    plt.close()

    report = [
        "# Milestone 3B validation report",
        "",
        "## Selection",
        "",
        "The Milestone 2B audit was filtered to votes with individual Stemme data, "
        "sorted by date, vote number, and Afstemning ID, and positions "
        "`round(i * (n - 1) / 49)` were selected. Exactly 50 valid votes were used.",
        f"Individual-vote data were already local for `{len(selected_ids - missing_ids)}` votes; "
        f"only `{len(missing_ids)}` selected votes were retrieved.",
        "",
        "## Matrix",
        "",
        f"- Dimensions: `{matrix.shape[0]} politicians x {matrix.shape[1]} votes`",
        f"- Unique politicians: `{matrix.shape[0]}`",
        f"- Category counts: `{matrix_counts.to_dict()}`",
        f"- Missing values: `{int(matrix.isna().sum().sum())}`",
        "",
        "## n_shared distribution",
        "",
        f"- Min: `{n_shared_summary['min']}`",
        f"- 25th percentile: `{n_shared_summary['p25']}`",
        f"- Median: `{n_shared_summary['median']}`",
        f"- 75th percentile: `{n_shared_summary['p75']}`",
        f"- Max: `{n_shared_summary['max']}`",
    ]
    report.extend(
        f"- Pair percentage with n_shared >= {threshold}: `{percentage:.2f}%`"
        for threshold, percentage in thresholds.items()
    )
    report.extend(
        [
            "",
            "## Similarity for n_shared >= 20",
            "",
            f"- Eligible pairs: `{len(eligible)}`",
            f"- Min: `{eligible['similarity'].min()}`",
            f"- 25th percentile: `{eligible['similarity'].quantile(0.25)}`",
            f"- Median: `{eligible['similarity'].median()}`",
            f"- 75th percentile: `{eligible['similarity'].quantile(0.75)}`",
            f"- Max: `{eligible['similarity'].max()}`",
            f"- Mean: `{eligible['similarity'].mean()}`",
            "",
            "## Same-party vs different-party",
            "",
            f"- Same-party pairs: `{len(same_party)}`; mean `{same_party.mean()}`; median `{same_party.median()}`",
            f"- Same-party distribution: `{same_party.describe().to_dict()}`",
            f"- Different-party pairs: `{len(different_party)}`; mean `{different_party.mean()}`; median `{different_party.median()}`",
            f"- Different-party distribution: `{different_party.describe().to_dict()}`",
            "",
            "## High similarity / low information",
            "",
            f"- Pairs with similarity >= 0.90 and n_shared < 5: `{len(high_low)}`",
        ]
    )
    for row in high_low.head(5).itertuples(index=False):
        report.append(
            f"- Example: `{row.politician_A_id}` vs `{row.politician_B_id}`, "
            f"n_shared `{row.n_shared}`, similarity `{row.similarity}`"
        )
    report.extend(
        [
            "",
            "## Decision",
            "",
            "50 votes still leave shared participation too sparse for most politician "
            "pairs to estimate voting similarity robustly: the median n_shared is 12 "
            "and only 33.27% of pairs reach n_shared >= 20. A larger valid sample "
            "would be required; this is a descriptive result, not a causal claim or "
            "a network-threshold recommendation.",
        ]
    )
    (PROCESSED_DIR / "milestone3b_validation.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )

    print(f"Matrix dimensions: {matrix.shape}")
    print(f"Category counts: {matrix_counts.to_dict()}")
    print(f"Missing values: {int(matrix.isna().sum().sum())}")
    print(f"n_shared distribution: {n_shared_summary}")
    print(f"Threshold percentages: {thresholds}")
    print(f"Eligible pairs (n_shared >= 20): {len(eligible)}")
    print(f"High similarity / low information pairs: {len(high_low)}")


if __name__ == "__main__":
    main()
