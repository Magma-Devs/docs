// Keep the left nav anchored at the top on load (drpc-style), instead of
// Material auto-scrolling it down to the active item. Runs after Material's
// own scroll positioning settles.
document$.subscribe(function () {
  var wrap = document.querySelector(".md-sidebar--primary .md-sidebar__scrollwrap");
  if (!wrap) return;
  // let Material finish its layout/auto-scroll, then pin to top
  requestAnimationFrame(function () {
    requestAnimationFrame(function () { wrap.scrollTop = 0; });
  });
});
