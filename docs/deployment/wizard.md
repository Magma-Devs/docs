---
title: "Config wizard"
description: "Run `make wizard`, an interactive TUI that picks chains, collects upstreams, health-checks them, writes the config, and brings up the stack in one pass."
---

# Config wizard

The fastest way to a running Smart Router. The wizard is an interactive terminal
app that walks you from *"which chains?"* to a **health-verified, running** router in
one pass — picking chains, collecting upstreams, validating every endpoint, writing
the config, and bringing up the local Docker stack.

It builds the same `config/local/<name>.yml` you'd otherwise write by hand, so you can
graduate to editing YAML directly at any point — see [Configuration](../configuration/index.md).

## Run it

From the repo root:

```bash
make wizard
```

This builds the `smartrouter` binary first (the wizard needs it for its health
checks), then launches the TUI. Other targets:

| Command | What it does |
| --- | --- |
| `make wizard` | Build the router, then launch the wizard. |
| `make wizard-last` | Reprint the run command from your most recent wizard run (no build, no TUI). |
| `make wizard-build` | Build the wizard binary to `build/sr-wizard` without launching. |
| `make wizard-test` | Run the wizard's (non-TUI) Go tests. |

You can also run it directly: `cd tools/wizard && go run . --repo /path/to/smart-router`.

!!! note "Network access"
    The wizard fetches the chain catalog, family taxonomy, and icons from the live
    [`lava-specs`](https://github.com/Magma-Devs/lava-specs) repo and the docs site at
    runtime — nothing is vendored. An offline run falls back to the chains in the
    bundled `specs/` directory and plain family glyphs.

## The flow

`Esc` steps back exactly one prompt anywhere in the flow.

1. **Chains** — a family-tabbed (**EVM · Cosmos · BTC · Other-L1 · Specialty**),
   fuzzy-searchable, multi-select picker over the live lava-specs catalog. Keys:
   `tab` switches family, `/` filters, `space` toggles, `a` toggles all, `s` switches
   the spec source (local vs. remote), `enter` confirms.
2. **Interfaces** — for chains that expose more than one (`jsonrpc` / `rest` / `grpc` /
   `tendermintrpc`), pick which to serve. Listener ports are auto-assigned from `3360`.
3. **Endpoints** — collected per chain as a **round**: one backend supplies a URL (plus
   optional auth and websocket) across the chain's interfaces, then you **name the
   backend once**. Each interface is emitted as its own node named `<base>-<iface>`.
    - **Skippable interfaces** — leave a URL blank to skip just that interface, so a
      backend can serve a subset of its chain's interfaces.
    - **Websockets before addons** — `jsonrpc` upstreams collect a paired `wss://` url
      (ETH1-derived specs require it). The websocket choice comes first because the
      `archive` addon probe's verdict depends on it.
    - **Live verification** — every upstream, websocket, and explicitly chosen addon is
      checked with `smartrouter health` against a throwaway config, so the wizard's
      green verdict matches what the router will do at boot.
    - **Auth** — optional per backend; secrets are stored as `${VAR}` (see [Secrets](#secrets)).
4. **Backups · Cache · Dashboard** — each an optional step. Backups populate the
   `backup-direct-rpc` tier (same round model). Cache adds the `smartrouter cache`
   sidecar. Dashboard adds the Prometheus + dashboard overlay.
5. **Save** — writes the config to `config/local/`, lints it, then runs a full
   `health <config>` pass over the whole thing (every node, node-url, websocket,
   and addon) **before** anything starts.
6. **Run → Smoke** — prints copy-pasteable render / `up` / teardown commands,
   optionally runs `docker compose up --build`, then smoke-tests each localhost
   listener. The `up` command layers a generated `<name>.compose.override.yml` that
   publishes exactly the ports your listeners bind, so the base compose keeps its
   example ports (3360–3362) and yours are added on top.

When the dashboard is enabled, the run output prints its access details: UI at
<http://localhost:3000> (login `admin` / `password`), API on `:8000`, Prometheus on `:9090`.

## Which specs the router loads (`SR_SPEC`)

The base compose passes `--use-static-spec ${SR_SPEC:-specs/}`. The wizard sets
`SR_SPEC` for you based on where its catalog came from:

| `SR_SPEC` | Meaning |
| --- | --- |
| `specs/` *(default)* | The lava-specs snapshot **bundled into the image** — the chains in the repo's `specs/` directory. |
| `https://github.com/Magma-Devs/lava-specs/tree/main` | The **live lava-specs repo** — resolves every chain in the catalog, including ones not bundled (e.g. `LAV1`). Fetched and cached at startup. |

You can override `SR_SPEC` by hand on any `docker compose … up`; the router accepts a
local directory or a GitHub/GitLab URL, same as the [`--use-static-spec` flag](../reference/cli.md#specs).

## Secrets

Auth values never land in the YAML. They're written as `${VAR}` placeholders into a
gitignored `.env` and rendered via `envsubst` into the router-readable `*.yml` at run
time. Generated configs default to `config/local/` (gitignored) because the rendered
endpoint URL embeds the full API key — treat it as a bearer credential.

## Chain icons

On terminals that support inline images the wizard shows real rasterized chain logos
(fetched from the docs site, rasterized in pure Go):

- **Kitty graphics protocol** — Kitty, Ghostty, recent WezTerm.
- **iTerm2** inline images.
- **Sixel** — as a side-panel preview.
- Everything else falls back to per-family glyphs (◆ ⚛ ₿ ⬡ ✦).

Force a mode with `WIZARD_ICONS=glyph|kitty|iterm|sixel` (`off` / `none` also force
glyphs; `NO_COLOR` does the same). Run `build/sr-wizard --diagnose` to print what your
terminal supports and exit.

## Flags

| Flag | Effect |
| --- | --- |
| `--repo <path>` | Repo root (default: two levels up from the working directory). |
| `--specs <remote\|local\|auto>` | Spec source. Empty = ask interactively. |
| `--diagnose` | Print terminal + icon capability and exit. |
| `--last` | Reprint the run command from the most recent run and exit (same as `make wizard-last`). |

The last-run plan is persisted to `~/.config/smartrouter-wizard/last-run.json` (XDG,
outside the repo).

## Known limits

- Catalog, taxonomy, and icons come from the network; a fully offline run is limited to
  the chains in the bundled `specs/` and family glyphs.
- A chain not in the bundled `specs/` only resolves when `SR_SPEC` points at the remote
  lava-specs repo — which the wizard sets automatically for a remote catalog.
- `cross-validation:` is emitted as a documented TODO in the config header; configure it
  afterwards (see [Cross-validation](../configuration/failover/cross-validation.md)).
