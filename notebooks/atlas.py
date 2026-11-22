"""
atlas.py - interaktivt PCA/t-SNE-atlas ud fra DINE egne TF-IDF- og LDA-matricer
================================================================================
Inspireret af "Corpus Atlas" i Social Graphs uge 7. Læg filen ved siden af din
notebook og kald:

    from atlas import lav_atlas, top_ord
    lav_atlas(df_lda, tfidf_citat, topic_distributions,
              emne_navne=topic_names, emne_ord=top_ord(lda, count_vec),
              out="atlas.html")

Krav til input (rækkerne SKAL være i samme rækkefølge i alle tre):
  df      DataFrame med mindst kolonnerne politiker, parti og citat.
          Valgfrit: stance_label + stance_score (giver "Farv efter stance"),
          source og date (vises ved hvert citat).
  tfidf   TF-IDF-matrix for citaterne, fx TfidfVectorizer().fit_transform(...)
  theta   LDA-emnefordeling per citat, fx lda.fit_transform(dtm) / lda.transform(dtm)

Det, siden regner:
  * Naboer findes i det oprindelige rum: cosinus på TF-IDF (efter LSA) og
    Hellinger på LDA (cosinus på sqrt(theta)). Kortet bruges kun til at tegne.
  * PCA og t-SNE for begge repræsentationer, både for citater og for politikere
    (en politiker = gennemsnittet af sine citater).
  * Hvor mange af de 5 rigtige naboer kortet bevarer, og hvor ofte naboer er fra samme parti.
Kræver numpy, pandas, scikit-learn. Siden bruger Plotly fra internettet.
"""
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.manifold import TSNE
from sklearn.preprocessing import normalize

PARTI_FARVER = {"EL": "#C2185B", "SF": "#E57399", "S": "#D7262B", "RV": "#7B3F98", "M": "#9C7BD6",
                "KF": "#2E8B57", "V": "#1F5FAD", "LA": "#2BA3B4", "DD": "#4A7FD0", "DF": "#E3B61F",
                "ALT": "#5F9E3A", "IA": "#8C564B", "SP": "#6B8E9E", "N": "#999999", "JF": "#777777", "UFG": "#AAAAAA"}
PARTI_ORDEN = ["EL", "SF", "ALT", "S", "RV", "M", "KF", "V", "LA", "DD", "DF"]
STANCE_FARVER = {"For": "#2E8B57", "Neutral": "#9AA1A9", "Imod": "#D7262B"}
EMNE_FARVER = ["#1F5FAD", "#E3A01F", "#2E8B57", "#7B3F98", "#E3120B", "#2BA3B4", "#8C564B", "#D45087",
               "#5F7A1F", "#555555"]
K_NN = 5


def top_ord(lda, vectorizer, n=8):
    """De n vigtigste ord per emne fra en sklearn-LDA, som tekst."""
    vocab = np.array(vectorizer.get_feature_names_out())
    return [", ".join(vocab[np.argsort(-t)[:n]]) for t in lda.components_]


def _scale(xy):
    xy = xy - xy.mean(0)
    return xy / np.abs(xy).max()


def _knn(V):
    S = V @ V.T
    np.fill_diagonal(S, -np.inf)
    nn = np.argsort(-S, axis=1)[:, :K_NN]
    return nn, np.take_along_axis(S, nn, 1)


def _overlap(nn, xy):
    d = ((xy[:, None, :] - xy[None, :, :]) ** 2).sum(-1)
    np.fill_diagonal(d, np.inf)
    mnn = np.argsort(d, axis=1)[:, :K_NN]
    return float(np.mean([len(set(a) & set(b)) for a, b in zip(nn, mnn)]))


