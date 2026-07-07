---
title: "Docker Compose"
description: "Run Smart Router and its dependencies with the bundled Docker Compose stack."
---

# Docker Compose

Run a config you already have (or one copied from the examples) with a single
`docker compose` command. If you don't have a config yet, the [wizard](wizard.md) is the
faster way in.

The repo ships one parameterized compose stack. The base file
(`docker/docker-compose.yml`) runs the **router** against any example config; optional
overlays add the **cache** and the **dashboard**.

## Run the router

```bash
# Default: the Ethereum example, no cache
docker compose -f docker/docker-compose.yml up --build

# Smoke-test it
curl -X POST http://localhost:3360 \
     -H 'content-type: application/json' \
     -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Tear down
docker compose -f docker/docker-compose.yml down
```

Pick a different example with `SR_CONFIG` (any file under `config/smartrouter_examples/`,
or your own under `config/local/`):

```bash
SR_CONFIG=config/smartrouter_examples/smartrouter_multichain.yml \
  docker compose -f docker/docker-compose.yml up --build
```

The compose file publishes the superset of ports the bundled examples use; a config
only binds the listeners it declares, the rest sit idle.

| Port | Chain (index) | Interface | Used by |
| --- | --- | --- | --- |
| `3360` | Ethereum (`ETH1`) | JSON-RPC | eth, multichain |
| `3361` | Solana (`SOLANA`) | JSON-RPC | solana, multichain |
| `3362` | Bitcoin (`BTC`) | JSON-RPC | bitcoin, multichain |
| `3363` | Hyperliquid (`HYPERLIQUID`) | JSON-RPC | hyperliquid, multichain |
| `3364` | Cosmos Hub (`COSMOSHUB`) | REST | cosmos, multichain |
| `3365` | Cosmos Hub (`COSMOSHUB`) | Tendermint RPC | cosmos, multichain |
| `3366` | Cosmos Hub (`COSMOSHUB`) | gRPC | cosmos, multichain |
| `3367` | Aptos (`APT1`) | REST | aptos, multichain |
| `7779` | — | — | router Prometheus metrics |

Single-chain examples (e.g. `smartrouter_solana.yml`) bind their chain on `3360`;
the `multichain` example is the only config that lights up the whole `3360`–`3367`
range at once, one listener per chain/interface as above.

## Environment variables

| Variable | Default | Effect |
| --- | --- | --- |
| `SR_CONFIG` | `config/smartrouter_examples/smartrouter_eth.yml` | Which config the router runs. |
| `SR_SPEC` | `specs/` | Spec source — the bundled snapshot, or a lava-specs GitHub/GitLab URL to resolve any chain (e.g. `LAV1`). See [the wizard's `SR_SPEC` note](wizard.md#which-specs-the-router-loads-sr_spec). |
| `SR_LOG_LEVEL` | `info` | `debug` / `info` / `warn` / `error`. |
| `SR_LOG_FORMAT` | `json` | `json` or `text`. |

## Add the cache

Run a `*_cached.yml` config (which declares `cache-be: cache:20100`) and layer the cache
overlay to start the cache sidecar:

```bash
SR_CONFIG=config/smartrouter_examples/smartrouter_eth_cached.yml \
  docker compose -f docker/docker-compose.yml \
                 -f docker/docker-compose.cache.yml up --build
```

Without the overlay the cache service never starts. Full detail — what's cached, TTLs,
shared state — is on the [Cache](cache.md) page.

## Add the dashboard

The [Smart Router Dashboard](https://github.com/Magma-Devs/smart-router-dashboard) is a
separate repo that ships its own self-contained stack (router + Prometheus + dashboard):

```bash
git clone https://github.com/Magma-Devs/smart-router-dashboard
cd smart-router-dashboard && make up
```

The UI is on <http://localhost:3000>. See the [Dashboard](dashboard.md) page for what it
shows, the full port map, and configuration (auth, values file, logs).

## Confirm it's healthy

The router has no separate "ready" page — a listener is healthy once it answers a real
RPC query, and the metrics server exposes an aggregate health probe. Three checks tell
you the stack came up cleanly:

**1. Overall health probe** — the metrics server answers `200` with `Health status OK`
once startup health checks pass (`503 Unhealthy` otherwise):

```bash
curl -i http://localhost:7779/metrics/overall-health
# HTTP/1.1 200 OK
# ...
# Health status OK
```

**2. Metrics are being scraped** — the Prometheus endpoint returns exposition text, and
`smartrouter_*` series appear once the router has served traffic:

```bash
curl -s http://localhost:7779/metrics | head
```

**3. A real relay succeeds** — send a JSON-RPC request to the chain's listener and get a
non-error result back. For the default Ethereum example on `3360`:

```bash
curl -s -X POST http://localhost:3360 \
     -H 'content-type: application/json' \
     -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

A healthy response is a JSON-RPC result, not an `error` object — the hex value is the
current block height (it advances on each call):

```json
{"jsonrpc":"2.0","id":1,"result":"0x14f8b42"}
```

If you ran the `multichain` example, swap the port and method for the chain you want to
hit — e.g. `3364` for the Cosmos Hub REST listener:

```bash
curl -s http://localhost:3364/cosmos/base/tendermint/v1beta1/blocks/latest
```

A successful relay also carries `Smart-Router-*` response headers naming the upstream
that served it — add `-i` to the `curl` to see them. Persistent `error` responses or
connection refusals mean the listener never came up; check the container logs
(`docker compose -f docker/docker-compose.yml logs router`) for the failing upstream or
config.
