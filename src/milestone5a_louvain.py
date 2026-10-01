"""Run weighted Louvain stability and null diagnostics for the Rule B graph."""

from __future__ import annotations

import itertools
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from sklearn.metrics import normalized_mutual_info_score


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "outputs" / "figures"
NODE_PATH = PROCESSED / "milestone4c_nodes.csv"
EDGE_PATH = PROCESSED / "milestone4c_edges.csv"
PAIRWISE_PATH = PROCESSED / "milestone4b_null_pairwise.csv"
SEEDS = list(range(1001, 1021))
NULL_SEEDS = list(range(5001, 5101))
WEIGHT = "weight"


def build_graph(nodes: pd.DataFrame, edges: pd.DataFrame) -> nx.Graph:
    graph = nx.Graph()
    for row in nodes.itertuples(index=False):
        graph.add_node(
            int(row.politician_id),
            politician_name=row.politician_name,
            party=row.party,
            participation_count=int(row.participation_count),
            participation_rate=float(row.participation_rate),
        )
    for row in edges.itertuples(index=False):
        graph.add_edge(
            int(row.politician_A_id),
            int(row.politician_B_id),
            weight=float(row.excess_similarity),
            excess_similarity=float(row.excess_similarity),
        )
    return graph


def partition_labels(graph: nx.Graph, seed: int) -> tuple[dict[int, int], float]:
    communities = nx.community.louvain_communities(
        graph, weight=WEIGHT, seed=seed, resolution=1
    )
    labels: dict[int, int] = {}
    for community_id, community in enumerate(
        sorted(communities, key=lambda values: min(values))
    ):
        for node in community:
            labels[node] = community_id
    quality = nx.community.modularity(graph, communities, weight=WEIGHT)
    return labels, float(quality)


def pairwise_nmi(label_maps: list[dict[int, int]], nodes: list[int]) -> pd.DataFrame:
    values = []
    for left in range(len(label_maps)):
        row = []
        for right in range(len(label_maps)):
            row.append(
                normalized_mutual_info_score(
                    [label_maps[left][node] for node in nodes],
                    [label_maps[right][node] for node in nodes],
                )
            )
        values.append(row)
    return pd.DataFrame(values)


def edge_swap_graph(
    original: nx.Graph,
    seed: int,
    swaps_per_edge: int = 3,
) -> nx.Graph:
    rng = np.random.default_rng(seed)
    graph = nx.Graph()
    graph.add_nodes_from(original.nodes(data=True))
    edges = [(int(left), int(right)) for left, right in original.edges()]
    edge_set = set(edges)
    target_swaps = swaps_per_edge * len(edges)
    accepted = 0
    attempts = 0
    max_attempts = max(target_swaps * 30, 1000)
    while accepted < target_swaps and attempts < max_attempts:
        attempts += 1
        first, second = rng.choice(len(edges), size=2, replace=False)
        a, b = edges[first]
        c, d = edges[second]
        if len({a, b, c, d}) < 4:
            continue
        if rng.random() < 0.5:
            new_first, new_second = (a, d), (c, b)
        else:
            new_first, new_second = (a, c), (b, d)
        if new_first[0] > new_first[1]:
            new_first = (new_first[1], new_first[0])
        if new_second[0] > new_second[1]:
            new_second = (new_second[1], new_second[0])
        if new_first[0] == new_first[1] or new_second[0] == new_second[1]:
            continue
        if new_first in edge_set or new_second in edge_set:
            continue
        edge_set.remove(edges[first])
        edge_set.remove(edges[second])
        edges[first], edges[second] = new_first, new_second
        edge_set.add(new_first)
        edge_set.add(new_second)
        accepted += 1
    graph.add_edges_from(edges)
    if sorted(dict(graph.degree()).values()) != sorted(dict(original.degree()).values()):
        raise RuntimeError("Degree-preserving shuffle changed the degree sequence")
    weights = [original[left][right]["weight"] for left, right in original.edges()]
    rng.shuffle(weights)
    for edge, weight in zip(graph.edges(), weights):
        graph.edges[edge]["weight"] = float(weight)
    return graph


