// Add the page's main H1 as the first entry in the right-hand Table of contents.
// Material omits the H1 by default; this surfaces it on every page so the TOC
// always opens with the page title. Re-runs on every instant-nav load.
document$.subscribe(function () {
  var toc = document.querySelector(".md-sidebar--secondary .md-nav--secondary > .md-nav__list");
  var h1 = document.querySelector(".md-content article h1, .md-content__inner h1");
  if (!toc || !h1) return;
  if (toc.querySelector(".md-nav__item--toc-title")) return; // already added

  // ensure the H1 has an id to link to
  if (!h1.id) {
    h1.id = h1.textContent.trim().toLowerCase().replace(/[^\w]+/g, "-").replace(/^-+|-+$/g, "");
  }
  var title = h1.textContent.replace(/¶$/, "").trim();

  var li = document.createElement("li");
  li.className = "md-nav__item md-nav__item--toc-title";
  var a = document.createElement("a");
  a.className = "md-nav__link";
  a.href = "#" + h1.id;
  a.textContent = title;
  li.appendChild(a);
  toc.insertBefore(li, toc.firstChild);
});
