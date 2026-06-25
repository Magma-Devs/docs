# Metrics

Every metric the Smart Router exposes over Prometheus, with its type, labels, and
meaning. All metrics are defined under [`protocol/metrics/`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/metrics).

The classified-error counter [`smartrouter_errors_total`](#classified-errors-smartrouter_errors_) is
broken down by error name and category; see [Error codes](error-codes.md) for the
full taxonomy of names it can carry.

Already running the [dashboard overlay](../deployment/docker-compose.md#add-the-dashboard)? It
ships pre-built panels over these series — this page is the underlying reference and the
recipes for rolling your own.

## What to watch

If you only graph a handful of things, graph these:

| Question | Metric(s) |
| --- | --- |
| Is the router up and serving? | `smartrouter_overall_health`, `smartrouter_total_relays_serviced` |
| Are requests failing? | `smartrouter_total_errored`, `smartrouter_errors_total` (by `error_category` / `retryable`) |
| How fast is it? | `smartrouter_end_to_end_latency_milliseconds` (histogram → p50/p95/p99) |
| Is a node degrading? | `rpc_endpoint_overall_health`, `rpc_endpoint_end_to_end_latency_milliseconds`, `rpc_endpoint_latest_block` |
| Is failover working hard? | `smartrouter_retries_total`, `smartrouter_hedge_total` |
| Is the cache earning its keep? | `smartrouter_cache_success_total` / `smartrouter_cache_requests_total` |

## Querying — PromQL recipes

Copy-paste starting points (adjust labels / windows to taste).

```promql
# Request error ratio (last 5m)
sum(rate(smartrouter_total_errored[5m]))
  / sum(rate(smartrouter_total_relays_serviced[5m]))

# p99 end-to-end latency, per chain (ms)
histogram_quantile(0.99,
  sum by (spec, le) (rate(smartrouter_end_to_end_latency_milliseconds_bucket[5m])))

# Cache hit ratio
sum(rate(smartrouter_cache_success_total[5m]))
  / sum(rate(smartrouter_cache_requests_total[5m]))

# Retry rate per relay (how often the first attempt isn't enough)
sum(rate(smartrouter_retries_total[5m]))
  / sum(rate(smartrouter_total_relays_serviced[5m]))

# Non-retryable (terminal) errors only — usually client/chain problems, not infra
sum by (error_name) (rate(smartrouter_errors_total{retryable="false"}[5m]))

# Nodes currently unhealthy
rpc_endpoint_overall_health == 0

# Per-node request share (is selection lopsided?)
sum by (provider_address) (rate(smartrouter_requests_total[5m]))
```

## Suggested alerts

Starting points — tune thresholds to your traffic.

| Alert | Expression sketch | Why |
| --- | --- | --- |
| Router unhealthy | `smartrouter_overall_health == 0 for 1m` | No endpoint is serving. |
| High error ratio | error-ratio recipe `> 0.05 for 5m` | Something broke upstream or in config. |
| Latency regression | p99 recipe `> 2000 for 10m` | Tail latency degraded. |
| Node down | `rpc_endpoint_overall_health == 0 for 5m` | A configured upstream is out. |
| Cache cold | hit-ratio recipe `< 0.2 for 30m` | Cache misconfigured or bypassed — cost/latency risk. |
| Post-finality divergence | `increase(smartrouter_cross_validation_mismatch_total{finality="finalized"}[15m]) > 0` | A node disagreed on *finalized* data — high-signal correctness alert. |

## Exposition

Metrics are served in Prometheus text format from an HTTP server started by the
metrics manager.

| Path | Format | Description |
| --- | --- | --- |
| `/metrics` | Prometheus | All registered metrics ([`promhttp.Handler()`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/metrics/smartrouter_metrics_manager.go#L623)) |
| `/metrics/overall-health` | text | `200 Health status OK` if ≥1 endpoint is healthy, else `503 Unhealthy` |
| `/metrics/health-overall` | text | Alias of the above (backward-compat path) |

### Configuration

| Flag / env | Default | Effect |
| --- | --- | --- |
| `--metrics-listen-address` | `disabled` | Address to expose Prometheus metrics on, e.g. `:7779` or `localhost:7779`. The literal `disabled` turns the metrics server off entirely. |
| `--optimizer-qos-sampling-interval` | `1s` | How often the optimizer-QoS sampler refreshes the `rpc_optimizer_selection_score` gauge and — when `--usage-otel-enabled` is set — emits `optimizer_qos` events to the OTel usage pipeline. |

```bash
# enable, then scrape
smartrouter ... --metrics-listen-address ":7779"
curl http://localhost:7779/metrics
```

The flag name and the `disabled` sentinel live in
[`flags.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/metrics/flags.go#L8).

!!! note "Optimizer scores are always on"
    The optimizer-QoS client is created unconditionally, so
    `rpc_optimizer_selection_score` is populated on `/metrics` regardless of
    telemetry config. Remote shipping of these reports flows through the OTel
    usage pipeline (`--usage-otel-enabled`), not a dedicated push address.

### Conventions

- **Latency histograms** all share the same buckets, in **milliseconds**
  ([`buckets.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/metrics/buckets.go#L7)):
  `1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000`.
- **Attempt histograms** (`retry_attempts`, `hedge_attempts`) use integer buckets `1…10`.
- **Common labels**:
    - `spec` — chain spec id (e.g. `ETH1`, `LAV1`).
    - `apiInterface` — `jsonrpc`, `tendermintrpc`, `rest`, `grpc`.
    - `endpoint_id` — the configured upstream RPC endpoint.
    - `provider_address` — node the relay was routed to.
    - `method` — RPC method name.
    - `function` — relay function class; the `function` label lets one metric serve both
      the per-function breakdown and (via `sum by (...)`) the aggregate.
- **Boolean gauges** encode `1 = true / healthy / present`, `0 = false / unhealthy / absent`.
- **Protocol version** gauges encode `major*1e6 + minor*1e3 + patch`.
- Metrics are registered with `registerOrReuse`, which returns the already-registered
  collector instead of panicking on a duplicate — so re-registration (e.g. across test
  runs sharing the default registry) is safe.

---

## Smart Router metrics

These are the metrics specific to running as a Smart Router, defined in
[`smartrouter_metrics_manager.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/metrics/smartrouter_metrics_manager.go).
They split into **endpoint-scoped** (`rpc_endpoint_*`) and **router-scoped**
(`smartrouter_*`) families.

### Endpoint-scoped — `rpc_endpoint_*`

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `rpc_endpoint_total_relays_serviced` | Counter | `spec`, `apiInterface`, `endpoint_id`, `function` | Relays successfully served by this endpoint. |
| `rpc_endpoint_total_errored` | Counter | `spec`, `apiInterface`, `endpoint_id`, `function` | Errored relays for this endpoint. |
| `rpc_endpoint_requests_in_flight` | Gauge | `spec`, `apiInterface`, `endpoint_id`, `function` | Relays currently in flight to this endpoint. |
| `rpc_endpoint_end_to_end_latency_milliseconds` | Histogram | `spec`, `apiInterface`, `endpoint_id`, `function` | End-to-end latency per function for this endpoint. |
| `rpc_endpoint_overall_health` | Gauge | `spec`, `apiInterface`, `endpoint_id` | Endpoint health (1 healthy / 0 unhealthy). |
| `rpc_endpoint_overall_health_breakdown` | Gauge | `spec`, `apiInterface` | Aggregate health per chain/interface. |
| `rpc_endpoint_selection_score` | Gauge | `spec`, `apiInterface`, `endpoint_id`, `score_type` | Selection scores by `score_type` (availability / latency / sync / stake / composite). |
| `rpc_endpoint_latest_block` | Gauge | `spec`, `apiInterface`, `endpoint_id` | Latest block reported by the endpoint. |
| `rpc_endpoint_fetch_latest_fails` | Counter | `spec`, `apiInterface`, `endpoint_id` | Failed latest-block fetches. |
| `rpc_endpoint_fetch_block_fails` | Counter | `spec`, `apiInterface`, `endpoint_id` | Failed specific-block fetches. |
| `rpc_endpoint_fetch_latest_success` | Counter | `spec`, `apiInterface`, `endpoint_id` | Successful latest-block fetches. |
| `rpc_endpoint_fetch_block_success` | Counter | `spec`, `apiInterface`, `endpoint_id` | Successful specific-block fetches. |

### Optimizer

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `rpc_optimizer_selection_score` | Gauge | `spec`, `endpoint_id`, `score_type` | Periodic optimizer selection score per node, by `score_type`. |

### Router-scoped — `smartrouter_*`

#### Core relay & health

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_total_relays_serviced` | Counter | `spec`, `apiInterface`, `function` | Relays served by the router. |
| `smartrouter_total_errored` | Counter | `spec`, `apiInterface`, `function` | Errored relays. |
| `smartrouter_end_to_end_latency_milliseconds` | Histogram | `spec`, `apiInterface`, `function` | Router-level end-to-end latency. |
| `smartrouter_overall_health` | Gauge | — | Overall router health (1 / 0). |
| `smartrouter_overall_health_breakdown` | Gauge | `spec`, `apiInterface` | Per-chain/interface health. |
| `smartrouter_latest_block` | Gauge | `spec`, `apiInterface` | Latest block known to the router. |
| `smartrouter_protocol_version` | Gauge | `version` | Encoded protocol version. |

#### WebSocket

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_ws_connections_active` | Gauge | `spec`, `apiInterface` | Active WebSocket connections. |
| `smartrouter_ws_subscriptions_total` | Counter | `spec`, `apiInterface` | Total WebSocket subscription requests. |
| `smartrouter_ws_subscription_errors_total` | Counter | `spec`, `apiInterface` | Failed WebSocket subscription requests. |

#### Request breakdown

`requests_total` = `success` + `failed`. `read`/`write` partition by statefulness;
`debug_trace` and `archive` are orthogonal addon flags; `batch` is mutually exclusive
with read/write.

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_requests_total` | Counter | `spec`, `apiInterface`, `provider_address`, `method` | All requests. |
| `smartrouter_requests_success_total` | Counter | `spec`, `apiInterface`, `provider_address`, `method` | Successful requests. |
| `smartrouter_requests_failed_total` | Counter | `spec`, `apiInterface`, `provider_address`, `method` | Failed requests. |
| `smartrouter_requests_read_total` | Counter | `spec`, `apiInterface`, `provider_address`, `method` | Read (stateless) requests. |
| `smartrouter_requests_write_total` | Counter | `spec`, `apiInterface`, `provider_address`, `method` | Write (stateful) requests. |
| `smartrouter_requests_debug_trace_total` | Counter | `spec`, `apiInterface`, `provider_address`, `method` | Debug/trace addon requests. |
| `smartrouter_requests_archive_total` | Counter | `spec`, `apiInterface`, `provider_address`, `method` | Archive requests. |
| `smartrouter_requests_batch_total` | Counter | `spec`, `apiInterface`, `provider_address`, `method` | Batch requests. |

#### Errors

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_node_errors_total` | Counter | `spec`, `apiInterface`, `provider_address`, `method` | Node errors returned by endpoints. |
| `smartrouter_protocol_errors_total` | Counter | `spec`, `apiInterface`, `provider_address`, `method` | Protocol/transport errors (connection/session failures). |

#### Retries

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_retries_total` | Counter | `spec`, `apiInterface`, `method` | Retry attempts triggered (beyond the first try). |
| `smartrouter_retries_success_total` | Counter | `spec`, `apiInterface`, `method` | Retried requests that succeeded. |
| `smartrouter_retries_failed_total` | Counter | `spec`, `apiInterface`, `method` | Retried requests that failed. |
| `smartrouter_retry_attempts` | Histogram | `spec`, `apiInterface`, `method` | Attempts per retried request (buckets 1…10). |

#### Consistency

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_consistency_total` | Counter | `spec`, `apiInterface`, `method` | Requests enforcing consistency (seenBlock). |
| `smartrouter_consistency_success_total` | Counter | `spec`, `apiInterface`, `method` | Consistency-enforced requests that succeeded. |
| `smartrouter_consistency_failed_total` | Counter | `spec`, `apiInterface`, `method` | Consistency-enforced requests that failed. |

#### Hedging

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_hedge_total` | Counter | `spec`, `apiInterface`, `method` | Hedge (batch-ticker) relays sent. |
| `smartrouter_hedge_success_total` | Counter | `spec`, `apiInterface`, `method` | Hedged requests that succeeded. |
| `smartrouter_hedge_failed_total` | Counter | `spec`, `apiInterface`, `method` | Hedged requests that failed. |
| `smartrouter_hedge_attempts` | Histogram | `spec`, `apiInterface`, `method` | Hedge relays per request (buckets 1…10). |

#### Cross-validation

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_cross_validation_requests_total` | Counter | `spec`, `apiInterface`, `method` | Cross-validated requests. |
| `smartrouter_cross_validation_success_total` | Counter | `spec`, `apiInterface`, `method` | Requests that reached consensus. |
| `smartrouter_cross_validation_failed_total` | Counter | `spec`, `apiInterface`, `method` | Requests that failed to reach consensus. |
| `smartrouter_cross_validation_provider_agreements_total` | Counter | `spec`, `apiInterface`, `method`, `provider_address` | Times a node agreed with consensus. |
| `smartrouter_cross_validation_provider_disagreements_total` | Counter | `spec`, `apiInterface`, `method`, `provider_address` | Times a node disagreed with consensus. |
| `smartrouter_cross_validation_mismatch_total` | Counter | `spec`, `apiInterface`, `method`, `group`, `finality` | **Content outliers** by group: one increment per distinct outlier group per successful deterministic cross-validation request (a response whose `SHA256(reply.data)` diverged from the reached consensus). Only emitted when a quorum was reached. `finality` is `finalized` / `not_finalized` / `unknown`; post-finality divergence is the high-signal alert. Bounded cardinality (keyed by operator-defined `group`, not node address). |
| `smartrouter_cross_validation_failures_total` | Counter | `spec`, `apiInterface`, `method`, `reason` | **Failures by reason** — the by-reason breakdown of `cross_validation_failed_total` (which stays unlabeled, so existing dashboards are unaffected). `reason` is a closed enum: quorum-time `no-agreement` / `insufficient-responses` / `diversity-unmet` / `group-quorum-unmet`, or request-time structural `insufficient-capacity` / `insufficient-groups`. Separates a structural failure (client should fall back) from a quorum disagreement (a retry may help). |

#### Cache

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_cache_requests_total` | Counter | `spec`, `apiInterface`, `method` | Cache lookup attempts. |
| `smartrouter_cache_success_total` | Counter | `spec`, `apiInterface`, `method` | Cache hits. |
| `smartrouter_cache_failed_total` | Counter | `spec`, `apiInterface`, `method` | Cache misses. |
| `smartrouter_cache_latency_milliseconds` | Histogram | `spec`, `apiInterface`, `method` | Cache lookup latency. |

#### CSM state-store sizes (diagnostics)

Expose otherwise black-box Consumer-Session-Manager state so integration tests can
assert `/debug/reset-all` emptied each store. All drop to `0` after a reset.

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_csm_blocked_providers` | Gauge | `spec`, `apiInterface` | Size of the previous-epoch blocked-providers store. |
| `smartrouter_csm_blocked_backup_providers` | Gauge | `spec`, `apiInterface` | Size of the blocked-backup-providers store. |
| `smartrouter_csm_sticky_sessions` | Gauge | `spec`, `apiInterface` | Live sticky-session affinities. |
| `smartrouter_csm_reported_providers` | Gauge | `spec`, `apiInterface` | Size of the reported-providers register. |

---

## Shared metrics

### Classified errors — `smartrouter_errors_*`

Defined in [`error_metrics.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/metrics/error_metrics.go).
The `error_name` and `error_category` labels come from the classifier registry — see
[Error codes](error-codes.md) for the full set of names and their retryability.

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_errors_total` | Counter | `error_name`, `error_category`, `retryable`, `chain_id` | Errors classified by name, category, retryability, and chain. |
