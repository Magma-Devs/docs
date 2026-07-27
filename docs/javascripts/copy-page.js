// "Copy page" button (Mintlify-style) injected next to each page's H1.
// Copies the page's Markdown twin (URL minus trailing slash + .md — emitted by
// hooks/llms_full.py) so readers can paste a clean page into an LLM, plus a
// dropdown to view the raw Markdown or open the page in ChatGPT / Claude.
// Re-runs on every instant-nav load; no-ops if the button is already present.
document$.subscribe(function () {
  var article = document.querySelector(".md-content article");
  var h1 = article && article.querySelector("h1");
  if (!article || !h1) return;
  if (article.querySelector(".mdx-copy-page")) return; // already added

  // Directory-style URL -> Markdown twin: trailing slash becomes .md;
  // the site root serves at /index.md.
  var mdPath = location.pathname.replace(/\/+$/, "");
  mdPath = mdPath === "" ? "/index.md" : mdPath + ".md";
  // Clipboard copy fetches same-origin (works on any host, incl. local
  // builds); the share links use the canonical public URL so ChatGPT/Claude
  // can actually reach the page.
  var fetchUrl = location.origin + mdPath;
  var canonical = document.querySelector('link[rel="canonical"]');
  var mdUrl = canonical ? new URL(mdPath, canonical.href).href : fetchUrl;

  var askPrompt = encodeURIComponent("Read " + mdUrl + " so I can ask questions about this documentation page.");

  var wrap = document.createElement("div");
  wrap.className = "mdx-copy-page";
  wrap.innerHTML =
    '<button type="button" class="mdx-copy-page__btn" title="Copy this page as Markdown for use with LLMs">' +
      '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>' +
      '<span>Copy page</span>' +
    "</button>" +
    '<button type="button" class="mdx-copy-page__caret" aria-haspopup="true" aria-expanded="false" title="More LLM options">' +
      '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M7.41 8.59 12 13.17l4.59-4.58L18 10l-6 6-6-6z"/></svg>' +
    "</button>" +
    '<div class="mdx-copy-page__menu" hidden>' +
      '<a href="' + mdUrl + '" target="_blank" rel="noopener">View as Markdown</a>' +
      '<a href="https://chatgpt.com/?hints=search&q=' + askPrompt + '" target="_blank" rel="noopener">Open in ChatGPT</a>' +
      '<a href="https://claude.ai/new?q=' + askPrompt + '" target="_blank" rel="noopener">Open in Claude</a>' +
    "</div>";

  h1.parentNode.insertBefore(wrap, h1);

  var btn = wrap.querySelector(".mdx-copy-page__btn");
  var label = btn.querySelector("span");
  var caret = wrap.querySelector(".mdx-copy-page__caret");
  var menu = wrap.querySelector(".mdx-copy-page__menu");

  // Async Clipboard API first; hidden-textarea execCommand fallback for
  // contexts where the clipboard-write permission is denied.
  function copyText(text) {
    return navigator.clipboard.writeText(text).catch(function () {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      var ok = document.execCommand("copy");
      document.body.removeChild(ta);
      if (!ok) throw new Error("copy failed");
    });
  }

  btn.addEventListener("click", function () {
    fetch(fetchUrl)
      .then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.text();
      })
      .then(copyText)
      .then(function () {
        label.textContent = "Copied";
        btn.classList.add("mdx-copy-page__btn--done");
        setTimeout(function () {
          label.textContent = "Copy page";
          btn.classList.remove("mdx-copy-page__btn--done");
        }, 2000);
      })
      .catch(function () {
        // Clipboard blocked or twin missing — fall back to showing the raw file.
        window.open(mdUrl, "_blank", "noopener");
      });
  });

  // Safety net: ChatGPT/Claude drop the ?q= prompt when they bounce the
  // visitor through login. Copy the prompt on click so it can be pasted.
  var promptText = "Read " + mdUrl + " so I can ask questions about this documentation page.";
  menu.querySelectorAll('a[href*="chatgpt.com"], a[href*="claude.ai"]').forEach(function (a) {
    a.addEventListener("click", function () {
      copyText(promptText).catch(function () {});
    });
  });

  caret.addEventListener("click", function (e) {
    e.stopPropagation();
    var open = !menu.hidden;
    menu.hidden = open;
    caret.setAttribute("aria-expanded", String(!open));
  });
  document.addEventListener("click", function () {
    if (!menu.hidden) {
      menu.hidden = true;
      caret.setAttribute("aria-expanded", "false");
    }
  });
});
