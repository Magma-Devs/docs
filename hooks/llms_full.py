"""
MkDocs hook: generate `llms-full.txt` at build time.

`llms.txt` (hand-maintained in docs/) is the *index* — a curated map of the
docs with one-line descriptions. `llms-full.txt` is the *corpus* — the full
Markdown body of every page concatenated in nav order, which is what LLM
crawlers (ChatGPT, Claude, Perplexity) ingest to answer questions about Smart
Router accurately.

We derive it from the rendered page set so it never drifts from the real docs:
on `on_page_markdown` we capture each page's source Markdown; on
`on_post_build` we write them out in nav order to site/llms-full.txt.

Wired via `hooks:` in mkdocs.yml. No manual upkeep.
"""

from __future__ import annotations

import os

# path -> (title, markdown). Populated during the page pass, drained at post-build.
_PAGES: dict[str, tuple[str, str]] = {}
# src_uris in nav order, captured at on_nav (the only hook with the resolved tree).
_NAV_ORDER: list[str] = []


def on_nav(nav, *, config, files):
    """Capture nav order while the resolved Navigation object is available."""
    _NAV_ORDER.clear()

    def walk(items):
        for item in items:
            if item.is_page and item.file is not None:
                _NAV_ORDER.append(item.file.src_uri)
            elif item.is_section:
                walk(item.children)

    walk(nav.items)
    return nav


def on_page_markdown(markdown, *, page, config, files):
    # Capture the raw Markdown (front-matter already stripped by MkDocs).
    _PAGES[page.file.src_uri] = (page.title or page.file.src_uri, markdown)
    return markdown


def on_post_build(*, config):
    site_dir = config["site_dir"]
    site_url = (config.get("site_url") or "").rstrip("/")
    site_name = config.get("site_name", "Smart Router")
    site_desc = config.get("site_description", "")

    # Order pages by nav (captured at on_nav); append any captured pages not in
    # nav (defensive — e.g. pages reachable but not listed).
    ordered: list[str] = []
    seen: set[str] = set()

    for uri in _NAV_ORDER:
        if uri in _PAGES and uri not in seen:
            ordered.append(uri)
            seen.add(uri)
    for uri in _PAGES:
        if uri not in seen:
            ordered.append(uri)
            seen.add(uri)

    lines: list[str] = []
    lines.append(f"# {site_name} — Full Documentation")
    lines.append("")
    if site_desc:
        lines.append(f"> {site_desc}")
        lines.append("")
    lines.append(
        "This file is the full text of the Smart Router documentation, "
        "concatenated for LLM ingestion. The curated index lives at "
        f"{site_url}/llms.txt."
    )
    lines.append("")

    for uri in ordered:
        title, md = _PAGES[uri]
        page_url = f"{site_url}/{uri[:-3].rstrip('/')}/" if uri.endswith(".md") else f"{site_url}/{uri}"
        page_url = page_url.replace("/index/", "/")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(f"# {title}")
        lines.append("")
        lines.append(f"Source: {page_url}")
        lines.append("")
        lines.append(md.strip())
        lines.append("")

    out_path = os.path.join(site_dir, "llms-full.txt")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")

    # MkDocs skips dot-directories in docs/, so docs/.well-known/ is not copied
    # to the build. Copy it through explicitly so /.well-known/security.txt
    # (RFC 9116) is served.
    docs_dir = config["docs_dir"]
    src_well_known = os.path.join(docs_dir, ".well-known")
    if os.path.isdir(src_well_known):
        dst_well_known = os.path.join(site_dir, ".well-known")
        os.makedirs(dst_well_known, exist_ok=True)
        for name in os.listdir(src_well_known):
            src = os.path.join(src_well_known, name)
            if os.path.isfile(src):
                with open(src, "rb") as rf, open(os.path.join(dst_well_known, name), "wb") as wf:
                    wf.write(rf.read())

    _PAGES.clear()
    _NAV_ORDER.clear()
