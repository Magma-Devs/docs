// Supported-chains explorer — logo-wall hero + filterable card grid with shared
// search and ecosystem filters. Renders into #chains-explorer if present.
// Re-runs on every Material instant-nav load.
document$.subscribe(function () {
  var root = document.getElementById("chains-explorer");
  if (!root || !window.CHAINS) return;
  if (root.dataset.built) return; // guard against double-build
  root.dataset.built = "1";

  var CHAINS = window.CHAINS;
  var ECOS = ["All", "EVM", "Cosmos", "L1", "BTC", "Specialty"];
  var ICON_BASE = root.getAttribute("data-icon-base") || "../../assets/chains/";

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function icon(id) {
    return '<img class="cx-ico" loading="lazy" src="' + ICON_BASE + id + '.svg" alt="">';
  }
  function netBadges(c) {
    var s = "";
    if (c.main) s += '<span class="badge net-main">Mainnet</span>';
    if (c.test) s += '<span class="badge net-test">Testnet</span>';
    if (!c.main && !c.test) s += '<span class="badge net-test">Testnet</span>';
    return s;
  }
  function ifaceBadges(c) {
    var meta = {
      "JSON-RPC": ["iface-rpc", "RPC"], "REST": ["iface-rest", "REST"],
      "Tendermint": ["iface-tm", "TM"], "gRPC": ["iface-grpc", "gRPC"]
    };
    return c.ifs.map(function (i) {
      var m = meta[i] || ["iface-rpc", i];
      return '<span class="badge iface ' + m[0] + '">' + m[1] + "</span>";
    }).join("");
  }
  function specLinks(c) {
    return c.specs.map(function (u) {
      var f = u.split("/").pop();
      return '<a class="cx-spec" href="' + u + '" title="View spec: ' + f + '" target="_blank" rel="noopener">↗</a>';
    }).join("");
  }

  // ---- build DOM ----
  var controls = el("div", "cx-controls");
  var search = el("input", "cx-search");
  search.type = "search";
  search.placeholder = "Search " + CHAINS.length + " chains…";
  search.setAttribute("aria-label", "Search chains");
  var chips = el("div", "cx-chips");
  ECOS.forEach(function (e, i) {
    var chip = el("button", "cx-chip" + (i === 0 ? " on" : ""), e);
    chip.dataset.eco = e;
    chips.appendChild(chip);
  });
  controls.appendChild(search);
  controls.appendChild(chips);

  var wall = el("div", "cx-wall");
  var cards = el("div", "cx-cards");
  var empty = el("p", "cx-empty", "No chains match.");
  empty.style.display = "none";

  CHAINS.forEach(function (c) {
    var tile = el("a", "cx-tile");
    tile.href = "#cx-" + c.id;
    tile.title = c.name;
    tile.dataset.id = c.id;
    tile.innerHTML = icon(c.id);
    wall.appendChild(tile);

    var card = el("div", "cx-card");
    card.id = "cx-" + c.id;
    card.dataset.name = c.name.toLowerCase();
    card.dataset.eco = c.eco;
    card.innerHTML =
      '<div class="cx-spec-row">' + specLinks(c) + "</div>" +
      icon(c.id) +
      '<span class="cx-name">' + c.name + "</span>" +
      '<div class="cx-nets">' + netBadges(c) + "</div>" +
      '<div class="cx-ifs">' + ifaceBadges(c) + "</div>";
    cards.appendChild(card);
  });

  // pagination footer
  var pager = el("div", "cx-pager");
  var prev = el("button", "cx-page-btn", "‹ Prev");
  var pageInfo = el("span", "cx-page-info");
  var next = el("button", "cx-page-btn", "Next ›");
  var showAll = el("button", "cx-showall", "Show all");
  pager.appendChild(prev);
  pager.appendChild(pageInfo);
  pager.appendChild(next);
  pager.appendChild(showAll);

  root.appendChild(controls);
  root.appendChild(wall);
  root.appendChild(cards);
  root.appendChild(empty);
  root.appendChild(pager);

  // ---- filtering + pagination ----
  var PAGE = 9;
  var activeEco = "All";
  var page = 0;
  var all = false;

  function matched() {
    var q = search.value.trim().toLowerCase();
    return CHAINS.filter(function (c) {
      return (activeEco === "All" || c.eco === activeEco) &&
        (q === "" || c.name.toLowerCase().indexOf(q) !== -1 || c.id.indexOf(q) !== -1);
    });
  }
  function apply() {
    var list = matched();
    var ids = {};
    list.forEach(function (c) { ids[c.id] = true; });
    // wall: dim non-matches
    CHAINS.forEach(function (c) {
      wall.querySelector('[data-id="' + c.id + '"]').classList.toggle("dim", !ids[c.id]);
    });
    empty.style.display = list.length === 0 ? "" : "none";
    // pagination window
    var pages = all ? 1 : Math.max(1, Math.ceil(list.length / PAGE));
    if (page >= pages) page = pages - 1;
    if (page < 0) page = 0;
    var start = all ? 0 : page * PAGE;
    var end = all ? list.length : start + PAGE;
    var visible = {};
    list.slice(start, end).forEach(function (c) { visible[c.id] = true; });
    CHAINS.forEach(function (c) {
      document.getElementById("cx-" + c.id).style.display = visible[c.id] ? "" : "none";
    });
    // footer state
    pager.style.display = list.length > PAGE ? "" : "none";
    prev.disabled = all || page === 0;
    next.disabled = all || page >= pages - 1;
    pageInfo.style.display = all ? "none" : "";
    pageInfo.textContent = "Page " + (page + 1) + " of " + pages + " · " + list.length + " chains";
    showAll.textContent = all ? "Show pages" : "Show all (" + list.length + ")";
  }
  function reset() { page = 0; apply(); }

  search.addEventListener("input", reset);
  chips.addEventListener("click", function (ev) {
    var b = ev.target.closest(".cx-chip");
    if (!b) return;
    activeEco = b.dataset.eco;
    chips.querySelectorAll(".cx-chip").forEach(function (x) { x.classList.toggle("on", x === b); });
    reset();
  });
  prev.addEventListener("click", function () { page--; apply(); root.scrollIntoView({ behavior: "smooth", block: "start" }); });
  next.addEventListener("click", function () { page++; apply(); root.scrollIntoView({ behavior: "smooth", block: "start" }); });
  showAll.addEventListener("click", function () { all = !all; page = 0; apply(); });
  apply();

  // Clicking a wall tile jumps to the page holding that card, then flashes it.
  wall.addEventListener("click", function (ev) {
    var t = ev.target.closest(".cx-tile");
    if (!t) return;
    ev.preventDefault();
    var id = t.dataset.id;
    var list = matched();
    var idx = list.findIndex(function (c) { return c.id === id; });
    if (idx === -1) {
      // tile is filtered out — clear filters so it's reachable
      search.value = "";
      activeEco = "All";
      chips.querySelectorAll(".cx-chip").forEach(function (x) { x.classList.toggle("on", x.dataset.eco === "All"); });
      list = matched();
      idx = list.findIndex(function (c) { return c.id === id; });
    }
    if (!all) page = Math.floor(idx / PAGE);
    apply();
    var card = document.getElementById("cx-" + id);
    if (!card) return;
    card.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(function () {
      card.classList.add("flash");
      setTimeout(function () { card.classList.remove("flash"); }, 1400);
    }, 250);
  });
});
