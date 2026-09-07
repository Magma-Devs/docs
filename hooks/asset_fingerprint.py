"""
MkDocs hook: fingerprint the repo's own scripts and stylesheets.

Every local entry in `extra_javascript` / `extra_css` is rewritten at build
time to carry a content hash — `javascripts/chains-data.js` becomes
`javascripts/chains-data.js?v=3f9c1a2b7e`. A changed file is therefore a new
URL, and an unchanged file keeps the URL it had.

Why: docs.magmadevs.com is served through Cloudflare, which caches static
assets at the edge for hours and does not know when a deploy happened. With
bare paths the first visit after a deploy pins whatever the origin held at
that moment for the rest of the TTL, and a follow-up deploy is invisible until
it expires — a broken chains-data.js shipped that way once and its fix, six
minutes later, stayed hidden for hours. Cloudflare's default cache key
includes the query string, so a new hash is a cache miss by construction.

Material's own bundles are already content-hashed; this covers only what this
repo ships. External URLs (a scheme or a leading `//`) and paths that do not
resolve under docs_dir are left untouched.

Wired via `hooks:` in mkdocs.yml. No manual upkeep.
"""

from __future__ import annotations

import hashlib
import logging
import os
from urllib.parse import urlsplit

log = logging.getLogger("mkdocs.hooks.asset_fingerprint")

# Ten hex chars of SHA-256: unique enough for a handful of files, short enough
# to read in a URL.
_HASH_LEN = 10


def _digest(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()[:_HASH_LEN]


def _fingerprint(raw: str, docs_dir: str) -> str | None:
    """Return `raw` with `?v=<hash>` appended, or None to leave it alone."""
    parsed = urlsplit(raw)
    if parsed.scheme or parsed.netloc or raw.startswith("//"):
        return None  # external — not ours to version
    if parsed.query or parsed.fragment:
        return None  # already carries a version (or something deliberate)
    local = os.path.join(docs_dir, *parsed.path.split("/"))
    if not os.path.isfile(local):
        return None  # MkDocs will report it, if it reports anything
    return f"{raw}?v={_digest(local)}"


def on_config(config):
    docs_dir = config["docs_dir"]
    stamped: list[str] = []

    for i, path in enumerate(config["extra_css"]):
        new = _fingerprint(path, docs_dir)
        if new is not None:
            config["extra_css"][i] = new
            stamped.append(new)

    for i, script in enumerate(config["extra_javascript"]):
        # A plain YAML entry is still a str here; a mapping entry (`path:` +
        # `type:`/`defer:`) is an ExtraScriptValue whose `.path` is the URL.
        if isinstance(script, str):
            new = _fingerprint(script, docs_dir)
            if new is not None:
                config["extra_javascript"][i] = new
                stamped.append(new)
        else:
            new = _fingerprint(script.path, docs_dir)
            if new is not None:
                script.path = new
                stamped.append(new)

    log.info("Fingerprinted %d local asset URL(s)", len(stamped))
    for s in stamped:
        log.debug("  %s", s)
    return config