def component_party_table(graph: nx.Graph, labels: dict[int, int], nodes: pd.DataFrame) -> pd.DataFrame:
    metadata = nodes.set_index("politician_id")
    rows = []
    for community_id in sorted(set(labels.values())):
        members = [node for node, label in labels.items() if label == community_id]
        counts = metadata.loc[members, "party"].value_counts().sort_index()
        row = {"community": community_id, "size": len(members)}
        row.update({f"party_{party}": int(count) for party, count in counts.items()})
        row["mean_participation_rate"] = float(
            metadata.loc[members, "participation_rate"].mean()
        )
        row["mean_strength"] = float(
            sum(graph.degree(node, weight=WEIGHT) for node in members) / len(members)
        )
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    nodes = pd.read_csv(NODE_PATH)
    edges = pd.read_csv(EDGE_PATH)
    rule_b = build_graph(nodes, edges)
    if rule_b.number_of_nodes() != 150 or rule_b.number_of_edges() != 3086:
        raise RuntimeError("Rule B graph does not match Milestone 4C counts")

    pairwise = pd.read_csv(PAIRWISE_PATH)
    rule_c_edges = pairwise[
        (pairwise["politician_A_id"].isin(nodes["politician_id"]))
        & (pairwise["politician_B_id"].isin(nodes["politician_id"]))
        & (pairwise["n_shared"] >= 40)
        & (pairwise["excess_similarity"] > 0)
        & (pairwise["q_value"] < 0.01)
    ]
    rule_c = build_graph(nodes, rule_c_edges.rename(columns={"excess_similarity": "excess_similarity"}))

    run_rows = []
    full_labels = []
    for seed in SEEDS:
        labels, modularity = partition_labels(rule_b, seed)
        full_labels.append(labels)
        run_rows.append(
            {
                "analysis": "full_ruleB",
                "seed": seed,
                "number_of_communities": len(set(labels.values())),
                "modularity": modularity,
            }
        )
    full_nmi = pairwise_nmi(full_labels, list(rule_b.nodes()))
    average_nmi = full_nmi.mean(axis=1)
    representative_index = int(average_nmi.idxmax())
    representative_seed = SEEDS[representative_index]
    representative_labels = full_labels[representative_index]

    giant_nodes = max(nx.connected_components(rule_b), key=len)
    giant = rule_b.subgraph(giant_nodes).copy()
    giant_labels = []
    for seed in SEEDS:
        labels, modularity = partition_labels(giant, seed)
        giant_labels.append(labels)
        run_rows.append(
            {
                "analysis": "giant_ruleB",
                "seed": seed,
                "number_of_communities": len(set(labels.values())),
                "modularity": modularity,
            }
        )
    giant_nmi = pairwise_nmi(giant_labels, list(giant.nodes()))
    giant_average_nmi = giant_nmi.mean(axis=1)
    giant_rep_index = int(giant_average_nmi.idxmax())
    giant_rep_labels = giant_labels[giant_rep_index]

    common_active = sorted(set(rule_b.nodes()) & set(rule_c.nodes()))
    c_labels, c_modularity = partition_labels(rule_c, representative_seed)
    b_common_labels = {node: representative_labels[node] for node in common_active}
    c_common_labels = {node: c_labels[node] for node in common_active}
    rule_c_nmi = normalized_mutual_info_score(
        [b_common_labels[node] for node in common_active],
        [c_common_labels[node] for node in common_active],
    )
    run_rows.append(
        {
            "analysis": "ruleC_representative_seed",
            "seed": representative_seed,
            "number_of_communities": len(set(c_labels.values())),
            "modularity": c_modularity,
        }
    )

    real_modularity = run_rows[representative_index]["modularity"]
    null_modularities = []
    for seed in NULL_SEEDS:
        null_graph = edge_swap_graph(rule_b, seed)
        _, null_q = partition_labels(null_graph, seed)
        null_modularities.append(null_q)
    null_modularities = np.array(null_modularities)
    null_p = (1 + int((null_modularities >= real_modularity).sum())) / (1 + len(null_modularities))
    run_rows.extend(
        {
            "analysis": "null_degree_preserving",
            "seed": seed,
            "number_of_communities": np.nan,
            "modularity": modularity,
        }
        for seed, modularity in zip(NULL_SEEDS, null_modularities)
    )
    runs = pd.DataFrame(run_rows)
    runs.to_csv(PROCESSED / "milestone5a_louvain_runs.csv", index=False)

    nmi_table = full_nmi.copy()
    nmi_table.index = SEEDS
    nmi_table.columns = SEEDS
    nmi_table.to_csv(PROCESSED / "milestone5a_nmi_matrix.csv")

    community_table = component_party_table(rule_b, representative_labels, nodes)
    community_table.to_csv(PROCESSED / "milestone5a_community_party_table.csv", index=False)

    plt.figure(figsize=(7, 4.5))
    plt.hist(null_modularities, bins=15, alpha=0.75, edgecolor="white")
    plt.axvline(real_modularity, color="red", linestyle="--", label="Real Rule B")
    plt.xlabel("Weighted modularity")
    plt.ylabel("Number of null networks")
    plt.title("Rule B modularity versus degree-preserving null")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES / "milestone5a_modularity_null.png", dpi=150)
    plt.close()

    full_nmi_values = full_nmi.to_numpy()
    upper = full_nmi_values[np.triu_indices_from(full_nmi_values, k=1)]
    mean_nmi = float(upper.mean())
    median_nmi = float(np.median(upper))
    min_nmi = float(upper.min())
    max_nmi = float(upper.max())
    party_labels = nodes.set_index("politician_id").loc[list(rule_b.nodes()), "party"]
    party_nmi = normalized_mutual_info_score(
        [representative_labels[node] for node in rule_b.nodes()],
        party_labels.tolist(),
    )
    giant_nmi_values = giant_nmi.to_numpy()
    giant_upper = giant_nmi_values[np.triu_indices_from(giant_nmi_values, k=1)]
    giant_party_nmi = normalized_mutual_info_score(
        [giant_rep_labels[node] for node in giant.nodes()],
        nodes.set_index("politician_id").loc[list(giant.nodes()), "party"].tolist(),
    )
    plt.figure(figsize=(6, 5))
    plt.imshow(full_nmi_values, vmin=0, vmax=1, cmap="viridis")
    plt.colorbar(label="NMI")
    plt.xlabel("Louvain run")
    plt.ylabel("Louvain run")
    plt.title("Louvain partition stability")
    plt.tight_layout()
    plt.savefig(FIGURES / "milestone5a_nmi_stability.png", dpi=150)
    plt.close()

    report = [
        "# Milestone 5A community-structure validation",
        "",
        "## Scope and Louvain handling",
        "",
        "The main analysis used all 150 Rule B nodes. Louvain was run on the "
        "disconnected graph without silently dropping components. Disconnected "
        "components were available to the partition algorithm as separate graph "
        "regions; the three zero-degree isolates were retained as singleton "
        "communities. The 117-node giant component was analyzed separately as a "
        "sensitivity check.",
        "",
        "## Weighted Louvain stability",
        "",
        f"- Seeds: `{SEEDS}`",
        f"- Number of communities across full-network runs: `{runs[runs.analysis == 'full_ruleB']['number_of_communities'].tolist()}`",
        f"- Modularity range across full-network runs: `{runs[runs.analysis == 'full_ruleB']['modularity'].min()}` to `{runs[runs.analysis == 'full_ruleB']['modularity'].max()}`",
        f"- Pairwise NMI: mean `{mean_nmi}`, median `{median_nmi}`, min `{min_nmi}`, max `{max_nmi}`",
        f"- Stability assessment: **{'highly stable' if mean_nmi >= 0.9 else 'moderately stable' if mean_nmi >= 0.7 else 'unstable'}** based on the observed NMI distribution.",
        "",
        "## Representative partition",
        "",
        f"- Rule: run with the highest average NMI to all other full-network runs.",
        f"- Chosen seed: `{representative_seed}`",
        f"- Communities: `{len(set(representative_labels.values()))}`",
        f"- Modularity: `{real_modularity}`",
        f"- Average NMI to other runs: `{average_nmi.iloc[representative_index]}`",
        "",
        "## Party comparison",
        "",
        f"- Representative-community versus party NMI: `{party_nmi}`",
        "Party labels are not ground truth and were used only as a descriptive comparison.",
        "",
        "## Degree/strength null modularity",
        "",
        "Each null graph preserved the full Rule B node set and degree sequence using "
        "degree-preserving double-edge swaps. The observed Rule B edge-weight multiset "
        "was randomly permuted across the shuffled edges; this preserves the marginal "
        "weight distribution while removing its association with particular endpoints.",
        f"- Real representative modularity: `{real_modularity}`",
        f"- Null networks: `{len(null_modularities)}`",
        f"- Null modularity mean: `{null_modularities.mean()}`",
        f"- Null modularity SD: `{null_modularities.std(ddof=1)}`",
        f"- Null z-score: `{(real_modularity - null_modularities.mean()) / null_modularities.std(ddof=1)}`",
        f"- Empirical one-sided p-value: `{null_p}`",
        "",
        "## Giant-component sensitivity",
        "",
        f"- Giant nodes: `{len(giant)}`",
        f"- Giant representative seed: `{SEEDS[giant_rep_index]}`",
        f"- Giant communities: `{len(set(giant_rep_labels.values()))}`",
        f"- Giant representative modularity: `{runs[(runs.analysis == 'giant_ruleB') & (runs.seed == SEEDS[giant_rep_index])].modularity.iloc[0]}`",
        f"- Giant pairwise NMI: mean `{giant_upper.mean()}`, median `{np.median(giant_upper)}`, min `{giant_upper.min()}`, max `{giant_upper.max()}`",
        f"- Giant party-alignment NMI: `{giant_party_nmi}`",
        "",
        "## Rule C robustness",
        "",
        f"- Rule C representative seed: `{representative_seed}`",
        f"- Rule C communities: `{len(set(c_labels.values()))}`",
        f"- Rule C modularity: `{c_modularity}`",
        f"- Rule B/Rule C NMI on common active nodes: `{rule_c_nmi}`",
        "",
        "## Decision",
        "",
        f"1. The observed modularity is {'above' if real_modularity > null_modularities.mean() else 'not above'} the degree/strength null mean; the null comparison gives an empirical p-value of `{null_p}`.",
        f"2. Louvain partitions are {'highly stable' if mean_nmi >= 0.9 else 'moderately stable' if mean_nmi >= 0.7 else 'unstable'} across seeds by pairwise NMI.",
        f"3. The representative partition's NMI with formal party labels is `{party_nmi}`; this is an alignment measure, not a causal or ground-truth claim.",
        f"4. Rule B versus Rule C has common-active-node NMI `{rule_c_nmi}`, so robustness is assessed descriptively without replacing Rule B.",
        "No politician ranking, ideology inference, community label, modularity optimization choice, or final political interpretation was made.",
    ]
    (PROCESSED / "milestone5a_validation.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )

    print(f"Full representative seed: {representative_seed}")
    print(f"Full mean pairwise NMI: {mean_nmi}")
    print(f"Real modularity: {real_modularity}")
    print(f"Null mean modularity: {null_modularities.mean()}")
    print(f"Null p-value: {null_p}")
    print(f"Party NMI: {party_nmi}")
    print(f"Rule C NMI: {rule_c_nmi}")


if __name__ == "__main__":
    main()
