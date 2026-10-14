---
title: "Secondary cache"
description: "On a primary miss, read a second, read-only cache (usually another zone's) before going to upstream nodes, without duplicating node infrastructure."
---

# Secondary cache

The router can read from an optional **secondary cache** when the primary has no answer,
*before* it goes to your upstream nodes. Use it to reuse data that another zone has already
fetched from its nodes.

The secondary is a second cache backend, and the router only ever **reads** it. A hit is
served to the caller and copied into the router's own primary cache. Nothing is ever
written to the secondary.

The typical deployment is zone-segregated. An external-zone router reads the internal
(trusted) zone's cache on a miss, and reuses data that zone already fetched from its nodes.
The result is fewer redundant upstream calls, no duplicated node infrastructure, and a
strictly one-way, read-only relationship between zones.

## How it works

```
request ──► primary cache ──hit──► served ("Cached")
                │ miss / down
                ▼
            secondary cache ──hit──► served ("Cached") + copied into primary
                │ miss / down / timeout
                ▼
            upstream nodes (normal routing)
```

- **Read-only.** The router has no write or flush path to the secondary, for responses or
  for admin operations. The router holds it behind a read-only interface that exposes only
  "is it up?" and "get an entry", so writes cannot be reached at all. As the operator, you
  must still make sure the secondary *endpoint* is reachable only read-only across zones
  (network policy, directionality).
- **Best effort.** A secondary that is slow, down, or unreachable never affects request
  serving. A configurable timeout limits the lookup, any error counts as a miss, and the
  request goes on to your upstreams. The router reconnects in the background, exactly as it
  does for the primary.
- **Backfill.** After a secondary hit, the entry is written into the router's *own*
  primary. The same eligibility rules apply as for upstream responses: cached node errors
  and error statuses are served, but never re-written as successes. The next identical
  request hits the primary directly. So for an explicit-block query, the router checks the
  secondary once per entry, not once per request.
- **Node errors are labelled the same from either tier.** A cached node error is served
  with the `lava-identified-node-error` response header, exactly like a live one. A
  replayed error is never mistaken for a success, and the caller sees the same thing
  whichever cache answered.
- **Independent of the primary.** The secondary keeps serving while the primary is down.
  It is also valid with no primary configured at all: reads work, nothing backfills, and
  the router logs an advisory warning for that topology.

Any backend that speaks the Smart Router cache protocol works as either tier. The
secondary is just a second cache address. Run the same cache engine on both tiers. Pairing
*different* engines across the two tiers is not a supported configuration.

## What crosses the zone boundary

Every entry that comes in from the secondary is copied and stripped before it is served or
backfilled. This matters because cache entries carry data that identifies where they came
from: the upstream's response headers plus the writer's signatures. Only the stripped copy
is used, so nothing unsanitised can reach your primary either.

| Field | What happens |
| --- | --- |
| `Sig`, `SigBlocks` | Dropped entirely. |
| `Metadata` (upstream response headers) | Reduced to an **allowlist**: `Content-Type` and `Content-Encoding`. Everything else is removed, including header names this router does not know. It is an allowlist, not a denylist, because upstream response headers are an open set that no denylist can be proven to cover. |
| `LatestBlock` | Dropped. The router stamps its *own* tracked tip in its place. |
| Block-hash→height mappings | Not requested from the secondary, so there is nothing to strip. The lookup asks for none. |

So the caller sees the response body, its content type, and the router's own locally
created headers (`Lava-Provider-Address: Cached`, the GUID, `Provider-Latest-Block`). This
is the same header set that a primary-cache hit produces.

The last two rows stop your router from adopting another zone's view of the chain. If left
as-is, a foreign `LatestBlock` would publish that zone's chain head into your cache. It
would become the block that `latest`, `safe`, `finalized`, and `pending` resolve to, for
the whole chain, and it could not be lowered until it expired. Foreign hash→height
mappings would cause the same problem in a different way. Those heights raise the
effective requested block (which gates endpoint sync and optimiser selection) and decide
archive routing. The two tiers' values are combined max-for-latest / min-for-earliest, so
the more extreme value always wins, and a foreign tier would always beat your own primary.
That is why the secondary lookup never asks for them. Hash-keyed archive detection uses
only your primary's mappings, or none in a secondary-only topology, exactly as on a router
with no cache configured.

## What happens in each situation

| Situation | What the router does | How you see it |
| --- | --- | --- |
| **Primary misses, secondary has it** | Serves the secondary's answer, then copies it into the primary. No upstream call. | `Lava-Provider-Address: Cached`; `smartrouter_cache_success_total{cache_tier="secondary"}` increments |
| **Both tiers miss** | Goes to your upstream nodes, exactly as it would without the tier. The only cost is the one extra lookup, limited by the timeout. | `smartrouter_cache_failed_total{cache_tier="secondary",outcome="miss"}` increments; the response carries a real upstream address |
| **Secondary is down, slow, or unreachable** | Skips the tier and goes to upstreams. Reconnects in the background. Serving is unaffected. | `outcome="error"` or `outcome="timeout"`; latency stays inside `secondary-cache-timeout` |
| **No secondary configured** (the default) | Same as previous releases. Nothing is added to the request path. | No `cache_tier="secondary"` series exist at all |

