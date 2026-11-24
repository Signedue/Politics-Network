"""Party co-occurrence network from the 2022 mærkesager (policy priorities).

Nodes are parties. Two parties are connected when they have at least one
mærkesag in the same policy category (``kategori``). Edge weight is the number
of shared categories; ``jaccard`` is the Jaccard overlap of category sets.

Outputs:
  data/processed/milestone6b_nodes.csv        party nodes with attributes
  data/processed/milestone6b_edges.csv        party-party edges with weights
  data/processed/milestone6b_party_category.csv  party x category count matrix
  data/processed/milestone6b_maerkesager.graphml GraphML for Gephi/Cytoscape
  outputs/figures/milestone6b_category_overlap.png  shared-category heatmap
  data/processed/milestone6b_validation.md        descriptive audit report
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROCESSED = DATA / "processed"
FIGURES = ROOT / "outputs" / "figures"
SOURCE = DATA / "maerkesager_2022.csv"
SEP = ";"

# "Andet" is a catch-all, not a policy category; exclude it from edges
# (matches the convention in notebooks/mærkesager.ipynb).
EXCLUDE_CATEGORIES = {"Andet"}
MIN_SHARED = 1


def to_markdown(df: pd.DataFrame) -> str:
    """Render a DataFrame as a markdown table without the tabulate dependency."""
    if df.empty:
        return "(empty)\n"
    cols = df.columns.tolist()
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join("" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v) for v in row) + " |")
    return "\n".join(lines)


def load_mærkesager(path: Path = SOURCE) -> pd.DataFrame:
    df = pd.read_csv(path, sep=SEP, encoding="utf-8-sig")
    expected = {"parti", "partikode", "maerkesag", "kategori"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"{path} is missing columns: {sorted(missing)}")
    df = df.dropna(subset=["parti", "partikode", "kategori"]).copy()
    df["parti"] = df["parti"].astype(str).str.strip()
    df["partikode"] = df["partikode"].astype(str).str.strip()
    df["kategori"] = df["kategori"].astype(str).str.strip()
    return df


def category_matrix(df: pd.DataFrame) -> pd.DataFrame:
    mk = df[~df["kategori"].isin(EXCLUDE_CATEGORIES)].copy()
    mat = (
        mk.groupby(["partikode", "parti", "kategori"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    # ensure a stable, complete column order
    cats = sorted(c for c in df["kategori"].unique() if c not in EXCLUDE_CATEGORIES)
    for c in cats:
        if c not in mat.columns:
            mat[c] = 0
    mat = mat[["partikode", "parti"] + cats]
    return mat.set_index("partikode")


def build_network(mat: pd.DataFrame) -> tuple[nx.Graph, pd.DataFrame, pd.DataFrame]:
    cat_cols = [c for c in mat.columns if c != "parti"]
    codes = mat.index.tolist()
    names = mat["parti"].tolist()
    name_of = dict(zip(codes, names))
    n_sager = mat[cat_cols].sum(axis=1).astype(int)
    category_lists = mat[cat_cols].apply(
        lambda r: ", ".join(c for c, v in zip(cat_cols, r) if v > 0), axis=1
    )

    G = nx.Graph()
    for code, name, n, cats in zip(codes, names, n_sager, category_lists):
        G.add_node(code, parti=name, partikode=code, n_sager=int(n), categories=cats)

    edge_rows = []
    for i, a in enumerate(codes):
        row_a = mat.loc[a, cat_cols]
        set_a = set(c for c, v in zip(cat_cols, row_a) if v > 0)
        for b in codes[i + 1 :]:
            row_b = mat.loc[b, cat_cols]
            set_b = set(c for c, v in zip(cat_cols, row_b) if v > 0)
            shared = set_a & set_b
            if len(shared) < MIN_SHARED:
                continue
            union = set_a | set_b
            weight = len(shared)
            jaccard = weight / len(union) if union else 0.0
            n_shared_sager = int(mat.loc[a, list(shared)].sum() + mat.loc[b, list(shared)].sum())
            G.add_edge(a, b, weight=weight, jaccard=round(jaccard, 4),
                       n_shared_sager=n_shared_sager, shared_categories=", ".join(sorted(shared)))
            edge_rows.append(
                {
                    "party_A": name_of[a],
                    "party_B": name_of[b],
                    "code_A": a,
                    "code_B": b,
                    "weight": weight,
                    "jaccard": round(jaccard, 4),
                    "n_shared_sager": n_shared_sager,
                    "shared_categories": ", ".join(sorted(shared)),
                }
            )

    nodes = pd.DataFrame(
        {
            "parti": names,
            "partikode": codes,
            "n_sager": n_sager.to_numpy(),
            "categories": category_lists.to_numpy(),
        }
    )
    edges = pd.DataFrame(edge_rows)
    return G, nodes, edges


def write_graphml(path: Path, G: nx.Graph, nodes: pd.DataFrame, edges: pd.DataFrame) -> None:
    node_lookup = nodes.set_index("partikode")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"',
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        ' xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns '
        'http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">',
        '<key id="parti" for="node" attr.name="parti" attr.type="string"/>',
        '<key id="partikode" for="node" attr.name="partikode" attr.type="string"/>',
        '<key id="n_sager" for="node" attr.name="n_sager" attr.type="int"/>',
        '<key id="categories" for="node" attr.name="categories" attr.type="string"/>',
        '<key id="degree" for="node" attr.name="degree" attr.type="int"/>',
        '<key id="strength" for="node" attr.name="strength" attr.type="double"/>',
        '<key id="weight" for="edge" attr.name="weight" attr.type="int"/>',
        '<key id="jaccard" for="edge" attr.name="jaccard" attr.type="double"/>',
        '<key id="n_shared_sager" for="edge" attr.name="n_shared_sager" attr.type="int"/>',
        '<key id="shared_categories" for="edge" attr.name="shared_categories" attr.type="string"/>',
        '<graph id="milestone6b_maerkesager" edgedefault="undirected">',
    ]
    degree = dict(G.degree())
    strength = {n: float(sum(d["weight"] for _, d in G[n].items())) for n in G.nodes}
    for code in G.nodes:
        row = node_lookup.loc[code]
        lines.append(f'<node id="{code}">')
        lines.append(f'<data key="parti">{row["parti"]}</data>')
        lines.append(f'<data key="partikode">{code}</data>')
        lines.append(f'<data key="n_sager">{int(row["n_sager"])}</data>')
        lines.append(f'<data key="categories">{row["categories"]}</data>')
        lines.append(f'<data key="degree">{int(degree[code])}</data>')
        lines.append(f'<data key="strength">{strength[code]:.4f}</data>')
        lines.append("</node>")
    for index, (a, b, d) in enumerate(G.edges(data=True)):
        lines.append(f'<edge id="e{index}" source="{a}" target="{b}">')
        lines.append(f'<data key="weight">{int(d["weight"])}</data>')
        lines.append(f'<data key="jaccard">{float(d["jaccard"])}</data>')
        lines.append(f'<data key="n_shared_sager">{int(d["n_shared_sager"])}</data>')
        lines.append(f'<data key="shared_categories">{d["shared_categories"]}</data>')
        lines.append("</edge>")
    lines.extend(["</graph>", "</graphml>"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot_overlap(mat: pd.DataFrame, path: Path) -> None:
    cat_cols = [c for c in mat.columns if c != "parti"]
    codes = mat.index.tolist()
    names = mat["parti"].tolist()
    n = len(codes)
    overlap = pd.DataFrame(0, index=codes, columns=codes, dtype=int)
    for i in range(n):
        row_i = mat.iloc[i][cat_cols]
        set_i = set(c for c, v in zip(cat_cols, row_i) if v > 0)
        for j in range(i + 1, n):
            row_j = mat.iloc[j][cat_cols]
            set_j = set(c for c, v in zip(cat_cols, row_j) if v > 0)
            v = len(set_i & set_j)
            overlap.iloc[i, j] = v
            overlap.iloc[j, i] = v

    fig, ax = plt.subplots(figsize=(0.55 * n + 2, 0.5 * n + 2))
    im = ax.imshow(overlap.values, cmap="Blues", vmin=0, vmax=overlap.values.max())
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels([f"{c}\n{nm}" for c, nm in zip(codes, names)], rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels([f"{c}\n{nm}" for c, nm in zip(codes, names)], fontsize=8)
    vmax = float(overlap.values.max())
    for i in range(n):
        for j in range(n):
            v = int(overlap.iloc[i, j])
            ax.text(j, i, str(v), ha="center", va="center",
                    color="white" if v > 0.6 * vmax and v > 0 else "#1a1a1a", fontsize=8)
    ax.set_title("Shared policy categories between parties (mærkesager 2022, excl. 'Andet')",
                 fontsize=11, pad=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    df = load_mærkesager()
    mat = category_matrix(df)
    mat.to_csv(PROCESSED / "milestone6b_party_category.csv", encoding="utf-8-sig")

    G, nodes, edges = build_network(mat)
    nodes.to_csv(PROCESSED / "milestone6b_nodes.csv", index=False, encoding="utf-8-sig")
    edges.to_csv(PROCESSED / "milestone6b_edges.csv", index=False, encoding="utf-8-sig")
    write_graphml(PROCESSED / "milestone6b_maerkesager.graphml", G, nodes, edges)
    plot_overlap(mat, FIGURES / "milestone6b_category_overlap.png")

    density = nx.density(G)
    components = list(nx.connected_components(G))
    giant = max(components, key=len)
    degree = dict(G.degree())
    strength = {n: float(sum(d["weight"] for _, d in G[n].items())) for n in G.nodes}
    isolates = [n for n in G.nodes if degree[n] == 0]
    same_code = sum(1 for a, b in G.edges if a == b)  # always 0, placeholder

    describe = lambda s: {
        "min": float(s.min()), "p25": float(s.quantile(0.25)), "median": float(s.median()),
        "mean": float(s.mean()), "p75": float(s.quantile(0.75)), "max": float(s.max()),
    }

    report = [
        "# Milestone 6B mærkesager party co-occurrence network",
        "",
        "## Source",
        "",
        f"- File: `data/maerkesager_2022.csv` ({len(df)} mærkesager)",
        f"- Parties: {df['parti'].nunique()} ({', '.join(sorted(df['partikode'].unique()))})",
        f"- Categories used in network: {', '.join(sorted(c for c in df['kategori'].unique() if c not in EXCLUDE_CATEGORIES))}",
        f"- Excluded category: `Andet` (catch-all, not a policy category)",
        f"- Edge rule: weight = number of shared categories (min {MIN_SHARED}); undirected, unweighted projection",
        "",
        "## Basic validation",
        "",
        f"- Nodes (parties): `{G.number_of_nodes()}`",
        f"- Edges (party pairs sharing >= {MIN_SHARED} category): `{G.number_of_edges()}`",
        f"- Max possible edges: `{G.number_of_nodes() * (G.number_of_nodes() - 1) // 2}`",
        f"- Density: `{density:.6f}`",
        f"- Connected components: `{len(components)}`",
        f"- Giant component: `{len(giant)}` parties",
        f"- Isolates: `{len(isolates)}` ({', '.join(isolates) if isolates else 'none'})",
        f"- Mean degree: `{sum(degree.values()) / len(degree):.3f}`",
        f"- Mean strength: `{sum(strength.values()) / len(strength):.3f}`",
        "",
        "## Degree / strength summary",
        "",
        f"- Degree: `{describe(pd.Series(degree))}`",
        f"- Strength: `{describe(pd.Series(strength))}`",
        "",
        "## Edges (sorted by weight)",
        "",
        edges.sort_values(["weight", "n_shared_sager"], ascending=False).pipe(to_markdown),
        "",
        "## Nodes",
        "",
        nodes.sort_values("n_sager", ascending=False).pipe(to_markdown),
        "",
        "## Decision",
        "",
        "This is a descriptive co-occurrence projection: parties are linked when they "
        "prioritise the same policy categories in their 2022 mærkesager. Edge weight "
        "is the count of shared categories. No community detection, centrality "
        "ranking, or causal claim is made at this stage.",
    ]
    (PROCESSED / "milestone6b_validation.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Nodes={G.number_of_nodes()} Edges={G.number_of_edges()} Density={density:.4f} Components={len(components)} Giant={len(giant)} Isolates={len(isolates)}")


if __name__ == "__main__":
    main()
