(function () {
  "use strict";

  const PARTY_ORDER = ["EL", "SF", "ALT", "RV", "S", "M", "V", "KF", "LA", "DD", "DF", "NB"];
  const CATEGORY_COLORS = {
    "Sundhed og ældrepleje": "#2b6cb0",
    "Klima og miljø": "#2f855a",
    "Skoler og børnepasning": "#b7791f",
    "Økonomi og skat": "#c53030",
    "Flygtninge og indvandrere": "#dd6b20",
    "Retspolitik og tryghed": "#4a5568",
    "Forsvar og sikkerhed": "#553c9a",
    "Pension og tilbagetrækning": "#319795"
  };
  const SVG_NS = "http://www.w3.org/2000/svg";
  const selectedCategories = new Set(["Sundhed og ældrepleje"]);
  const svg = document.getElementById("mk-network");
  const panel = document.getElementById("mk-panel");
  const tooltip = document.getElementById("mk-tooltip");
  let categories = [];
  let parties = [];
  let edges = [];
  let selectedParty = null;

  function loadJson(path) {
    return fetch(path).then(function (response) {
      if (!response.ok) throw new Error("Could not load " + path);
      return response.json();
    });
  }

  function htmlElement(name, className, parent) {
    const node = document.createElement(name);
    if (className) node.className = className;
    if (parent) parent.appendChild(node);
    return node;
  }

  function svgElement(name, attributes) {
    const node = document.createElementNS(SVG_NS, name);
    Object.keys(attributes).forEach(function (key) {
      node.setAttribute(key, attributes[key]);
    });
    return node;
  }

  function chosenCategories() {
    return categories.filter(function (category) {
      return selectedCategories.has(category);
    });
  }

  function titlesFor(party, category) {
    return party.kategorier[category] || [];
  }

  function selectedCount(party) {
    return chosenCategories().reduce(function (count, category) {
      return count + titlesFor(party, category).length;
    }, 0);
  }

  function showTooltip(content, event) {
    tooltip.replaceChildren();
    tooltip.appendChild(content);
    tooltip.classList.add("is-visible");
    moveTooltip(event);
  }

  function moveTooltip(event) {
    const margin = 12;
    const rect = tooltip.getBoundingClientRect();
    const left = Math.min(event.clientX + 14, window.innerWidth - rect.width - margin);
    const top = Math.min(event.clientY + 14, window.innerHeight - rect.height - margin);
    tooltip.style.left = Math.max(margin, left) + "px";
    tooltip.style.top = Math.max(margin, top) + "px";
  }

  function hideTooltip() {
    tooltip.classList.remove("is-visible");
  }

  function nodeTooltip(party) {
    const content = document.createDocumentFragment();
    const heading = htmlElement("strong", null, content);
    heading.textContent = party.partinavn;
    const count = htmlElement("span", null, content);
    count.textContent = selectedCount(party) + " af " + party.antal_maerkesager_i_alt + " mærkesager i de valgte kategorier";
    return content;
  }

  function edgeTooltip(edge) {
    const content = document.createDocumentFragment();
    const heading = htmlElement("strong", null, content);
    heading.textContent = edge.first.partikode + " – " + edge.second.partikode + " · " + edge.category;
    const list = htmlElement("ul", null, content);
    [edge.first, edge.second].forEach(function (party) {
      const item = htmlElement("li", null, list);
      item.textContent = party.partikode + ": " + titlesFor(party, edge.category).join("; ");
    });
    return content;
  }

  function positionFor(index) {
    const angle = (-150 + index * 30) * Math.PI / 180;
    return {
      x: 320 + Math.cos(angle) * 258,
      y: 320 + Math.sin(angle) * 258
    };
  }

  function pathFor(edge) {
    const first = positionFor(edge.firstIndex);
    const second = positionFor(edge.secondIndex);
    const dx = second.x - first.x;
    const dy = second.y - first.y;
    const length = Math.hypot(dx, dy);
    const ux = dx / length;
    const uy = dy / length;
    const start = { x: first.x + ux * 19, y: first.y + uy * 19 };
    const end = { x: second.x - ux * 19, y: second.y - uy * 19 };
    const middle = { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 };
    const offset = edge.parallelOffset;
    const control = {
      x: middle.x - uy * offset,
      y: middle.y + ux * offset
    };
    return "M " + start.x + " " + start.y + " Q " + control.x + " " + control.y + " " + end.x + " " + end.y;
  }

  function buildEdges() {
    edges = [];
    for (let firstIndex = 0; firstIndex < parties.length; firstIndex += 1) {
      for (let secondIndex = firstIndex + 1; secondIndex < parties.length; secondIndex += 1) {
        const first = parties[firstIndex];
        const second = parties[secondIndex];
        const shared = categories.filter(function (category) {
          return titlesFor(first, category).length && titlesFor(second, category).length;
        });
        shared.forEach(function (category, index) {
          edges.push({
            first: first,
            second: second,
            firstIndex: firstIndex,
            secondIndex: secondIndex,
            category: category,
            parallelOffset: (index - (shared.length - 1) / 2) * 12
          });
        });
      }
    }
  }

  function renderNetwork() {
    svg.replaceChildren();
    const edgeLayer = svgElement("g", { "aria-hidden": "true" });
    const nodeLayer = svgElement("g", {});
    svg.appendChild(edgeLayer);
    svg.appendChild(nodeLayer);

    edges.forEach(function (edge) {
      if (!selectedCategories.has(edge.category)) return;
      const path = svgElement("path", {
        d: pathFor(edge),
        class: "mk-edge",
        stroke: CATEGORY_COLORS[edge.category],
        opacity: selectedParty
          ? (edge.first === selectedParty || edge.second === selectedParty ? "0.9" : "0.07")
          : "0.52",
        "aria-label": edge.first.partikode + " – " + edge.second.partikode + " · " + edge.category
      });
      path.addEventListener("mouseenter", function (event) { showTooltip(edgeTooltip(edge), event); });
      path.addEventListener("mousemove", moveTooltip);
      path.addEventListener("mouseleave", hideTooltip);
      edgeLayer.appendChild(path);
    });

    parties.forEach(function (party, index) {
      const position = positionFor(index);
      const active = selectedCount(party) > 0;
      const node = svgElement("g", {
        class: "mk-node" + (selectedParty === party ? " is-selected" : ""),
        transform: "translate(" + position.x + " " + position.y + ")",
        tabindex: "0",
        role: "button",
        "aria-label": party.partinavn + ", " + selectedCount(party) + " af " + party.antal_maerkesager_i_alt + " mærkesager i de valgte kategorier"
      });
      node.appendChild(svgElement("circle", {
        r: 19,
        fill: active ? party.farve : "#aeb7c1",
        opacity: active ? "1" : "0.78"
      }));
      const label = svgElement("text", {});
      label.textContent = party.partikode;
      node.appendChild(label);

      node.addEventListener("mouseenter", function (event) { showTooltip(nodeTooltip(party), event); });
      node.addEventListener("mousemove", moveTooltip);
      node.addEventListener("mouseleave", hideTooltip);
      node.addEventListener("focus", function () {
        const rect = node.getBoundingClientRect();
        showTooltip(nodeTooltip(party), { clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2 });
      });
      node.addEventListener("blur", hideTooltip);
      node.addEventListener("click", function () { toggleParty(party); });
      node.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          toggleParty(party);
        }
      });
      nodeLayer.appendChild(node);
    });
  }

  function renderPanel() {
    panel.replaceChildren();
    if (selectedParty) {
      const heading = htmlElement("h2", null, panel);
      heading.textContent = selectedParty.partinavn + " (" + selectedParty.partikode + ")";
      chosenCategories().forEach(function (category) {
        const categoryHeading = htmlElement("h3", null, panel);
        categoryHeading.textContent = category;
        const titles = titlesFor(selectedParty, category);
        if (!titles.length) {
          const empty = htmlElement("p", null, panel);
          empty.textContent = "Ingen mærkesager i denne kategori.";
          return;
        }
        const list = htmlElement("ul", null, panel);
        titles.forEach(function (title) {
          const item = htmlElement("li", null, list);
          item.textContent = title;
        });
      });
      if (!chosenCategories().length) {
        const empty = htmlElement("p", null, panel);
        empty.textContent = "Vælg mindst én kategori for at se partiets mærkesager.";
      }
      return;
    }

    const heading = htmlElement("h2", null, panel);
    heading.textContent = "Mærkesager i valgte kategorier";
    if (!chosenCategories().length) {
      const empty = htmlElement("p", null, panel);
      empty.textContent = "Vælg mindst én kategori for at se fælles mærkesager.";
      return;
    }
    chosenCategories().forEach(function (category) {
      const categoryHeading = htmlElement("h3", null, panel);
      categoryHeading.textContent = category;
      const matching = parties.filter(function (party) {
        return titlesFor(party, category).length > 0;
      });
      const summary = htmlElement("p", null, panel);
      summary.textContent = matching.length
        ? matching.map(function (party) {
          return party.partikode + " (" + titlesFor(party, category).length + ")";
        }).join(", ")
        : "Ingen partier";
    });
  }

  function render() {
    renderNetwork();
    renderPanel();
  }

  function toggleParty(party) {
    selectedParty = selectedParty === party ? null : party;
    render();
  }

  function renderCategoryButtons() {
    const container = document.getElementById("mk-category-buttons");
    categories.forEach(function (category) {
      const button = htmlElement("button", "mk-category-button", container);
      button.type = "button";
      button.textContent = category;
      button.style.setProperty("--mk-category-color", CATEGORY_COLORS[category]);
      button.setAttribute("aria-pressed", String(selectedCategories.has(category)));
      button.addEventListener("click", function () {
        if (selectedCategories.has(category)) selectedCategories.delete(category);
        else selectedCategories.add(category);
        button.setAttribute("aria-pressed", String(selectedCategories.has(category)));
        render();
      });
    });
  }

  document.getElementById("mk-select-all").addEventListener("click", function () {
    categories.forEach(function (category) { selectedCategories.add(category); });
    document.querySelectorAll(".mk-category-button").forEach(function (button) {
      button.setAttribute("aria-pressed", "true");
    });
    render();
  });
  document.getElementById("mk-select-none").addEventListener("click", function () {
    selectedCategories.clear();
    document.querySelectorAll(".mk-category-button").forEach(function (button) {
      button.setAttribute("aria-pressed", "false");
    });
    render();
  });

  document.addEventListener("DOMContentLoaded", function () {
    loadJson("assets/data/maerkesager_2022.json")
      .then(function (json) {
        categories = json.kategorier;
        parties = PARTY_ORDER.map(function (code) {
          return json.partier.find(function (party) { return party.partikode === code; });
        }).filter(Boolean);
        if (parties.length !== PARTY_ORDER.length) throw new Error("maerkesager_2022.json mangler et eller flere partier");
        renderCategoryButtons();
        buildEdges();
        render();
      })
      .catch(function (error) {
        const message = htmlElement("p", null, panel);
        message.textContent = "Fejl ved indlæsning af mærkesagsdata: " + error.message;
        console.error(error);
      });
  });
}());
