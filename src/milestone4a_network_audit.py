"""Audit candidate agreement-network constructions without community detection."""

from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
MATRIX_PATH = PROCESSED_DIR / "milestone3c_session_matrix.csv"
PAIRWISE_PATH = PROCESSED_DIR / "milestone3d_null_pairwise.csv"
NODE_RULES = [20, 40, 60, 80]
GLOBAL_THRESHOLDS = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25]
BACKBONE_ALPHAS = [0.05, 0.10, 0.20, 0.30]
PARTICIPATED = {"For", "Imod", "Hverken for eller imod"}
def connected_components(nodes: list[int], edges: pd.DataFrame) -> list[set[int]]:
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


def graph_stats(
    nodes: list[int],
    edges: pd.DataFrame,
    all_nodes: list[int],
) -> dict[str, float | int]:
    edge_pairs = set(
        zip(edges["politician_A_id"], edges["politician_B_id"])
    )
    active = set(edges["politician_A_id"]) | set(edges["politician_B_id"])
    components = connected_components(nodes, edges)
    degree = pd.Series(0, index=all_nodes, dtype=int)
    for row in edges.itertuples(index=False):
        degree[row.politician_A_id] += 1
        degree[row.politician_B_id] += 1
    return {
        "nodes_total": len(nodes),
        "nodes_with_edges": len(active),
        "edges": len(edge_pairs),
        "density": (
            len(edge_pairs) / (len(nodes) * (len(nodes) - 1) / 2)
            if len(nodes) > 1
            else 0.0
        ),
        "isolates": len(nodes) - len(active),
        "components": len(components),
        "giant_component_size": max((len(component) for component in components), default=0),
        "median_degree": float(degree.reindex(nodes).median()) if nodes else 0.0,
        "weight_min": float(edges["excess_similarity"].min()) if len(edges) else np.nan,
        "weight_median": float(edges["excess_similarity"].median()) if len(edges) else np.nan,
        "weight_mean": float(edges["excess_similarity"].mean()) if len(edges) else np.nan,
        "weight_max": float(edges["excess_similarity"].max()) if len(edges) else np.nan,
        "same_party_fraction": (
            float((edges["party_A"] == edges["party_B"]).mean()) if len(edges) else np.nan
        ),
        "different_party_fraction": (
            float((edges["party_A"] != edges["party_B"]).mean()) if len(edges) else np.nan
        ),
    }


def edge_set(edges: pd.DataFrame) -> set[tuple[int, int]]:
    return set(zip(edges["politician_A_id"], edges["politician_B_id"]))


def jaccard(left: pd.DataFrame, right: pd.DataFrame) -> float:
    left_set, right_set = edge_set(left), edge_set(right)
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 1.0


def disparity_backbone(edges: pd.DataFrame, alpha: float) -> pd.DataFrame:
    if edges.empty:
        return edges.copy()
    degree = pd.concat(
        [edges["politician_A_id"], edges["politician_B_id"]]
    ).value_counts()
    strength: dict[int, float] = {}
    for row in edges.itertuples(index=False):
        strength[row.politician_A_id] = strength.get(row.politician_A_id, 0.0) + row.excess_similarity
        strength[row.politician_B_id] = strength.get(row.politician_B_id, 0.0) + row.excess_similarity
    keep: list[bool] = []
    alpha_left: list[float] = []
    alpha_right: list[float] = []
    for row in edges.itertuples(index=False):
        left_degree = int(degree[row.politician_A_id])
        right_degree = int(degree[row.politician_B_id])
        left_p = row.excess_similarity / strength[row.politician_A_id]
        right_p = row.excess_similarity / strength[row.politician_B_id]
        left_alpha = 0.0 if left_degree <= 1 else (1.0 - left_p) ** (left_degree - 1)
        right_alpha = 0.0 if right_degree <= 1 else (1.0 - right_p) ** (right_degree - 1)
        alpha_left.append(left_alpha)
        alpha_right.append(right_alpha)
        keep.append(left_alpha <= alpha or right_alpha <= alpha)
    result = edges.loc[keep].copy()
    result["alpha_A"] = np.array(alpha_left)[keep]
    result["alpha_B"] = np.array(alpha_right)[keep]
    return result


