/* Site-wide "managed solution" nudge.
   Appears a few seconds after the first page load, then follows the reader
   across every docs page until they dismiss it. Dismissal is remembered. */
(function () {
  var DISMISS_KEY = "sr-managed-dismissed";   // persists across sessions
  var SEEN_KEY = "sr-managed-seen";           // per-tab: skip the delay after first appearance
  var DELAY_MS = 4000;

  function dismissed() {
    try { return localStorage.getItem(DISMISS_KEY) === "1"; } catch (e) { return false; }
  }
  function markDismissed() {
    try { localStorage.setItem(DISMISS_KEY, "1"); } catch (e) {}
  }
  function seenThisSession() {
    try { return sessionStorage.getItem(SEEN_KEY) === "1"; } catch (e) { return false; }
  }
  function markSeen() {
    try { sessionStorage.setItem(SEEN_KEY, "1"); } catch (e) {}
  }

  function build() {
    if (document.querySelector(".sr-managed-popup")) return;

    var el = document.createElement("aside");
    el.className = "sr-managed-popup";
    el.setAttribute("role", "complementary");
    el.setAttribute("aria-label", "Managed Smart Router");
    el.innerHTML =
      '<button class="sr-managed-close" aria-label="Dismiss">&times;</button>' +
      '<p class="sr-managed-title">Looking for a managed solution?</p>' +
      '<p class="sr-managed-body">These docs cover the self-hosted Smart Router. ' +
      "If you'd rather not operate it yourself, we'll run it for you.</p>" +
      '<a class="sr-managed-cta" href="https://magmadevs.com/contact" target="_blank" rel="noopener">Talk to us &rarr;</a>';

    el.querySelector(".sr-managed-close").addEventListener("click", function () {
      el.classList.remove("is-visible");
      markDismissed();
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 260);
    });

    document.body.appendChild(el);
    // force reflow so the transition runs
    void el.offsetWidth;
    el.classList.add("is-visible");
    markSeen();
  }

  function init() {
    if (dismissed()) return;
    if (seenThisSession()) {
      build();           // already shown earlier this session — appear right away
    } else {
      setTimeout(build, DELAY_MS);
    }
  }

  // The cookie-consent card owns the bottom-right corner and must be answered
  // first. While it's unresolved, hold the managed nudge back so the two don't
  // stack; re-arm once the visitor accepts/rejects.
  //
  // Material stores the decision in localStorage — NOT a cookie — under a
  // path-scoped key like "/.__consent" (base path + ".__consent"). Rather than
  // hardcode the base, treat consent as resolved when any "*.__consent" key
  // holds a value. This is what survives base-path changes and Material's
  // internals; checking `!el.hidden` alone races the un-hide on load.
  function consentResolved() {
    try {
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (k && /__consent$/.test(k) && localStorage.getItem(k)) return true;
      }
    } catch (e) {
      return true; // storage unavailable — don't block the nudge indefinitely
    }
    return false;
  }
  function consentPending() {
    var el = document.getElementById("__consent");
    if (!el) return false;                 // consent not configured — nothing to wait on
    return !consentResolved();             // wait until a choice is recorded
  }

  function start() {
    if (dismissed()) return;

    // Consent already answered on a clean load — show via the normal path.
    if (!consentPending()) { init(); return; }

    // Consent still open. Wait for the choice, but DON'T build the instant it
    // resolves: Material reacts to accept/reject by calling location.reload(),
    // which would wipe a just-built popup (the "flash then gone"). Instead, once
    // resolved, wait a short grace period — if the reload comes, this whole
    // script is torn down and the fresh load's `init()` shows the popup cleanly;
    // if no reload comes (e.g. reject with no analytics), we build after the
    // grace period so the nudge still appears.
    var iv = setInterval(function () {
      if (!consentPending()) {
        clearInterval(iv);
        setTimeout(function () {
          if (!document.querySelector(".sr-managed-popup")) init();
        }, 1200);
      }
    }, 300);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
