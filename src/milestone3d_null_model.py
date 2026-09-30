"""Test observed voting similarity against a vote-preserving null model."""

from __future__ import annotations

import itertools
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
FIGURES_DIR = ROOT / "outputs" / "figures"
MATRIX_PATH = PROCESSED_DIR / "milestone3c_session_matrix.csv"
N_SHUFFLES = 100
RANDOM_SEED = 20260930
MIN_SHARED = 40
PARTICIPATED = ["For", "Imod", "Hverken for eller imod"]
ALL_CATEGORIES = PARTICIPATED + ["Fravær"]


def load_matrix() -> tuple[pd.DataFrame, pd.DataFrame]:
    saved = pd.read_csv(MATRIX_PATH)
    info = saved[["politician_id", "politician_name", "party"]].copy()
    matrix = saved.drop(columns=["politician_name", "party"]).set_index("politician_id")
    matrix.columns = [str(column) for column in matrix.columns]
    return matrix, info.set_index("politician_id")


def pair_index(n_politicians: int) -> tuple[np.ndarray, np.ndarray]:
    return tuple(
        np.array(values, dtype=int)
        for values in zip(*itertools.combinations(range(n_politicians), 2))
    )


def similarity_from_matrix(
    matrix: pd.DataFrame,
    left_indices: np.ndarray,
    right_indices: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    values = matrix.to_numpy(dtype=object)
    participating = np.isin(values, PARTICIPATED)
    n_shared = (participating[left_indices] & participating[right_indices]).sum(axis=1)
    same = np.zeros(len(left_indices), dtype=int)
    for category in PARTICIPATED:
        encoded = values == category
        same += (encoded[left_indices] & encoded[right_indices]).sum(axis=1)
    similarity = np.divide(
        same,
        n_shared,
        out=np.full(len(n_shared), np.nan, dtype=float),
        where=n_shared > 0,
    )
    return n_shared.astype(int), similarity


def shuffle_matrix(matrix: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    values = matrix.to_numpy(dtype=object).copy()
    for column_index in range(values.shape[1]):
        participating_indices = np.flatnonzero(
            np.isin(values[:, column_index], PARTICIPATED)
        )
        values[participating_indices, column_index] = rng.permutation(
            values[participating_indices, column_index]
        )
    return pd.DataFrame(values, index=matrix.index, columns=matrix.columns)


def distribution(series: pd.Series) -> dict[str, float | int]:
    return {
        "count": int(series.count()),
        "min": float(series.min()),
        "p25": float(series.quantile(0.25)),
        "median": float(series.median()),
        "mean": float(series.mean()),
        "p75": float(series.quantile(0.75)),
        "max": float(series.max()),
    }


def format_examples(
    report: list[str],
    title: str,
    examples: pd.DataFrame,
) -> None:
    report.extend(
        [
            "",
            f"### {title}",
            "",
            "| A | B | Party A | Party B | n_shared | Observed | Null mean | Excess | z-score | Empirical p |",
            "|---:|---:|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in examples.itertuples(index=False):
        report.append(
            f"| {row.politician_A_id} | {row.politician_B_id} | {row.party_A} | "
            f"{row.party_B} | {row.n_shared} | {row.observed_similarity:.4f} | "
            f"{row.null_mean_similarity:.4f} | {row.excess_similarity:.4f} | "
            f"{row.z_score:.4f} | {row.empirical_p_value:.4f} |"
        )


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    matrix, info = load_matrix()
    left_indices, right_indices = pair_index(len(matrix))
    observed_n_shared, observed_similarity = similarity_from_matrix(
        matrix, left_indices, right_indices
    )
    eligible_mask = observed_n_shared >= MIN_SHARED
    eligible_indices = np.flatnonzero(eligible_mask)

    original_counts = {
        column: matrix[column].value_counts(dropna=False).to_dict()
        for column in matrix.columns
    }
    rng = np.random.default_rng(RANDOM_SEED)
    shuffled = shuffle_matrix(matrix, rng)
    mismatch_rows: list[dict[str, object]] = []
    for column in matrix.columns:
        for category in ALL_CATEGORIES:
            original_count = int((matrix[column] == category).sum())
            shuffled_count = int((shuffled[column] == category).sum())
            if original_count != shuffled_count:
                mismatch_rows.append(
                    {
                        "vote": column,
                        "category": category,
                        "original": original_count,
                        "shuffled": shuffled_count,
                    }
                )
        original_missing = int(matrix[column].isna().sum())
        shuffled_missing = int(shuffled[column].isna().sum())
        if original_missing != shuffled_missing:
            mismatch_rows.append(
                {
                    "vote": column,
                    "category": "missing",
                    "original": original_missing,
                    "shuffled": shuffled_missing,
                }
            )
    if mismatch_rows:
        raise RuntimeError(f"One-shuffle marginal validation failed: {mismatch_rows[:5]}")

    null_similarities: list[np.ndarray] = []
    n_shared_mismatches: list[dict[str, int]] = []
    for simulation_index in range(N_SHUFFLES):
        shuffled_matrix = shuffle_matrix(matrix, rng)
        shuffled_n_shared, shuffled_similarity = similarity_from_matrix(
            shuffled_matrix, left_indices, right_indices
        )
        if not np.array_equal(shuffled_n_shared, observed_n_shared):
            mismatch_count = int((shuffled_n_shared != observed_n_shared).sum())
            n_shared_mismatches.append(
                {"simulation": simulation_index + 1, "mismatches": mismatch_count}
            )
        null_similarities.append(shuffled_similarity[eligible_mask])
    if n_shared_mismatches:
        raise RuntimeError(f"n_shared changed under null model: {n_shared_mismatches[:5]}")

    null_array = np.vstack(null_similarities)
    observed = observed_similarity[eligible_mask]
    eligible_pairs = pd.DataFrame(
        {
            "politician_A_id": matrix.index.to_numpy()[left_indices[eligible_indices]],
            "politician_B_id": matrix.index.to_numpy()[right_indices[eligible_indices]],
            "n_shared": observed_n_shared[eligible_indices],
            "observed_similarity": observed,
            "null_mean_similarity": np.nanmean(null_array, axis=0),
            "null_sd_similarity": np.nanstd(null_array, axis=0, ddof=1),
            "empirical_p_value": (
                (1 + np.sum(null_array >= observed[np.newaxis, :], axis=0))
                / (N_SHUFFLES + 1)
            ),
        }
    )
    eligible_pairs["excess_similarity"] = (
        eligible_pairs["observed_similarity"]
        - eligible_pairs["null_mean_similarity"]
    )
    eligible_pairs["z_score"] = np.where(
        eligible_pairs["null_sd_similarity"] > 0,
        eligible_pairs["excess_similarity"] / eligible_pairs["null_sd_similarity"],
        np.nan,
    )
    eligible_pairs["party_A"] = eligible_pairs["politician_A_id"].map(
        info["party"]
    )
    eligible_pairs["party_B"] = eligible_pairs["politician_B_id"].map(
        info["party"]
    )
    eligible_pairs["party_relation"] = np.where(
        eligible_pairs["party_A"] == eligible_pairs["party_B"],
        "same-party",
        "different-party",
    )
    eligible_pairs = eligible_pairs[
        [
            "politician_A_id",
            "politician_B_id",
            "party_A",
            "party_B",
            "party_relation",
            "n_shared",
            "observed_similarity",
            "null_mean_similarity",
            "null_sd_similarity",
            "excess_similarity",
            "z_score",
            "empirical_p_value",
        ]
    ]
    eligible_pairs.to_csv(
        PROCESSED_DIR / "milestone3d_null_pairwise.csv", index=False
    )

    high_raw_small_excess = eligible_pairs.sort_values(
        ["observed_similarity", "excess_similarity", "politician_A_id", "politician_B_id"],
        ascending=[False, True, True, True],
    ).head(3)
    high_excess = eligible_pairs.sort_values(
        ["excess_similarity", "observed_similarity", "politician_A_id", "politician_B_id"],
        ascending=[False, False, True, True],
    ).head(3)
    close_to_null = eligible_pairs.sort_values(
        ["excess_similarity", "politician_A_id", "politician_B_id"],
        key=lambda values: values.abs() if values.name == "excess_similarity" else values,
    ).head(3)

    same_party = eligible_pairs[
        eligible_pairs["party_relation"] == "same-party"
    ]["excess_similarity"]
    different_party = eligible_pairs[
        eligible_pairs["party_relation"] == "different-party"
    ]["excess_similarity"]

    plt.figure(figsize=(7, 4.5))
    plt.hist(
        eligible_pairs["observed_similarity"],
        bins=25,
        alpha=0.60,
        label="Observed",
        edgecolor="white",
    )
    plt.hist(
        eligible_pairs["null_mean_similarity"],
        bins=25,
        alpha=0.60,
        label="Null mean",
        edgecolor="white",
    )
    plt.xlabel("Pairwise similarity")
    plt.ylabel("Number of politician pairs")
    plt.title("Observed similarity versus vote-preserving null expectation")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "milestone3d_observed_vs_null.png", dpi=150)
    plt.close()

    observed_distribution = distribution(eligible_pairs["observed_similarity"])
    null_distribution = distribution(eligible_pairs["null_mean_similarity"])
    excess_distribution = distribution(eligible_pairs["excess_similarity"])
    z_distribution = distribution(eligible_pairs["z_score"].dropna())
    report = [
        "# Milestone 3D validation report",
        "",
        "## Null-model specification",
        "",
        f"- Source matrix: `milestone3c_session_matrix.csv`",
        f"- Valid votes: `{len(matrix.columns)}`",
        f"- Politicians: `{len(matrix.index)}`",
        f"- Eligible pairs: `{len(eligible_pairs)}` with original n_shared >= `{MIN_SHARED}`",
        f"- Simulations: `{N_SHUFFLES}`",
        f"- Random seed: `{RANDOM_SEED}` using NumPy `default_rng`",
        "- For each vote, participation, absence, and missingness were held fixed; "
        "participating political positions were permuted independently.",
        "",
        "## One-shuffle validation",
        "",
        f"- Marginal count mismatches: `{len(mismatch_rows)}`",
        f"- One-shuffle validation: `{'PASS' if not mismatch_rows else 'FAIL'}`",
        f"- n_shared mismatches across all simulations: `{len(n_shared_mismatches)}`",
        f"- n_shared invariant validation: `{'PASS' if not n_shared_mismatches else 'FAIL'}`",
        "",
        "## Pair-level distributions",
        "",
        f"- Observed similarity: `{observed_distribution}`",
        f"- Null mean similarity: `{null_distribution}`",
        f"- Excess similarity: `{excess_distribution}`",
        f"- z-scores: `{z_distribution}`",
        "",
        "## Sanity-check examples",
    ]
    format_examples(report, "High raw similarity, small excess", high_raw_small_excess)
    format_examples(report, "High excess similarity", high_excess)
    format_examples(report, "Observed similarity close to null expectation", close_to_null)
    report.extend(
        [
            "",
            "## Same-party / different-party excess similarity",
            "",
            f"- Same-party pairs: `{len(same_party)}`; mean `{same_party.mean()}`; median `{same_party.median()}`",
            f"- Different-party pairs: `{len(different_party)}`; mean `{different_party.mean()}`; median `{different_party.median()}`",
            "",
            "## Decision",
            "",
            "Yes, but not as a uniform upward shift in all pairwise similarities. "
            "The overall observed similarity distribution is close to the "
            "vote-preserving null expectation, while the positive same-party "
            "excess and negative different-party excess indicate that the mapping "
            "of positions to politicians contains structure beyond vote-level "
            "marginals. This supports proceeding to network construction as a "
            "separate, explicitly thresholded step.",
            "This is descriptive only. No edge threshold, graph, community method, "
            "or causal interpretation was introduced.",
        ]
    )
    (PROCESSED_DIR / "milestone3d_validation.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )

    print(f"Eligible pairs: {len(eligible_pairs)}")
    print(f"One-shuffle marginal mismatches: {len(mismatch_rows)}")
    print(f"n_shared mismatches: {len(n_shared_mismatches)}")
    print(f"Observed distribution: {observed_distribution}")
    print(f"Null mean distribution: {null_distribution}")
    print(f"Excess distribution: {excess_distribution}")
    print(f"z-score distribution: {z_distribution}")
    print(f"Same-party excess mean/median: {same_party.mean()} / {same_party.median()}")
    print(
        "Different-party excess mean/median: "
        f"{different_party.mean()} / {different_party.median()}"
    )


if __name__ == "__main__":
    main()
