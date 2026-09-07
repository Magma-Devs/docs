# Magma Devs Documentation

Documentation site for [Smart Router](https://github.com/Magma-Devs/smart-router) — the centralised
RPC routing gateway with QoS-based selection, caching, and failover policies.

Built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/). All content lives under
[`docs/`](docs/); the site is configured in [`mkdocs.yml`](mkdocs.yml).

## Preview locally

```bash
pip install -r requirements.txt
mkdocs serve            # http://127.0.0.1:8000
```

## Build

```bash
mkdocs build --strict   # output in site/ (gitignored); --strict fails on broken links
```

## Asset URLs are fingerprinted

`hooks/asset_fingerprint.py` rewrites every local `extra_css` / `extra_javascript` entry at
build time to `<path>?v=<sha256 prefix>` of the file's content. The site sits behind
Cloudflare, whose edge caches static assets for hours without knowing when a deploy
happened; a content hash makes a changed file a new URL, so a deploy is visible on the first
request. Nothing to maintain — add the bare path to `mkdocs.yml` and the hook stamps it.

## Deployment

Pushing to `main` triggers [`.github/workflows/docs.yml`](.github/workflows/docs.yml), which builds the
site and publishes it to GitHub Pages at <https://magma-devs.github.io/docs/>.

> One-time setup: in the repo's **Settings → Pages → Build and deployment**, set **Source** to
> **"GitHub Actions"** for the deploy job to publish.
