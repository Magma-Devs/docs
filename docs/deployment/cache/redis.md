---
title: "Redis / Valkey backend"
description: "Run the Smart Router cache against a RESP-compatible backend — Redis, Valkey, ElastiCache, or MemoryDB — for a cache that persists, is shared by every replica, and follows Sentinel or Cluster failover."
---

# Redis / Valkey backend

The router can run its cache against any **RESP-compatible backend** — Redis, Valkey, and
managed services such as AWS ElastiCache or MemoryDB — instead of the default
[cache sidecar](index.md). The router executes the same cache engine in-process, so lookup
rules, validity checks, and TTLs are identical to the sidecar's; only the storage changes.

Parity is structural rather than reimplemented: the cache semantics live in one
storage-agnostic engine that both the sidecar and this backend execute, over an in-memory
store and a Redis/Valkey adapter respectively. The router consumes both through one
interface, so no call site can tell them apart.

## When to use it

The sidecar holds cache state in memory, per process. Reach for a RESP backend when that
costs you something concrete:

- **Persistence** — the cache survives router and cache restarts; no re-warming from your
  upstream nodes.
- **Shared state** — every router replica reads and writes the same cache, so horizontal
  scaling stops costing hit rate.
- **High availability** — Sentinel or Cluster failover is handled by the backend and
  followed transparently by the router.
