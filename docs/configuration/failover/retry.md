# Retry

When an upstream returns a **retryable** error, Smart Router rotates to a different node and tries again. The pool is filtered to nodes that haven't already failed for this relay; the [RPC Node selection](../projects/selection-policies.md) policy picks the next candidate.

## What's retryable

The error classifier ([`protocol/common/error_registry.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/common/error_registry.go)) assigns every failure a coded classification with a **retryable** flag. The flag is the primary signal: a non-retryable classification short-circuits retries for *every* terminal error — connection failures, malformed requests, and chain-level rejections alike.

| Layer | Examples | Behaviour |
|---|---|---|
| **`PROTOCOL_*`** (connection / session) | network timeout, connection reset, node unavailable | mostly retryable — rotate node |
| **`NODE_*`** (node response) | 5xx upstream, rate limited, node syncing → retryable; method not found / unimplemented → terminal | per-code; unsupported methods are zero-CU and cached |
| **`CHAIN_*`** (execution / state) | `eth_call` reverted, out of gas, nonce too low → terminal; block/tx not found, state pruned → retryable | per-code |
| **`USER_*`** (bad request) | malformed JSON, invalid params, invalid address | always terminal; charges normal CU |

The full code tables and per-code retryability are in [Error codes](../../reference/error-codes.md).

Same-response retries are deduplicated: if two nodes return the identical response, Smart Router won't burn a third attempt looking for a different answer. The dedup is a hash cache in [`protocol/lavaprotocol/relay_retries_manager.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/lavaprotocol/relay_retries_manager.go).

## Limits

| Limit | Value | Notes |
|---|---|---|
| Max attempts per relay | 10 | hardcoded constant `MaximumNumberOfTickerRelayRetries` |
| Overall budget | `--default-processing-timeout` | ends retries even if attempts remain |
| Per-attempt budget | `--min-relay-timeout` floor, or `lava-relay-timeout` header | retries get the same per-attempt timeout |

The 10-attempt cap is not currently exposed as a YAML knob.

## When retries kick in

Retries are **always on** for retryable errors. There's no opt-out for individual relays. If you want a single attempt with no retry on failure, the closest control is to lower the overall `--default-processing-timeout` and accept that the first failure surfaces immediately — but you'll lose other failover behaviour at the same time.

## When retries don't help

Some classes of failure look retryable on the wire but won't recover by switching nodes — for example:

- A bad request (malformed JSON, unknown method) — always terminal.
- A consensus-level error returned by every healthy node (the chain itself rejected it).
- A method your nodes genuinely don't support.

The classifier handles these cases without burning the budget.

## Pinning to one node

The `Lava-Provider-Address` header pins the request to a specific upstream. If that upstream fails, retry kicks in **on the rest of the pool** — pinning isn't a way to disable retry. See [Directives](../../api/directives.md).

## Observability

| Metric | Meaning |
|---|---|
| `smartrouter_retries_total` | retry attempts triggered (beyond the first try) |
| `smartrouter_retries_success_total` / `smartrouter_retries_failed_total` | retried requests that succeeded / failed |
| `smartrouter_retry_attempts` | histogram of attempts per retried request (buckets 1…10) |
| Tracing | each retry attempt is a span; correlate via the trace ID in response headers |

See the [Metrics reference](../../reference/metrics.md#retries) for labels and types.
