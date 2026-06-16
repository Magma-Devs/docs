// Add a ⌘K / Ctrl+K hint badge to the search box and bind the shortcut to
// focus search (Material binds "/" and "s" but not Ctrl/⌘+K). Runs once.
document$.subscribe(function () {
  var form = document.querySelector(".md-search__form");
  var input = document.querySelector(".md-search__input");
  if (!form || !input) return;
  if (!form.querySelector(".md-search__keyhint")) {
    var isMac = /Mac|iPhone|iPad/.test(navigator.platform);
    var hint = document.createElement("kbd");
    hint.className = "md-search__keyhint";
    hint.textContent = isMac ? "⌘K" : "Ctrl K";
    form.appendChild(hint);
  }
});

// Global shortcut (bind once). Open Material's search the same way its own
// hotkeys do: flip the toggle, fire `change` so Material wires up the results
// observable, then focus the input.
if (!window.__cxSearchKey) {
  window.__cxSearchKey = true;
  document.addEventListener("keydown", function (e) {
    if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
      e.preventDefault();
      var toggle = document.querySelector("[data-md-toggle=search]");
      var input = document.querySelector(".md-search__input");
      if (toggle) {
        toggle.checked = true;
        toggle.dispatchEvent(new Event("change", { bubbles: true }));
      }
      if (input) {
        // focus on the next frame so Material's change handler has run
        requestAnimationFrame(function () { input.focus(); });
      }
    }
  });
}
