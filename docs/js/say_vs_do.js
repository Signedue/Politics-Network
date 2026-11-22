(function () {
  "use strict";

  const PARTIES = ["S", "V", "M", "SF", "DD", "LA", "KF", "EL", "DF", "RV", "ALT"];
  let data;
  let mode = "parties";

  const layoutBase = {
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "#ffffff",
    font: { family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", color: "#17202a" },
    margin: { l: 150, r: 24, t: 28, b: 50 },
    hoverlabel: { bgcolor: "#ffffff", bordercolor: "#d7e1e3", font: { color: "#17202a" } },
    autosize: true, showlegend: false
  };
  const config = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] };

  function loadJson(path) {
    return fetch(path).then(function (response) {
      if (!response.ok) throw new Error("Could not load " + path);
      return response.json();
    });
  }
  function partyName(party) { return data.parties[party] ? data.parties[party].name : party; }
  function partyColor(party) { return data.parties[party] ? data.parties[party].color : "#9AA3AB"; }

  function renderDiverging(topicId) {
    const say = data.say[topicId] || {};
    const doData = data.do[topicId] || {};
    const parties = PARTIES.filter(function (party) { return say[party] && say[party].n_quotes >= 3; });

    parties.sort(function (a, b) { return say[b].deviation - say[a].deviation; });
    document.getElementById("svd-data-count").textContent = parties.length < 3
      ? "Kun " + parties.length + " partier har nok citater om dette emne, så sammenligningen er usikker"
      : "";

    const sayMean = parties.length ? parties.reduce(function (sum, party) { return sum + say[party].score; }, 0) / parties.length : 0;
    const doPresent = parties.filter(function (party) { return doData[party]; });
    const doMean = doPresent.length ? doPresent.reduce(function (sum, party) { return sum + doData[party].score; }, 0) / doPresent.length : 0;

    function barTrace(source, kind) {
      const y = parties.map(function (party) { return party + " · n = " + (kind === "say" ? say[party].n_quotes + " citater" : (doData[party] ? doData[party].n_votes + " stemmer" : "mangler data")); });
      const x = parties.map(function (party) {
        if (kind === "say") return say[party].score - sayMean;
        return doData[party] ? doData[party].score - doMean : null;
      });
      return {
        type: "bar", orientation: "h", y: y, x: x,
        marker: { color: parties.map(partyColor), line: { width: 0 } },
        customdata: parties.map(function (party) {
          const s = say[party];
          const d = doData[party];
          return [partyName(party), kind === "say" ? s.score - sayMean : (d ? d.score - doMean : null), kind === "say" ? s.score : (d ? d.score : null), s.n_quotes, d ? d.n_votes : null];
        }),
        hovertemplate: kind === "say"
          ? "%{customdata[0]}<br>Afvigelse: %{x:.3f}<br>Score: %{customdata[2]:.3f}<br>n = %{customdata[3]} citater<extra></extra>"
          : "%{customdata[0]}<br>Afvigelse: %{x:.3f}<br>Score: %{customdata[2]:.3f}<br>n = %{customdata[4]} stemmer<extra></extra>"
      };
    }

    const common = {
      margin: { l: 150, r: 24, t: 28, b: 50 },
      xaxis: { range: [-1, 1], title: "Afvigelse", gridcolor: "#d7e1e3", zeroline: true, zerolinecolor: "#66717d", zerolinewidth: 2 },
      yaxis: { type: "category", autorange: "reversed", tickfont: { size: 11 } }
    };
    Plotly.react("say-chart", [barTrace(say, "say")], { ...layoutBase, ...common }, config);
    Plotly.react("do-chart", [barTrace(doData, "do")], { ...layoutBase, ...common }, config);
  }

  function makePartyAvatar(party) {
    const el = document.createElement("span");
    el.className = "svd-avatar";
    el.style.backgroundColor = partyColor(party);
    el.textContent = party;
    return el;
  }

  function makeCard(row) {
    const isParty = mode === "parties";
    const party = row.party;
    const name = isParty ? partyName(party) : row.name;
    const card = document.createElement("article");
    card.className = "svd-person-card";
    card.tabIndex = 0;

    const head = document.createElement("div");
    head.className = "svd-person-head";
    head.appendChild(makePartyAvatar(party));
    const identity = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = name;
    const badge = document.createElement("span");
    badge.className = "svd-party-badge";
    badge.style.backgroundColor = partyColor(party);
    badge.textContent = party;
    identity.appendChild(title); identity.appendChild(badge);
    head.appendChild(identity);

    const pct = document.createElement("div");
    pct.className = "svd-consistency";
    pct.textContent = "Holder i " + row.holder + " af " + (row.holder + row.holder_ikke) + " emner";
    head.appendChild(pct);
    card.appendChild(head);

    const swap = document.createElement("p");
    swap.className = "svd-swap-line";
    const first = row.sagde_for === 0 ? "–" : row.for_til_imod + " af " + row.sagde_for;
    const second = row.sagde_imod === 0 ? "–" : row.imod_til_for + " af " + row.sagde_imod;
    swap.textContent = "Sagde FOR, stemte IMOD: " + first + " emner · Sagde IMOD, stemte FOR: " + second + " emner";
    card.appendChild(swap);

    const quoteCount = document.createElement("p");
    quoteCount.className = "svd-card-meta";
    const quoteTotal = isParty
      ? row.topics.reduce(function (sum, topic) { return sum + (topic.n_quotes || 0); }, 0)
      : row.n_quotes;
    quoteCount.textContent = quoteTotal + " citater i alt";
    if (!isParty && row.own_votes === false) quoteCount.textContent += " · * partiets stemmer";
    card.appendChild(quoteCount);

    const detail = document.createElement("div");
    detail.className = "svd-topic-details";
    row.topics.forEach(function (topic) {
      const chip = document.createElement("span");
      chip.className = "svd-topic-chip " + (topic.dom === "Holder" ? "holder" : topic.dom === "Holder ikke" ? "holder-not" : "unclear");
      chip.textContent = topic.emne + " — Sagde " + topic.sagde + " → Stemte " + topic.stemte;
      detail.appendChild(chip);
    });
    card.appendChild(detail);

    card.addEventListener("click", function () { card.classList.toggle("open"); });
    card.addEventListener("keydown", function (event) { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); card.classList.toggle("open"); } });
    return card;
  }

  function renderRankings() {
    const list = mode === "parties" ? data.party_summary : data.politicians;
    const eligible = list.filter(function (row) { return (row.holder + row.holder_ikke) >= 2; });
    const holder = eligible.filter(function (row) { return row.holder > row.holder_ikke; }).sort(function (a, b) { return b.holder - a.holder || (b.holder_ikke - a.holder_ikke); }).slice(0,5);
    const least = eligible.filter(function (row) { return row.holder_ikke > row.holder; }).sort(function (a, b) { return b.holder_ikke - a.holder_ikke || b.holder - a.holder; }).slice(0,5);
    const mixed = eligible.filter(function (row) { return row.holder === row.holder_ikke; });

    const containers = [["svd-holder-most", holder], ["svd-holder-least", least], ["svd-holder-mixed", mixed]];
    containers.forEach(function (entry) {
      const container = document.getElementById(entry[0]);
      container.replaceChildren();
      if (!entry[1].length) {
        const empty = document.createElement("p");
        empty.className = "svd-empty";
        empty.textContent = mode === "parties" ? "Ingen partier i denne gruppe" : "Ingen politikere i denne gruppe";
        container.appendChild(empty);
      } else entry[1].forEach(function (row) { container.appendChild(makeCard(row)); });
    });
  }

  function renderTable() {
    const head = document.getElementById("svd-table-head");
    const body = document.getElementById("svd-table-body");
    const detail = document.getElementById("svd-cell-detail");
    const hr = document.createElement("tr");
    const partyTh = document.createElement("th"); partyTh.textContent = "Parti"; hr.appendChild(partyTh);
    data.topics.forEach(function (topic) { const th=document.createElement("th"); th.textContent=topic.label; hr.appendChild(th); });
    head.replaceChildren(hr); body.replaceChildren();

    PARTIES.forEach(function (party) {
      const summary = data.party_summary.find(function (row) { return row.party === party; });
      if (!summary) return;
      const tr=document.createElement("tr");
      const name=document.createElement("th"); name.className="svd-table-party";
      const avatar=makePartyAvatar(party); name.appendChild(avatar);
      const label=document.createElement("span"); label.textContent=partyName(party); name.appendChild(label); tr.appendChild(name);
      data.topics.forEach(function(topic) {
        const td=document.createElement("td");
        const row=summary.topics.find(function(r){return r.emne===topic.id;});
        if (!row) { td.text="–"; td.textContent="–"; td.className="svd-cell svd-cell-none"; td.title="For lidt data"; }
        else {
          td.className="svd-cell "+(row.dom=== "Holder"?"svd-cell-holder":row.dom=== "Holder ikke"?"svd-cell-not":"svd-cell-unclear");
          td.textContent=row.dom=== "Holder"?"✓":row.dom=== "Holder ikke"?"✗":"?";
          const text="Sagde: "+row.sagde+" ("+row.n_quotes+" citater) · Stemte: "+row.stemte+" ("+Math.round(row.share_for*100)+" % for)";
          td.title=text; td.tabIndex=0;
          function show(){detail.textContent=partyName(party)+" — "+topic.label+" · "+text;} 
          td.addEventListener("mouseenter",show); td.addEventListener("focus",show); td.addEventListener("click",show);
        }
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    loadJson("assets/data/say_vs_do.json").then(function (json) {
      data=json;
      const select=document.getElementById("svd-topic");
      data.topics.forEach(function(topic){const option=document.createElement("option");option.value=topic.id;option.textContent=topic.label+" ("+topic.stance+")";select.appendChild(option);});
      select.addEventListener("change",function(){renderDiverging(select.value);});
      document.querySelectorAll(".svd-toggle-button").forEach(function(button){button.addEventListener("click",function(){document.querySelectorAll(".svd-toggle-button").forEach(function(b){b.classList.remove("active");});button.classList.add("active");mode=button.dataset.mode;renderRankings();});});
      renderDiverging(data.topics[0].id); renderRankings(); renderTable();
    }).catch(function(error){console.error(error);});
  });
}());