## Configuration

One setting turns it on. The others have defaults.

=== "Config file"

    ```yaml
    cache-be: "cache-internal:20100"
    secondary-cache-be: "cache-shared.other-zone:20100"
    secondary-cache-timeout: 100ms      # optional
    secondary-cache-mode: read-only     # optional (the default and only mode)
    ```

=== "Flags"

    ```bash
    smartrouter config.yml --cache-be "cache-internal:20100" \
      --secondary-cache-be "cache-shared.other-zone:20100"
    ```

    A flag you pass explicitly overrides the YAML value. Environment variables are not read.

=== "Docker Compose"

    Add the secondary overlay on top of the cache overlay, and use a config that declares
    both addresses:

    ```bash
    SR_CONFIG=config/smartrouter_examples/smartrouter_eth_two_tier.yml \
      docker compose -f docker/docker-compose.yml \
                     -f docker/docker-compose.cache.yml \
                     -f docker/docker-compose.secondary-cache.yml up --build
    ```

    Both compose caches start empty. To see a real secondary *hit*, you need a second
    writer to warm the shared cache.

| Setting | Default | Meaning |
| --- | --- | --- |
| `secondary-cache-be` | *(unset - disabled)* | Secondary cache address, in the same `host:port` form as `cache-be`. |
| `secondary-cache-timeout` | `50ms` | Time budget per lookup. A lookup that goes over it counts as a miss, and the request falls through. Raise it for cross-zone network hops. |
| `secondary-cache-mode` | `read-only` | Access mode. `read-only` is the only supported value. |

The router fails fast on misconfiguration. A zero or negative timeout, or `read-write`
mode, each abort startup with a specific error. The router warns but still starts when the
secondary equals the primary address, when a secondary is configured with no primary, or
when tuning options are set with no address (below). When the secondary is enabled, the
startup log prints its full configuration on one line.

!!! note "Tuning options with no address are a warning, not a failure"
    If you set `secondary-cache-timeout` while `secondary-cache-be` is empty, the router
    starts with the secondary disabled and logs a warning. This setup is usually a typo.
    But it is also what a single templated YAML looks like across a fleet where only some
    routers run a secondary. Failing startup there would turn an unused key into an outage
    on every router that does not run one.

If you remove the configuration, the router goes back fully to single-cache behaviour.

## Observability

Cache metrics are split per tier by the `cache_tier` label (`primary` | `secondary`):

```bash
curl -s http://<router>:7779/metrics | grep smartrouter_cache_success_total
# … cache_tier="primary" - served from the router's own cache
# … cache_tier="secondary" - rescued from the secondary
```

Non-hits are classified in `smartrouter_cache_failed_total` by `outcome`: `miss` (not
found), `error` (transport or server error), or `timeout` (budget exceeded). So you can
tell a broken or slow secondary from a cold one right away. Lookup latency is recorded per
tier on every attempt, including hits. See the
[Metrics reference](../../reference/metrics.md#cache) for the full series and the dashboard
migration note.

With [tracing](../../reference/traces.md) enabled, each lookup is a span that carries
`cache.tier` and `cache.outcome`. The request's root span records which tier served it.

The tier also logs its decisions, with one line at startup and one per lookup:

```bash
grep -i 'secondary cache' <router log>
# INF secondary cache configured  address=cache-shared.other-zone:20100 mode=read-only timeout=100ms
# DBG secondary cache lookup produced no hit  requestedBlockForCache=…
# DBG secondary cache hit  chainId=ETH1 isNodeError=false requestedBlock=18000000
```

The per-lookup lines are `DBG`, so they need `--log-level debug`. The startup line is `INF`
and always appears when a secondary is configured.

!!! tip "The response headers don't name the tier"
    Both tiers answer with the same locally created header set and the same body bytes.
    So `Lava-Provider-Address: Cached` alone cannot tell you which tier served the
    response. Use the `cache_tier` counter to tell them apart.

## Limits

These are out of scope on purpose. The router rejects them at startup instead of silently
ignoring them:

- **Read-write secondary mode.** `secondary-cache-mode` accepts only `read-only`.
  `read-write` aborts startup with an explicit "reserved for a future iteration" error. The
  setting exists so that read-only is an explicit choice in your config that you can
  audit, not an implicit default.

## See also

- [Cache](index.md) - what's cached, TTLs, and the default sidecar.
- [Redis / Valkey backend](redis.md) - a persistent, shared primary; works with this tier.
- [Metrics](../../reference/metrics.md#cache) - the per-tier `smartrouter_cache_*` series.
