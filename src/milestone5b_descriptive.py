"""Produce descriptive politician and party summaries for Milestone 5B.

This script reuses the validated Milestone 3C, 4C, and 5A outputs. It does
not retrieve data, rerun community detection, or change the Rule B network.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "outputs" / "figures"

MATRIX_PATH = PROCESSED / "milestone3c_session_matrix.csv"
PAIRWISE_PATH = PROCESSED / "milestone4b_null_pairwise.csv"
NODES_PATH = PROCESSED / "milestone4c_nodes.csv"
EDGES_PATH = PROCESSED / "milestone4c_edges.csv"
COMMUNITY_PATH = PROCESSED / "milestone5a_community_party_table.csv"

MIN_PARTICIPATION = 40
PARTICIPATED = {"For", "Imod", "Hverken for eller imod"}
KNOWN_PARTIES = {
    "ALT",
    "DD",
    "DF",
    "EL",
    "IA",
    "JF",
    "KF",
    "LA",
    "M",
    "N",
    "RV",
    "S",
    "SF",
    "SP",
    "V",
    "UFG",
}


def quantile(values: pd.Series, probability: float) -> float:
    return float(values.quantile(probability))


def load_population() -> pd.DataFrame:
    matrix = pd.read_csv(MATRIX_PATH)
    vote_columns = [
        column
        for column in matrix.columns
        if column not in {"politician_id", "politician_name", "party"}
    ]
    matrix["participation_count"] = matrix[vote_columns].isin(PARTICIPATED).sum(axis=1)
    matrix["participation_rate"] = matrix["participation_count"] / len(vote_columns)
    matrix["included"] = matrix["participation_count"] >= MIN_PARTICIPATION
    matrix["exclusion_reason"] = np.where(
        matrix["included"],
        "",
        f"participation_count < {MIN_PARTICIPATION} "
        "(fewer than the minimum observed participated votes)",
    )
    return matrix[
        [
            "politician_id",
            "politician_name",
            "party",
            "participation_count",
            "participation_rate",
            "included",
            "exclusion_reason",
        ]
    ].copy()


def party_summary(population: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for party, group in population.groupby("party", dropna=False, sort=True):
        label = "MISSING" if pd.isna(party) or str(party).strip() == "" else str(party)
        included = group[group["included"]]
        rows.append(
            {
                "party": label,
                "observed_count": len(group),
                "included_count": int(group["included"].sum()),
                "excluded_count": int((~group["included"]).sum()),
                "inclusion_rate": float(group["included"].mean()),
                "participation_count_min": int(group["participation_count"].min()),
                "participation_count_q25": quantile(group["participation_count"], 0.25),
                "participation_count_median": quantile(group["participation_count"], 0.5),
                "participation_count_q75": quantile(group["participation_count"], 0.75),
                "participation_count_max": int(group["participation_count"].max()),
                "participation_count_mean": float(group["participation_count"].mean()),
                "participation_rate_min": float(group["participation_rate"].min()),
                "participation_rate_median": float(group["participation_rate"].median()),
                "participation_rate_max": float(group["participation_rate"].max()),
            }
        )
    return pd.DataFrame(rows)


def community_composition() -> tuple[pd.DataFrame, pd.DataFrame]:
    wide = pd.read_csv(COMMUNITY_PATH).fillna(0)
    party_columns = sorted(
        column.removeprefix("party_")
        for column in wide.columns
        if column.startswith("party_")
    )
    long_rows = []
    diversity_rows = []
    for row in wide.itertuples(index=False):
        community = int(row.community)
        size = int(row.size)
        counts = {
            party: int(getattr(row, f"party_{party}", 0) or 0)
            for party in party_columns
        }
        nonzero = {party: count for party, count in counts.items() if count > 0}
        diversity_rows.append(
            {
                "community": community,
                "community_size": size,
                "party_diversity": len(nonzero),
                "mean_participation_rate": float(row.mean_participation_rate),
                "mean_strength": float(row.mean_strength),
            }
        )
        for party, count in counts.items():
            long_rows.append(
                {
                    "community": community,
                    "party": party,
                    "count": count,
                    "share": count / size if size else np.nan,
                    "community_size": size,
                }
            )
    return pd.DataFrame(long_rows), pd.DataFrame(diversity_rows)


def party_pair_agreement(population: pd.DataFrame) -> pd.DataFrame:
    eligible_ids = set(
        population.loc[population["included"], "politician_id"].astype(int)
    )
    pairwise = pd.read_csv(PAIRWISE_PATH)
    eligible = pairwise[
        pairwise["politician_A_id"].isin(eligible_ids)
        & pairwise["politician_B_id"].isin(eligible_ids)
        & (pairwise["n_shared"] >= MIN_PARTICIPATION)
    ].copy()
    eligible["party_left"] = eligible[["party_A", "party_B"]].min(axis=1)
    eligible["party_right"] = eligible[["party_A", "party_B"]].max(axis=1)

    edges = pd.read_csv(EDGES_PATH)
    edges["party_left"] = edges[["party_A", "party_B"]].min(axis=1)
    edges["party_right"] = edges[["party_A", "party_B"]].max(axis=1)
    edge_counts = (
        edges.groupby(["party_left", "party_right"])
        .size()
        .rename("ruleB_edge_count")
    )

    rows = []
    for (left, right), group in eligible.groupby(
        ["party_left", "party_right"], sort=True
    ):
        key = (left, right)
        positive = group["excess_similarity"] > 0
        rule_b_edges = int(edge_counts.get(key, 0))
        rows.append(
            {
                "party_A": left,
                "party_B": right,
                "party_relation": "within-party" if left == right else "between-party",
                "eligible_pair_count": len(group),
                "mean_excess_similarity": float(group["excess_similarity"].mean()),
                "median_excess_similarity": float(
                    group["excess_similarity"].median()
                ),
                "positive_excess_fraction": float(positive.mean()),
                "ruleB_edge_count": rule_b_edges,
                "ruleB_edge_fraction": (
                    rule_b_edges / len(group) if len(group) else np.nan
                ),
            }
        )
    return pd.DataFrame(rows)


def save_figures(
    summary: pd.DataFrame,
    community_long: pd.DataFrame,
    pair_agreement: pd.DataFrame,
) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    party_order = summary.sort_values(
        ["observed_count", "party"], ascending=[False, True]
    )["party"].tolist()
    plot_summary = summary.set_index("party").loc[party_order]

    ax = plot_summary[
        ["observed_count", "included_count", "excluded_count"]
    ].plot.bar(
        figsize=(10, 5),
        color=["#9fb9b7", "#1e6b68", "#c5d0d0"],
        edgecolor="none",
    )
    ax.set_xlabel("Party label")
    ax.set_ylabel("Politicians")
    ax.set_title("Observed, included, and excluded politicians by party")
    ax.legend(title="")
    ax.grid(axis="y", alpha=0.2)
    plt.tight_layout()
    plt.savefig(FIGURES / "milestone5b_party_representation.png", dpi=180)
    plt.close()

    community_pivot = community_long.pivot(
        index="community", columns="party", values="share"
    ).fillna(0)
    community_pivot = community_pivot.reindex(
        columns=sorted(community_pivot.columns), fill_value=0
    )
    ax = community_pivot.plot(
        kind="bar",
        stacked=True,
        figsize=(11, 5.5),
        colormap="tab20",
        edgecolor="none",
    )
    ax.set_xlabel("Representative community (seed 1004)")
    ax.set_ylabel("Share of community")
    ax.set_ylim(0, 1)
    ax.set_title("Party composition within representative communities")
    ax.legend(title="Party", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.grid(axis="y", alpha=0.2)
    plt.tight_layout()
    plt.savefig(FIGURES / "milestone5b_community_party.png", dpi=180)
    plt.close()

    parties = sorted(set(pair_agreement["party_A"]) | set(pair_agreement["party_B"]))
    heatmap = pd.DataFrame(np.nan, index=parties, columns=parties)
    for row in pair_agreement.itertuples(index=False):
        heatmap.loc[row.party_A, row.party_B] = row.mean_excess_similarity
        heatmap.loc[row.party_B, row.party_A] = row.mean_excess_similarity
    within = pair_agreement[pair_agreement["party_A"] == pair_agreement["party_B"]]
    for row in within.itertuples(index=False):
        heatmap.loc[row.party_A, row.party_B] = row.mean_excess_similarity

    fig, ax = plt.subplots(figsize=(9, 7))
    image = ax.imshow(heatmap.to_numpy(dtype=float), cmap="RdBu_r", vmin=-0.5, vmax=0.35)
    ax.set_xticks(range(len(parties)), parties, rotation=45, ha="right")
    ax.set_yticks(range(len(parties)), parties)
    ax.set_title("Mean excess similarity by party pair")
    fig.colorbar(image, ax=ax, label="Mean excess similarity")
    fig.tight_layout()
    fig.savefig(FIGURES / "milestone5b_party_pair_heatmap.png", dpi=180)
    plt.close(fig)


def write_validation(
    population: pd.DataFrame,
    summary: pd.DataFrame,
    community_long: pd.DataFrame,
    diversity: pd.DataFrame,
    pair_agreement: pd.DataFrame,
) -> None:
    def markdown_table(frame: pd.DataFrame) -> str:
        headers = list(frame.columns)
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
        ]
        for row in frame.itertuples(index=False, name=None):
            lines.append("| " + " | ".join(str(value) for value in row) + " |")
        return "\n".join(lines)

    missing = int(population["party"].isna().sum())
    unknown = int(
        population["party"].fillna("").astype(str).str.strip().str.upper().isin(
            {"", "UNKNOWN", "UKENDT", "N/A", "NA"}
        ).sum()
    )
    ufg = int((population["party"] == "UFG").sum())
    excluded = population[~population["included"]]
    community_sizes = diversity[["community", "community_size", "party_diversity"]]
    overall_counts = population["participation_count"]
    overall_rates = population["participation_rate"]
    lines = [
        "# Milestone 5B descriptive validation",
        "",
        "## Scope and denominator definitions",
        "",
        "- Reused only `milestone3c_session_matrix.csv`, `milestone4b_null_pairwise.csv`, `milestone4c_nodes.csv`, `milestone4c_edges.csv`, and `milestone5a_community_party_table.csv`.",
        "- No new data were retrieved, no thresholds were changed, and no community detection was rerun.",
        "- Observed population: all 188 politicians in the Milestone 3C session matrix.",
        "- Participation count: number of `For`, `Imod`, or `Hverken for eller imod` values across 168 valid votes; `Fravær` is not participation.",
        "- Inclusion denominator: 188 observed politicians; inclusion requires participation count >= 40.",
        "- Eligible pair denominator: unordered pairs among included politicians with `n_shared >= 40` (8,794 pairs).",
        "- Rule B edge denominator: the same eligible pairs; an edge additionally requires positive excess similarity and q < 0.05.",
        "",
        "## Population reconciliation",
        "",
        f"- Observed politicians: `{len(population)}` (expected 188)",
        f"- Included politicians: `{int(population['included'].sum())}` (expected 150)",
        f"- Excluded politicians: `{len(excluded)}` (expected 38)",
        f"- Included + excluded: `{int(population['included'].sum()) + len(excluded)}`",
        f"- Participation rule: `participation_count >= {MIN_PARTICIPATION}`",
        "",
        "## Party metadata quality",
        "",
        "- Party labels are the official short labels carried into Milestone 3C from the actor biography `partyShortname` field.",
        "- They are biography metadata values available in the retrieved actor records, not a reconstructed historical party-membership series for each vote.",
        "- No historical party label was assigned silently; labels were reused exactly as stored in the validated matrix.",
        f"- Missing party labels: `{missing}`",
        f"- Unknown/blank party labels by token check: `{unknown}`",
        f"- UFG labels: `{ufg}`",
        f"- Labels outside the documented known-label set: `{sorted(set(population['party'].dropna()) - KNOWN_PARTIES)}`",
        "",
        "## Overall participation distribution",
        "",
        f"- Participation count: min `{int(overall_counts.min())}`, Q1 `{quantile(overall_counts, 0.25):.2f}`, median `{quantile(overall_counts, 0.5):.2f}`, Q3 `{quantile(overall_counts, 0.75):.2f}`, max `{int(overall_counts.max())}`, mean `{overall_counts.mean():.2f}`.",
        f"- Participation rate: min `{overall_rates.min():.4f}`, Q1 `{overall_rates.quantile(0.25):.4f}`, median `{overall_rates.median():.4f}`, Q3 `{overall_rates.quantile(0.75):.4f}`, max `{overall_rates.max():.4f}`, mean `{overall_rates.mean():.4f}`.",
        "",
        "## Participation and inclusion by party",
        "",
        "The following party-level inclusion rates are descriptive only. They identify how the >=40 rule changes representation; they do not interpret the cause of participation differences.",
        markdown_table(
            summary[
                [
                    "party",
                    "observed_count",
                    "included_count",
                    "excluded_count",
                    "inclusion_rate",
                    "participation_count_min",
                    "participation_count_median",
                    "participation_count_max",
                ]
            ].sort_values("party")
        ),
        "",
        "## Milestone 4C and 5A reconciliation",
        "",
        f"- Rule B nodes: `{len(pd.read_csv(NODES_PATH))}` (expected 150)",
        f"- Rule B edges: `{len(pd.read_csv(EDGES_PATH))}` (expected 3,086)",
        f"- Representative communities: `{diversity['community'].nunique()}` (expected 9)",
        f"- Representative community members: `{int(diversity['community_size'].sum())}` (expected 150)",
        f"- Eligible pair rows used for party-pair summaries: `{sum(pair_agreement['eligible_pair_count'])}` (expected 8,794)",
        f"- Rule B edges represented in party-pair summaries: `{int(pair_agreement['ruleB_edge_count'].sum())}` (expected 3,086)",
        "",
        "## Community sizes and party diversity",
        "",
        markdown_table(community_sizes),
        "",
        "## Exclusion interpretation",
        "",
        f"- All `{len(excluded)}` exclusions have the exact rule-based reason: participation count below `{MIN_PARTICIPATION}`.",
        "- Exclusion is descriptive and does not interpret why participation differs.",
        "",
        "## Party-pair agreement interpretation",
        "",
        "- Mean and median excess similarity summarize pairwise agreement relative to the existing vote-preserving null.",
        "- Positive-excess fraction counts eligible politician pairs with excess similarity > 0.",
        "- Rule B edge fraction counts only graph edges under the already validated Rule B definition; it is not the same quantity as positive excess fraction.",
    ]
    (PROCESSED / "milestone5b_validation.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    population = load_population()
    summary = party_summary(population)
    excluded = population[~population["included"]].copy()
    excluded.to_csv(PROCESSED / "milestone5b_excluded_politicians.csv", index=False)
    summary.to_csv(PROCESSED / "milestone5b_party_summary.csv", index=False)

    community_long, diversity = community_composition()
    community_output = community_long.merge(
        diversity[["community", "party_diversity"]],
        on="community",
        how="left",
    )
    community_output.to_csv(PROCESSED / "milestone5b_community_party.csv", index=False)

    pair_agreement = party_pair_agreement(population)
    pair_agreement.to_csv(
        PROCESSED / "milestone5b_party_pair_agreement.csv", index=False
    )
    save_figures(summary, community_long, pair_agreement)
    write_validation(population, summary, community_long, diversity, pair_agreement)

    print(f"Observed politicians: {len(population)}")
    print(f"Included politicians: {int(population['included'].sum())}")
    print(f"Excluded politicians: {len(excluded)}")
    print(f"Eligible pair rows: {int(pair_agreement['eligible_pair_count'].sum())}")
    print(f"Rule B edges represented: {int(pair_agreement['ruleB_edge_count'].sum())}")
    print("Milestone 5B outputs written.")


if __name__ == "__main__":
    main()
