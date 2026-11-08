---
title: "CLI flags"
description: "Command-line flags and options for the Smart Router binary."
---

# CLI reference

This page lists every command-line flag the `smartrouter` binary accepts, grouped by
purpose, so you can look up a flag's default and what it does.

You pass the config file as a positional argument. Flags change runtime behaviour.

```bash
smartrouter <config.yml> --use-static-spec specs/ [flags...]
```

!!! tip "Authoritative source"
    This table follows `smartrouter --help`. If anything here disagrees with the binary,
    trust the binary. Run `smartrouter --help` to check against your build.

## Subcommands

| Command | Purpose |
| --- | --- |
| `smartrouter <config.yml>` | Start the router. This is the default; the config file is a positional argument. |
| `smartrouter cache <host:port>` | Run the standalone cache server. The address is a positional argument. |
| `smartrouter health <config.yml>` | Run a one-shot, spec-driven health probe over every node, URL, websocket, and add-on in a config. It prints a JSON report and exits. Flags: `--include-backup`, `--timeout` (default `30s`), `--skip-websocket-verification`, `--use-static-spec` (required). |
| `smartrouter version` | Print the version and commit. The first line is only the version, for use in scripts. |
| `smartrouter test …` | Internal test commands (`rpcsmartrouter`, `connection-server`, `connection-probe`). |

## Specs

| Flag | Default | Description |
| --- | --- | --- |
| `--use-static-spec` | - | Load specs from a file, a directory, or a remote GitHub/GitLab URL. You can repeat the flag. For the same chain id, later sources override earlier ones. |
| `--github-token` | - | GitHub PAT for private spec repos or higher rate limits. |
| `--gitlab-token` | - | GitLab PAT for private spec repos. |

## RPC node selection (QoS)

| Flag | Default | Description |
| --- | --- | --- |
| `--strategy` | `balanced` | Selection strategy: `balanced`, `latency`, `sync-freshness`, `cost`, `privacy`, `accuracy`, `distributed`. |
| `--qos-availability-weight` | `0.3` | Weight of availability in the composite score. |
| `--qos-latency-weight` | `0.3` | Weight of latency. |
| `--qos-sync-weight` | `0.2` | Weight of sync freshness. |
| `--qos-stake-weight` | `0.2` | Weight of node stake. |
| `--qos-min-selection-chance` | `0.01` | Minimum probability that any node is picked, whatever its score. |
| `--optimizer-qos-sampling-interval` | `1s` | How often selection scores (and OTel QoS events) are sampled. |
| `--probe-update-weight` | `0.25` | Weight multiplier for probe-driven liveness/latency updates. |
| `--probe-loop-interval` | `5s` | How often nodes are probed for liveness and latency. Probing is always on. The value must be greater than 0. |

See [RPC Node selection](../configuration/projects/selection-policies.md).

## Retry, timeout & failover

