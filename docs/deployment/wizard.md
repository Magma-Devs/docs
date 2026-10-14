---
title: "Config wizard"
description: "Run `make wizard`, an interactive TUI that picks chains, collects upstreams, health-checks them, writes the config, and brings up the stack in one pass."
---

# Config wizard

The wizard is the fastest way to a running Smart Router. It is an interactive terminal
app that takes you from *"which chains?"* to a **health-verified, running** router in
one pass.

On the way, it picks chains, collects upstreams, validates every endpoint, writes the
config, and brings up the local Docker stack. It builds the same `config/local/<name>.yml`
you would otherwise write by hand, so you can switch to editing YAML directly at any
point. See [Configuration](../configuration/index.md).

## Run it

From the repo root:

```bash
make wizard
```

This builds the `smartrouter` binary first, because the wizard needs it for its health
checks. Then it starts the TUI. Other targets:

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
    runtime. None of this is vendored. An offline run falls back to the chains in the
    bundled `specs/` directory and plain family glyphs.

## The flow

Press `Esc` anywhere in the flow to step back exactly one prompt.

1. **Chains**: a multi-select picker over the live lava-specs catalog, with one tab per
   family (**EVM · Cosmos · BTC · Other-L1 · Specialty**) and fuzzy search. Keys:
   `tab` switches family, `/` filters, `space` toggles, `a` toggles all, `s` switches
   the spec source (local vs. remote), `enter` confirms.
2. **Interfaces**: if a chain exposes more than one (`jsonrpc` / `rest` / `grpc` /
   `tendermintrpc`), pick which ones to serve. Listener ports are assigned automatically,
   starting at `3360`.
3. **Endpoints**: collected per chain as a **round**. One backend supplies a URL (plus
   optional auth and websocket) across the chain's interfaces. Then you **name the
   backend once**. Each interface is written as its own node named `<base>-<iface>`.
    - **Skippable interfaces**: leave a URL blank to skip just that interface, so a
      backend can serve only some of its chain's interfaces.
    - **Websockets before addons**: `jsonrpc` upstreams collect a paired `wss://` url
      (ETH1-derived specs require it). The wizard asks about the websocket first, because
      the result of the `archive` addon probe depends on it.
    - **Live verification**: the wizard checks every upstream, websocket, and explicitly
      chosen addon with `smartrouter health` against a temporary config. This way, a
      green result in the wizard matches what the router will do at boot.
    - **Auth**: optional, per backend. Secrets are stored as `${VAR}` (see [Secrets](#secrets)).
4. **Backups · Cache · Dashboard**: each is an optional step. Backups populate the
   `backup-direct-rpc` tier (same round model). Cache adds the `smartrouter cache`
   sidecar. Dashboard adds the Prometheus + dashboard overlay.
5. **Save**: writes the config to `config/local/` and lints it. Then it runs a full
   `health <config>` check over the whole config (every node, node-url, websocket,
   and addon) **before** anything starts.
6. **Run → Smoke**: prints render / `up` / teardown commands you can copy and paste.
   If you choose, it runs `docker compose up --build`, then smoke-tests each localhost
   listener. The `up` command adds a generated `<name>.compose.override.yml` that
   publishes exactly the ports your listeners bind. The base compose keeps its
   example ports (3360–3362), and your ports are added on top.

When the dashboard is enabled, the run output prints its access details: UI at
<http://localhost:3000> (login `admin` / `password`), API on `:8000`, Prometheus on `:9090`.

## Which specs the router loads (`SR_SPEC`)

The wizard sets `SR_SPEC` for you, based on where its catalog came from. The base
compose passes it to the router as `--use-static-spec ${SR_SPEC:-specs/}`:

| `SR_SPEC` | Meaning |
| --- | --- |
| `specs/` *(default)* | The lava-specs snapshot **bundled into the image**: the chains in the repo's `specs/` directory. |
| `https://github.com/Magma-Devs/lava-specs/tree/main` | The **live lava-specs repo**. It resolves every chain in the catalog, including ones not bundled (e.g. `LAV1`). It is fetched and cached at startup. |

You can override `SR_SPEC` by hand on any `docker compose … up`. The router accepts a
local directory or a GitHub/GitLab URL, the same as the [`--use-static-spec` flag](../reference/cli.md#specs).

## Secrets

Auth values are never stored in the YAML. They're written as `${VAR}` placeholders into a
gitignored `.env` and rendered via `envsubst` into the router-readable `*.yml` at run
time. Generated configs go to `config/local/` (gitignored) by default, because the
rendered endpoint URL contains the full API key. Treat that URL as a bearer credential.

## Chain icons

On terminals that support inline images, the wizard shows real rasterized chain logos
(fetched from the docs site, rasterized in pure Go):

- **Kitty graphics protocol** - Kitty, Ghostty, recent WezTerm.
- **iTerm2** inline images.
- **Sixel** - as a side-panel preview.
- All other terminals fall back to per-family glyphs (◆ ⚛ ₿ ⬡ ✦).

To force a mode, set `WIZARD_ICONS=glyph|kitty|iterm|sixel`. `off` / `none` also force
glyphs, and so does `NO_COLOR`. `build/sr-wizard --diagnose` prints what your terminal
supports and exits.

## Flags

| Flag | Effect |
| --- | --- |
| `--repo <path>` | Repo root (default: two levels up from the working directory). |
| `--specs <remote\|local\|auto>` | Spec source. If empty, the wizard asks you. |
| `--diagnose` | Print terminal + icon capability and exit. |
| `--last` | Reprint the run command from the most recent run and exit (same as `make wizard-last`). |

The wizard saves the last-run plan to `~/.config/smartrouter-wizard/last-run.json`
(XDG, outside the repo).

## Known limits

- The catalog, taxonomy, and icons come from the network. A fully offline run is limited
  to the chains in the bundled `specs/` and family glyphs.
- A chain that is not in the bundled `specs/` resolves only when `SR_SPEC` points at the
  remote lava-specs repo. The wizard sets this automatically for a remote catalog.
- The wizard writes `cross-validation:` as a documented TODO in the config header.
  Configure it afterwards (see [Cross-validation](../configuration/failover/cross-validation.md)).
