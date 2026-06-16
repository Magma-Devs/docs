// Material for MkDocs — make the chain catalog tables sortable by their first
// column. Targets tables whose first header is "Chain" or "Spec" (the catalog
// tables, including Specialty); prose tables elsewhere are untouched.
// Re-runs on every instant-nav page load.
document$.subscribe(function () {
  document.querySelectorAll("article table").forEach(function (table) {
    var firstTh = table.querySelector("thead th");
    if (!firstTh) return;
    var label = firstTh.textContent.trim();
    if (label === "Chain" || label === "Spec") {
      firstTh.classList.add("th-sortable");
      new Tablesort(table);
    }
  });
});
