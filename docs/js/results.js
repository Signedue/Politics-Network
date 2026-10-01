(function () {
  "use strict";

  const palette = {
    accent: "#1e6b68",
    accentSoft: "rgba(30, 107, 104, 0.55)",
    secondary: "rgba(102, 113, 125, 0.48)",
    ink: "#17202a",
    muted: "#66717d",
    line: "#dce3e8"
  };

  const layoutBase = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "#ffffff",
    font: { family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", color: palette.ink },
    margin: { l: 56, r: 24, t: 42, b: 52 },
    hoverlabel: { bgcolor: "#ffffff", bordercolor: palette.line, font: { color: palette.ink } },
    legend: { orientation: "h", y: 1.08, x: 0 },
    autosize: true
  };

  const config = {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"]
  };

  function renderSimilarity(data) {
    const observed = data.map((row) => row.observed_similarity);
    const nullMean = data.map((row) => row.null_mean);
    const traces = [
      {
        x: observed,
        type: "histogram",
        name: "Observed",
        opacity: 0.62,
        marker: { color: palette.accentSoft, line: { color: palette.accent, width: 0.5 } },
        hovertemplate: "Observed similarity: %{x:.3f}<br>Pairs: %{y}<extra></extra>"
      },
      {
        x: nullMean,
        type: "histogram",
        name: "Null mean",
        opacity: 0.62,
        marker: { color: palette.secondary, line: { color: palette.muted, width: 0.5 } },
        hovertemplate: "Null mean similarity: %{x:.3f}<br>Pairs: %{y}<extra></extra>"
      }
    ];
    Plotly.newPlot("similarity-chart", traces, {
      ...layoutBase,
      title: { text: "Observed similarity and null expectation", font: { size: 16 } },
      barmode: "overlay",
      xaxis: { title: "Pairwise similarity", gridcolor: palette.line, zeroline: false },
      yaxis: { title: "Number of pairs", gridcolor: palette.line, zeroline: false }
    }, config);
  }

  function renderNmi(data) {
    Plotly.newPlot("nmi-chart", [{
      z: data.values,
      x: data.seeds,
      y: data.seeds,
      type: "heatmap",
      colorscale: [[0, "#eef3f3"], [0.5, "#8db7b4"], [1, palette.accent]],
      zmin: 0,
      zmax: 1,
      colorbar: { title: "NMI", thickness: 12 },
      hovertemplate: "Run %{y} × %{x}<br>NMI: %{z:.4f}<extra></extra>"
    }], {
      ...layoutBase,
      title: { text: "Louvain partition stability", font: { size: 16 } },
      margin: { l: 56, r: 24, t: 42, b: 56 },
      xaxis: { title: "Louvain seed", type: "category", gridcolor: palette.line },
      yaxis: { title: "Louvain seed", type: "category", gridcolor: palette.line, autorange: "reversed" }
    }, config);
  }

  function renderModularity(data) {
    Plotly.newPlot("modularity-chart", [{
      x: data.null_modularity,
      type: "histogram",
      name: "Null modularity",
      marker: { color: palette.secondary, line: { color: palette.muted, width: 0.5 } },
      hovertemplate: "Null Q: %{x:.4f}<br>Networks: %{y}<extra></extra>"
    }, {
      x: [data.real_q, data.real_q],
      y: [0, 1],
      type: "scatter",
      mode: "lines",
      name: "Real Q = 0.1530",
      line: { color: palette.accent, width: 3 },
      hovertemplate: "Real Q: %{x:.4f}<extra></extra>"
    }], {
      ...layoutBase,
      title: { text: "Observed modularity versus null", font: { size: 16 } },
      xaxis: { title: "Weighted modularity Q", gridcolor: palette.line, zeroline: false },
      yaxis: { title: "Number of null networks", gridcolor: palette.line, zeroline: false },
      bargap: 0.08
    }, config);
  }

  function loadJson(path) {
    return fetch(path).then(function (response) {
      if (!response.ok) {
        throw new Error("Could not load " + path);
      }
      return response.json();
    });
  }

  Promise.all([
    loadJson("assets/data/similarity_null.json"),
    loadJson("assets/data/louvain_nmi.json"),
    loadJson("assets/data/modularity_null.json")
  ]).then(function (datasets) {
    renderSimilarity(datasets[0]);
    renderNmi(datasets[1]);
    renderModularity(datasets[2]);
  }).catch(function (error) {
    document.querySelectorAll(".chart-container").forEach(function (container) {
      container.innerHTML = "<p class=\"chart-error\">Interactive chart data could not be loaded.</p>";
    });
    console.error(error);
  });
}());
