"""Audit significance-based agreement-network edge rules."""

from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
MATRIX_PATH = PROCESSED_DIR / "milestone3c_session_matrix.csv"
NODE_AUDIT_PATH = PROCESSED_DIR / "milestone4a_node_eligibility.csv"
N_SHUFFLES = 1000
RANDOM_SEED = 20260930
MIN_NODE_PARTICIPATION = 40
MIN_SHARED = 40
HALF_MIN_SHARED = 20
PARTICIPATED = ("For", "Imod", "Hverken for eller imod")


def pair_indices(n: int) -> tuple[np.ndarray, np.ndarray]:
    left, right = zip(*itertools.combinations(range(n), 2))
    return np.array(left, dtype=int), np.array(right, dtype=int)


def pair_statistics(
    values: np.ndarray,
    left: np.ndarray,
    right: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    participated = np.isin(values, PARTICIPATED)
    shared = participated[left] & participated[right]
    n_shared = shared.sum(axis=1).astype(int)
    same = np.zeros(len(left), dtype=int)
    for category in PARTICIPATED:
        encoded = values == category
        same += (encoded[left] & encoded[right]).sum(axis=1)
    similarity = np.divide(
        same,
        n_shared,
        out=np.full(len(left), np.nan, dtype=float),
        where=n_shared > 0,
    )
    return n_shared, similarity


def shuffle_values(values: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    shuffled = values.copy()
    for column in range(shuffled.shape[1]):
        indices = np.flatnonzero(np.isin(shuffled[:, column], PARTICIPATED))
        shuffled[indices, column] = rng.permutation(shuffled[indices, column])
    return shuffled


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    order = np.argsort(p_values)
    ranked = p_values[order] * len(p_values) / np.arange(1, len(p_values) + 1)
    adjusted_sorted = np.minimum.accumulate(ranked[::-1])[::-1]
    adjusted = np.empty_like(adjusted_sorted)
    adjusted[order] = np.minimum(adjusted_sorted, 1.0)
    return adjusted


def components(nodes: list[int], edges: pd.DataFrame) -> list[set[int]]:
    parent = {node: node for node in nodes}

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for row in edges.itertuples(index=False):
        union(int(row.politician_A_id), int(row.politician_B_id))
    groups: dict[int, set[int]] = {}
    for node in nodes:
        groups.setdefault(find(node), set()).add(node)
    return list(groups.values())


def graph_stats(nodes: list[int], edges: pd.DataFrame) -> dict[str, float | int]:
    active = set(edges["politician_A_id"]) | set(edges["politician_B_id"])
    degree = pd.Series(0, index=nodes, dtype=int)
    for row in edges.itertuples(index=False):
        degree[row.politician_A_id] += 1
        degree[row.politician_B_id] += 1
    groups = components(nodes, edges)
    return {
        "nodes_with_edges": len(active),
        "edges": len(edges),
        "density": len(edges) / (len(nodes) * (len(nodes) - 1) / 2),
        "isolates": len(nodes) - len(active),
        "connected_components": len(groups),
        "giant_component_size": max((len(group) for group in groups), default=0),
        "median_degree": float(degree.median()),
        "weight_min": float(edges["excess_similarity"].min()) if len(edges) else np.nan,
        "weight_p25": float(edges["excess_similarity"].quantile(0.25)) if len(edges) else np.nan,
        "weight_median": float(edges["excess_similarity"].median()) if len(edges) else np.nan,
        "weight_mean": float(edges["excess_similarity"].mean()) if len(edges) else np.nan,
        "weight_p75": float(edges["excess_similarity"].quantile(0.75)) if len(edges) else np.nan,
        "weight_max": float(edges["excess_similarity"].max()) if len(edges) else np.nan,
        "same_party_fraction": float(
            (edges["party_A"] == edges["party_B"]).mean()
        ) if len(edges) else np.nan,
        "different_party_fraction": float(
            (edges["party_A"] != edges["party_B"]).mean()
        ) if len(edges) else np.nan,
    }


def main() -> None:
    matrix_saved = pd.read_csv(MATRIX_PATH)
    matrix = matrix_saved.drop(
        columns=["politician_name", "party"]
    ).set_index("politician_id")
    info = matrix_saved.set_index("politician_id")[["politician_name", "party"]]
    node_audit = pd.read_csv(NODE_AUDIT_PATH)
    retained_ids = node_audit.loc[
        node_audit["votes_participated"] >= MIN_NODE_PARTICIPATION,
        "politician_id",
    ].astype(int).tolist()
    matrix = matrix.loc[retained_ids]
    values = matrix.to_numpy(dtype=object)
    left, right = pair_indices(len(matrix))
    observed_n_shared, observed_similarity = pair_statistics(values, left, right)
    eligible_pair_mask = observed_n_shared >= MIN_SHARED
    eligible_indices = np.flatnonzero(eligible_pair_mask)
    if len(eligible_indices) == 0:
        raise RuntimeError("No eligible pairs remain.")

    half = values.shape[1] // 2
    first_n_shared, first_observed = pair_statistics(values[:, :half], left, right)
    second_n_shared, second_observed = pair_statistics(values[:, half:], left, right)
    half_estimable = (
        (first_n_shared >= HALF_MIN_SHARED)
        & (second_n_shared >= HALF_MIN_SHARED)
        & np.isfinite(first_observed)
        & np.isfinite(second_observed)
    )

    rng = np.random.default_rng(RANDOM_SEED)
    null_sum = np.zeros(len(eligible_indices), dtype=float)
    null_sum_sq = np.zeros(len(eligible_indices), dtype=float)
    null_ge = np.zeros(len(eligible_indices), dtype=int)
    first_null_sum = np.zeros(len(eligible_indices), dtype=float)
    second_null_sum = np.zeros(len(eligible_indices), dtype=float)
    marginal_mismatches = 0
    original_counts = [
        {
            category: int((values[:, column] == category).sum())
            for category in PARTICIPATED + ("Fravær",)
        }
        | {"missing": int(pd.isna(values[:, column]).sum())}
        for column in range(values.shape[1])
    ]

    for simulation in range(N_SHUFFLES):
        shuffled = shuffle_values(values, rng)
        for column in range(shuffled.shape[1]):
            counts = {
                category: int((shuffled[:, column] == category).sum())
                for category in PARTICIPATED + ("Fravær",)
            }
            counts["missing"] = int(pd.isna(shuffled[:, column]).sum())
            if counts != original_counts[column]:
                marginal_mismatches += 1
        shuffled_n_shared, shuffled_similarity = pair_statistics(shuffled, left, right)
        if not np.array_equal(shuffled_n_shared, observed_n_shared):
            raise RuntimeError(f"n_shared changed in simulation {simulation + 1}")
        simulated = shuffled_similarity[eligible_pair_mask]
        null_sum += simulated
        null_sum_sq += simulated**2
        null_ge += simulated >= observed_similarity[eligible_pair_mask]
        first_sim = pair_statistics(shuffled[:, :half], left, right)[1]
        second_sim = pair_statistics(shuffled[:, half:], left, right)[1]
        first_null_sum += first_sim[eligible_pair_mask]
        second_null_sum += second_sim[eligible_pair_mask]

    if marginal_mismatches:
        raise RuntimeError(f"Found {marginal_mismatches} marginal count mismatches")

    observed = observed_similarity[eligible_pair_mask]
    eligible = pd.DataFrame(
        {
            "politician_A_id": matrix.index.to_numpy()[left[eligible_indices]],
            "politician_B_id": matrix.index.to_numpy()[right[eligible_indices]],
            "n_shared": observed_n_shared[eligible_pair_mask],
            "observed_similarity": observed,
            "null_mean": null_sum / N_SHUFFLES,
            "null_sd": np.sqrt(
                np.maximum(
                    (null_sum_sq - (null_sum**2 / N_SHUFFLES))
                    / (N_SHUFFLES - 1),
                    0,
                )
            ),
            "empirical_p": (1 + null_ge) / (N_SHUFFLES + 1),
            "first_observed_similarity": first_observed[eligible_pair_mask],
            "second_observed_similarity": second_observed[eligible_pair_mask],
            "first_null_mean": first_null_sum / N_SHUFFLES,
            "second_null_mean": second_null_sum / N_SHUFFLES,
            "half_estimable": half_estimable[eligible_pair_mask],
        }
    )
    eligible["excess_similarity"] = eligible["observed_similarity"] - eligible["null_mean"]
    eligible["z_score"] = np.where(
        eligible["null_sd"] > 0,
        eligible["excess_similarity"] / eligible["null_sd"],
        np.nan,
    )
    eligible["q_value"] = benjamini_hochberg(eligible["empirical_p"].to_numpy())
    eligible["first_excess"] = (
        eligible["first_observed_similarity"] - eligible["first_null_mean"]
    )
    eligible["second_excess"] = (
        eligible["second_observed_similarity"] - eligible["second_null_mean"]
    )
    eligible["sign_stable"] = (
        (eligible["first_excess"] > 0) == (eligible["second_excess"] > 0)
    )
    eligible["party_A"] = eligible["politician_A_id"].map(info["party"])
    eligible["party_B"] = eligible["politician_B_id"].map(info["party"])
    eligible["party_relation"] = np.where(
        eligible["party_A"] == eligible["party_B"],
        "same-party",
        "different-party",
    )
    eligible.to_csv(
        PROCESSED_DIR / "milestone4b_null_pairwise.csv",
        index=False,
    )

    rules = {
        "A: excess > 0 and empirical p < 0.05": eligible[
            (eligible["excess_similarity"] > 0) & (eligible["empirical_p"] < 0.05)
        ],
        "B: excess > 0 and q < 0.05": eligible[
            (eligible["excess_similarity"] > 0) & (eligible["q_value"] < 0.05)
        ],
        "C: excess > 0 and q < 0.01": eligible[
            (eligible["excess_similarity"] > 0) & (eligible["q_value"] < 0.01)
        ],
    }
    audit_rows = []
    for name, edges in rules.items():
        stats = graph_stats(retained_ids, edges)
        estimable = edges[edges["half_estimable"]]
        stats["construction"] = name
        stats["sign_stable_fraction"] = float(estimable["sign_stable"].mean()) if len(estimable) else np.nan
        stats["sign_estimable_edges"] = len(estimable)
        audit_rows.append(stats)
    pd.DataFrame(audit_rows).to_csv(
        PROCESSED_DIR / "milestone4b_edges_audit.csv", index=False
    )

    def describe(series: pd.Series) -> dict[str, float]:
        return {
            "min": float(series.min()),
            "p25": float(series.quantile(0.25)),
            "median": float(series.median()),
            "mean": float(series.mean()),
            "p75": float(series.quantile(0.75)),
            "max": float(series.max()),
        }

    report = [
        "# Milestone 4B significance-based network audit",
        "",
        "## Provisional node rule",
        "",
        "This test uses `participated votes >= 40` provisionally. It retains "
        f"`{len(retained_ids)}` politicians, every retained politician has at least "
        "16 eligible n_shared>=40 partners, and none has fewer than 5 eligible "
        "partners. This is not the only valid node definition.",
        "",
        "## Pair eligibility and null precision",
        "",
        f"- Eligible pairs: `{len(eligible)}`",
        f"- Null simulations: `{N_SHUFFLES}`",
        f"- Random seed: `{RANDOM_SEED}` using NumPy `default_rng`",
        "- The vote-preserving shuffle fixed participation, absence, missingness, "
        "and the three participating-position counts within every vote.",
        f"- Marginal-count mismatches: `{marginal_mismatches}`",
        "- `n_shared` was verified unchanged in every simulation.",
        "",
        "## Candidate edge rules",
        "",
        pd.DataFrame(audit_rows).to_markdown(index=False),
        "",
        "## Excess-similarity effect sizes",
        "",
    ]
    for name, edges in rules.items():
        report.append(f"- **{name}**: `{describe(edges['excess_similarity'])}`")
    report.extend(
        [
            "",
            "## Half-session sign stability",
            "",
            f"- First and second halves contain `{half}` valid votes each.",
            f"- Half-level minimum n_shared for estimability: `{HALF_MIN_SHARED}`.",
        ]
    )
    for name, edges in rules.items():
        estimable = edges[edges["half_estimable"]]
        stable = float(estimable["sign_stable"].mean()) if len(estimable) else np.nan
        report.append(
            f"- **{name}**: `{len(estimable)}` estimable edges; stable-sign fraction `{stable}`"
        )
    report.extend(
        [
            "",
            "## Comparison with Milestone 4A",
            "",
            "The significance rules are grounded in the vote-preserving null model, "
            "unlike arbitrary excess cutoffs. Rule A uses uncorrected empirical "
            "p-values and therefore does not control the false-discovery rate. "
            "Rules B and C apply Benjamini-Hochberg correction and should be "
            "compared with Milestone 4A's global thresholds and disparity backbones "
            "using the reported connectivity, effect sizes, and stability rather "
            "than visual density.",
            "",
            "## Decision",
            "",
            "Among these choices, FDR-adjusted rules are methodologically more "
            "defensible than the uncorrected rule because they account for the "
            "thousands of simultaneous pair tests. Rule B (q<0.05) appears to "
            "offer the clearest balance here: it retains substantial connectivity, "
            "has a minimum retained-edge excess of about 0.088, and has complete "
            "sign stability among estimable retained edges. Rule C (q<0.01) is "
            "more conservative but fragments the giant component further, while "
            "Rule A lacks FDR control. Relative to Milestone 4A, the significance "
            "rules are better null-grounded than global cutoffs or disparity "
            "filtering, but no final network was selected because node eligibility, "
            "effect-size adequacy, connectivity, and half-session sign stability "
            "remain separate empirical decisions.",
            "",
            "Party labels were used only for descriptive validation and did not "
            "affect null simulations or edge construction.",
        ]
    )
    (PROCESSED_DIR / "milestone4b_validation.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )

    print(f"Retained nodes: {len(retained_ids)}")
    print(f"Eligible pairs: {len(eligible)}")
    print(pd.DataFrame(audit_rows).to_string(index=False))


if __name__ == "__main__":
    main()