def _build_map(V, parties, seed, metric, perp):
    nn, sim = _knn(V)
    pca = PCA(n_components=2, random_state=seed).fit(V)
    p2 = _scale(pca.transform(V))
    t2 = _scale(TSNE(n_components=2, perplexity=perp, metric=metric, init="pca",
                     learning_rate="auto", random_state=seed).fit_transform(V))
    parties = np.asarray(parties)
    counts = pd.Series(parties).value_counts()
    return {"pca": np.round(p2, 4).tolist(), "tsne": np.round(t2, 4).tolist(),
            "nn": nn.tolist(), "sim": np.round(sim, 3).tolist(),
            "evr": [round(float(v), 4) for v in pca.explained_variance_ratio_],
            "stats": {"pca": round(_overlap(nn, p2), 2), "tsne": round(_overlap(nn, t2), 2),
                      "party": round(float(np.mean(parties[nn] == parties[:, None])), 3),
                      "base": round(float(np.mean([(counts[p] - 1) / (len(parties) - 1) for p in parties])), 3)}}


def _tfidf_dense(X, seed, dim=100):
    """TF-IDF er meget bred og sparse; LSA (TruncatedSVD) gør t-SNE hurtig og stabil."""
    if sparse.issparse(X) or X.shape[1] > dim:
        k = min(dim, X.shape[1] - 1, X.shape[0] - 1)
        X = TruncatedSVD(n_components=k, random_state=seed).fit_transform(X)
    return normalize(np.asarray(X, dtype=float))


def lav_atlas(df, tfidf, theta, emne_navne=None, emne_ord=None, out="atlas.html",
              min_citater=3, seed=42, titel="Et atlas over valgkampens citater", aaben=True):
    df = df.reset_index(drop=True)
    theta = np.asarray(theta, dtype=float)
    if not (len(df) == tfidf.shape[0] == theta.shape[0]):
        raise ValueError(f"Rækkerne passer ikke sammen: df={len(df)}, tfidf={tfidf.shape[0]}, theta={theta.shape[0]}")
    for c in ("politiker", "parti", "citat"):
        if c not in df.columns:
            raise ValueError(f"df mangler kolonnen '{c}'")
    k = theta.shape[1]
    emne_navne = list(emne_navne) if emne_navne is not None else [f"Emne {i}" for i in range(k)]
    emne_navne = [str(e).strip() for e in emne_navne]
    emne_ord = list(emne_ord) if emne_ord is not None else [""] * k

    theta = theta / theta.sum(1, keepdims=True)
    Vt = _tfidf_dense(tfidf, seed)
    Vl = np.sqrt(theta)  # Hellinger: cosinus på sqrt(theta) = Bhattacharyya-koefficient

    n = df.groupby("politiker").size()
    pols = sorted(n[n >= min_citater].index)
    pol_arr = df["politiker"].to_numpy()
    rows = [np.flatnonzero(pol_arr == p) for p in pols]
    Pt = normalize(np.stack([Vt[r].mean(0) for r in rows]))
    Ptheta = np.stack([theta[r].mean(0) for r in rows])
    ppa = [df.loc[r, "parti"].mode().iloc[0] for r in rows]

    pc = min(30, (len(df) - 1) / 3)
    pp = max(2, min(10, (len(pols) - 1) / 3))
    maps = {"citat": {"tfidf": _build_map(Vt, df["parti"], seed, "cosine", pc),
                      "lda": _build_map(Vl, df["parti"], seed, "euclidean", pc)},
            "politiker": {"tfidf": _build_map(Pt, ppa, seed, "cosine", pp),
                          "lda": _build_map(np.sqrt(Ptheta), ppa, seed, "euclidean", pp)}}

    has_stance = "stance_label" in df.columns
    def src(r):
        parts = [str(r[c]) for c in ("source", "date") if c in df.columns and pd.notna(r[c])]
        return " · ".join(parts)
    citater = []
    for i, r in df.iterrows():
        c = {"p": r["politiker"], "pa": r["parti"], "c": html.escape(str(r["citat"])),
             "lt": int(theta[i].argmax()), "lp": round(float(theta[i].max()), 2), "src": src(r)}
        if has_stance:
            c["s"] = str(r["stance_label"]) if pd.notna(r["stance_label"]) else ""
            c["sc"] = round(float(r.get("stance_score", 0) or 0), 2)
        citater.append(c)
    lengths = df["citat"].astype(str).str.len().to_numpy()
    pol = [{"n": p, "pa": ppa[j], "k": int(len(rows[j])), "lt": int(Ptheta[j].argmax()),
            "lp": round(float(Ptheta[j].max()), 2),
            # eksempler: de citater, der ligger tættest på politikerens eget LDA-gennemsnit
            "ex": [int(i) for i in rows[j][np.argsort(-(Vl[rows[j]] @ np.sqrt(Ptheta[j])) - 1e-6 * lengths[rows[j]])][:3]]}
           for j, p in enumerate(pols)]
    partier = set(df["parti"])
    data = {
        "partier": [p for p in PARTI_ORDEN if p in partier] + sorted(partier - set(PARTI_ORDEN)),
        "partiFarver": PARTI_FARVER, "stanceFarver": STANCE_FARVER, "hasStance": has_stance,
        "ldaFarver": [EMNE_FARVER[i % len(EMNE_FARVER)] for i in range(k)],
        "topics": [{"label": emne_navne[i], "words": emne_ord[i]} for i in range(k)],
        "citater": citater, "pol": pol, "maps": maps,
        "meta": {"n": len(df), "nPol": len(pols), "minCit": min_citater, "k": K_NN,
                 "tf": f"{tfidf.shape[1]} ord, reduceret med LSA", "lda": f"LDA med {k} emner"},
    }
    js = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    Path(out).write_text(TEMPLATE.replace("__DATA__", js).replace("__TITLE__", html.escape(titel))
                         .replace("Et atlas over valgkampens citater", html.escape(titel)), encoding="utf-8")

    stats = pd.DataFrame([{"niveau": lvl, "repræsentation": rep, "bevaret_PCA": m["stats"]["pca"],
                           "bevaret_tSNE": m["stats"]["tsne"], "samme_parti": m["stats"]["party"],
                           "tilfældigt": m["stats"]["base"]} for lvl, mm in maps.items() for rep, m in mm.items()])
    print(f"Gemt {out}: {len(df)} citater, {len(pols)} politikere (min. {min_citater} citater).")
    if aaben:  # åbner siden i din standardbrowser
        import webbrowser
        webbrowser.open(Path(out).resolve().as_uri())
    return stats


