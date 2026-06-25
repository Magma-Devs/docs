# CLI reference

Every command-line flag the `smartrouter` binary accepts, grouped by purpose. The
config file is passed positionally; flags tune runtime behaviour.

```bash
smartrouter <config.yml> --use-static-spec specs/ [flags...]
```

!!! tip "Authoritative source"
    This table mirrors `smartrouter --help`. If anything here disagrees with the binary,
    the binary wins — run `smartrouter --help` to confirm against your build.

## Subcommands

| Command | Purpose |
| --- | --- |
| `smartrouter <config.yml>` | Start the router (default; config file is positional). |
| `smartrouter cache <host:port>` | Run the standalone cache server. Address is positional. |
| `smartrouter version` | Print version + commit (first line is just the version, for scripting). |
| `smartrouter test …` | Internal test commands (`rpc-smart-router`, connection probes). |

## Specs

| Flag | Default | Description |
| --- | --- | --- |
| `--use-static-spec` | — | Load specs from a file, directory, or remote GitHub/GitLab URL. Repeatable; later sources override earlier ones for the same chain id. |
| `--github-token` | — | GitHub PAT for private spec repos / higher rate limits. |
| `--gitlab-token` | — | GitLab PAT for private spec repos. |

## RPC node selection (QoS)

| Flag | Default | Description |
| --- | --- | --- |
| `--strategy` | `balanced` | Selection strategy: `balanced`, `latency`, `sync-freshness`, `cost`, `privacy`, `accuracy`, `distributed`. |
| `--qos-availability-weight` | `0.3` | Weight of availability in the composite score. |
| `--qos-latency-weight` | `0.3` | Weight of latency. |
| `--qos-sync-weight` | `0.2` | Weight of sync freshness. |
| `--qos-stake-weight` | `0.2` | Weight of node stake. |
| `--qos-min-selection-chance` | `0.01` | Floor probability any node is picked, regardless of score. |
| `--optimizer-qos-sampling-interval` | `1s` | How often selection scores (and OTel QoS events) are sampled. |
| `--probe-update-weight` | `0.25` | Weight multiplier for probe-driven liveness/latency updates. |
| `--enable-periodic-probe-providers` | `false` | Periodically probe nodes for liveness/latency. |
| `--periodic-probe-providers-interval` | `5s` | Interval for periodic probing. |

See [RPC Node selection](../configuration/projects/selection-policies.md).

## Retry, timeout & failover

| Flag | Default | Description |
| --- | --- | --- |
| `--set-relay-retry-limit` | `2` | Max total retry attempts across all error types (node + protocol). `0` disables retries. |
| `--default-processing-timeout` | `30s` | Overall budget for a whole relay (all retries + hedges). |
| `--min-relay-timeout` | `1s` | Per-attempt timeout floor. The `lava-relay-timeout` header can raise it. |
| `--max-sessions-per-provider` | `1000` | Max concurrent sessions per node. |
| `--maximum-streams-per-connection` | `100` | Max parallel streams over a single gRPC connection. |
| `--disable-batch-request-retry` | `true` | Don't retry JSON-RPC batch requests. |
| `--batch-node-error-on-any` | `false` | Treat a batch as a node error if **any** sub-request fails (vs. only if **all** do). |
| `--max-batch-request-size` | `0` | Max requests per JSON-RPC batch (`0` = unlimited). |

See [Failover & retry](../configuration/failover/index.md).

## Consistency tuning

| Flag | Default | Description |
| --- | --- | --- |
| `--chain-tracker-polling-multiplier` | `16` | "Polling relief" — smaller = slower polling = fewer upstream calls. Allowed `[4,16]`. |
| `--consistency-block-gap-factor` | `2` | Widen the consistency lag gate (`blockLagForQosSync × factor`). Allowed `[2,8]`. |

## Cache & shared state

| Flag | Default | Description |
| --- | --- | --- |
| `--cache-be` | — | Address of the cache server (e.g. `127.0.0.1:20100`). In Compose the cache address usually comes from `cache-be:` in the config instead. |
| `--shared-state` | `false` | Share consistency state across router instances via the cache (use with `--cache-be`). |

## WebSocket

| Flag | Default | Description |
| --- | --- | --- |
| `--rate-limit-websocket-requests-per-connection` | `-1` (unlimited) | Per-second request rate limit per WS connection. |
| `--ban-duration-for-websocket-rate-limit-exceeded` | no ban | Ban duration once the WS rate limit is hit. |
| `--limit-parallel-websocket-connections-per-ip` | `0` (unlimited) | Max parallel WS connections per IP. |
| `--limit-websocket-connection-idle-time` | `1200` | WS idle timeout (seconds; default 20 min). |
| `--skip-websocket-verification` | `false` | Skip startup WS verification for chains that require ws/wss endpoints. |

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
| `--usage-otel-enabled` | `false` | Emit per-relay usage + QoS events as OTLP logs. |
| `--usage-otel-endpoint` | — | OTLP/HTTP endpoint (default `localhost:4318` / `OTEL_EXPORTER_OTLP_ENDPOINT`). |
| `--usage-otel-insecure` | `true` | Skip TLS for the OTLP exporter. |
| `--usage-otel-queue-size` | `50000` | In-memory usage-event queue capacity (full queue drops events). |
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
| `--relays-health-enable` | `true` | Enable relay health checks. |
| `--relays-health-interval` | `5m` | Interval between health checks. |
| `--epoch-duration` | disabled | Duration of each epoch (e.g. `30m`); unset disables epochs. |
| `--shutdown-grace-period` | `25s` | Graceful-shutdown deadline for in-flight requests + WS clients. |

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
| `--debug-address` | — | Debug HTTP server (integration tests) — exposes `/debug/*`. |
| `--test-mode` | `false` | Send dummy data and print all listener metadata. |
| `--allow-insecure-provider-dialing` | `false` | Allow non-TLS upstream connections. Dev/test only. |
| `--pprof-address` | — | pprof server address (e.g. `localhost:6060`). |
| `--pyroscope-address` | — | Pyroscope continuous-profiling address. |
| `--pyroscope-app-name` | `smartrouter` | Pyroscope application name. |
| `--pyroscope-mutex-profile-fraction` | `5` | Mutex profile sampling rate (1 in N). |
| `--pyroscope-block-profile-rate` | `1` | Block profile rate (ns; 1 records all). |
| `--pyroscope-tags` | — | Comma-separated `key=value` tags. |

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
