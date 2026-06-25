// Inject a drpc-style search box at the top of the mobile nav drawer.
//
// Material's mobile drawer has no search field of its own — search lives behind a
// magnifier toggle in the header. drpc puts a "Search documentation…" box at the
// top of the slide-out nav. We mirror that: a lightweight input that, when the
// user starts typing (or taps it), hands off to Material's real search overlay so
// indexing/results stay fully native.
document$.subscribe(function () {
  var list = document.querySelector(".md-sidebar--primary .md-nav--primary > .md-nav__list");
  if (!list) return;

  // Guard against double-injection on instant-navigation re-renders.
  if (list.parentElement.querySelector(".lc-drawer-search")) return;

  var box = document.createElement("div");
  box.className = "lc-drawer-search";

  var input = document.createElement("input");
  input.type = "text";
  input.placeholder = "Search documentation…";
  input.setAttribute("aria-label", "Search documentation");
  input.autocomplete = "off";
  input.spellcheck = false;
  box.appendChild(input);

  // Insert above the section list, inside the scrollwrap so it scrolls with it.
  list.parentElement.insertBefore(box, list);

  // The real search input + the search/drawer toggles Material already rendered.
  var realInput = document.querySelector(".md-search__input");
  var searchToggle = document.getElementById("__search");
  var drawerToggle = document.getElementById("__drawer");

  function handoff() {
    if (!realInput || !searchToggle) return;
    // Close the nav drawer so the search overlay owns the screen, then open it
    // and move focus + any typed text into the real input.
    if (drawerToggle) drawerToggle.checked = false;
    searchToggle.checked = true;
    var typed = input.value;
    // Defer so the overlay is visible before we focus/seed it.
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
