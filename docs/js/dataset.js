(function () {
  "use strict";

  const palette = {
    accent: "#1e6b68",
    accentSoft: "rgba(30, 107, 104, 0.78)",
    muted: "#66717d",
    ink: "#17202a",
    line: "#dce3e8",
    excluded: "#b9c5c6"
  };
  const layoutBase = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "#ffffff",
    font: { family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", color: palette.ink },
    margin: { l: 56, r: 24, t: 42, b: 56 },
    hoverlabel: { bgcolor: "#ffffff", bordercolor: palette.line, font: { color: palette.ink } },
    autosize: true
  };
  const config = { responsive: true, displaylogo: false };

  function loadJson(path) {
    return fetch(path).then(function (response) {
      if (!response.ok) throw new Error("Could not load " + path);
      return response.json();
    });
  }

  function renderPartyRepresentation(rows) {
    const parties = rows.map(row => row.party);
    Plotly.newPlot("party-representation-chart", [
      {
        x: parties,
        y: rows.map(row => row.included_count),
        type: "bar",
        name: "Included",
        marker: { color: palette.accentSoft },
        customdata: rows.map(row => [row.observed_count, row.excluded_count, row.inclusion_rate]),
        hovertemplate: "%{x}<br>Included: %{y}<br>Observed: %{customdata[0]}<br>Excluded: %{customdata[1]}<br>Inclusion: %{customdata[2]:.1%}<extra></extra>"
      },
      {
        x: parties,
        y: rows.map(row => row.excluded_count),
        type: "bar",
        name: "Excluded",
        marker: { color: palette.excluded },
        customdata: rows.map(row => [row.observed_count, row.inclusion_rate]),
        hovertemplate: "%{x}<br>Excluded: %{y}<br>Observed: %{customdata[0]}<br>Inclusion: %{customdata[1]:.1%}<extra></extra>"
      }
    ], {
      ...layoutBase,
      title: { text: "Included and excluded politicians by party", font: { size: 16 } },
      barmode: "stack",
      xaxis: { title: "Party", gridcolor: palette.line },
      yaxis: { title: "Politicians", gridcolor: palette.line, rangemode: "tozero" },
      legend: { orientation: "h", y: 1.08, x: 0 }
    }, config);
  }

  function renderParticipation(rows) {
    const traces = rows.map(function (row) {
      return {
        y: row.counts,
        type: "box",
        name: row.party,
        boxpoints: "all",
        jitter: 0.28,
        pointpos: 0,
        marker: { color: palette.accent, size: 5, opacity: 0.65 },
        line: { color: palette.accent },
        hovertemplate: row.party + "<br>Participation count: %{y}<extra></extra>"
      };
    });
    Plotly.newPlot("participation-chart", traces, {
      ...layoutBase,
      title: { text: "Participation counts by party", font: { size: 16 } },
      yaxis: { title: "Participated votes out of 168", gridcolor: palette.line, rangemode: "tozero" },
      xaxis: { title: "Party", gridcolor: palette.line },
      showlegend: false,
      shapes: [{ type: "line", x0: -0.5, x1: rows.length - 0.5, y0: 40, y1: 40, line: { color: palette.accent, dash: "dash", width: 2 } }],
      annotations: [{ x: 1, y: 40, xref: "paper", yref: "y", text: "40-vote threshold", showarrow: false, font: { color: palette.accent } }]
    }, config);
  }

  function populateDirectory(people) {
    const body = document.getElementById("politician-table-body");
    const search = document.getElementById("politician-search");
    const party = document.getElementById("politician-party");
    const status = document.getElementById("politician-status");
    const count = document.getElementById("directory-count");
    Array.from(new Set(people.map(row => row.party))).sort().forEach(function (value) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      party.appendChild(option);
    });
    let sortKey = "politician_name";
    let ascending = true;
    document.querySelectorAll(".data-table th[data-sort]").forEach(function (header) {
      header.addEventListener("click", function () {
        if (sortKey === header.dataset.sort) ascending = !ascending;
        else { sortKey = header.dataset.sort; ascending = true; }
        render();
      });
    });
    [search, party, status].forEach(control => control.addEventListener("input", render));
    function render() {
      const query = search.value.toLowerCase().trim();
      const filtered = people.filter(function (row) {
        const matchesQuery = !query || String(row.politician_id).includes(query) || row.politician_name.toLowerCase().includes(query);
        const matchesParty = !party.value || row.party === party.value;
        const matchesStatus = !status.value || row.status === status.value;
        return matchesQuery && matchesParty && matchesStatus;
      }).sort(function (left, right) {
        const a = left[sortKey], b = right[sortKey];
        return String(a).localeCompare(String(b), undefined, { numeric: true }) * (ascending ? 1 : -1);
      });
      body.innerHTML = filtered.map(function (row) {
        return "<tr><td>" + row.politician_name + " <small>#" + row.politician_id + "</small></td><td>" + row.party + "</td><td>" + row.participation_count + "</td><td>" + (row.participation_rate * 100).toFixed(1) + "%</td><td><span class=\"table-status-pill " + row.status.toLowerCase() + "\">" + row.status + "</span></td><td>" + (row.exclusion_reason || "—") + "</td></tr>";
      }).join("");
      count.textContent = "Showing " + filtered.length + " of " + people.length + " politicians.";
    }
    render();
  }

  loadJson("assets/data/dataset.json").then(function (data) {
    renderPartyRepresentation(data.party_summary);
    renderParticipation(data.participation_by_party);
    populateDirectory(data.politicians);
  }).catch(function (error) {
    document.querySelectorAll(".chart-container").forEach(function (container) {
      container.innerHTML = "<p class=\"chart-error\">Dataset chart data could not be loaded.</p>";
    });
    console.error(error);
  });
}());
