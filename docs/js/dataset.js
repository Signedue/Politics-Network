(function () {
  "use strict";

  const palette = {
    accent: "#1e6b68",
    accentSoft: "rgba(30, 107, 104, 0.78)",
    muted: "#66717d",
    ink: "#17202a",
    line: "#dce3e8",
    missing: "#b9c5c6"
  };
  const layoutBase = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "#ffffff",
    font: { family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", color: palette.ink },
    margin: { l: 60, r: 24, t: 42, b: 62 },
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

  function renderCoverage(rows) {
    Plotly.newPlot("coverage-chart", [
      {
        x: rows.map(row => row.label),
        y: rows.map(row => row.with_records),
        type: "bar",
        name: "With individual records",
        marker: { color: palette.accentSoft },
        customdata: rows.map(row => [row.total_votes, row.without_records]),
        hovertemplate: "%{x}<br>With records: %{y}<br>Total votes: %{customdata[0]}<br>Without records: %{customdata[1]}<extra></extra>"
      },
      {
        x: rows.map(row => row.label),
        y: rows.map(row => row.without_records),
        type: "bar",
        name: "Without individual records",
        marker: { color: palette.missing },
        customdata: rows.map(row => [row.total_votes, row.with_records]),
        hovertemplate: "%{x}<br>Without records: %{y}<br>Total votes: %{customdata[0]}<br>With records: %{customdata[1]}<extra></extra>"
      }
    ], {
      ...layoutBase,
      title: { text: "Vote coverage by session and year", font: { size: 16 } },
      barmode: "stack",
      xaxis: { title: "Session / year", gridcolor: palette.line, tickangle: -35 },
      yaxis: { title: "Votes", gridcolor: palette.line, rangemode: "tozero" },
      legend: { orientation: "h", y: 1.08, x: 0 }
    }, config);
  }

  function renderParticipation(rows) {
    Plotly.newPlot("participation-chart", rows.map(function (row) {
      return {
        y: row.counts,
        type: "box",
        name: row.party,
        boxpoints: "all",
        jitter: 0.28,
        pointpos: 0,
        marker: { color: palette.accent, size: 5, opacity: 0.65 },
        line: { color: palette.accent },
        hovertemplate: row.party + "<br>Participated positions: %{y}<extra></extra>"
      };
    }), {
      ...layoutBase,
      title: { text: "Participation counts by party", font: { size: 16 } },
      yaxis: { title: "For + Imod + Hverken", gridcolor: palette.line, rangemode: "tozero" },
      xaxis: { title: "Party", gridcolor: palette.line },
      showlegend: false
    }, config);
  }

  function populateDirectory(people) {
    const body = document.getElementById("politician-table-body");
    const search = document.getElementById("politician-search");
    const party = document.getElementById("politician-party");
    const count = document.getElementById("directory-count");
    Array.from(new Set(people.map(row => row.party))).sort().forEach(function (value) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      party.appendChild(option);
    });
    let sortKey = "name";
    let ascending = true;
    document.querySelectorAll(".data-table th[data-sort]").forEach(function (header) {
      header.addEventListener("click", function () {
        if (sortKey === header.dataset.sort) ascending = !ascending;
        else { sortKey = header.dataset.sort; ascending = true; }
        render();
      });
    });
    [search, party].forEach(control => control.addEventListener("input", render));
    function render() {
      const query = search.value.toLowerCase().trim();
      const filtered = people.filter(function (row) {
        const matchesQuery = !query ||
          String(row.actor_id).includes(query) ||
          row.name.toLowerCase().includes(query);
        return matchesQuery && (!party.value || row.party === party.value);
      }).sort(function (left, right) {
        const a = left[sortKey], b = right[sortKey];
        return String(a).localeCompare(String(b), undefined, { numeric: true }) * (ascending ? 1 : -1);
      });
      body.innerHTML = filtered.map(function (row) {
        return "<tr><td>" + row.name + " <small>#" + row.actor_id + "</small></td><td>" +
          row.party + "</td><td>" + row.for_count + "</td><td>" + row.against_count +
          "</td><td>" + row.neither_count + "</td><td>" + row.absent_count +
          "</td><td>" + row.recorded_vote_rows + "</td><td>" +
          (row.participation_rate * 100).toFixed(1) + "%</td></tr>";
      }).join("");
      count.textContent = "Showing " + filtered.length + " of " + people.length + " politicians.";
    }
    render();
  }

  loadJson("assets/data/post2022_dataset.json").then(function (data) {
    renderCoverage(data.coverage);
    renderParticipation(data.participation_by_party);
    populateDirectory(data.politicians);
  }).catch(function (error) {
    document.querySelectorAll(".chart-container").forEach(function (container) {
      container.innerHTML = "<p class=\"chart-error\">Full-period dataset chart data could not be loaded.</p>";
    });
    console.error(error);
  });
}());
