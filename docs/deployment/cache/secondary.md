---
title: "Secondary cache"
description: "Consult a second, read-only cache on a primary miss before falling through to upstream nodes — typically another zone's cache, reused without duplicating node infrastructure."
---

# Secondary cache

The router can read from an optional **secondary cache**: a second cache backend consulted
when the primary has no answer, *before* falling through to your upstream nodes. The router
only ever **reads** it. A hit is served to the caller and copied into the router's own
primary cache; nothing is ever written to the secondary.

The typical deployment is zone-segregated — an external-zone router reads the internal
(trusted) zone's cache on a miss, reusing data that zone already fetched from its nodes.
Fewer redundant upstream calls, no duplicated node infrastructure, and a strictly one-way,
read-only relationship between zones.

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

- **Read-only.** The router has no write or flush path to the secondary — not for
  responses, not for admin operations. It's held behind a read-only interface exposing only
  "is it up?" and "get an entry", so writes aren't merely unused, they're unreachable.
  Enforcing that the secondary *endpoint* is reachable read-only across zones (network
  policy, directionality) is still yours as the operator.
- **Best effort.** A secondary that is slow, down, or unreachable never affects request
  serving: the lookup is bounded by a configurable timeout, any error counts as a miss, and
  the request proceeds to your upstreams. The router reconnects in the background, exactly
  like the primary.
- **Backfill.** After a secondary hit, the entry is written into the router's *own* primary
  under the same eligibility rules applied to upstream responses — cached node errors and
  error statuses are served but never re-written as successes. The next identical request
  hits the primary directly, so for an explicit-block query the secondary is consulted once
  per entry, not per request.
- **Node errors are labelled the same from either tier.** A cached node error is served
  with the `lava-identified-node-error` response header, exactly as a live one is — a
  replayed error is never mistaken for a success, and which cache answered makes no
  difference to what the caller sees.
- **Independent of the primary.** The secondary keeps serving while the primary is down,
  and is valid with no primary configured at all: reads work, nothing backfills, and the
  router logs an advisory warning for that topology.

Any backend that speaks the Smart Router cache protocol works as either tier — the
secondary is simply a second cache address. Run the same cache engine on both; pairing
*different* engines across the two tiers is not a supported configuration.

## What crosses the zone boundary

Cache entries carry data identifying where they came from — the upstream's response headers
plus the writer's signatures. Every entry crossing in from the secondary is copied and
stripped before it is served or backfilled, and the stripped copy is the only copy used, so
nothing unsanitised can reach your primary either.

| Field | What happens |
| --- | --- |
| `Sig`, `SigBlocks` | Dropped entirely. |
| `Metadata` (upstream response headers) | Reduced to an **allowlist** — `Content-Type` and `Content-Encoding`. Everything else goes, including header names this router has never heard of. An allowlist rather than a denylist, because upstream response headers are an open set no denylist can be proven to cover. |
| `LatestBlock` | Dropped, and the router re-stamps its *own* tracked tip in its place. |
| Block-hash→height mappings | Never requested from the secondary at all. |

The caller therefore sees the response body, its content type, and the router's own locally
minted headers (`Lava-Provider-Address: Cached`, the GUID, `Provider-Latest-Block`) — the
same header set a primary-cache hit produces.

The last two rows are about not adopting another zone's view of the chain. Left as-is, a
foreign `LatestBlock` would publish that zone's chain head into your cache as the block
`latest`, `safe`, `finalized`, and `pending` resolve to — chain-wide, and unlowerable until
it expires. Foreign hash→height mappings would do the same by a different route: those
heights raise the effective requested block (gating endpoint sync and optimiser selection)
and decide archive routing, and the two tiers' values are folded max-for-latest /
min-for-earliest, so the more extreme value always wins and a foreign tier would beat your
own primary by construction. Hash-keyed archive detection therefore uses your primary's
mappings alone — or none in a secondary-only topology, exactly as on a router with no cache
configured.

## What happens in each situation

| Situation | What the router does | How you see it |
| --- | --- | --- |
| **Primary misses, secondary has it** | Serves the secondary's answer, then copies it into the primary. No upstream call. | `Lava-Provider-Address: Cached`; `smartrouter_cache_success_total{cache_tier="secondary"}` increments |
| **Both tiers miss** | Falls through to your upstream nodes exactly as without the tier. The only cost is the one extra lookup, bounded by the timeout. | `smartrouter_cache_failed_total{cache_tier="secondary",outcome="miss"}` increments; the response carries a real upstream address |
| **Secondary is down, slow, or unreachable** | Skips the tier and goes to upstreams. Reconnects in the background. Serving is unaffected. | `outcome="error"` or `outcome="timeout"`; latency stays inside `secondary-cache-timeout` |
| **No secondary configured** (the default) | Identical to previous releases. Nothing is added to the request path. | No `cache_tier="secondary"` series exist at all |

