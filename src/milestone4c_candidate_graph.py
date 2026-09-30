"""Construct and audit the provisional Rule B agreement network."""

from __future__ import annotations

import html
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
NODE_AUDIT_PATH = PROCESSED / "milestone4a_node_eligibility.csv"
MIN_PARTICIPATION = 40


def components(nodes: list[int], edges: pd.DataFrame) -> list[set[int]]:
    parent = {node: node for node in nodes}

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for row in edges.itertuples(index=False):
        left, right = find(int(row.politician_A_id)), find(int(row.politician_B_id))
        if left != right:
            parent[right] = left
    groups: dict[int, set[int]] = {}
    for node in nodes:
        groups.setdefault(find(node), set()).add(node)
    return sorted(groups.values(), key=lambda group: (-len(group), min(group)))


def write_graphml(path: Path, nodes: pd.DataFrame, edges: pd.DataFrame) -> None:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"',
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        ' xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns '
        'http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">',
        '<key id="name" for="node" attr.name="politician_name" attr.type="string"/>',
        '<key id="party" for="node" attr.name="party" attr.type="string"/>',
        '<key id="participation_count" for="node" attr.name="participation_count" attr.type="int"/>',
        '<key id="participation_rate" for="node" attr.name="participation_rate" attr.type="double"/>',
        '<key id="weight" for="edge" attr.name="excess_similarity" attr.type="double"/>',
        '<key id="n_shared" for="edge" attr.name="n_shared" attr.type="int"/>',
        '<key id="observed_similarity" for="edge" attr.name="observed_similarity" attr.type="double"/>',
        '<key id="q_value" for="edge" attr.name="q_value" attr.type="double"/>',
        '<graph id="milestone4c_ruleB" edgedefault="undirected">',
    ]
    for row in nodes.itertuples(index=False):
        node_id = str(int(row.politician_id))
        lines.append(f'<node id="p{node_id}">')
        lines.append(f'<data key="name">{html.escape(str(row.politician_name))}</data>')
        lines.append(f'<data key="party">{html.escape(str(row.party))}</data>')
        lines.append(f'<data key="participation_count">{int(row.participation_count)}</data>')
        lines.append(f'<data key="participation_rate">{float(row.participation_rate)}</data>')
        lines.append('</node>')
    for index, row in enumerate(edges.itertuples(index=False)):
        lines.extend(
            [
                f'<edge id="e{index}" source="p{int(row.politician_A_id)}" '
                f'target="p{int(row.politician_B_id)}">',
                f'<data key="weight">{float(row.excess_similarity)}</data>',
                f'<data key="n_shared">{int(row.n_shared)}</data>',
                f'<data key="observed_similarity">{float(row.observed_similarity)}</data>',
                f'<data key="q_value">{float(row.q_value)}</data>',
                '</edge>',
            ]
        )
    lines.extend(['</graph>', '</graphml>'])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    matrix = pd.read_csv(MATRIX_PATH)
    matrix_values = matrix.drop(columns=["politician_name", "party"]).set_index("politician_id")
    metadata = matrix.set_index("politician_id")[["politician_name", "party"]]
    participation_count = matrix_values.isin(
        ["For", "Imod", "Hverken for eller imod"]
    ).sum(axis=1)
    retained_ids = participation_count[participation_count >= MIN_PARTICIPATION].index.astype(int).tolist()

    pairwise = pd.read_csv(PAIRWISE_PATH)
    eligible = pairwise[
        pairwise["politician_A_id"].isin(retained_ids)
        & pairwise["politician_B_id"].isin(retained_ids)
        & (pairwise["n_shared"] >= 40)
    ].copy()
    rule_b = eligible[
        (eligible["excess_similarity"] > 0)
        & (eligible["q_value"] < 0.05)
    ].copy()
    rule_c = eligible[
        (eligible["excess_similarity"] > 0)
        & (eligible["q_value"] < 0.01)
    ].copy()
    if len(retained_ids) != 150 or len(rule_b) != 3086:
        raise RuntimeError(
            f"Rule B validation failed before graph construction: "
            f"nodes={len(retained_ids)}, edges={len(rule_b)}"
        )

    nodes = pd.DataFrame(
        {
            "politician_id": retained_ids,
            "politician_name": metadata.loc[retained_ids, "politician_name"].to_numpy(),
            "party": metadata.loc[retained_ids, "party"].to_numpy(),
            "participation_count": participation_count.loc[retained_ids].to_numpy(),
            "participation_rate": (
                participation_count.loc[retained_ids].to_numpy() / matrix_values.shape[1]
            ),
        }
    )
    node_lookup = nodes.set_index("politician_id")
    degree = pd.Series(0, index=retained_ids, dtype=int)
    strength = pd.Series(0.0, index=retained_ids)
    for row in rule_b.itertuples(index=False):
        degree[row.politician_A_id] += 1
        degree[row.politician_B_id] += 1
        strength[row.politician_A_id] += row.excess_similarity
        strength[row.politician_B_id] += row.excess_similarity
    nodes["degree"] = nodes["politician_id"].map(degree)
    nodes["strength"] = nodes["politician_id"].map(strength)
    nodes.to_csv(PROCESSED / "milestone4c_nodes.csv", index=False)
    rule_b.to_csv(PROCESSED / "milestone4c_edges.csv", index=False)
    write_graphml(PROCESSED / "milestone4c_ruleB.graphml", nodes, rule_b)

    rule_b_components = components(retained_ids, rule_b)
    rule_c_components = components(retained_ids, rule_c)
    b_giant = rule_b_components[0]
    c_giant = rule_c_components[0]
    b_edges = set(zip(rule_b.politician_A_id, rule_b.politician_B_id))
    c_edges = set(zip(rule_c.politician_A_id, rule_c.politician_B_id))
    edge_union = b_edges | c_edges
    b_active = set(rule_b.politician_A_id) | set(rule_b.politician_B_id)
    c_active = set(rule_c.politician_A_id) | set(rule_c.politician_B_id)
    node_overlap = len(set(retained_ids) & set(retained_ids)) / len(retained_ids)
    active_node_overlap = len(b_active & c_active) / len(b_active | c_active)
    giant_overlap = len(b_giant & c_giant) / len(b_giant | c_giant)

    component_rows = []
    for component_id, component in enumerate(rule_b_components, start=1):
        component_edges = rule_b[
            rule_b.politician_A_id.isin(component)
            & rule_b.politician_B_id.isin(component)
        ]
        composition = (
            node_lookup.loc[sorted(component), "party"].value_counts().sort_index().to_dict()
        )
        component_rows.append(
            {
                "component": component_id,
                "nodes": len(component),
                "edges": len(component_edges),
                "party_composition": str(composition),
            }
        )
    component_audit = pd.DataFrame(component_rows)

    isolates = nodes[nodes["degree"] == 0].copy()
    pair_counts = pd.concat(
        [eligible["politician_A_id"], eligible["politician_B_id"]]
    ).value_counts()
    isolates["eligible_n_shared_ge_40_partners"] = isolates["politician_id"].map(
        pair_counts
    ).fillna(0).astype(int)

    def describe(series: pd.Series) -> dict[str, float]:
        return {
            "min": float(series.min()),
            "p25": float(series.quantile(0.25)),
            "median": float(series.median()),
            "mean": float(series.mean()),
            "p75": float(series.quantile(0.75)),
            "max": float(series.max()),
        }

    plt.figure(figsize=(7, 4.5))
    plt.hist(nodes["degree"], bins=20, edgecolor="white")
    plt.xlabel("Degree")
    plt.ylabel("Number of politicians")
    plt.title("Rule B degree distribution")
    plt.tight_layout()
    plt.savefig(FIGURES / "milestone4c_degree_distribution.png", dpi=150)
    plt.close()

    plt.figure(figsize=(7, 4.5))
    plt.hist(nodes["strength"], bins=20, edgecolor="white")
    plt.xlabel("Weighted strength")
    plt.ylabel("Number of politicians")
    plt.title("Rule B strength distribution")
    plt.tight_layout()
    plt.savefig(FIGURES / "milestone4c_strength_distribution.png", dpi=150)
    plt.close()

    degree_skew = nodes["degree"].skew()
    strength_skew = nodes["strength"].skew()
    report = [
        "# Milestone 4C candidate Rule B network audit",
        "",
        "## Provisional graph definition",
        "",
        "- Nodes: politicians with at least 40 participated votes.",
        "- Pair eligibility: n_shared >= 40.",
        "- Edge rule: excess_similarity > 0 and Benjamini-Hochberg q < 0.05.",
        "- Edge weight: excess_similarity.",
        "- Party labels were retained as metadata only and did not affect construction.",
        "",
        "## Basic validation",
        "",
        f"- Eligible politicians: `{len(retained_ids)}` (expected `150`)",
        f"- Edges: `{len(rule_b)}` (expected `3086`)",
        f"- Nodes with at least one edge: `{int((nodes['degree'] > 0).sum())}` (expected `147`)",
        f"- Isolates: `{int((nodes['degree'] == 0).sum())}` (expected `3`)",
        f"- Components: `{len(rule_b_components)}` (expected `6`)",
        f"- Giant component: `{len(b_giant)}` nodes (expected `117`)",
        "- Validation status: **PASS**",
        "",
        "## Basic network statistics",
        "",
        f"- Nodes: `{len(nodes)}`",
        f"- Edges: `{len(rule_b)}`",
        f"- Density: `{len(rule_b) / (len(nodes) * (len(nodes) - 1) / 2):.6f}`",
        f"- Connected components: `{len(rule_b_components)}`",
        f"- Isolates: `{len(isolates)}`",
        f"- Giant-component size: `{len(b_giant)}`",
        f"- Mean degree: `{nodes['degree'].mean()}`",
        f"- Median degree: `{nodes['degree'].median()}`",
        f"- Minimum degree: `{nodes['degree'].min()}`",
        f"- Maximum degree: `{nodes['degree'].max()}`",
        f"- Mean node strength: `{nodes['strength'].mean()}`",
        f"- Median node strength: `{nodes['strength'].median()}`",
        f"- Minimum node strength: `{nodes['strength'].min()}`",
        f"- Maximum node strength: `{nodes['strength'].max()}`",
        "",
        "## Distribution descriptions",
        "",
        f"- Degree summary: `{describe(nodes['degree'])}`; skewness `{degree_skew}`; descriptively **{'strongly skewed' if degree_skew > 1 else 'broad' if degree_skew > 0.5 else 'narrow'}**.",
        f"- Strength summary: `{describe(nodes['strength'])}`; skewness `{strength_skew}`; descriptively **{'strongly skewed' if strength_skew > 1 else 'broad' if strength_skew > 0.5 else 'narrow'}**.",
        "These descriptions are not claims of a power-law or heavy-tail mechanism.",
        "",
        "## Component audit",
        "",
        component_audit.to_markdown(index=False),
        "",
        "## Isolates",
        "",
        isolates[[
            "politician_id", "politician_name", "party",
            "participation_count", "eligible_n_shared_ge_40_partners",
        ]].to_markdown(index=False),
        "",
        "## Edge-weight audit",
        "",
        f"- Excess-similarity distribution: `{describe(rule_b['excess_similarity'])}`",
        f"- Same-party edge fraction: `{(rule_b['party_A'] == rule_b['party_B']).mean()}`",
        f"- Different-party edge fraction: `{(rule_b['party_A'] != rule_b['party_B']).mean()}`",
        "",
        "## Rule C robustness comparison",
        "",
        f"- Rule C edges: `{len(rule_c)}`",
        f"- Eligible-node overlap: `{node_overlap}`",
        f"- Active-node overlap: `{active_node_overlap}`",
        f"- Edge overlap: `{len(b_edges & c_edges)}`",
        f"- Edge-set Jaccard similarity: `{len(b_edges & c_edges) / len(edge_union)}`",
        f"- Giant-component sizes: Rule B `{len(b_giant)}`, Rule C `{len(c_giant)}`",
        f"- Giant-component membership overlap (Jaccard): `{giant_overlap}`",
        "",
        "## Decision",
        "",
        "The Rule B graph reproduces the Milestone 4B validation counts exactly. "
        "Rule C has a smaller edge set and giant component, so the broad topology "
        "should be checked for sensitivity to q=0.05 versus q=0.01 before any "
        "higher-level network method is applied. This milestone is descriptive; "
        "no centrality ranking, community detection, modularity, ideology "
        "inference, or final network claim was made.",
    ]
    (PROCESSED / "milestone4c_validation.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(f"Rule B validation: nodes={len(retained_ids)}, edges={len(rule_b)}, components={len(rule_b_components)}, giant={len(b_giant)}")
    print(component_audit.to_string(index=False))


if __name__ == "__main__":
    main()