def main() -> None:
    matrix = pd.read_csv(MATRIX_PATH)
    matrix_values = matrix.drop(columns=["politician_name", "party"]).set_index("politician_id")
    all_nodes = [int(node) for node in matrix_values.index]
    participation = matrix_values.isin(PARTICIPATED).sum(axis=1)
    recorded = matrix_values.notna().sum(axis=1)
    pairwise = pd.read_csv(PAIRWISE_PATH)
    pairwise = pairwise[pairwise["n_shared"] >= 40].copy()
    pairwise["excess_similarity"] = (
        pairwise["observed_similarity"] - pairwise["null_mean_similarity"]
    )
    positive = pairwise[pairwise["excess_similarity"] > 0].copy()

    pair_counts = pd.concat(
        [pairwise["politician_A_id"], pairwise["politician_B_id"]]
    ).value_counts()
    node_rows = pd.DataFrame(
        {
            "politician_id": all_nodes,
            "votes_with_recorded_row": [int(recorded[node]) for node in all_nodes],
            "votes_participated": [int(participation[node]) for node in all_nodes],
            "participation_rate": [float(participation[node] / len(matrix_values.columns)) for node in all_nodes],
            "eligible_pairs_n_shared_ge_40": [int(pair_counts.get(node, 0)) for node in all_nodes],
        }
    )
    node_rows.to_csv(PROCESSED_DIR / "milestone4a_node_eligibility.csv", index=False)

    eligibility_rows = []
    for minimum in NODE_RULES:
        retained = node_rows[node_rows["votes_participated"] >= minimum]
        eligible_counts = retained["eligible_pairs_n_shared_ge_40"]
        eligibility_rows.append(
            {
                "construction": f"node participation >= {minimum}",
                "nodes_retained": len(retained),
                "median_eligible_pairs": float(eligible_counts.median()) if len(retained) else 0.0,
                "minimum_eligible_pairs": int(eligible_counts.min()) if len(retained) else 0,
                "nodes_with_fewer_than_5_eligible_partners": int((eligible_counts < 5).sum()),
            }
        )

    audit_rows: list[dict[str, object]] = []
    candidate_stats = graph_stats(all_nodes, positive, all_nodes)
    audit_rows.append({"construction": "candidate positive excess graph", **candidate_stats})
    global_graphs: dict[float, pd.DataFrame] = {}
    for threshold in GLOBAL_THRESHOLDS:
        if threshold == 0:
            edges = pairwise[pairwise["excess_similarity"] > 0].copy()
        else:
            edges = pairwise[pairwise["excess_similarity"] >= threshold].copy()
        global_graphs[threshold] = edges
        audit_rows.append(
            {
                "construction": (
                    "global excess > 0"
                    if threshold == 0
                    else f"global excess >= {threshold:.2f}"
                ),
                **graph_stats(all_nodes, edges, all_nodes),
            }
        )

    backbone_graphs: dict[float, pd.DataFrame] = {}
    for alpha in BACKBONE_ALPHAS:
        edges = disparity_backbone(positive, alpha)
        backbone_graphs[alpha] = edges
        audit_rows.append(
            {"construction": f"disparity alpha <= {alpha:.2f}", **graph_stats(all_nodes, edges, all_nodes)}
        )
    network_audit = pd.DataFrame(audit_rows)
    network_audit.to_csv(PROCESSED_DIR / "milestone4a_network_audit.csv", index=False)

    backbone_audit_rows = []
    for left, right in zip(GLOBAL_THRESHOLDS, GLOBAL_THRESHOLDS[1:]):
        backbone_audit_rows.append(
            {
                "family": "global threshold",
                "setting_left": "> 0" if left == 0 else f">= {left:.2f}",
                "setting_right": f">= {right:.2f}",
                "jaccard_edge_overlap": jaccard(global_graphs[left], global_graphs[right]),
            }
        )
    for left, right in zip(BACKBONE_ALPHAS, BACKBONE_ALPHAS[1:]):
        backbone_audit_rows.append(
            {
                "family": "disparity backbone",
                "setting_left": f"alpha <= {left:.2f}",
                "setting_right": f"alpha <= {right:.2f}",
                "jaccard_edge_overlap": jaccard(backbone_graphs[left], backbone_graphs[right]),
            }
        )
    backbone_audit = pd.DataFrame(backbone_audit_rows)
    backbone_audit.to_csv(PROCESSED_DIR / "milestone4a_backbone_audit.csv", index=False)

    report = [
        "# Milestone 4A network-construction audit",
        "",
        "## Scope",
        "",
        "- Source: Milestone 3C session matrix and Milestone 3D null-model pairwise output.",
        "- All 188 politicians were retained for diagnostics; no node was removed.",
        "- Candidate pairs require `n_shared >= 40`.",
        "- Candidate edges require strictly positive excess similarity.",
        "- No graph object, edge list, community detection, or final threshold was created.",
        "",
        "## Node eligibility",
        "",
        "| Rule | Nodes retained | Median eligible pairs | Minimum eligible pairs | Nodes with <5 eligible partners |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in eligibility_rows:
        report.append(
            f"| {row['construction']} | {row['nodes_retained']} | "
            f"{row['median_eligible_pairs']:.1f} | {row['minimum_eligible_pairs']} | "
            f"{row['nodes_with_fewer_than_5_eligible_partners']} |"
        )
    report.extend(
        [
            "",
            "## Disparity filter definition",
            "",
            "Only strictly positive excess-similarity edges enter the candidate graph. "
            "For a node with positive incident weights, each edge uses "
            "`p_ij = w_ij / sum_j(w_ij)` and the disparity-filter value "
            "`alpha_ij = (1 - p_ij)^(k_i - 1)`. An edge is retained when its "
            "alpha is at or below the tested value at either endpoint. Nodes with "
            "degree 1 retain their sole positive edge because their local alpha is "
            "defined as 0. Negative and zero weights are excluded before filtering; "
            "zero-strength nodes therefore do not enter the candidate graph.",
            "",
            "## Network audit",
            "",
            network_audit.to_markdown(index=False),
            "",
            "## Adjacent-setting edge overlap",
            "",
            backbone_audit.to_markdown(index=False),
            "",
            "## Decision",
            "",
            "Node eligibility, edge-weight definition, and sparsification are separate "
            "choices. The positive-excess candidate graph is the least sparse and "
            "should be treated as a dense diagnostic baseline. Global thresholds "
            "become progressively sparser and must be judged against their component "
            "and isolate changes rather than selected by appearance. The disparity "
            "backbones provide local sparsification, but their edge counts and "
            "adjacent-setting Jaccard values must be inspected for sensitivity. "
            "No final node rule or network construction was selected.",
        ]
    )
    (PROCESSED_DIR / "milestone4a_validation.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )

    print(network_audit.to_string(index=False))
    print(backbone_audit.to_string(index=False))


if __name__ == "__main__":
    main()