## Configuration

One setting enables it; the rest have defaults.

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

    An explicitly-passed flag overrides the YAML value. Environment variables are not read.

=== "Docker Compose"

    Layer the secondary overlay on top of the cache one, with a config declaring both
    addresses:

    ```bash
    SR_CONFIG=config/smartrouter_examples/smartrouter_eth_two_tier.yml \
      docker compose -f docker/docker-compose.yml \
                     -f docker/docker-compose.cache.yml \
                     -f docker/docker-compose.secondary-cache.yml up --build
    ```

    Both compose caches start empty, so demonstrating an actual secondary *hit* needs a
    second writer warming the shared cache.

| Setting | Default | Meaning |
| --- | --- | --- |
| `secondary-cache-be` | *(unset — disabled)* | Secondary cache address; same formats as `cache-be` (`host:port` or `unix:` socket). |
| `secondary-cache-timeout` | `50ms` | Per-lookup budget. An exceeded lookup counts as a miss and the request falls through. Raise it for cross-zone network hops. |
| `secondary-cache-mode` | `read-only` | Access mode. `read-only` is the only supported value. |

The router fails fast on misconfiguration: a timeout or mode set *without* an address, a
zero or negative timeout, or `read-write` mode each abort startup with a specific error. It
warns but starts when the secondary equals the primary address, or when a secondary is
configured with no primary. When enabled, the startup log prints the full secondary
configuration on one line.

!!! note "Tuning options with no address are a warning, not a failure"
    Setting `secondary-cache-timeout` while `secondary-cache-be` is empty starts the router
    with the secondary disabled and logs a warning. That shape is usually a typo — but it's
    also what a single templated YAML looks like across a fleet where only some routers run
    a secondary, and failing startup there would turn an unused key into an outage on every
    router that doesn't.

Removing the configuration fully reverts the router to single-cache behaviour.

## Observability

Cache metrics are split per tier via the `cache_tier` label (`primary` | `secondary`):

```bash
curl -s http://<router>:7779/metrics | grep smartrouter_cache_success_total
# … cache_tier="primary"    — served from the router's own cache
# … cache_tier="secondary"  — rescued from the secondary
```

Non-hits are classified in `smartrouter_cache_failed_total` by `outcome`: `miss` (not
found), `error` (transport or server error), or `timeout` (budget exceeded) — so a broken
or slow secondary is immediately distinguishable from a cold one. Lookup latency is
recorded per tier on every attempt, hits included. See the
[Metrics reference](../../reference/metrics.md#cache) for the full series and the dashboard
migration note.

With [tracing](../../reference/traces.md) enabled, each lookup is a span carrying
`cache.tier` and `cache.outcome`, and the request's root span records which tier served it.

The tier also logs its decisions — one line at startup and one per lookup:

```bash
grep -i 'secondary cache' <router log>
# INF secondary cache configured  address=cache-shared.other-zone:20100 mode=read-only timeout=100ms
# DBG secondary cache lookup produced no hit  requestedBlockForCache=…
# DBG secondary cache hit  chainId=ETH1 isNodeError=false requestedBlock=18000000
```

The per-lookup lines are `DBG`, so they need `--log-level debug`. The startup line is `INF`
and always appears when a secondary is configured.

!!! tip "The response headers don't name the tier"
    Both tiers answer with the same locally minted header set and the same body bytes, so
    `Lava-Provider-Address: Cached` alone can't tell you which one served. The `cache_tier`
    counter is what distinguishes them.

## Limits

Deliberately out of scope, and rejected at startup rather than silently ignored:

- **Read-write secondary mode.** `secondary-cache-mode` accepts only `read-only`;
  `read-write` aborts startup with an explicit "reserved for a future iteration" error. The
  setting exists so that read-only is an explicit, auditable choice in your config rather
  than an implicit default.

## See also

- [Cache](index.md) — what's cached, TTLs, and the default sidecar.
- [Redis / Valkey backend](redis.md) — a persistent, shared primary; works with this tier.
- [Metrics](../../reference/metrics.md#cache) — the per-tier `smartrouter_cache_*` series.