TEMPLATE = r'''<!DOCTYPE html>
<html lang="da"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,600&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
/* VOICE: avisens grafikredaktion – sagligt, præcist, roligt
   IDEA: et atlas over valgkampen; kortet skifter, vektorerne gør ikke
   PICTURE: ét stort kort med naboer trukket op som linjer, panel ved siden af
   COLOUR and TYPE: hvid, sort blæk, rød fane; Source Serif 4 + Inter
   LAYOUT: rød fane, overskrift, kontrolstribe, kort 2/3 + panel 1/3, tal og emner under */
:root{color-scheme:light dark;--bg:light-dark(#ffffff,#10191e);--ink:light-dark(#121212,#e9eef0);--mute:light-dark(#5b6670,#9aa8b1);
--rule:light-dark(#d9dee2,#26343b);--panel:light-dark(#e3ecf0,#17242b);--red:#e3120b;--chip:light-dark(#fff,#10191e)}
:root[data-theme=light]{color-scheme:light}:root[data-theme=dark]{color-scheme:dark}
*{box-sizing:border-box;min-width:0}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 Inter,system-ui,-apple-system,"Segoe UI",sans-serif;overflow-x:clip}
.band{padding:clamp(20px,3vw,40px) max(4vw,16px);max-width:1360px;margin:0 auto}
.tab-red{display:block;width:44px;height:8px;background:var(--red);margin-bottom:14px}
h1{font:600 clamp(30px,4.2vw,46px)/1.05 "Source Serif 4",Georgia,serif;margin:0 0 10px;text-wrap:balance;max-width:26ch}
.lede{color:var(--mute);margin:0;max-width:72ch}
.bar{display:flex;gap:12px 22px;align-items:end;flex-wrap:wrap;padding:18px 0 14px;border-bottom:1px solid var(--rule)}
.ctl{display:flex;flex-direction:column;gap:4px}.lbl{font-size:13px;color:var(--mute)}
.seg{display:inline-flex;border:1px solid var(--rule);border-radius:8px;overflow:hidden;flex-wrap:wrap}
.seg button{border:0;background:var(--chip);color:var(--ink);padding:0 13px;min-height:40px;font:500 14px Inter,sans-serif;cursor:pointer}
.seg button+button{border-left:1px solid var(--rule)}.seg button[aria-pressed=true]{background:var(--ink);color:var(--bg)}
.seg button:disabled{opacity:.35;cursor:not-allowed}
button:focus-visible,input:focus-visible{outline:2px solid var(--red);outline-offset:2px}
label.chk{display:inline-flex;gap:6px;align-items:center;font-size:14px;cursor:pointer;min-height:40px}
.main{display:grid;grid-template-columns:minmax(0,1.9fr) minmax(0,1fr);gap:0}
.mapwrap{padding:12px 18px 0 0;border-right:1px solid var(--rule)}
#map{height:min(70vh,640px);min-height:420px}
.mapsub{font-size:13px;color:var(--mute);margin:0}
aside{padding:14px 0 14px 18px}
input[type=search]{font:16px Inter,sans-serif;padding:0 12px;min-height:44px;border:1px solid var(--rule);border-radius:8px;background:var(--chip);color:var(--ink);width:100%}
.res{display:flex;flex-direction:column;margin-top:6px}
.res button,.nb{all:unset;cursor:pointer;display:block;padding:8px 6px;border-bottom:1px solid var(--rule);font-size:14px}
.res button:hover,.nb:hover{background:var(--panel)}.res button:focus-visible,.nb:focus-visible{outline:2px solid var(--red)}
.sel{margin-top:14px}
h2{font:600 20px/1.2 "Source Serif 4",Georgia,serif;margin:0 0 4px}
h3{font:600 16px/1.3 Inter,sans-serif;margin:18px 0 2px}
.meta{font-size:13px;color:var(--mute)}
q{display:block;font-size:15px;margin:6px 0}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;vertical-align:1px}
.simbar{height:4px;background:var(--rule);margin-top:5px}.simbar i{display:block;height:4px;background:var(--red)}
.nb .t{display:flex;justify-content:space-between;gap:10px}.nb .v{font-variant-numeric:tabular-nums;color:var(--mute);white-space:nowrap}
.verdict{background:var(--panel);padding:10px 12px;font-size:14px;margin-top:12px}
.empty{color:var(--mute);font-size:15px}
.btn{border:1px solid var(--rule);background:var(--chip);color:var(--ink);border-radius:8px;padding:0 14px;min-height:40px;font:500 14px Inter,sans-serif;cursor:pointer;margin-top:10px}
.lower{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:0 36px;border-top:1px solid var(--rule);margin-top:8px;padding-top:6px}
table{border-collapse:collapse;width:100%;font-size:14px;margin-top:8px}
th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--rule);vertical-align:top}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.topics div{padding:7px 0;border-bottom:1px solid var(--rule);font-size:14px}
.note{background:var(--panel);padding:16px 18px;margin-top:22px;font-size:15px}.note p{margin:0 0 8px;max-width:85ch}.note p:last-child{margin:0}
@media(max-width:900px){.main,.lower{grid-template-columns:minmax(0,1fr)}.mapwrap{border-right:0;padding-right:0}aside{padding-left:0;border-top:1px solid var(--rule)}#map{height:460px}}
@media(max-width:600px){table{font-size:13px}.stack thead{display:none}.stack tr{display:grid;padding-block:10px}.stack td{display:flow-root;border:0;padding:3px 0;padding-inline-start:9em;text-align:start}.stack td::before{content:attr(data-l);float:inline-start;width:8.5em;margin-inline-start:-9em;white-space:normal;color:var(--mute)}}
</style></head><body>
<div class="band">
  <span class="tab-red"></span>
  <h1>Et atlas over valgkampens citater</h1>
  <p class="lede" id="lede"></p>
  <div class="bar">
    <div class="ctl"><span class="lbl">Niveau</span><div class="seg" id="s-level"><button data-v="citat">Citater</button><button data-v="politiker">Politikere</button></div></div>
    <div class="ctl"><span class="lbl">Repræsentation</span><div class="seg" id="s-rep"><button data-v="tfidf">TF-IDF</button><button data-v="lda">LDA</button></div></div>
    <div class="ctl"><span class="lbl">Kort</span><div class="seg" id="s-map"><button data-v="pca">PCA</button><button data-v="tsne">t-SNE</button></div></div>
    <div class="ctl"><span class="lbl">Farv efter</span><div class="seg" id="s-color"><button data-v="parti">Parti</button><button data-v="lda">LDA-emne</button><button data-v="stance">Stance</button></div></div>
    <label class="chk"><input type="checkbox" id="lines" checked> Linjer til naboer</label>
  </div>
  <div class="main">
    <div class="mapwrap"><div id="map" role="img" aria-label="Kort over citater"></div><p class="mapsub" id="mapsub"></p></div>
    <aside>
      <input type="search" id="q" placeholder="Søg citat, politiker eller parti" aria-label="Søg">
      <div class="res" id="res"></div>
      <div class="sel" id="sel"></div>
    </aside>
  </div>
  <div class="lower">
    <section><h2>Hvor meget kan man stole på kortet?</h2><p class="meta" id="statsub"></p>
      <table class="stack"><thead><tr><th>Repræsentation</th><th class="n">Naboer bevaret, PCA</th><th class="n">Naboer bevaret, t-SNE</th><th class="n">Naboer fra samme parti</th></tr></thead><tbody id="stats"></tbody></table>
    </section>
    <section class="topics"><h2>LDA-emnerne</h2><p class="meta" id="ldasub"></p><div id="topics"></div></section>
  </div>
  <div class="note" id="note"></div>
</div>
<script>
{
const D = __DATA__;
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || "#888";
const fmt = (v, d = 1) => v.toFixed(d).replace(".", ",");
const pct = v => Math.round(v * 100) + " %";
const C = D.citater, P = D.pol, K = D.meta.k, T = D.topics;
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
const S = { level: "citat", rep: "tfidf", map: "tsne", color: "parti", sel: null, lines: true };
try { const h = location.hash.slice(1); if (h === "politikere") S.level = "politiker"; } catch (e) {}

$("lede").innerHTML = `${D.meta.n} citater og ${D.meta.nPol} politikere (med mindst ${D.meta.minCit} citater). Hvert citat er en vektor – enten TF-IDF eller en LDA-emnefordeling. ` +
  `Kortet tegner vektorerne i 2D, men <b>naboerne i panelet regnes i det oprindelige rum</b>. Klik på et punkt eller søg for at sammenligne.`;

const items = () => S.level === "citat" ? C : P;
const M = () => D.maps[S.level][S.rep];
const tname = i => T[i].label;
const groupDefs = {
  parti: { of: x => x.pa, list: () => D.partier, col: g => D.partiFarver[g] || "#888" },
  lda: { of: x => tname(x.lt), list: () => T.map((_, i) => tname(i)), col: g => D.ldaFarver[T.findIndex(t => t.label === g)] },
  stance: { of: x => x.s, list: () => ["For", "Neutral", "Imod"], col: g => D.stanceFarver[g] },
};
function wrap(s, w = 60, max = 6) {
  const out = []; let line = "";
  for (const word of s.split(" ")) {
    if ((line + " " + word).length > w && line) { out.push(line); line = word; if (out.length >= max) break; } else line = line ? line + " " + word : word;
  }
  if (out.length < max && line) out.push(line);
  const joined = out.join(" ");
  return out.join("<br>") + (joined.length < s.length - 2 ? " …" : "");
}
const hov = i => {
  const x = items()[i];
  return S.level === "citat"
    ? `<b>${esc(x.p)}</b> (${esc(x.pa)})<br>${wrap(x.c)}<br><i>${esc(tname(x.lt))} (${pct(x.lp)})${x.s ? " · " + x.s : ""}${x.src ? " · " + esc(x.src) : ""}</i>`
    : `<b>${esc(x.n)}</b> (${esc(x.pa)}) · ${x.k} citater<br><i>Mest ${esc(tname(x.lt))} (${pct(x.lp)})</i>`;
};
const label = i => S.level === "citat" ? C[i].p : P[i].n;

function traces() {
  const g = groupDefs[S.color], xy = M()[S.map], it = items();
  const tr = g.list().map(name => {
    const ix = it.map((x, i) => g.of(x) === name ? i : -1).filter(i => i >= 0);
    return { type: "scatter", mode: "markers", name, x: ix.map(i => xy[i][0]), y: ix.map(i => xy[i][1]), customdata: ix,
      hovertext: ix.map(hov), hovertemplate: "%{hovertext}<extra></extra>",
      marker: { size: S.level === "citat" ? 8 : ix.map(i => 9 + Math.min(P[i].k, 40) / 2.5), color: g.col(name),
        opacity: S.sel == null ? .85 : .3, line: { width: .6, color: css("--bg") } } };
  }).filter(t => t.x.length);
  const s = S.sel, nn = s == null ? [] : M().nn[s];
  const lx = [], ly = [];
  if (s != null && S.lines) nn.forEach(j => { lx.push(xy[s][0], xy[j][0], null); ly.push(xy[s][1], xy[j][1], null); });
  tr.push({ type: "scatter", mode: "lines", x: lx, y: ly, hoverinfo: "skip", showlegend: false, line: { color: css("--red"), width: 1.4 } });
  tr.push({ type: "scatter", mode: "markers+text", x: nn.map(j => xy[j][0]), y: nn.map(j => xy[j][1]), customdata: nn, showlegend: false,
    text: nn.map((j, r) => String(r + 1)), textposition: "top center", textfont: { size: 11, color: css("--red") },
    hovertext: nn.map(hov), hovertemplate: "%{hovertext}<extra></extra>",
    marker: { size: 15, color: "rgba(0,0,0,0)", line: { width: 2, color: css("--red") } } });
  tr.push({ type: "scatter", mode: "markers", x: s == null ? [] : [xy[s][0]], y: s == null ? [] : [xy[s][1]], customdata: s == null ? [] : [s],
    showlegend: false, hovertext: s == null ? [] : [hov(s)], hovertemplate: "%{hovertext}<extra></extra>",
    marker: { size: 20, color: css("--red"), symbol: "circle", line: { width: 3, color: css("--bg") } } });
  return tr;
}
function layout() {
  const ax = { visible: false, range: [-1.12, 1.12], fixedrange: false };
  return { paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: { family: "Inter, sans-serif", color: css("--ink") },
    margin: { l: 6, r: 6, t: 6, b: 6 }, hovermode: "closest", dragmode: "pan", xaxis: ax, yaxis: { ...ax },
    legend: { orientation: "h", x: 0, y: 1.0, yanchor: "bottom", font: { size: 12 }, bgcolor: "rgba(0,0,0,0)" },
    hoverlabel: { bgcolor: css("--bg"), bordercolor: css("--rule"), font: { size: 12, color: css("--ink"), family: "Inter, sans-serif" }, align: "left" },
    uirevision: S.level + S.rep };
}
const cfg = { responsive: true, scrollZoom: true, displaylogo: false, modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d", "toggleSpikelines"] };
let first = true;
function draw(animate = false) {
  const tr = traces();
  if (animate && !first) Plotly.animate("map", { data: tr, traces: tr.map((_, i) => i) },
    { transition: { duration: reduce ? 0 : 700, easing: "cubic-in-out" }, frame: { duration: reduce ? 0 : 700, redraw: false } });
  else Plotly.react("map", tr, layout(), cfg);
  if (first) { first = false; $("map").on("plotly_click", ev => { const p = ev.points[0]; if (p && p.customdata != null) select(p.customdata); }); }
  const m = M();
  $("mapsub").textContent = S.map === "pca"
    ? `PCA: de to akser forklarer ${pct(m.evr[0] + m.evr[1])} af variansen. Retning og afstand er lineære, men groft.`
    : "t-SNE: tætte klumper betyder lignende naboer. Afstande mellem klumper og klumpernes størrelse betyder næsten ingenting.";
  syncButtons(); panel(); stats();
}
function syncButtons() {
  for (const [id, k] of [["s-level", "level"], ["s-rep", "rep"], ["s-map", "map"], ["s-color", "color"]])
    for (const b of $(id).children) b.setAttribute("aria-pressed", b.dataset.v === S[k]);
  $("s-color").querySelector('[data-v="stance"]').disabled = S.level !== "citat" || !D.hasStance;
}
function mapNeighbors(s) {
  const xy = M()[S.map];
  return xy.map((p, j) => [j, (p[0] - xy[s][0]) ** 2 + (p[1] - xy[s][1]) ** 2]).filter(d => d[0] !== s)
    .sort((a, b) => a[1] - b[1]).slice(0, K).map(d => d[0]);
}
function itemCard(i) {
  if (S.level === "citat") { const c = C[i];
    return `<h2><span class="dot" style="background:${D.partiFarver[c.pa] || "#888"}"></span>${esc(c.p)} (${esc(c.pa)})</h2>
      <q>${c.c}</q><div class="meta">${esc(tname(c.lt))} (${pct(c.lp)})${c.s ? ` · <span style="color:${D.stanceFarver[c.s]}">${c.s}</span> ${fmt(c.sc, 2)}` : ""}${c.src ? " · " + esc(c.src) : ""}</div>`; }
  const p = P[i];
  return `<h2><span class="dot" style="background:${D.partiFarver[p.pa] || "#888"}"></span>${esc(p.n)} (${esc(p.pa)})</h2>
    <div class="meta">${p.k} citater · mest ${esc(tname(p.lt))} (${pct(p.lp)})</div>
    ${p.ex.map(j => `<q>${C[j].c}</q>`).join("")}`;
}
function nbRow(j, r, sim) {
  const x = items()[j];
  const title = S.level === "citat" ? `${esc(x.p)} (${esc(x.pa)})` : `${esc(x.n)} (${esc(x.pa)})`;
  const sub = S.level === "citat" ? `<div class="meta">${x.c.length > 140 ? x.c.slice(0, 140) + " …" : x.c}</div>` : `<div class="meta">${x.k} citater · ${esc(tname(x.lt))}</div>`;
  return `<button class="nb" data-i="${j}"><div class="t"><span><b>${r + 1}.</b> ${title}</span><span class="v">${fmt(sim, 2)}</span></div>${sub}
    <div class="simbar"><i style="width:${Math.max(0, sim) * 100}%"></i></div></button>`;
}
function panel() {
  const s = S.sel;
  if (s == null) { $("sel").innerHTML = `<p class="empty">Klik på et punkt, eller søg efter et ord eller en politiker. Her ser du så de ${K} nærmeste naboer målt med cosinus i det oprindelige rum – og om kortet placerer dem tæt på.</p><button class="btn" id="rnd">Vælg et tilfældigt</button>`;
    $("rnd").onclick = () => select(Math.floor(Math.random() * items().length)); return; }
  const m = M(), nn = m.nn[s], kept = mapNeighbors(s).filter(j => nn.includes(j)).length;
  const same = nn.filter(j => items()[j].pa === items()[s].pa).length;
  $("sel").innerHTML = itemCard(s) +
    `<h3>${K} nærmeste naboer · ${S.rep === "lda" ? "LDA (Hellinger)" : "TF-IDF (cosinus)"}</h3>` +
    nn.map((j, r) => nbRow(j, r, m.sim[s][r])).join("") +
    `<div class="verdict">På ${S.map === "pca" ? "PCA" : "t-SNE"}-kortet er <b>${kept} af ${K}</b> af dem også blandt de ${K} nærmeste punkter. ${same} af ${K} er fra samme parti.</div>`;
  for (const b of $("sel").querySelectorAll(".nb")) b.onclick = () => select(+b.dataset.i);
}
function stats() {
  const lvl = D.maps[S.level];
  $("statsub").textContent = `Gennemsnit over alle ${S.level === "citat" ? "citater" : "politikere"}: hvor mange af de ${K} rigtige naboer kortet også lægger blandt de ${K} nærmeste, og hvor ofte naboerne er fra samme parti.`;
  $("stats").innerHTML = ["tfidf", "lda"].map(r => { const s = lvl[r].stats;
    return `<tr${r === S.rep ? ' style="font-weight:600"' : ""}><td>${r === "lda" ? "LDA" : "TF-IDF"}</td><td class="n">${fmt(s.pca)} af ${K}</td><td class="n">${fmt(s.tsne)} af ${K}</td><td class="n">${pct(s.party)} (tilfældigt ${pct(s.base)})</td></tr>`; }).join("");
}
function select(i) { S.sel = i; draw(); }
function setOpt(k, v) {
  if (S[k] === v) return;
  const anim = k === "map"; S[k] = v;
  if (k === "level" || k === "rep") { if (k === "level") { S.sel = null; if (v !== "citat" && S.color === "stance") S.color = "parti";
    try { history.replaceState(null, "", v === "politiker" ? "#politikere" : "#citater"); } catch (e) {} } }
  draw(anim);
}
for (const [id, k] of [["s-level", "level"], ["s-rep", "rep"], ["s-map", "map"], ["s-color", "color"]])
  $(id).addEventListener("click", e => { const b = e.target.closest("button"); if (b && !b.disabled) setOpt(k, b.dataset.v); });
$("lines").addEventListener("change", e => { S.lines = e.target.checked; draw(); });
let tq;
$("q").addEventListener("input", e => { clearTimeout(tq); tq = setTimeout(() => search(e.target.value), 150); });
$("q").addEventListener("keydown", e => { if (e.key === "Enter") { const b = $("res").querySelector("button"); if (b) b.click(); } });
function search(v) {
  const q = v.trim().toLowerCase();
  if (!q) { $("res").innerHTML = ""; return; }
  const it = items(), hits = [];
  it.forEach((x, i) => { const hay = S.level === "citat" ? (x.c + " " + x.p + " " + x.pa) : (x.n + " " + x.pa); if (hay.toLowerCase().includes(q)) hits.push(i); });
  $("res").innerHTML = hits.length ? hits.slice(0, 8).map(i => `<button data-i="${i}"><b>${esc(label(i))}</b>${S.level === "citat" ? ` – <span class="meta">${C[i].c.slice(0, 90)} …</span>` : ""}</button>`).join("") +
    (hits.length > 8 ? `<p class="meta">${hits.length} træf – viser 8.</p>` : "") : `<p class="meta">Ingen træf.</p>`;
  for (const b of $("res").querySelectorAll("button")) b.onclick = () => { select(+b.dataset.i); $("res").innerHTML = ""; };
}
$("ldasub").textContent = `${D.meta.lda}. De vigtigste ord per emne:`;
$("topics").innerHTML = T.map((t, i) => `<div><span class="dot" style="background:${D.ldaFarver[i]}"></span><b>${esc(t.label)}</b>${t.words ? " · " + esc(t.words) : ""}</div>`).join("");
$("note").innerHTML = `<p><b>To repræsentationer, to slags lighed.</b> TF-IDF (${esc(D.meta.tf)}) finder citater, der bruger de samme sjældne ord. LDA beskriver hvert citat som en blanding af emner, og to citater er naboer, hvis blandingerne ligner hinanden (Hellinger-afstand). Politikere er gennemsnittet af deres citater.</p>
<p><b>Forbehold.</b> Citaterne er korte, så mange citater får næsten ét LDA-emne, og emnerne kan være svage. Kortet er kun et billede: brug nabolisten, og læs citaterne, før du konkluderer.</p>`;
const themeObs = new MutationObserver(() => draw());
themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
if (typeof Plotly === "undefined") $("lede").textContent = "Plotly kunne ikke indlæses. Tjek din internetforbindelse og genindlæs siden.";
else draw();
}
</script>
</body></html>
'''
