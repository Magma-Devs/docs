---
title: "Metrics"
description: "Prometheus metrics exposed by Smart Router for routing, cache, and provider health."
---

# Metrics

This page lists every metric Smart Router exposes over Prometheus, with its type, labels,
and meaning, so you can look up any series you see on a dashboard or in an alert.

Metrics are defined under [`protocol/metrics/`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/metrics).
The exception is the [rate-limit hold-off](#rate-limit-hold-off) pair: the registry that
owns those events emits them itself from
[`protocol/holdoff/metrics.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/holdoff/metrics.go).

The classified-error counter [`smartrouter_errors_total`](#classified-errors-smartrouter_errors_) is
split by error name and category. See [Error codes](error-codes.md) for the full list of
names it can carry.

If you run the [dashboard overlay](../deployment/docker-compose.md#add-the-dashboard), it
already has pre-built panels for these series. This page is the reference behind them,
with recipes for building your own.

## What to watch

If you only graph a few things, graph these:

| Question | Metric(s) |
| --- | --- |
| Is the router up and serving? | `smartrouter_overall_health`, `smartrouter_total_relays_serviced` |
| Are requests failing? | `smartrouter_total_errored`, `smartrouter_errors_total` (by `error_category` / `retryable`) |
| How fast is it? | `smartrouter_end_to_end_latency_milliseconds` (histogram → p50/p95/p99) |
| Is a node degrading? | `rpc_endpoint_overall_health`, `rpc_endpoint_end_to_end_latency_milliseconds`, `rpc_endpoint_latest_block` |
| How much load does the router itself put on your node? | `rpc_endpoint_tracker_requests_total` (by `kind`) - the router's own polling, separate from the relays you sent it; `rpc_endpoint_tracker_gate_skips_total` (by `source`) - the polls it chose not to send |
| How often does the router retry or hedge? | `smartrouter_retries_total`, `smartrouter_hedge_total` |
| Is an upstream rate-limiting you? | `smartrouter_rate_limit_holdoffs_total` (by `provider` / `event`), `smartrouter_rate_limit_holdoff_seconds` |
| Is the cache helping? | `smartrouter_cache_success_total` / `smartrouter_cache_requests_total` |
| What do batched calls look like? | `smartrouter_requests_total{method=~"batch:.*"}`, `smartrouter_batch_size` |

## Querying - PromQL recipes

Starting points you can copy. Adjust the labels and windows to fit your setup.

```promql
# Request error ratio (last 5m)
sum(rate(smartrouter_total_errored[5m]))
  / sum(rate(smartrouter_total_relays_serviced[5m]))

# p99 end-to-end latency, per chain (ms)
histogram_quantile(0.99,
  sum by (spec, le) (rate(smartrouter_end_to_end_latency_milliseconds_bucket[5m])))

# Cache hit ratio (both tiers; add cache_tier="primary" to scope it)
sum(rate(smartrouter_cache_success_total[5m]))
  / sum(rate(smartrouter_cache_requests_total[5m]))

# Is the secondary cache broken, or just cold?
sum by (outcome) (rate(smartrouter_cache_failed_total{cache_tier="secondary"}[5m]))

# Retry rate per relay (how often the first attempt isn't enough)
sum(rate(smartrouter_retries_total[5m]))
  / sum(rate(smartrouter_total_relays_serviced[5m]))

# Non-retryable (terminal) errors only - usually client/chain problems, not infra
sum by (error_name) (rate(smartrouter_errors_total{retryable="false"}[5m]))

# Nodes currently unhealthy
rpc_endpoint_overall_health == 0

# Per-node request share (is selection lopsided?)
sum by (provider_address) (rate(smartrouter_requests_total[5m]))

# Upstreams currently tripping their rate-limit caps
sum by (provider) (increase(smartrouter_rate_limit_holdoffs_total{event="recorded"}[15m])) > 0

# Busiest batch shapes, and how big those batches run
topk(10, sum by (method) (rate(smartrouter_requests_total{method=~"batch:.*"}[5m])))
histogram_quantile(0.95,
  sum by (spec, le) (rate(smartrouter_batch_size_bucket[5m])))

# Error ratio per batch shape (which shapes are failing?)
sum by (method) (rate(smartrouter_requests_failed_total{method=~"batch:.*"}[5m]))
  / sum by (method) (rate(smartrouter_requests_total{method=~"batch:.*"}[5m]))
```

## Suggested alerts

Starting points. Tune the thresholds to your traffic.

| Alert | Expression sketch | Why |
| --- | --- | --- |
| Router unhealthy | `smartrouter_overall_health == 0 for 1m` | No endpoint is serving. |
| High error ratio | error-ratio recipe `> 0.05 for 5m` | Something broke upstream or in config. |
| Latency regression | p99 recipe `> 2000 for 10m` | Tail latency degraded. |
| Node down | `rpc_endpoint_overall_health == 0 for 5m` | A configured upstream is out. |
| Cache cold | hit-ratio recipe `< 0.2 for 30m` | The cache is misconfigured or bypassed. This is a cost and latency risk. |
| RESP cache backend unreachable | `smartrouter_resp_cache_connected == 0 for 5m` | Redis/Valkey is down or rejecting auth. Relays still succeed through the upstreams, so nothing else alerts, but you pay for every read. |
| Post-finality divergence | `increase(smartrouter_cross_validation_mismatch_total{finality="finalized"}[15m]) > 0` | A node disagreed on *finalized* data. This is a high-signal correctness alert. |
| Vendor-wide rate limit | `increase(smartrouter_rate_limit_holdoffs_total{event="escalated"}[1h]) > 0` | Two of a provider's URLs were held off at once, so the router stopped calling that provider on every chain. You are over an account-wide cap, not a per-endpoint one. |
| Batch shapes merging | `increase(smartrouter_batch_signature_overflow_total[1h]) > 0` | Clients send more batch shapes than the breakdown can name, so shapes are merging into `batch:other`. |

## Exposition

The metrics manager starts an HTTP server that serves metrics in Prometheus text format.

| Path | Format | Description |
| --- | --- | --- |
| `/metrics` | Prometheus | All registered metrics ([`promhttp.Handler()`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/metrics/smartrouter_metrics_manager.go#L647)) |
| `/metrics/overall-health` | text | `200 Health status OK` if ≥1 endpoint is healthy, else `503 Unhealthy`. Fail-closed at boot: it switches to `200` once endpoint setup has verified a provider. Health changes are published immediately. While a chain is unhealthy, the router re-probes it every `--relays-health-unhealthy-interval` (default `15s`). |
| `/metrics/health-overall` | text | Alias of the above, kept for backward compatibility |
| `/readyz` | text | Alias of `/metrics/overall-health` for a Kubernetes readiness probe. It removes the pod from the Service without restarting it. |
| `/livez` | text | Always `200` while the process serves HTTP. Liveness only: it does not check provider health, by design. |

### Configuration

| Flag / env | Default | Effect |
| --- | --- | --- |
| `--metrics-listen-address` | `disabled` | Address to expose Prometheus metrics on, e.g. `:7779` or `localhost:7779`. The value `disabled` turns the metrics server off completely. |
| `--optimizer-qos-sampling-interval` | `1s` | How often the optimizer-QoS sampler refreshes the `rpc_optimizer_selection_score` gauge. When `--usage-otel-enabled` is set, it also emits `optimizer_qos` events to the OTel usage pipeline. |

```bash
# enable, then scrape
smartrouter ... --metrics-listen-address ":7779"
curl http://localhost:7779/metrics
```

The flag name and the `disabled` sentinel value are defined in
[`flags.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/metrics/flags.go#L8-L25).

!!! note "Optimizer scores are always on"
    The optimizer-QoS client is always created, so `rpc_optimizer_selection_score`
    is populated on `/metrics` whatever your telemetry config is. To send these
    reports to a remote system, the router uses the OTel usage pipeline
    (`--usage-otel-enabled`), not a dedicated push address.

### Conventions

- **Latency histograms** all share the same buckets, in **milliseconds**
  ([`buckets.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/metrics/buckets.go#L7)):
  `1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000`.
- **Attempt histograms** (`retry_attempts`, `hedge_attempts`) use integer buckets `1…10`.
- **Common labels**:
    - `spec` - chain spec id (e.g. `ETH1`, `LAV1`).
    - `apiInterface` - `jsonrpc`, `tendermintrpc`, `rest`, `grpc`, `graphql`.
    - `endpoint_id` - the configured upstream RPC endpoint.
    - `provider_address` - node the relay was routed to.
    - `method` - RPC method name. Batch requests carry a
      [batch signature](#batch-requests) instead, e.g. `batch:eth_call+eth_getBalance`.
    - `function` - the RPC method or REST path the relay called. The latency
      histograms and relay counters carry it. It has the same values as `method`;
      `sum by (...)` over it gives the aggregate. Requests to methods outside the
      spec appear as `Default-<method>`.
- **Boolean gauges** encode `1 = true / healthy / present`, `0 = false / unhealthy / absent`.
- **Protocol version** gauges encode `major*1e6 + minor*1e3 + patch`.
- Metrics are registered with `registerOrReuse`, which returns the already-registered
  collector instead of panicking on a duplicate. So re-registration (e.g. across test
  runs that share the default registry) is safe.

### Counting semantics - relays vs client requests

Any dashboard or alert built on the request counters depends on these distinctions.
They were verified against a live router under a controlled load:

- **`smartrouter_requests_total` counts *relays*, not client requests.** A
  cross-validated request increments it once per participant. Cache-served requests
  appear under `provider_address="Cached"`. The router's own chain-tracker and
  verification traffic also lands in it, even with zero client load. Use it for
  per-provider and relay-level views.
- **`smartrouter_end_to_end_latency_milliseconds_count` increments exactly once per
  client request** (cache hits included, internal probes excluded). It is the
  accurate source for "requests served" and RPS. Its `function` label also gives the
  per-method breakdown.
- **`requests_success_total` is transport-level success.** An upstream that answers
  with a JSON-RPC *error object* (invalid params, method not found, execution
  reverted) still counts as a successful relay. The error is recorded separately in
  `node_errors_total` and the classified `smartrouter_errors_total`. So `total −
  success` measures transport and routing failures, not "callers who got an error".
- **Consistency counters:** `consistency_total` = reads that enforced a minimum seen
  block, `consistency_success_total` = checks that **passed**, and
  `consistency_failed_total` = stale responses actually caught. Lazily registered
  families (retries, hedge, cache, cross-validation, ws, classified errors) are
  absent from `/metrics` until the feature first fires. An absent family means zero
  events, not missing instrumentation.

---

## Smart Router metrics

These metrics are specific to running as a Smart Router. They are defined in
[`smartrouter_metrics_manager.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/metrics/smartrouter_metrics_manager.go)
and split into **endpoint-scoped** (`rpc_endpoint_*`) and **router-scoped**
(`smartrouter_*`) families.

### Endpoint-scoped - `rpc_endpoint_*`

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
| `rpc_endpoint_fetch_latest_fails` | Counter | `spec`, `apiInterface`, `endpoint_id` | Latest-block fetch failures. An **event** counter, not a request counter. |
| `rpc_endpoint_fetch_block_fails` | Counter | `spec`, `apiInterface`, `endpoint_id` | Failed specific-block fetches. |
| `rpc_endpoint_fetch_latest_success` | Counter | `spec`, `apiInterface`, `endpoint_id` | New-block **detections** by the chain tracker, not successful requests. |
| `rpc_endpoint_fetch_block_success` | Counter | `spec`, `apiInterface`, `endpoint_id` | Successful specific-block fetches. |
| `rpc_endpoint_tracker_requests_total` | Counter | `spec`, `apiInterface`, `endpoint_id`, `kind` | Requests the chain tracker actually sent upstream, by `kind`: `latest_block`, or `block_hash` (zero unless [`--enable-fork-detection`](cli.md#polling-relief)). This is the only metric that measures tracker **request volume**. |
| `rpc_endpoint_tracker_gate_skips_total` | Counter | `spec`, `apiInterface`, `endpoint_id`, `source` | Poll ticks the tracker skipped because the upstream's tip was already fresh, by `source`: `relay` (served traffic in the last block time) or `peer` (another replica's poll, shared via [`--shared-state`](cli.md#cache-shared-state)). It is the complement of `requests_total`: together they account for every tick. |
| `rpc_endpoint_tracker_gate_errors_total` | Counter | `spec`, `apiInterface`, `endpoint_id`, `op` | Failed calls the fleet gate made to the cache's observation store, by `op`: `fetch` or `publish`. A failed fetch falls back to a local poll. A failed publish costs a peer one real poll. It rises when the sidecar is older than the observation RPC. |

On a multi-replica deployment with `--shared-state`, the fleet-wide
`sum(rate(rpc_endpoint_tracker_requests_total{kind="latest_block"}[5m]))` for an upstream
should settle near a single replica's worth, and `source="peer"` skips should be non-zero on
every replica. If `peer` stays at zero with the flag on, there are three possible causes: the
router is on the [RESP backend](../deployment/cache/redis.md#caveats), which has no peer gate
at all; the replicas are not reaching the same cache; or the cache is reached but the calls
fail, for example because the sidecar is older than the router.
`rpc_endpoint_tracker_gate_errors_total` separates the last cause from the other two. A
failing store raises it; a fleet with nothing to share leaves it flat.

Keep two things in mind when you read the chain-tracker counters:

- **`fetch_latest_success` can read *higher* with fork detection off.** With the
  flag on, a failed block-hash fetch stops the poll cycle before the new-block
  callback fires. So endpoints with unreliable hash fetches under-count detections.
  With the flag off, every detected block is recorded. A rise after you disable the
  flag means the counter now records detections it used to miss, not extra load.
- **`endpoint_id` holds a provider name, and several providers can share one
  physical URL.** The tracker polls per provider, so a bare `sum()` over
  `rpc_endpoint_tracker_requests_total` counts one physical request once per
  provider sharing that URL. When you estimate the load on a metered node, keep
  the `endpoint_id` breakdown (or dedupe by URL) instead of summing everything.

### Optimizer

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `rpc_optimizer_selection_score` | Gauge | `spec`, `endpoint_id`, `score_type` | Periodic optimizer selection score per node, by `score_type`. |

### Router-scoped - `smartrouter_*`

#### Core relay & health

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_total_relays_serviced` | Counter | `spec`, `apiInterface`, `function` | Relays served by the router. |
| `smartrouter_total_errored` | Counter | `spec`, `apiInterface`, `function` | Errored relays. |
| `smartrouter_end_to_end_latency_milliseconds` | Histogram | `spec`, `apiInterface`, `function` | Router-level end-to-end latency. |
| `smartrouter_overall_health` | Gauge | - | Overall router health (1 / 0). |
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

`requests_total` = `success` + `failed`. `read`/`write` split requests into stateless
and stateful. `debug_trace` and `archive` are independent addon flags. A request counted
as `batch` is not counted as read or write.

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

#### Batch requests

A batch has no single method, so its `method` label carries a **batch signature**: the
sorted set of distinct sub-methods, prefixed `batch:`.

```
[eth_call ×30, eth_getBalance]   →   method="batch:eth_call+eth_getBalance"
[eth_call ×3]                    →   method="batch:eth_call"
[eth_call]                       →   method="eth_call"
```

The signature identifies the *shape* of a batch, not its contents in order. Two batches
with the same set of methods share a series, whatever the order of the elements and
however many times each one repeats. The element count is in `smartrouter_batch_size`.
This keeps the label space limited by the number of method *combinations* your clients
send, not by the number of batches they send.

Single-method requests are unaffected: `method="eth_call"` means one `eth_call`. So
`method=~"batch:.*"` and `method!~"batch:.*"` cleanly split batch traffic from single
traffic. Because the signature uses the normal `method` label, every per-method view
(success rate, latency, per-provider share) also works per batch shape.

Cache hits work the same way. A batch served from the router's cache keeps its signature
and, like every cached relay, lands under `provider_address="Cached"` (see
[counting semantics](#counting-semantics-relays-vs-client-requests)). So a per-provider
view of a batch shape lists that pseudo-provider next to the real nodes. Its sizes are
recorded in `smartrouter_batch_size` like any other batch.

A one-element batch produces the same label as a plain single request and is not counted
in `smartrouter_batch_size`. `smartrouter_requests_batch_total` still identifies it as a
batch.

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_batch_size` | Histogram | `spec`, `apiInterface` | Sub-requests per batch (buckets `2, 3, 5, 10, 25, 50, 100, 250, 500`). |
| `smartrouter_batch_signature_overflow_total` | Counter | `spec`, `reason` | Batches whose signature landed in `batch:other`. `reason="cap"`: the chain reached its limit of 64 distinct signatures. `reason="wide"`: one batch mixed more than 8 distinct methods. |

While `smartrouter_batch_signature_overflow_total` is zero, the batch-shape breakdown is
complete. Once it rises, some shapes are merged into `batch:other`. The other series
stay accurate, but the breakdown no longer names every shape.

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

#### Rate-limit hold-off

When an upstream answers `429`, the router stops sending it requests for a while instead
of retrying into the limit. See [Rate-limited upstreams](../configuration/failover/retry.md#rate-limited-upstreams)
for the behaviour. The hold-off registry emits these two series itself, so they cover
every path that talks to an upstream (relays, spec re-verification, recovery probes,
WebSocket subscriptions). A rate-limited relay is released with no QoS sample in either
direction, so a vendor cap does not show up in `rpc_endpoint_selection_score`. This pair
is the direct signal that an upstream is refusing you because of load.

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_rate_limit_holdoffs_total` | Counter | `provider`, `event` | Hold-off registry events. `event` is the closed set `recorded` (a `429` held an endpoint off), `escalated` (the hold-off widened to the whole provider; counted once on the transition, not per refresh), `cleared` (an answer removed a standing penalty; not counted when there was nothing to clear). |
| `smartrouter_rate_limit_holdoff_seconds` | Histogram | `provider` | Applied hold-off duration per `recorded` event, in **seconds** (buckets `15, 30, 60, 120, 300, 600, 1800, 3600`, not the shared millisecond latency buckets). Shows how long upstreams' `Retry-After` values are compared with the exponential default. |

`provider` is the configured provider name on the relay, probe, and re-verification
paths. The WebSocket-subscription path has no provider name and keys the registry by
node URL. Those keys are reduced to `scheme://host` before they become a label. Node URLs
can contain API keys in their path or query, and a credential must never reach a
Prometheus series.

```promql
# how long upstreams are telling us to wait (p90), per provider
histogram_quantile(0.9,
  sum by (provider, le) (rate(smartrouter_rate_limit_holdoff_seconds_bucket[1h])))
```

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
| `smartrouter_cross_validation_mismatch_total` | Counter | `spec`, `apiInterface`, `method`, `group`, `finality` | **Content outliers** by group: one increment per distinct outlier group per successful deterministic cross-validation request (a response whose `SHA256(reply.data)` diverged from the reached consensus). Emitted only when a quorum was reached. `finality` is `finalized` / `not_finalized` / `unknown`; post-finality divergence is the high-signal alert. Cardinality is bounded (keyed by operator-defined `group`, not node address). |
| `smartrouter_cross_validation_failures_total` | Counter | `spec`, `apiInterface`, `method`, `reason` | **Failures by reason**: the by-reason breakdown of `cross_validation_failed_total` (which stays unlabeled, so existing dashboards are unaffected). `reason` is a closed enum: quorum-time `no-agreement` / `insufficient-responses` / `diversity-unmet` / `group-quorum-unmet`, or request-time structural `insufficient-capacity` / `insufficient-groups`. It separates a structural failure (client should fall back) from a quorum disagreement (a retry may help). |

#### Cache

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_cache_requests_total` | Counter | `spec`, `apiInterface`, `method`, `cache_tier` | Cache lookup attempts per tier (`primary` \| `secondary`). A tier that is unconfigured, disconnected, or bypassed emits nothing for that request. |
| `smartrouter_cache_success_total` | Counter | `spec`, `apiInterface`, `method`, `cache_tier` | Cache hits per tier. |
| `smartrouter_cache_failed_total` | Counter | `spec`, `apiInterface`, `method`, `cache_tier`, `outcome` | Non-hit lookups, split by the closed enum `outcome` = `miss` (clean not-found) \| `error` (transport/server error) \| `timeout` (per-lookup budget exceeded). |
| `smartrouter_cache_latency_milliseconds` | Histogram | `spec`, `apiInterface`, `method`, `cache_tier` | Cache lookup latency, observed on **every attempted lookup** - hits and non-hits. |

Per tier, `cache_requests_total` = `cache_success_total` +
`sum without (outcome) (cache_failed_total)`. Note the `sum without`: the identity only
holds after an explicit aggregation across `outcome`.

The `cache_tier="secondary"` series exist only when a
[secondary cache](../deployment/cache/secondary.md) is configured.

!!! warning "Dashboard migration"
    These series previously had no `cache_tier` label, `_failed_total` had no `outcome`,
    and the latency histogram was observed on hits only. Aggregating queries
    (`sum by (spec, method)`) keep working. **Exact label matchers must add
    `cache_tier="primary"`**. Latency-based alerts should expect non-hit observations.
    These usually *lower* percentiles, because misses return faster than hits. Timeouts
    now appear as a bounded tail instead of being invisible.

#### RESP cache backend

These series exist only when the router runs against a [RESP-compatible (Redis/Valkey) cache
backend](../deployment/cache/redis.md). Use them to alert on cache degradation. The shared
`smartrouter_cache_*` series above keep firing unchanged on any backend, but they cannot
tell a backend error or timeout from a clean miss. These series can.

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_resp_cache_failed_total` | Counter | `op`, `kind` | Backend-level operation failures (never clean misses). `op` = `get` \| `set`; `kind` = `error` (unreachable / protocol error) \| `timeout` (budget exceeded, so saturation looks different from an outage). |
| `smartrouter_resp_cache_connection_errors_total` | Counter | - | Failed background health probes (PING, every 10s). |
| `smartrouter_resp_cache_connected` | Gauge | - | `1` while the last health probe succeeded, `0` after a failure. Reachability *transitions* are also logged; nothing is logged in steady state. |
| `smartrouter_resp_cache_pool_total_conns` | Gauge | - | Connections held by the client pool(s). With the read/write split configured, this is write and read summed. |
| `smartrouter_resp_cache_pool_idle_conns` | Gauge | - | Idle pool connections. |
| `smartrouter_resp_cache_pool_stale_conns` | Gauge | - | Stale connections removed from the pool. |

A failing backend never fails relays. Lookups fall back to misses within the caller's
budget, and requests go on to the upstreams. Alert on `smartrouter_resp_cache_connected == 0` or
a `smartrouter_resp_cache_failed_total` rate, not on request errors.

#### CSM state-store sizes (diagnostics)

These gauges show Consumer-Session-Manager state that is otherwise hidden, so
integration tests can check that `/debug/reset-all` emptied each store. All of them drop
to `0` after a reset.

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_csm_blocked_providers` | Gauge | `spec`, `apiInterface` | Size of the previous-epoch blocked-providers store. |
| `smartrouter_csm_blocked_backup_providers` | Gauge | `spec`, `apiInterface` | Size of the blocked-backup-providers store. |
| `smartrouter_csm_sticky_sessions` | Gauge | `spec`, `apiInterface` | Live sticky-session affinities held by this replica. |
| `smartrouter_csm_reported_providers` | Gauge | `spec`, `apiInterface` | Size of the reported-providers register. |

#### Cross-pod sticky sessions

With `--shared-state` and a cache backend, a `lava-stickiness` id resolves to the same
upstream on every replica, through a shared claim. Each resolution is counted by its
outcome:

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_csm_sticky_claims_total` | Counter | `spec`, `apiInterface`, `outcome` | Claim resolutions. `outcome`: `local_hit` (answered from this replica's confirmed claim), `adopted` (routed by a live claim read from the shared registry rather than one held in memory; usually a peer's, see below), `claimed` (this replica made the claim), `lost_race` (a peer's claim naming a different upstream won), `error` (the claim could not be read or written, so the request failed), `no_candidate` (this replica had no upstream to offer), `invalidated` (a claim was dropped because its upstream could not serve here). |

A session that crossed replicas shows up as `adopted`. The `Lava-Provider-Address` reply
header looks the same whether a replica used its own claim or a peer's. But `adopted` alone
does not prove a crossing. A replica that drops its local copy of a claim (`invalidated`)
leaves the shared claim in place, so its next request reads its own claim back and also
counts `adopted`. The same happens after `/debug/reset-all` clears a replica's local table, if
the shared claim outlived the reset. A rise in `adopted` on a replica whose `invalidated`
count did not change, with no reset in between, is a peer's claim.

You can also read the same counts without the metrics port, at `GET /debug/sticky-claims` on
the debug server (`--debug-address`). It returns one row per endpoint:

```json
[{"ChainID": "ETH1", "ApiInterface": "jsonrpc", "PodID": "eth-router-7d9f8b6c5-x2kqp/3fa9c1d2",
  "SharedSticky": true,
  "Outcomes": {"local_hit": 1, "adopted": 1, "claimed": 0, "lost_race": 0,
               "error": 0, "no_candidate": 0, "invalidated": 0}}]
```

`SharedSticky` is `false` on a router without `--shared-state` and a cache backend, where every
count stays `0`. This lets you tell "off" from "never fired". The counts are cumulative
since the router process started, so read them before and after the requests you send.

`PodID` names the process that answered: the pod name, a slash, and a suffix that changes when the
process restarts. The debug port is reached through a Service that balances across the router's
replicas, so two readings in a row can come from different replicas. Compare two readings only when
their `PodID` matches. A new suffix on the same pod name means the process restarted and its
counts began again from `0`.

---

## Shared metrics

### Classified errors - `smartrouter_errors_*`

These metrics are defined in [`error_metrics.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/metrics/error_metrics.go).
The `error_name` and `error_category` labels come from the classifier registry. See
[Error codes](error-codes.md) for the full set of names and their retryability.

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `smartrouter_errors_total` | Counter | `error_name`, `error_category`, `retryable`, `chain_id` | Errors classified by name, category, retryability, and chain. |
