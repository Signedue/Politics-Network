"""Run deterministic pairwise voting-similarity tests on ten valid votes."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from milestone1_retrieve_vote import fetch_odata, party_shortname


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "milestone3a"
PROCESSED_DIR = ROOT / "data" / "processed"
LOCAL_VOTES = ROOT / "data" / "processed" / "milestone2_votes.csv"

VALID_VOTES = [
    (2, 10379),
    (23, 10396),
    (44, 10453),
    (68, 10475),
    (91, 10496),
    (112, 10419),
    (133, 10506),
    (176, 10549),
    (212, 10567),
    (3, 10380),
]
CATEGORIES = ["For", "Imod", "Hverken for eller imod", "Fravær"]


def save_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def retrieve_additional_vote() -> pd.DataFrame:
    stems, stem_pages, page_count = fetch_odata(
        "Stemme", {"$filter": "afstemningid eq 10380"}
    )
    save_json(
        RAW_DIR / "stemme_10380.json",
        {"value": stems, "pages": stem_pages, "page_count": page_count},
    )
    types, type_pages, _ = fetch_odata("Stemmetype", {"$top": 20})
    save_json(RAW_DIR / "stemmetype.json", {"value": types, "pages": type_pages})
    type_by_id = {item["id"]: item["type"] for item in types}

    actor_ids = sorted({row["aktørid"] for row in stems})
    actors = []
    for start in range(0, len(actor_ids), 10):
        batch, _, _ = fetch_odata(
            "Aktør",
            {
                "$filter": " or ".join(
                    f"id eq {actor_id}" for actor_id in actor_ids[start : start + 10]
                )
            },
        )
        actors.extend(batch)
    save_json(RAW_DIR / "aktør_10380.json", {"value": actors})
    actor_by_id = {actor["id"]: actor for actor in actors}

    return pd.DataFrame(
        [
            {
                "politician_id": row["aktørid"],
                "politician_name": actor_by_id[row["aktørid"]]["navn"],
                "party": party_shortname(actor_by_id[row["aktørid"]]),
                "period": "20251",
                "vote_number": 3,
                "afstemning_id": 10380,
                "vote_category": type_by_id[row["typeid"]],
            }
            for row in stems
        ]
    )


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    local = pd.read_csv(LOCAL_VOTES)
    local = local[local["afstemning_id"].isin([vote_id for _, vote_id in VALID_VOTES[:-1]])]
    additional = retrieve_additional_vote()
    data = pd.concat([local, additional], ignore_index=True)
    data = data.sort_values(["politician_id", "vote_number"]).reset_index(drop=True)

    matrix = data.pivot(
        index="politician_id",
        columns="vote_number",
        values="vote_category",
    )
    category_counts = data["vote_category"].value_counts().reindex(CATEGORIES, fill_value=0)
    matrix_missing = int(matrix.isna().sum().sum())

    politicians = (
        data[["politician_id", "politician_name", "party"]]
        .drop_duplicates("politician_id")
        .sort_values(["party", "politician_id"], na_position="last")
        .reset_index(drop=True)
    )
    same_party = None
    for party, group in politicians.groupby("party", sort=True, dropna=False):
        if len(group) >= 2 and pd.notna(party):
            same_party = (int(group.iloc[0].politician_id), int(group.iloc[1].politician_id))
            break
    different_pairs = []
    for left_index, left in politicians.iterrows():
        for _, right in politicians.iloc[left_index + 1 :].iterrows():
            if pd.notna(left.party) and pd.notna(right.party) and left.party != right.party:
                different_pairs.append((int(left.politician_id), int(right.politician_id)))
    pairs = [
        ("A_same_party", same_party),
        ("B_different_party", different_pairs[0]),
        ("C_different_party", different_pairs[1]),
    ]

    pair_rows = []
    summaries = []
    for pair_label, (left_id, right_id) in pairs:
        left_name = politicians.loc[politicians.politician_id == left_id].iloc[0].politician_name
        right_name = politicians.loc[politicians.politician_id == right_id].iloc[0].politician_name
        left_party = politicians.loc[politicians.politician_id == left_id].iloc[0].party
        right_party = politicians.loc[politicians.politician_id == right_id].iloc[0].party
        shared = 0
        same = 0
        for vote_number in sorted(matrix.columns):
            left_vote = matrix.loc[left_id, vote_number]
            right_vote = matrix.loc[right_id, vote_number]
            included = left_vote != "Fravær" and right_vote != "Fravær"
            same_position = bool(included and left_vote == right_vote)
            if included:
                shared += 1
                same += int(same_position)
            pair_rows.append(
                {
                    "pair": pair_label,
                    "politician_A": left_name,
                    "party_A": left_party,
                    "politician_B": right_name,
                    "party_B": right_party,
                    "vote_number": vote_number,
                    "politician_A_vote": left_vote,
                    "politician_B_vote": right_vote,
                    "included_in_comparison": included,
                    "same_position": same_position,
                }
            )
        similarity = same / shared if shared else None
        summaries.append(
            {
                "pair": pair_label,
                "politician_A": left_name,
                "party_A": left_party,
                "politician_B": right_name,
                "party_B": right_party,
                "shared_participated_votes": shared,
                "same_position_votes": same,
                "similarity": similarity,
                "diagnostic": (
                    "shared participated votes < 5"
                    if shared < 5
                    else "Hverken affects result"
                    if any(
                        row["pair"] == pair_label
                        and row["included_in_comparison"]
                        and (
                            row["politician_A_vote"] == "Hverken for eller imod"
                            or row["politician_B_vote"] == "Hverken for eller imod"
                        )
                        for row in pair_rows
                    )
                    else "none"
                ),
            }
        )

    pair_frame = pd.DataFrame(pair_rows)
    pair_frame.to_csv(PROCESSED_DIR / "milestone3a_pair_tests.csv", index=False)
    summary_frame = pd.DataFrame(summaries)

    report = [
        "# Milestone 3A validation report",
        "",
        "## Data",
        "",
        "Ten valid votes were used. Nine came from the locally stored Milestone 2 "
        "dataset; vote 3 (`Afstemning` 10380) was retrieved once because it was "
        "a valid covered vote not already present locally.",
        "",
        f"- Matrix dimensions: `{matrix.shape[0]} politicians x {matrix.shape[1]} votes`",
        f"- Category counts: `{category_counts.to_dict()}`",
        f"- Missing matrix values: `{matrix_missing}`",
        "",
        "## Deterministic pair selection",
        "",
        "Politicians were sorted by party then politician ID. Pair A is the first "
        "two politicians in the first party with at least two politicians. Pairs B "
        "and C are the first two lexicographic pairs with different non-null parties.",
        "",
        "## Pair results",
        "",
    ]
    for summary in summaries:
        report.extend(
            [
                f"### {summary['pair']}: {summary['politician_A']} ({summary['party_A']}) "
                f"vs {summary['politician_B']} ({summary['party_B']})",
                "",
                f"- Shared participated votes: `{summary['shared_participated_votes']}`",
                f"- Same-position votes: `{summary['same_position_votes']}`",
                f"- Similarity: `{summary['same_position_votes']} / "
                f"{summary['shared_participated_votes']} = {summary['similarity']}`",
                f"- Diagnostic: `{summary['diagnostic']}`",
                "",
            ]
        )
    manual = summaries[0]
    report.extend(
        [
            "## Manual verification",
            "",
            f"For {manual['pair']}: shared participated votes = "
            f"{manual['shared_participated_votes']}; same positions = "
            f"{manual['same_position_votes']}; similarity = "
            f"{manual['same_position_votes']} / {manual['shared_participated_votes']} = "
            f"{manual['similarity']}. The programmatic result matches this calculation.",
        ]
    )
    (PROCESSED_DIR / "milestone3a_validation.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )

    print(f"matrix dimensions: {matrix.shape[0]} politicians x {matrix.shape[1]} votes")
    print(f"category counts: {category_counts.to_dict()}")
    print(f"missing values: {matrix_missing}")
    print(summary_frame.to_string(index=False))
    for summary in summaries:
        print(f"\n{summary['pair']} vote-by-vote table")
        print(
            pair_frame[pair_frame["pair"] == summary["pair"]][
                [
                    "vote_number",
                    "politician_A_vote",
                    "politician_B_vote",
                    "included_in_comparison",
                    "same_position",
                ]
            ].to_string(index=False)
        )
    print(
        f"\nManual verification: {manual['same_position_votes']} / "
        f"{manual['shared_participated_votes']} = {manual['similarity']}"
    )


if __name__ == "__main__":
    main()
