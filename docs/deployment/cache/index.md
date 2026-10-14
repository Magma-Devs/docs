---
title: "Cache"
description: "Deploy the standalone, block-aware cache that answers repeat reads and can be shared by several router replicas."
---

# Cache

The cache is an optional in-memory (RAM) server that stores RPC responses, so a repeat
read does not hit an upstream node twice. Use it to cut **cost** (fewer billed upstream
calls) and **tail latency** (a hit returns immediately).

Repeat reads include finalised-block calls, archive lookups and contract-state reads. The
cache does more than any other single change to lower both cost and tail latency.

It is the **same `smartrouter` binary**, run as a separate process with the `cache`
subcommand. One cache can be shared by many router instances.

## Pick a backend

The sidecar on this page is the default. It needs no extra infrastructure. Two other
options change *where* entries live, or *how many* places the router looks:

| Option | What it gives you |
| --- | --- |
| **Cache sidecar** (this page) | In-memory, per process. Shared by many routers over gRPC. No external dependency. |
| **[Redis / Valkey backend](redis.md)** | The router runs the same cache engine in-process against a RESP-compatible store. The cache survives restarts, is shared by every replica, and can fail over or replicate across regions. Replaces the sidecar. |
| **[Secondary cache](secondary.md)** | A second cache that the router only ever **reads**. The router checks it when the primary misses, before it goes to your upstreams. Usually another zone's cache. Works in addition to the primary, whichever backend that is. |

The last two options are independent of each other. A router can read a secondary tier
whether its primary is the sidecar or a RESP backend.

## How the router finds it

The router finds the cache through `cache-be:` **in the config file**, not through a flag:

```yaml
# in your config.yml
cache-be: "cache:20100"
```

!!! warning "Don't pass `--cache-be` when the address is in the config"
    If you pass the `--cache-be` flag, even with an empty value, it overrides the YAML
    `cache-be:` in the config loader. So passing it can silently turn caching off. Set
    the address in **one** place. The config file is the recommended place.

## Run it

=== "Docker Compose"

    The cache comes as a Compose overlay. Use a `*_cached.yml` config (it declares
    `cache-be: cache:20100`) and add the cache compose file on top:

    ```bash
    SR_CONFIG=config/smartrouter_examples/smartrouter_eth_cached.yml \
      docker compose -f docker/docker-compose.yml \
                     -f docker/docker-compose.cache.yml up --build
    ```

    See [Docker Compose → Add the cache](../docker-compose.md#add-the-cache).

=== "Local binary"

    The cache address is a **positional** argument:

    ```bash
    smartrouter cache 127.0.0.1:20100 --metrics_address 127.0.0.1:5555
    ```

    Then set `cache-be: "127.0.0.1:20100"` in the router's config.

## What's actually cached

Each entry is keyed by **(chain, API interface, method, params, resolved block)**. The
JSON-RPC `id` is removed before keying and put back in the response, so the same query
with different ids shares one entry. The cache stores:

- **Read responses tied to a specific block.** Most of the cache's value comes from these.
  A call against a block at or beyond the chain's finalization distance is **finalised**:
  the answer never changes, so the cache can keep it for a long time. These calls benefit
  most: `eth_getBlockByNumber`, `eth_getTransactionReceipt`, `eth_getLogs` over a
  finalised range, `eth_call`/`eth_getBalance` at a fixed block, and their
  REST/Tendermint/Cosmos equivalents.
- **"Latest"-style reads** (non-finalised). These are cached only briefly, because the
  answer changes as the chain advances. A longer non-finalised TTL means fewer upstream
  calls but older "latest" data. This is the main trade-off when you tune the cache.
- **Block hash → height mappings.** Small, long-lived lookups that the router reuses to
  resolve block references.
- **Finalised node errors.** A deterministic error on a finalised block can also be cached
  (briefly), so a known-bad query is not sent again to every node.

What is **not** cached: writes (`eth_sendRawTransaction` and similar), pending/`latest`
mutable state beyond its short TTL, and anything a client marks with
[`lava-force-cache-refresh`](../../api/directives.md#force-a-cache-refresh). Each chain's
[spec](../../reference/chains/specs.md) categories decide which methods can be cached at
all. It is not a setting on the cache.

The cache lookup is skipped in exactly three cases: a stateful (write) method, a request
carrying `lava-force-cache-refresh`, and a request running
[cross-validation](../../configuration/failover/cross-validation.md), which needs fresh
answers from several nodes to compare.

!!! warning "Pinning a node does not bypass the cache"
    [`lava-select-provider`](../../api/directives.md#pin-to-a-specific-node) is a
    *selection* preference, and the cache is checked before selection runs. So a pinned
    request that hits a warm entry returns `Lava-Provider-Address: Cached` without
    contacting the named node. That response cannot tell you whether the node is
    reachable. Monitoring checks and any test that asserts on a specific node must also
    send `lava-force-cache-refresh`, or use a request the cache cannot answer.

## Tuning flags

Flags for `smartrouter cache <host:port>`:

| Flag | Default | Purpose |
| --- | --- | --- |
| `--metrics_address` | `disabled` | Prometheus metrics address (e.g. `0.0.0.0:5555`). |
| `--max-items` | `2147483648` | Maximum number of entries to keep. |
| `--expiration` | `1h` | TTL for finalised entries. |
| `--expiration-non-finalized` | `500ms` | TTL for non-finalised ("latest") entries. |
| `--expiration-multiplier` | `1.0` | Multiplier on the finalised TTL (`1.2` = 20% longer). |
| `--expiration-non-finalized-multiplier` | `1.0` | Multiplier on the non-finalised TTL. |
| `--expiration-blocks-hashes-to-heights` | `48h` | TTL for block-hash→height mappings. |
| `--expiration-finalized-node-errors` | `250ms` | TTL for cached finalised node errors. |
| `--log_level` | `info` | Cache log level. |

The cache also accepts the same `--pyroscope-*` [profiling](../../reference/profiling.md)
flags as the router.

## Sharing state across routers

When several router instances share one cache, add `--shared-state` to the routers. They
then also share three things through the cache:

- **consumer-consistency state**: their "seen block" views stay aligned, so a client
  that just read block N from one replica is not served N-1 by another;
- **chain-tracker poll observations**: each replica publishes the upstream polls it
  makes and reuses fresh ones from the others. Every upstream is then polled about once
  per interval across the fleet, instead of once per replica. This is what stops the
  router's own polling load from growing with the replica count;
- **sticky sessions**: a `lava-stickiness` id resolves to the same upstream on every
  replica. Without the flag, stickiness stays local to each pod.

The seen-block state and sticky sessions work through either backend. The chain-tracker
gate is a sidecar RPC, so it needs `cache-be:`. A router on the
[RESP backend](redis.md#caveats) polls locally and logs a warning.

See the [CLI reference](../../reference/cli.md#cache-shared-state) for the safety floors.
To confirm it is working, check
[`rpc_endpoint_tracker_gate_skips_total`](../../reference/metrics.md#endpoint-scoped-rpc_endpoint_).

## Observability

The cache exposes Prometheus metrics on its `--metrics_address` (e.g. `:5555`):

```bash
curl -s http://localhost:5555/metrics | grep cache_total_hits
```

The router reports its own view on `:7779`: `smartrouter_cache_requests_total`,
`_success_total`, `_failed_total`, and `_latency_milliseconds`. Each one is labelled with
the `cache_tier` that answered (`primary` or [`secondary`](secondary.md)). See the
[Metrics reference](../../reference/metrics.md#cache).
