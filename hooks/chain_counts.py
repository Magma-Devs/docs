"""Fill chain counts into pages from the chain catalog at build time.

Pages write placeholders instead of numbers:

    {{ chains.total }}    every chain in the catalog
    {{ chains.mainnet }}  chains that have a mainnet
    {{ chains.testnet }}  chains that have a testnet

The numbers come from docs/javascripts/chains-data.js, the same list the chains
explorer shows, so a page can never disagree with the explorer. Adding a chain
to that file updates every page on the next build.

This hook must run before llms_full.py (see `hooks:` in mkdocs.yml) so the
LLM corpus and the per-page Markdown twins get numbers, not placeholders.
"""

import json
import os
import re

_PLACEHOLDER = re.compile(r"\{\{\s*chains\.(total|mainnet|testnet)\s*\}\}")
_COUNTS = {}


def _load(config):
    path = os.path.join(config["docs_dir"], "javascripts", "chains-data.js")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    chains = json.loads(text[text.index("["): text.rindex("]") + 1])
    return {
        "total": len(chains),
        "mainnet": sum(1 for c in chains if c.get("main")),
        "testnet": sum(1 for c in chains if c.get("test")),
    }


def _fill(text):
    return _PLACEHOLDER.sub(lambda m: str(_COUNTS[m.group(1)]), text)


def on_config(config):
    _COUNTS.clear()
    _COUNTS.update(_load(config))
    return config


def on_page_markdown(markdown, *, page, config, files):
    for key in ("title", "description"):
        if isinstance(page.meta.get(key), str):
            page.meta[key] = _fill(page.meta[key])
    return _fill(markdown)


def on_post_build(*, config):
    # llms.txt is copied as a static file, so it is filled after the build.
    path = os.path.join(config["site_dir"], "llms.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_fill(text))
