# Cache

The cache is an optional in-memory (RAM) server that stores RPC responses so repeat
reads — finalised-block calls, archive lookups, contract-state reads — don't hit an
upstream node twice. It's the single biggest lever on both **cost** (fewer billed
upstream calls) and **tail latency** (a hit returns immediately).

It's the **same `smartrouter` binary**, run as a separate process via the `cache`
subcommand. One cache can be shared by many router instances.

## How the router finds it

The router connects to the cache through `cache-be:` **in the config file**, not a flag:

```yaml
# in your config.yml
cache-be: "cache:20100"
```

!!! warning "Don't pass `--cache-be` when the address is in the config"
    An explicitly-passed `--cache-be` flag (even empty) outranks the YAML `cache-be:` in
    the config loader — so passing it can silently disable caching. Set it in **one**
    place; the config is the recommended one.

## Run it

=== "Docker Compose"

    The cache ships as an overlay. Use a `*_cached.yml` config (which declares
    `cache-be: cache:20100`) and layer the cache compose file:

    ```bash
    SR_CONFIG=config/smartrouter_examples/smartrouter_eth_cached.yml \
      docker compose -f docker/docker-compose.yml \
                     -f docker/docker-compose.cache.yml up --build
    ```

    See [Docker Compose → Add the cache](docker-compose.md#add-the-cache).

=== "Local binary"

    The cache address is **positional**:

    ```bash
    smartrouter cache 127.0.0.1:20100 --metrics_address 127.0.0.1:5555
    ```

    Then set `cache-be: "127.0.0.1:20100"` in the router's config.

## What's actually cached

An entry is keyed by **(chain, API interface, method, params, resolved block)** — the
JSON-RPC `id` is stripped before keying and restored on the way out, so the same query
with different ids shares one entry. What gets stored:

- **Read responses tied to a specific block** — the bulk of cache value. A call against a
  block at or beyond the chain's finalization distance is **finalised**: immutable, so it
  can be held for a long time. `eth_getBlockByNumber`, `eth_getTransactionReceipt`,
  `eth_getLogs` over a finalised range, `eth_call`/`eth_getBalance` at a fixed block, and
  their REST/Tendermint/Cosmos equivalents are the sweet spot.
- **"Latest"-style reads** (non-finalised) — cached only briefly, because the answer
  changes as the chain advances. A longer non-finalised TTL means fewer upstream calls but
  staler "latest" data — that's the main tuning trade-off.
- **Block hash → height mappings** — small, long-lived lookups the router reuses to
  resolve block references.
- **Finalised node errors** — a deterministic error on a finalised block is itself
  cacheable (briefly), so a known-bad query isn't re-sent to every node.

What is **not** cached: writes (`eth_sendRawTransaction` and the like), pending/`latest`
mutable state beyond its short TTL, and anything a client marks
[`lava-force-cache-refresh`](../api/directives.md#force-a-cache-refresh). Which methods
are cacheable at all comes from each chain's [spec](../reference/chains/specs.md)
categories, not a setting on the cache.

## Tuning flags

Flags for `smartrouter cache <host:port>`:

| Flag | Default | Purpose |
| --- | --- | --- |
| `--metrics_address` | `disabled` | Prometheus metrics address (e.g. `0.0.0.0:5555`). |
| `--max-items` | `2147483648` | Max number of entries to keep. |
| `--expiration` | `1h` | TTL for finalised entries. |
| `--expiration-non-finalized` | `500ms` | TTL for non-finalised ("latest") entries. |
| `--expiration-multiplier` | `1.0` | Multiplier on the finalised TTL (`1.2` = 20% longer). |
| `--expiration-non-finalized-multiplier` | `1.0` | Multiplier on the non-finalised TTL. |
| `--expiration-blocks-hashes-to-heights` | `48h` | TTL for block-hash→height mappings. |
| `--expiration-finalized-node-errors` | `250ms` | TTL for cached finalised node errors. |
| `--log_level` | `info` | Cache log level. |

The cache also accepts the same `--pyroscope-*` [profiling](../reference/profiling.md)
flags as the router.

## Sharing state across routers

When several router instances share one cache, add `--shared-state` to the routers so
they also share consumer-consistency state through it — keeping their "seen block" views
aligned. See the [CLI reference](../reference/cli.md#cache-shared-state).

## Observability

The cache exposes Prometheus metrics on its `--metrics_address` (e.g. `:5555`):

```bash
curl -s http://localhost:5555/metrics | grep cache_total_hits
```