- **Multi-region replication** — with infrastructure such as ElastiCache Global Datastore,
  entries cached in one region serve reads in others; the router only needs the
  [read/write endpoint split](#multi-region-reads-readwrite-split).

The goal is resource efficiency — fewer calls to (and fewer copies of) your node
infrastructure. Latency wins are a side effect.

## Quick start

=== "Config file"

    The full surface lives in the `resp-cache:` block:

    ```yaml
    # in your config.yml
    resp-cache:
      addresses: ["my-valkey:6379"]
    ```

=== "Flag"

    One flag against an existing backend:

    ```bash
    smartrouter config.yml --resp-cache-addresses "my-valkey:6379"
    ```

    An explicitly-passed flag outranks the YAML value. Only `--resp-cache-addresses` and
    `--resp-cache-topology` exist as flags; everything else is config-file only.

=== "Docker Compose"

    The `resp-cache` overlay starts a Valkey next to the router. Pair it with a config
    that declares the `resp-cache:` block:

    ```bash
    SR_CONFIG=config/smartrouter_examples/smartrouter_eth_resp_cache.yml \
      docker compose -f docker/docker-compose.yml \
                     -f docker/docker-compose.resp-cache.yml up --build
    ```

!!! warning "Setting any `resp-cache` option without `addresses` is rejected at startup"
    A block (or flag) that configures TLS, credentials, or a topology but no addresses is
    dangling configuration, and so is every invalid combination in the table below. The
    router refuses to start rather than run half-configured with caching silently off.

## Configuration reference

| Key | Default | Meaning |
| --- | --- | --- |
| `topology` | `standalone` | `standalone`, `sentinel`, or `cluster`. |
| `addresses` | — (required) | Standalone: the node address. Sentinel: the **sentinel** addresses. Cluster: the **configuration endpoint** used as a discovery seed — never a node list; the client discovers topology itself. |
| `read-addresses` | *(unset)* | Optional separate endpoint(s) for **reads**. Writes stay on `addresses`. Selects an *endpoint*, not a replica role — see [Multi-region reads](#multi-region-reads-readwrite-split). |
| `master-name` | — | Sentinel only (required there): the monitored master set name. |
| `username` / `password` | *(unset)* | Static data-node credentials (AUTH / ACL). |
| `password-file` | *(unset)* | Rotation-capable credentials — see [Credential rotation](#credential-rotation). Mutually exclusive with `password`. |
| `credential-refresh-interval` | `10s` | Poll cadence for `password-file`. |
| `sentinel-username` / `sentinel-password` / `sentinel-password-file` | *(unset)* | **Sentinel control-plane** credentials. Sentinels authenticate independently of the data nodes; hardened deployments fail discovery without these. Only valid with `topology: sentinel`, and read once at startup (rotating them needs a restart). |
| `db` | `0` | Logical database (standalone/sentinel only; rejected for cluster). |
| `key-prefix` | `sr` | Namespace for every key. Restricted to `[A-Za-z0-9._-]+` — flush uses it as a `SCAN MATCH` glob. Give each deployment sharing a backend its own prefix. |
| `tls.enabled` | `false` | TLS to the backend. |
| `tls.ca-file` | *(system pool)* | PEM CA bundle for server verification. |
| `tls.cert-file` / `tls.key-file` | *(unset)* | Client keypair for mTLS (both or neither). |
| `tls.server-name` | *(unset)* | Overrides the verification / SNI name. |
| `tls.insecure-skip-verify` | `false` | Skips server verification. Testing only. |
| `dial-timeout` | `500ms` | Bounds a fresh connection's dial and TLS handshake, together with the caller's own deadline — whichever is sooner. Deliberately sub-second so a black-holed backend can't make cold lookups linger. |
| `read-timeout` / `write-timeout` | client defaults | Per-operation network limits. |
| `pool-size` | client default | Connection pool size, per client (the read client has its own). |

TTLs are the cache engine's own — finalised entries ~1h, non-finalised scaled to the
chain's block time, short-lived node errors — the same policy the
[sidecar](index.md#tuning-flags) applies.

!!! note "No environment expansion"
    Values in this block are read literally. A `${VAR}` written here is the string
    `${VAR}`, not the variable's value. Environment variables are not read for
    `resp-cache` at all.

## Topologies

=== "Standalone"

    One address. Also the shape for managed *primary / reader endpoints*
    (cluster-mode-disabled):

    ```yaml
    resp-cache:
      addresses: ["cache.internal:6379"]
    ```

=== "Sentinel"

    Automatic failover. The router connects to the sentinels, discovers the primary, and
    follows promotions transparently — no restart, no manual intervention. Note the two
    independent credential domains:

    ```yaml
    resp-cache:
      topology: sentinel
      addresses: ["sentinel-1:26379", "sentinel-2:26379", "sentinel-3:26379"]
      master-name: "mymaster"
      password-file: /etc/smartrouter/resp-cache.pw           # data nodes
      sentinel-password-file: /etc/smartrouter/resp-sentinel.pw  # the sentinels
    ```

    Supplying only the data-node credential is the common misconfiguration — a hardened
    sentinel set fails *discovery*, before any data node is reached.

=== "Cluster"

    Sharded. Point at the **configuration endpoint**; node membership, slots, and replicas
    are discovered and tracked automatically:

    ```yaml
    resp-cache:
      topology: cluster
      addresses: ["my-cluster.cfg.euw1.cache.amazonaws.com:6379"]
    ```

## Multi-region reads (read/write split)

With replicating infrastructure (ElastiCache Global Datastore, MemoryDB Multi-Region), give
routers in secondary regions their local reader endpoint:

```yaml
resp-cache:
  addresses: ["primary.global.cache:6379"]        # writes
  read-addresses: ["reader.eu-west-1.cache:6379"] # reads
```

Reads go to `read-addresses`; writes — including cache population and flush — to
`addresses`. Replication lag is safe by construction: an entry that hasn't replicated yet
is a plain cache miss, and the router's block-freshness validation runs on every hit, so a
lagging replica can never serve data older than what the client has already seen.

!!! warning "This selects an endpoint, not a replica role"
    Under `standalone` the addresses are dialled exactly as given, so a managed reader
    endpoint really does serve the reads — that is the shape this feature is for.

    Under `sentinel` and `cluster` the read client runs its **own discovery** from the
    seeds you give it and resolves to the master(s) of whatever topology they front, so
    pointing it at replicas of the *same* deployment routes your reads straight back to the
    primary. It is still meaningful pointed at a **separate replicated deployment**, which
    is why the router logs a warning rather than rejecting the config. Replica reads within
    one sentinel set or cluster are not supported; use the managed reader endpoint in
    `standalone` shape.

## Credential rotation

Use `password-file` with whatever refreshes the file — a Kubernetes secret mount, a sidecar
token refresher. The file is polled at `credential-refresh-interval`, and on change the
router pushes the new credentials to every live connection, which re-authenticates **in
place**: no reconnect, no dropped operations.

The file holds the password, or `username:password` to rotate the ACL user too.

!!! warning "A password containing `:` cannot be expressed in a password file"
    The first colon is always the `username:password` separator, so a file holding
    `p@ss:word` authenticates as user `p@ss` with password `word`. That fails closed, but
    it surfaces as an opaque `WRONGPASS` — the router deliberately withholds the server's
    auth reply from logs — so it warns once at startup when the file contains a colon,
    naming only the parsed username. Either avoid `:` in the password, or use the explicit
    `username:password` form deliberately.

Under `topology: sentinel` the underlying client can't stream re-auth to live connections,
so rotated credentials are resolved fresh **per connection attempt** — they apply on
reconnects and failovers rather than being pushed to idle connections. Keep the previous
credential valid for a rotation grace window (standard ACL dual-credential practice) and
rotation is seamless there too. This applies to the **data-node** password under sentinel,
not just `sentinel-password-file`. Because no in-place re-auth is possible there, the
router doesn't run the rotation poller under sentinel at all; it logs once at startup that
rotation applies on reconnect, rather than reporting rotations it can't deliver.

## Sizing and eviction

Recommended: **`volatile-lru`** with a `maxmemory` fitting your working set.

- Every key the router writes carries a TTL, so `volatile-lru` can evict across the
  router's whole keyspace by recency — and it will never touch non-TTL keys owned by other
  applications on a shared backend.
- `allkeys-lru` behaves identically on a dedicated backend, and is the safer choice if you
  ever write non-TTL keys under memory pressure. On a shared backend it can evict other
  tenants' data.
- Avoid `noeviction` for cache workloads: at `maxmemory` the router's cache writes start
  failing (visible in `smartrouter_resp_cache_failed_total`) until TTLs free space — the
  cache keeps serving hits, but stops growing.

Blockchain cache entries skew heavily toward the long finalised TTL, so steady state
approaches `maxmemory` and stays there. That's eviction working as intended, not a leak.

## Failure behaviour and monitoring

A failing backend **never fails requests**: lookups degrade to cache misses within the
relay's budget and requests proceed to your upstreams; writes are best-effort. Recovery is
automatic. Alert on the dedicated series rather than on request errors:

| Series | What it tells you |
| --- | --- |
| `smartrouter_resp_cache_connected` | `0` after a failed health probe (PING, 10s cadence). Reachability transitions are logged too, and an authentication rejection is reported as such rather than as "unreachable" — the credential itself is never logged. |
| `smartrouter_resp_cache_failed_total{op,kind}` | Backend-level operation failures, never clean misses. `kind` splits `error` (unreachable, protocol error) from `timeout` (budget exceeded), so saturation reads differently from an outage. |
| `smartrouter_resp_cache_connection_errors_total` | Failed background health probes. |
| `smartrouter_resp_cache_pool_*_conns` | Pool gauges — total, idle, stale. |

```bash
curl -s http://localhost:7779/metrics | grep smartrouter_resp_cache
```

The shared `smartrouter_cache_*` hit/miss series keep working unchanged. Full reference:
[Metrics → RESP cache backend](../../reference/metrics.md#resp-cache-backend).

A router started with `--debug-relays` adds a `Lava-Cache-Backend` header to cache-served
responses, naming the node that served the hit — the current master under sentinel, the
touched shard under cluster. It's debug-gated because it exposes internal infrastructure
addresses.

## Flush semantics

The router's `/debug/reset-all` flushes the backend **prefix-scoped**: a `SCAN` over
`key-prefix:*` with single-key `UNLINK`s. `FLUSHDB` is never issued, so a shared backend's
other tenants — and other prefixes — are untouched. If two deployments must be
flush-isolated, give them distinct `key-prefix` values.

## Precedence and rollback

Switching backends is a configuration change. The RESP cache starts cold; no data migrates
in either direction.

| Configuration | What serves |
| --- | --- |
| `resp-cache:` set | The RESP backend — **including when `cache-be:` is also set**. The router logs a prominent warning naming the precedence. |
| Both set, then `resp-cache:` removed | The preserved `cache-be:` sidecar takes over on the next start. Nothing is migrated, nothing is destroyed; the RESP data ages out on its own TTLs. |
| Neither set | The default path, exactly as before. The RESP backend is never constructed, so its metrics are **absent** rather than zero. |

Keeping `cache-be:` in place alongside `resp-cache:` is deliberate — it's the rollback
path.

## Caveats

- **The fleet chain-tracker gate isn't carried over.** The per-endpoint gate that lets pods
  borrow each other's successful upstream polls is a sidecar RPC backed by a dedicated
  store on the cache server, not a cache-engine behaviour, so it doesn't travel through the
  key/value seam this backend implements. A router on the RESP backend logs a warning once
  per listen endpoint and **polls locally**. Everything else the sidecar caches — relay
  entries, chain tip, shared-state seen-block, block-hash→height — works identically. If
  you need the peer gate, stay on the sidecar.
- **Sentinel credential rotation** applies per connection attempt, not in place. See
  [Credential rotation](#credential-rotation).
- **`read-addresses` selects an endpoint, not a replica role.** See
  [Multi-region reads](#multi-region-reads-readwrite-split).
- **Cold start.** No data migrates when switching backends, in either direction.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Router won't start: "`resp-cache` options are set without addresses" | A `resp-cache:` block or flag configures options but no `addresses`. Set them, or remove the block. |
| `smartrouter_resp_cache_connected` is `0` | The backend is unreachable, or authentication is being rejected — the log line distinguishes the two. Relays keep succeeding via your upstreams throughout. |
| Sentinel discovery fails with credentials that work on the data nodes | Sentinels authenticate separately. Set `sentinel-password` / `sentinel-password-file`. |
| Only `key-prefix:chaintip:*` keys appear | A `latest`-style query was relayed — those carry a sub-second TTL and expire before you can look. Request a finalised block to see a durable entry. |
| Reads still land on the primary under sentinel/cluster | Expected: `read-addresses` re-discovers and resolves to the master. Use a managed reader endpoint in `standalone` shape. |
| `Lava-Cache-Backend` header missing | Either the response wasn't a cache hit (check `Lava-Provider-Address`), or the router isn't running with `--debug-relays`. |

## See also

- [Cache](index.md) — what's cached, TTLs, and the default sidecar.
- [Secondary cache](secondary.md) — a read-only second tier, usable with either backend.
- [Metrics](../../reference/metrics.md#resp-cache-backend) — the full `smartrouter_resp_cache_*` reference.
