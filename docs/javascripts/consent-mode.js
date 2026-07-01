/*
 * Google Consent Mode v2 — accept-side updater.
 *
 * main.html initialises gtag with `consent: default` = all denied (cookieless
 * modeled pings). This script watches the Material cookie-consent state and,
 * once the visitor accepts the `analytics` category, calls `consent: update`
 * to grant analytics_storage so GA4 switches from modeled to full measurement.
 *
 * Material stores consent in the `__consent` cookie and exposes __md_get().
 * We poll briefly after load (the banner sets the cookie asynchronously on
 * click) and also re-check on the Material instant-navigation event so an
 * accept on one page grants on the next.
 */
(function () {
  function analyticsGranted() {
    try {
      var c = window.__md_get && window.__md_get("__consent");
      return !!(c && c.analytics);
    } catch (e) {
      return false;
    }
  }

  var granted = false;
  function grantIfConsented() {
    if (granted || !analyticsGranted()) return;
    granted = true;
    if (typeof window.gtag === "function") {
      window.gtag("consent", "update", {
        ad_storage: "granted",
        ad_user_data: "granted",
        ad_personalization: "granted",
        analytics_storage: "granted",
      });
    }
  }

  // Initial check + short poll to catch the click that sets the cookie.
  grantIfConsented();
  var ticks = 0;
  var iv = setInterval(function () {
    grantIfConsented();
    if (granted || ++ticks > 40) clearInterval(iv); // ~10s max
  }, 250);

  // Material instant loading re-runs scripts per navigation; also subscribe to
  // its document$ observable when available so a later accept is picked up.
  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(grantIfConsented);
  }
})();