| Flag | Default | Description |
| --- | --- | --- |
| `--set-relay-retry-limit` | `2` | Errors a request tolerates, across every node and error type (rate limits included), before it stops. `0` disables retries. The count does not know that a backup is still untried: with more primaries than this limit, a request whose primaries all fail stops before any backup. See [Primary and backup nodes](../configuration/failover/backup.md#errors-the-retry-limit-can-end-a-request-before-any-backup). |
| `--stateful-to-backup` | `false` | Also broadcast writes (transaction submission) to the backup tier. A write goes to every node it selects, so this sends **every** write to the backups, including the ones the primaries serve fine. See [Writes and batches](../configuration/failover/backup.md#writes-and-batches). |
| `--bench-after` | `50` | Consecutive failed requests to one URL before the router takes it out of rotation. A success resets the count. A provider with every URL out is blocked, and requests go to the other primaries or the backups. Must be greater than 0. |
| `--read-your-writes-window` | `30s` | How long a written transaction's sender and hash stay tied to the node that accepted it, so the sender's follow-up reads go there first (a backup included). Pod-local, first attempt only. `0` turns it off. |
| `--default-processing-timeout` | `30s` | Total time budget for one relay, including all retries and hedges. |
| `--min-relay-timeout` | `1s` | Lower limit for the per-attempt window, which sets when the router tries the next node. It does not cancel the attempt in flight. The `lava-relay-timeout` header overrides it. |
| `--max-caller-relay-timeout` | `0` | The longest time a caller's `lava-relay-timeout` header can make the router hold one request. The flag only lets the header extend a request past the budget it gets without the header. It never shortens a request. `0` allows no extension. An extended request does not hedge. |
| `--max-sessions-per-provider` | `1000` | Max concurrent sessions per node. |
| `--maximum-streams-per-connection` | `100` | Max parallel streams over a single gRPC connection. |
| `--disable-batch-request-retry` | `true` | Don't retry, fail over, or hedge JSON-RPC batch requests. A batch can carry a write. See [Batch requests](../configuration/failover/retry.md#batch-requests). |
| `--batch-node-error-on-any` | `false` | Treat a batch as a node error if **any** sub-request fails, instead of only when **all** fail. |
| `--max-batch-request-size` | `0` | Max requests per JSON-RPC batch (`0` = unlimited). |

See [Failover & retry](../configuration/failover/index.md).

## Polling relief

These flags lower the polling load that the router's chain trackers put on your
upstreams. Each configured upstream gets its own chain tracker, which polls it for the
latest block separately from the relays you send. All of these flags are process-wide.
You can watch the effect on
[`rpc_endpoint_tracker_requests_total`](metrics.md#endpoint-scoped-rpc_endpoint_).

| Flag | Default | Description |
| --- | --- | --- |
| `--enable-fork-detection` | `false` | Turn on block-hash polling (reorg detection on upstreams). Off by default - the larger of the per-pod savings. |
| `--chain-tracker-poll-divisor` | `2` | The tracker polls every `avgBlockTime ÷ divisor`. `1` halves the polling rate. `0.25` (one poll per **four** block times) cuts it eightfold. Allowed `[0.25,8]`; an out-of-range value reverts to the default. See [Polling slower than the chain](#polling-slower-than-the-chain). |
| `--shared-state` (with `--cache-be`) | `false` | Share poll observations across router replicas through the cache, so an upstream is polled about once per interval **fleet-wide** rather than once per pod. See [Cache & shared state](#cache-shared-state). |
| `--chain-tracker-idle-after` | `0` (off) | Idle mode. When a chain has served no client request for this long, its trackers stop polling until the next request. Minimum `10s`. Available from v1.6.0. See [Pausing an idle chain](#pausing-an-idle-chain). |
| `--chain-tracker-idle-poll-interval` | `0` | While a chain is idle, poll each upstream once per this interval, so a dead upstream is still noticed. `0` polls nothing while idle. No effect without `--chain-tracker-idle-after`. |

The tracker also skips a poll when something else has already kept the upstream's tip
fresh: the relays it served in the last block time, or (with `--shared-state`) a poll
that another replica made. Skipped ticks show up on
[`rpc_endpoint_tracker_gate_skips_total`](metrics.md#endpoint-scoped-rpc_endpoint_) by
`source`. If `requests_total` falls while `gate_skips_total` rises, the relief is
working and the tracker has not stalled.

### Pausing an idle chain

`--chain-tracker-idle-after` stops polling a chain nobody is using. It is off by
default. When it is on and a chain has served no client request for that long, its
trackers skip every poll, so the upstreams of an unused chain are not billed for it.

The next client request wakes the chain. The router polls every upstream of that chain
once, and that request waits for the first answer, up to 1 second, before it is routed.
Later requests are not delayed. While a chain is idle, `smartrouter_chain_idle` reads
`1`.

Things to know before you turn it on:

- **Pick a window longer than the gap between your requests.** Otherwise every request
  is a wake. `5m` to `10m` is a good start.
- **The router's latest block stands still while a chain is idle.** An alert on "the
  tip stopped moving" fires on an idle chain unless it skips chains where
  `smartrouter_chain_idle` is `1`.
- **Subscriptions do not keep a chain awake.** An open `eth_subscribe` neither keeps a
  chain active nor wakes it. Unary requests over a websocket do.
- **A disabled upstream recovers at the next epoch or after the wake.** Re-enabling an
  upstream needs polls, so while a chain is idle it waits.

### Polling slower than the chain

A divisor below `1` polls less often than the chain produces blocks. On a fast chain,
this is where the relief is. Measured requests per minute, per endpoint:

| Chain | `2` (default) | `1` | `0.5` | `0.25` |
| --- | --- | --- | --- | --- |
| Aptos | 600 | 300 | 150 | 75 |
| Solana | 300 | 150 | 75 | 37.5 |
| Base | 60 | 30 | 15 | 7.5 |
| Ethereum | 9.2 | 4.6 | 2.3 | 1.2 |

The staleness window sets the limit at the low end: `max(10 × avgBlockTime, 2s)`. Past
this window, an observation stops counting for consensus, the tip reads unknown, and the
probe scores a healthy upstream as not-alive. This flag does **not** change the window.
It changes how long a tip can go without a refresh, which is the other side of that
comparison. Both common cases stay well inside the window:

- **Idle upstream** - only its own poll refreshes the tip, so the gap *is* the
  interval: 4 × `avgBlockTime` at `0.25`, against a 10× window.
- **Served upstream** - relays refresh the same tip, so traffic limits the gap.

The edge case is between them. An upstream that trips the traffic gate and *then* goes
quiet is refreshed by neither, so the worst-case gap becomes
`(maxRelaySkips + 1) × interval`, which is 20 × `avgBlockTime` at `0.25`. This gap
depends on the **product** of this flag and the gate's skip budget, not on either one
alone. So the router logs a warning once per chain at startup instead of refusing to
start:

```
WRN poll cadence can outrun the staleness window when the traffic gate skips
    pollInterval=60s  worstCaseGapBetweenPolls=5m0s  stalenessWindow=2m30s  maxRelaySkips=4
```

This warning is for information only. It is not a failure, and the configuration is
safe for both common cases. If you see it on a chain with bursty traffic, move the
divisor back toward `0.5` or `1`.

## Consistency tuning

| Flag | Default | Description |
| --- | --- | --- |
| `--consistency-block-gap-factor` | `2` | Widen the consistency lag gate (`blockLagForQosSync × factor`). Allowed `[2,8]`. |

## Cache & shared state

| Flag | Default | Description |
| --- | --- | --- |
| `--cache-be` | - | Address of the cache server (e.g. `127.0.0.1:20100`). In Compose the cache address usually comes from `cache-be:` in the config instead. |
| `--shared-state` | `false` | Share state across router replicas through the cache backend (`cache-be` or `resp-cache`): the consumer-consistency "seen block", per-endpoint chain-tracker poll observations (so the fleet polls each upstream about once per interval instead of once per replica), and cross-pod sticky sessions. Poll sharing also requires `--cache-be`; see the [RESP backend caveats](../deployment/cache/redis.md#caveats). |
| `--resp-cache-addresses` | - | Comma-separated address(es) of a [RESP-compatible backend](../deployment/cache/redis.md) (Redis/Valkey). Enables the RESP backend, which takes precedence over `cache-be`. Standalone: the node address; sentinel: the sentinel addresses; cluster: the configuration endpoint. |
| `--resp-cache-topology` | `standalone` | `standalone`, `sentinel`, or `cluster`. |
| `--secondary-cache-be` | - | Address of an optional read-only [secondary cache](../deployment/cache/secondary.md), queried when the primary produces no hit. |
| `--secondary-cache-timeout` | `50ms` | Time budget for each secondary cache lookup. A lookup that runs over it is treated as a miss. |
| `--secondary-cache-mode` | `read-only` | Secondary cache access mode. Only `read-only` is supported. |

!!! note "The RESP backend's full surface is config-file only"
    You set TLS, credentials, credential rotation, the read/write split, and key prefixing
    in the `resp-cache:` YAML block. Only addresses and topology have flags. See
    [Redis / Valkey backend](../deployment/cache/redis.md#configuration-reference).

With `--shared-state`, every replica publishes each successful poll of an upstream to
the cache. Before it polls, a replica checks whether **another** replica polled that
upstream within the last block time. If one did, the replica skips the tick and adopts
the peer's block as its own view of the upstream's tip. Four rules keep this safe:

- a replica never borrows its own observation, so a single replica polls exactly as it
  would without the flag;
- a replica whose own last poll of an upstream failed does not borrow at all (it goes
  back to local polling at the full rate until its own poll succeeds);
- every replica still polls each upstream itself every few ticks (peer skips count
  against the same skip budget as relay skips), so a broken path from one pod stays
  detectable;
- an upstream that was disabled is only re-enabled by that pod's own successful poll;
  a peer observation never affects poll health.

Latency is never shared, because a peer's round-trip says nothing about this pod's path.

## WebSocket

| Flag | Default | Description |
| --- | --- | --- |
| `--rate-limit-websocket-requests-per-connection` | `-1` (unlimited) | Per-second request rate limit per WS connection. |
| `--ban-duration-for-websocket-rate-limit-exceeded` | no ban | Ban duration once the WS rate limit is hit. |
| `--limit-parallel-websocket-connections-per-ip` | `0` (unlimited) | Max parallel WS connections per IP. |
| `--limit-websocket-connection-idle-time` | `1200` | WS idle timeout (seconds; default 20 min). |
| `--skip-websocket-verification` | `false` | Connect to ws(s) node urls without running any spec check over them. An upstream with no ws(s) url is served over http either way, without subscriptions, and publishes [`missing-url`](metrics.md#the-websocket-as-its-own-part) on a chain with subscriptions. |

## CORS & HTTP

| Flag | Default | Description |
| --- | --- | --- |
| `--cors-origin` | `*` | Allowed origins. |
| `--cors-headers` | simple-cors | Allowed headers (`*` for all). |
| `--cors-methods` | `GET,POST,PUT,DELETE,OPTIONS` | Allowed methods. |
| `--cors-credentials` | `true` | `Access-Control-Allow-Credentials` value. |
| `--cdn-cache-duration` | `86400` | Preflight OPTIONS cache duration (seconds). |
| `--response-compression` | `gzip` | Client-facing compression: `gzip`, `brotli`, or `off`. |

## Metrics & telemetry

| Flag | Default | Description |
| --- | --- | --- |
| `--metrics-listen-address` | `disabled` | Prometheus `/metrics` address, e.g. `:7779`. |
| `--usage-otel-enabled` | `false` | Emit per-relay usage and QoS events as OTLP logs. |
| `--usage-otel-endpoint` | - | OTLP/HTTP endpoint (default `localhost:4318` / `OTEL_EXPORTER_OTLP_ENDPOINT`). |
| `--usage-otel-insecure` | `true` | Skip TLS for the OTLP exporter. |
| `--usage-otel-queue-size` | `50000` | Capacity of the in-memory usage-event queue. When the queue is full, events are dropped. |
| `--usage-otel-batch-size` | `1000` | Batch-size flush trigger. |
| `--usage-otel-flush-interval` | `500ms` | Time-based flush trigger. |
| `--usage-otel-export-timeout` | `10s` | Per-batch export timeout. |
| `--usage-otel-service-name` | `smartrouter` | OTel `service.name`. |
| `--usage-otel-service-instance-id` | hostname-pid | OTel `service.instance.id`. |
| `--otel-trace-body` | `false` | Record request/response bodies on trace spans. |

See [Metrics](metrics.md).

## Lifecycle & health

| Flag | Default | Description |
| --- | --- | --- |
| `--relays-health-enable` | `true` | Enable relay health checks. When `false`, `/readyz` and `/metrics/overall-health` always report `503`, so keep it on when you use a Kubernetes readiness probe. |
| `--relays-health-interval` | `5m` | Interval between health checks while a chain is healthy. A client relay that an upstream answers with a result delays the probe, so this is how often an idle chain is re-checked. See [When readiness changes](metrics.md#when-readiness-changes). |
| `--relays-health-unhealthy-interval` | `15s` | Probe interval while a chain is unhealthy, clamped to `--relays-health-interval`. It is also the longest a client relay that no upstream answered waits for the next probe. A router that is not ready gets no client relays, so this interval limits how fast `/readyz` follows upstreams going out of reach and coming back. |
| `--epoch-duration` | `15m` | Duration of each epoch (e.g. `30m`). Epochs always run: if unset or `0`, the router uses `15m`. At each epoch boundary the router re-verifies the upstreams and rebuilds the serving tier. Between epochs, each spec check an upstream is failing is retried on its own schedule (`--verification-retry-delay`), so an upstream can be taken out or come back before the next epoch. |
| `--verification-retry-delay` | `30s` | How long a spec check an upstream is failing waits for its first retry. Each check has its own wait, and each retry that still finds it failing doubles it, up to `--verification-retry-max-delay`, plus up to 20% jitter. `0` uses `30s`. See [Spec verification failures](metrics.md#spec-verification-failures). |
| `--verification-retry-max-delay` | `15m` | The longest a failing spec check waits between retries. A value below `--verification-retry-delay` acts as that delay. |
| `--shutdown-grace-period` | `25s` | Graceful-shutdown deadline for in-flight requests and WS clients. |

## Logging

| Flag | Default | Description |
| --- | --- | --- |
| `--log-level` | `info` | `debug` / `info` / `warn` / `error` / `fatal`. |
| `--log-format` | `text` | `text` or `json`. |
| `--rolling-log-level` | `off` | Rolling-log level (`off` / `debug` / … / `fatal`). |
| `--rolling-log-file-location` | `logs/rollingRPC.log` | Rolling-log file path. |
| `--rolling-log-max-size` | `100` | Max rolling-log size (MB). |
| `--rolling-log-max-age` | `1` | Max rolling-log age (days). |
| `--rolling-log-backups` | `3` | Old rolling-log files to keep. |
| `--rolling-log-format` | `json` | Rolling-log format (`json` / `text`). |

## Debugging & profiling

| Flag | Default | Description |
| --- | --- | --- |
| `--debug-relays` | `false` | Add debug info to relay response metadata (pairs with the `lava-debug-relay` header). |
| `--debug-probes` | `false` | Add debug info to probe responses. |
| `--enable-selection-stats` | `false` | Emit the `lava-selection-stats` response header. |
| `--debug-address` | - | Debug HTTP server for integration tests. It exposes `/debug/*`, including [`/debug/sticky-claims`](metrics.md#cross-pod-sticky-sessions) and [`/debug/verification`](metrics.md#verification-state-on-the-debug-server). |
| `--test-mode` | `false` | Send dummy data and print all listener metadata. |
| `--allow-insecure-provider-dialing` | `false` | Allow non-TLS upstream connections. Dev/test only. |
| `--pprof-address` | - | pprof server address (e.g. `localhost:6060`). |
| `--pyroscope-address` | - | Pyroscope continuous-profiling address. |
| `--pyroscope-app-name` | `smartrouter` | Pyroscope application name. |
| `--pyroscope-mutex-profile-fraction` | `5` | Mutex profile sampling rate (1 in N). |
| `--pyroscope-block-profile-rate` | `1` | Block profile rate (ns; 1 records all). |
| `--pyroscope-tags` | - | Comma-separated `key=value` tags. |

## Cache subcommand flags

Flags for `smartrouter cache <host:port>`:

| Flag | Default | Description |
| --- | --- | --- |
| `--metrics_address` | `disabled` | Prometheus metrics address for the cache (e.g. `0.0.0.0:5555`). |
| `--max-items` | `2147483648` | Max number of entries to keep in the cache. |
| `--expiration` | `1h` | TTL for finalized entries. |
| `--expiration-non-finalized` | `500ms` | TTL for non-finalized entries. |
| `--expiration-multiplier` | `1.0` | Multiplier on the finalized TTL (`1.2` = 20% longer). |
| `--expiration-non-finalized-multiplier` | `1.0` | Multiplier on the non-finalized TTL. |
| `--expiration-blocks-hashes-to-heights` | `48h` | TTL for block-hash→height mappings. |
| `--expiration-finalized-node-errors` | `250ms` | TTL for cached finalized node errors. |
| `--log_level` | `info` | Cache log level (`trace`…`panic`). |

!!! note "Underscore vs. dash"
    The cache subcommand uses `--metrics_address` and `--log_level` (underscores), unlike
    the router's `--metrics-listen-address` / `--log-level`. This matches the binary.
