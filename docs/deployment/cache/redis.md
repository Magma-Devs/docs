---
title: "Redis / Valkey backend"
description: "Use a RESP-compatible cache backend (Redis, Valkey, ElastiCache, MemoryDB) that persists, is shared by every replica, and follows Sentinel or Cluster failover."
---

# Redis / Valkey backend

The router can run its cache against any **RESP-compatible backend** instead of the default
[cache sidecar](index.md). Use it when you need a cache that survives restarts, is shared by
every replica, and follows backend failover.

RESP-compatible backends include Redis, Valkey, and managed services such as AWS
ElastiCache or MemoryDB. The router runs the same cache engine in-process, so lookup rules,
validity checks, and TTLs are identical to the sidecar's. Only the storage changes.

The two behave the same because they share code, not because the logic was written twice.
The cache logic lives in one storage-agnostic engine. The sidecar runs it over an
in-memory store, and this backend runs it over a Redis/Valkey adapter. The router uses both
through one interface, so no call site can tell them apart.

## When to use it

Use a RESP backend when the sidecar's in-memory, per-process cache state costs you
something concrete:

- **Persistence.** The cache survives router and cache restarts, so it does not need to
  re-warm from your upstream nodes.
- **Shared state.** Every router replica reads and writes the same cache, so adding
  replicas no longer lowers the hit rate.
- **High availability.** The backend handles Sentinel or Cluster failover, and the router
  follows it transparently.
