// Build a drpc-style header bar + search box at the top of the mobile nav drawer.
//
// Material's mobile drawer has no header or search field of its own. drpc keeps a
// bar inside the open drawer — logo (left), GitHub icon + close ✕ (right) — with a
// "Search documentation…" box below it. We mirror that:
//   1. A header row: cloned logo, cloned GitHub source link, and a ✕ that closes
//      the drawer (unchecks Material's #__drawer toggle).
//   2. A search input that hands off to Material's real search overlay on focus.
document$.subscribe(function () {
  var inner = document.querySelector(".md-sidebar--primary .md-sidebar__inner");
  var list = document.querySelector(".md-sidebar--primary .md-nav--primary > .md-nav__list");
  if (!inner || !list) return;

  // Guard against double-injection on instant-navigation re-renders.
  if (inner.querySelector(".lc-drawer-head")) return;

  var drawerToggle = document.getElementById("__drawer");
  var searchToggle = document.getElementById("__search");
  var realInput = document.querySelector(".md-search__input");

  // --- 1. Header bar: logo · GitHub · close ✕ ---------------------------------
  var head = document.createElement("div");
  head.className = "lc-drawer-head";

  // Clone the page header's logo (link to home).
  var srcLogo = document.querySelector(".md-header__button.md-logo");
  if (srcLogo) {
    var logo = srcLogo.cloneNode(true);
    logo.classList.add("lc-drawer-logo");
    head.appendChild(logo);
  }

  var actions = document.createElement("div");
  actions.className = "lc-drawer-actions";

  // Clone the GitHub source link (icon only).
  var srcRepo = document.querySelector(".md-header__source .md-source");
  if (srcRepo) {
    var gh = document.createElement("a");
    gh.className = "lc-drawer-gh";
    gh.href = srcRepo.getAttribute("href") || "#";
    gh.target = "_blank";
    gh.rel = "noopener";
    gh.setAttribute("aria-label", "Repository");
    var icon = srcRepo.querySelector(".md-source__icon svg");
    if (icon) gh.appendChild(icon.cloneNode(true));
    actions.appendChild(gh);
  }

  // Close ✕ — unchecks the drawer toggle.
  var close = document.createElement("button");
  close.type = "button";
  close.className = "lc-drawer-close";
  close.setAttribute("aria-label", "Close navigation");
  close.innerHTML =
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' " +
    "stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>" +
    "<path d='M18 6 6 18'/><path d='m6 6 12 12'/></svg>";
  close.addEventListener("click", function () {
    if (drawerToggle) drawerToggle.checked = false;
  });
  actions.appendChild(close);
  head.appendChild(actions);

  inner.insertBefore(head, inner.firstChild);

  // --- 2. Search box ----------------------------------------------------------
  var box = document.createElement("div");
  box.className = "lc-drawer-search";

  var input = document.createElement("input");
  input.type = "text";
  input.placeholder = "Search documentation…";
  input.setAttribute("aria-label", "Search documentation");
  input.autocomplete = "off";
  input.spellcheck = false;
  box.appendChild(input);

  // Place it in `.md-sidebar__inner` (sibling of the nav), directly after the
  // header bar — so header → search → nav stack vertically in one column.
  var nav = inner.querySelector(".md-nav--primary");
  inner.insertBefore(box, nav);

  function handoff() {
    if (!realInput || !searchToggle) return;
    // Close the nav drawer so the search overlay owns the screen, then open it
    // and move focus + any typed text into the real input.
    if (drawerToggle) drawerToggle.checked = false;
    searchToggle.checked = true;
    var typed = input.value;
    requestAnimationFrame(function () {
      realInput.focus();
      if (typed) {
        realInput.value = typed;
        realInput.dispatchEvent(new Event("input", { bubbles: true }));
      }
    });
    input.value = "";
  }

  input.addEventListener("focus", handoff);
  input.addEventListener("click", handoff);
});
