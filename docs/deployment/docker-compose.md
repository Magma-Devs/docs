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

| Port | Used by |
| --- | --- |
| `3360` | ETH1 JSON-RPC (eth, multichain) |
| `3361` | Arbitrum JSON-RPC (multichain) |
| `3362` | Base JSON-RPC (multichain) |
| `7779` | router Prometheus metrics |

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

A second overlay brings up Prometheus plus the dashboard UI (prebuilt GHCR images):

```bash
docker compose -f docker/docker-compose.dashboard.yml up
```

The UI is on <http://localhost:3000> (login `admin` / `password`). See the
[Dashboard](dashboard.md) page for what it shows, the full port map, and changing the
credentials.