- **Multi-region replication.** With infrastructure such as ElastiCache Global Datastore,
  entries cached in one region serve reads in other regions. The router only needs the
  [read/write endpoint split](#multi-region-reads-readwrite-split).

The goal is resource efficiency: fewer calls to (and fewer copies of) your node
infrastructure. Lower latency is a side effect.

## Quick start

=== "Config file"

    All options go in the `resp-cache:` block:

    ```yaml
    # in your config.yml
    resp-cache:
      addresses: ["my-valkey:6379"]
    ```

=== "Flag"

    To point at an existing backend, one flag is enough:

    ```bash
    smartrouter config.yml --resp-cache-addresses "my-valkey:6379"
    ```

    A flag you pass explicitly overrides the YAML value. Only `--resp-cache-addresses` and
    `--resp-cache-topology` exist as flags. Every other option is config-file only.

=== "Docker Compose"

    The `resp-cache` overlay starts a Valkey instance next to the router. Use it with a
    config that declares the `resp-cache:` block:

    ```bash
    SR_CONFIG=config/smartrouter_examples/smartrouter_eth_resp_cache.yml \
      docker compose -f docker/docker-compose.yml \
                     -f docker/docker-compose.resp-cache.yml up --build
    ```

!!! warning "Setting any `resp-cache` option without `addresses` is rejected at startup"
    The router refuses to start rather than run half-configured with caching silently off.
    This applies to a block (or flag) that configures TLS, credentials, or a topology but
    no addresses. It also applies to every invalid combination in the table below.

## Configuration reference

| Key | Default | Meaning |
| --- | --- | --- |
| `topology` | `standalone` | `standalone`, `sentinel`, or `cluster`. |
| `addresses` | - (required) | Standalone: the node address, exactly one: a longer list stops the router at startup. Sentinel: the **sentinel** addresses. Cluster: the **configuration endpoint**, used as a discovery seed. Never a node list: the client discovers the topology itself. |
| `read-addresses` | *(unset)* | Optional separate endpoint(s) for **reads**. Writes stay on `addresses`. Selects an *endpoint*, not a replica role. See [Multi-region reads](#multi-region-reads-readwrite-split). |
| `master-name` | - | Sentinel only (required there): the monitored master set name. |
| `username` / `password` | *(unset)* | Static data-node credentials (AUTH / ACL). |
| `password-file` | *(unset)* | Credentials that can be rotated. See [Credential rotation](#credential-rotation). Cannot be used together with `password`. |
| `credential-refresh-interval` | `10s` | How often `password-file` is polled. |
| `sentinel-username` / `sentinel-password` / `sentinel-password-file` | *(unset)* | **Sentinel control-plane** credentials. Sentinels authenticate separately from the data nodes, and hardened deployments fail discovery without these. Only valid with `topology: sentinel`. Read once at startup (rotating them needs a restart). |
| `db` | `0` | Logical database (standalone/sentinel only; rejected for cluster). |
| `key-prefix` | `sr` | Namespace for every key. Restricted to `[A-Za-z0-9._-]+`, because flush uses it as a `SCAN MATCH` glob. Give each deployment that shares a backend its own prefix. |
| `tls.enabled` | `false` | TLS to the backend. It must be `true` whenever another `tls.*` key is set: a `tls` block without it stops the router at startup, rather than send credentials in plain text. |
| `tls.ca-file` | *(system pool)* | PEM CA bundle for server verification. |
| `tls.cert-file` / `tls.key-file` | *(unset)* | Client keypair for mTLS (both or neither). |
| `tls.server-name` | *(unset)* | Overrides the verification / SNI name. |
| `tls.insecure-skip-verify` | `false` | Skips server verification. Testing only. |
| `dial-timeout` | `500ms` | Limits a new connection's dial and TLS handshake. The caller's own deadline also applies, and whichever is sooner wins. Kept sub-second on purpose, so a black-holed backend cannot make cold lookups wait long. Under `topology: sentinel` it also sets how long a Sentinel has to answer. See [Topologies → Sentinel](#topologies). |
| `read-timeout` / `write-timeout` | client defaults | Per-operation network limits. |
| `pool-size` | client default (10 × `GOMAXPROCS`) | Connection pool size, per client (the read client has its own). |
| `expiration.finalized` | `1h` | Lifetime of a finalised answer. The sidecar's `--expiration`. |
| `expiration.finalized-multiplier` | `1` | Multiplier on `expiration.finalized`. The sidecar's `--expiration-multiplier`. |
| `expiration.non-finalized` | `500ms` | Floor of a recent ("latest") answer's lifetime. The lifetime is an eighth of the chain's block time, and never shorter than this floor. The sidecar's `--expiration-non-finalized`. |
| `expiration.non-finalized-multiplier` | `1` | Multiplier on `expiration.non-finalized`. The sidecar's `--expiration-non-finalized-multiplier`. |
| `expiration.node-errors` | `250ms` | Lifetime of a cached node error on a finalised block. The sidecar's `--expiration-finalized-node-errors`. |
| `expiration.blocks-hashes-to-heights` | `48h` | Lifetime of a block-hash→height mapping. The sidecar's `--expiration-blocks-hashes-to-heights`. The router writes no such mappings, so this setting has no effect. |

The cache engine applies the same lifetimes as the [sidecar](index.md#tuning-flags), and
the `expiration` block sets them the way the sidecar's flags do. Every duration needs a
unit (`1h`, `3600s`, `250ms`): a bare number is read as nanoseconds, and a lifetime below
one millisecond stops the router at startup. Without the block, the defaults above apply.
A router does not take its lifetimes from the sidecar's flags, so when you move a router
from the sidecar to this backend, set the block to keep the same tuning.

!!! note "No environment expansion"
    Values in this block are read literally. A `${VAR}` written here is the string
    `${VAR}`, not the variable's value. Environment variables are not read for
    `resp-cache` at all.

## Topologies

=== "Standalone"

    One address. Use this shape for managed *primary / reader endpoints* too
    (cluster-mode-disabled):

    ```yaml
    resp-cache:
      addresses: ["cache.internal:6379"]
    ```

=== "Sentinel"

    Automatic failover. The router connects to the sentinels, discovers the primary, and
    follows promotions transparently, with no restart and no manual intervention. Note the
    two separate sets of credentials:

    ```yaml
    resp-cache:
      topology: sentinel
      addresses: ["sentinel-1:26379", "sentinel-2:26379", "sentinel-3:26379"]
      master-name: "mymaster"
      password-file: /etc/smartrouter/resp-cache.pw           # data nodes
      sentinel-password-file: /etc/smartrouter/resp-sentinel.pw  # the sentinels
    ```

    The common misconfiguration is to supply only the data-node credential. A hardened
    sentinel set then fails *discovery*, before any data node is reached.

    The router asks one sentinel, the one it is attached to, for the primary each time it
    opens a connection. That sentinel has two fifths of `dial-timeout` (200 ms at the
    default) to complete a connection, and the same again to answer each request. A
    sentinel that misses either limit, because its node is gone or its process hangs, is
    left within the same connection attempt. The router asks every sentinel it knows of,
    attaches to the first one that answers, and connects to the primary that one names. The
    cache operation that needed the connection fails, and the next one succeeds. None of
    this depends on `pool-size`.

    A healthy sentinel that is far away is held to the same limit: one that always takes
    longer than two fifths of `dial-timeout` to connect or to answer is never used. With
    sentinels in another region, set `dial-timeout` to at least 2.5 times the slowest
    sentinel's connection time.

    When the primary changes, the attached sentinel announces it, and the router drops its
    connections to the old primary. When that sentinel is lost together with the primary,
    no announcement arrives. Each idle connection to the lost primary then fails the
    operation that picks it up, after that operation's timeout. While the health probe is
    the only traffic (a 3 s timeout, one probe a second), that is about 4 s for each idle
    connection.

=== "Cluster"

    Sharded. Point at the **configuration endpoint**. Node membership, slots, and replicas
    are discovered and tracked automatically:

    ```yaml
    resp-cache:
      topology: cluster
      addresses: ["my-cluster.cfg.euw1.cache.amazonaws.com:6379"]
    ```

## Multi-region reads (read/write split)

With replicating infrastructure (ElastiCache Global Datastore, MemoryDB Multi-Region), give
the routers in secondary regions their local reader endpoint for reads:

```yaml
resp-cache:
  addresses: ["primary.global.cache:6379"]        # writes
  read-addresses: ["reader.eu-west-1.cache:6379"] # reads
```

Reads go to `read-addresses`. Writes, including cache population and flush, go to
`addresses`. Replication lag is safe by design. An entry that has not replicated yet is a
plain cache miss. The router's block-freshness validation runs on every hit, so a lagging
replica can never serve data older than what the client has already seen.

!!! warning "This selects an endpoint, not a replica role"
    Under `standalone`, the addresses are dialled exactly as given, so a managed reader
    endpoint really does serve the reads. This feature is built for that shape.

    Under `sentinel` and `cluster`, the read client runs its **own discovery** from the
    seeds you give it. It resolves to the master(s) of whatever topology those seeds front.
    So if you point it at replicas of the *same* deployment, your reads go straight back to
    the primary. The setting still makes sense when it points at a **separate replicated
    deployment**, which is why the router logs a warning instead of rejecting the config.
    Replica reads within one sentinel set or cluster are not supported. Use the managed
    reader endpoint in `standalone` shape instead.

## Credential rotation

Use `password-file` with whatever refreshes the file, such as a Kubernetes secret mount or
a sidecar token refresher. The file is polled at `credential-refresh-interval`. When it
changes, the router pushes the new credentials to every live connection. Each connection
re-authenticates **in place**, with no reconnect and no dropped operations.

The file holds the password, or `username:password` to rotate the ACL user too.

!!! warning "A password containing `:` cannot be expressed in a password file"
    The first colon is always read as the `username:password` separator. So a file
    holding `p@ss:word` authenticates as user `p@ss` with password `word`. That fails
    closed, but the error is an opaque `WRONGPASS`, because the router deliberately keeps
    the server's auth reply out of logs. For this reason, the router warns once at startup
    when the file contains a colon, and names only the parsed username. Either avoid `:` in
    the password, or use the explicit `username:password` form on purpose.

Under `topology: sentinel`, rotated credentials are resolved fresh **per connection
attempt**, because the underlying client cannot stream re-auth to live connections. They
apply on reconnects and failovers, and are not pushed to idle connections. Keep the
previous credential valid for a rotation grace window (standard ACL dual-credential
practice), and rotation works without interruption there too. This applies to the
**data-node** password under sentinel, not just `sentinel-password-file`. Because in-place
re-auth is not possible there, the router does not run the rotation poller under sentinel
at all. Instead, it logs once at startup that rotation applies on reconnect, rather than
reporting rotations it cannot deliver.

## Sizing and eviction

The recommended policy is **`volatile-lru`**, with a `maxmemory` that fits your working
set.

- Every key the router writes has a TTL, so `volatile-lru` can evict across the router's
  whole keyspace by recency. It never touches non-TTL keys that other applications own on
  a shared backend.
- `allkeys-lru` behaves the same on a dedicated backend. It is the safer choice if you
  ever write non-TTL keys under memory pressure. On a shared backend it can evict other
  tenants' data.
- Avoid `noeviction` for cache workloads. At `maxmemory`, the router's cache writes start
  failing (visible in `smartrouter_resp_cache_failed_total`) until TTLs free space. The
  cache keeps serving hits, but stops growing.

Most blockchain cache entries have the long finalised TTL, so in steady state memory use
approaches `maxmemory` and stays there. This is eviction working as intended, not a leak.

## Failure behaviour and monitoring

A failing backend **never fails requests**. Lookups become cache misses within the relay's
budget, and requests go on to your upstreams. Writes are best-effort. Recovery is
automatic. Alert on the dedicated series below, not on request errors:

| Series | What it tells you |
| --- | --- |
| `smartrouter_resp_cache_connected` | `0` after a failed health probe (PING, 10s cadence) against any endpoint. Changes in reachability are also logged, naming the failing endpoint. An authentication rejection is reported as an authentication rejection, not as "unreachable". The credential itself is never logged. |
| `smartrouter_resp_cache_endpoint_connected{role}` | The same, per endpoint (`write` or `read`). With the read/write split, alert on this one: it says which half is down. |
| `smartrouter_resp_cache_failed_total{op,kind}` | Backend-level operation failures. Clean misses are never counted here. `kind` separates `error` (unreachable, protocol error) from `timeout` (budget exceeded), so saturation looks different from an outage. Under `sentinel` and `cluster`, a read from an unreachable endpoint counts as `timeout`, so alert on the `connected` gauges there. |
| `smartrouter_resp_cache_breaker_open{role}` | `1` while the breaker for writes or for lookups is open. While it is open, the router skips that side's operations without contacting the backend, and probes every second until the backend answers within budget. |
| `smartrouter_resp_cache_skipped_total{op}` | Operations an open breaker skipped. |
| `smartrouter_resp_cache_connection_errors_total` | Failed background health probes. |
| `smartrouter_resp_cache_pool_*_conns` | Pool gauges: total, idle, stale. |

```bash
curl -s http://localhost:7779/metrics | grep smartrouter_resp_cache
```

The shared `smartrouter_cache_*` hit/miss series keep working as before. For the full
reference, see
[Metrics → RESP cache backend](../../reference/metrics.md#resp-cache-backend).

A router started with `--debug-relays` adds a `Lava-Cache-Backend` header to responses
served from the cache. The header names the node that served the hit: the current master
under sentinel, or the shard that was used under cluster. It is behind the debug flag
because it exposes internal infrastructure addresses.

### Client log lines

The client library's own lines go through the router's logger, in the router's log
format. A change of primary or of sentinel is logged at info, every time:

| Message | Attributes |
| --- | --- |
| `resp-cache client follows a new primary` | `master`, `address` |
| `resp-cache client attached to a sentinel` | `sentinel`, `primary` |
| `resp-cache client discovered a sentinel` | `sentinel`, `master` |

Every other line from the library is logged at warn as
`resp-cache client reported a failure`, with the library's text in `detail`. Each kind of
failure is printed at most once in 10 s, and the next line of that kind carries
`suppressed`, the number of lines dropped in between. The library has one logger for the
whole process, so these lines do not name the store they are about.

## Flush semantics

The router's `/debug/reset-all` flush is **prefix-scoped**: a `SCAN` over `key-prefix:*`
with single-key `UNLINK`s. `FLUSHDB` is never issued, so other tenants and other prefixes
on a shared backend are not touched. If two deployments must not flush each other's keys,
give them distinct `key-prefix` values.

## Precedence and rollback

Switching backends is a configuration change. The RESP cache starts cold, and no data
migrates in either direction.

| Configuration | What serves |
| --- | --- |
| `resp-cache:` set | The RESP backend, **including when `cache-be:` is also set**. The router logs a prominent warning that names the precedence. |
| Both set, then `resp-cache:` removed | The `cache-be:` sidecar, still in the config, takes over on the next start. Nothing is migrated and nothing is destroyed. The RESP data expires on its own TTLs. |
| Neither set | The default path, exactly as before. The RESP backend is never created, so its metrics are **absent**, not zero. |

Keeping `cache-be:` in place next to `resp-cache:` is intended: it is the rollback path.

## Caveats

- **The fleet chain-tracker gate is scoped to the key prefix.** The per-endpoint gate lets
  pods reuse each other's successful upstream polls, and it works on this backend as it
  does on the sidecar, with one difference in reach. Here the poll observations sit under
  `key-prefix` like every other key, so only routers on the same prefix reuse each other's
  polls. The sidecar shares them with every router that reaches it, whatever its prefix.
  Routers on different prefixes each poll for themselves: more upstream polls, never a
  different answer.
- **Sentinel credential rotation** applies per connection attempt, not in place. See
  [Credential rotation](#credential-rotation).
- **`read-addresses` selects an endpoint, not a replica role.** See
  [Multi-region reads](#multi-region-reads-readwrite-split).
- **Cold start.** No data migrates when switching backends, in either direction.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Router won't start: "`resp-cache` options are set without addresses" | A `resp-cache:` block or flag configures options but no `addresses`. Set them, or remove the block. |
| `smartrouter_resp_cache_connected` is `0` | The backend is unreachable, or authentication is being rejected. The log line tells you which. Relays keep succeeding through your upstreams the whole time. |
| Sentinel discovery fails with credentials that work on the data nodes | Sentinels authenticate separately. Set `sentinel-password` / `sentinel-password-file`. |
| Only `key-prefix:chaintip:*` keys appear | A `latest`-style query was relayed. Those entries have a sub-second TTL and expire before you can look. Request a finalised block to see an entry that lasts. |
| Reads still land on the primary under sentinel/cluster | Expected: `read-addresses` re-discovers and resolves to the master. Use a managed reader endpoint in `standalone` shape. |
| `Lava-Cache-Backend` header missing | Either the response wasn't a cache hit (check `Lava-Provider-Address`), or the router isn't running with `--debug-relays`. |

## See also

- [Cache](index.md) - what's cached, TTLs, and the default sidecar.
- [Secondary cache](secondary.md) - a read-only second tier, usable with either backend.
- [Metrics](../../reference/metrics.md#resp-cache-backend) - the full `smartrouter_resp_cache_*` reference.
