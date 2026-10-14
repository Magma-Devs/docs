---
title: "Retry"
description: "Retry failed responses automatically on a different provider."
---

# Retry

When an upstream returns a **retryable** error, Smart Router tries the request again on a different node.

For the next attempt, the pool holds only nodes that have not already failed for this relay. The [RPC Node selection](../projects/selection-policies.md) policy picks the next candidate from it.

## What's retryable

The error classifier ([`protocol/common/error_registry.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/common/error_registry.go)) gives every failure a coded classification with a **retryable** flag. This flag is the main signal. A non-retryable classification stops retries at once for *every* terminal error: connection failures, malformed requests and chain-level rejections alike.

| Layer | Examples | Behaviour |
|---|---|---|
| **`PROTOCOL_*`** (connection / session) | network timeout, connection reset, node unavailable | mostly retryable; rotate node |
| **`NODE_*`** (node response) | 5xx upstream, rate limited, node syncing → retryable; method not found / unimplemented → terminal | per-code; unsupported methods are zero-CU and cached |
| **`CHAIN_*`** (execution / state) | `eth_call` reverted, out of gas, nonce too low → terminal; block/tx not found, state pruned → retryable | per-code |
| **`USER_*`** (bad request) | malformed JSON, invalid params, invalid address | always terminal; charges normal CU |

The full code tables and per-code retryability are in [Error codes](../../reference/error-codes.md).

A retry re-sends the **same request** to a different node. It does not change what the request asks for. No extension such as `archive` is added on retry, so the retry pool is the same pool the first attempt used, minus the nodes that already failed. Each request starts with its own retry budget. Nothing is remembered between requests.

The router decides archive routing once, before the first attempt, from the block the request names. If the router cannot read the block from a request, it does not route that request to archive automatically. This covers methods that name a block or transaction by hash (such as `eth_getTransactionReceipt` or `debug_traceTransaction`), and [EIP-1898](https://eips.ethereum.org/EIPS/eip-1898) block objects such as `{"blockHash": …}` or `{"blockNumber": …}`. To send one of those to an archive node, set the [`lava-extension: archive`](../../api/directives.md#override-the-extension) directive.

## Limits

| Limit | Value | Notes |
|---|---|---|
| Error-retry limit | `--set-relay-retry-limit` (default `2`) | Errors tolerated before the relay gives up. `0` turns retries off completely. This is the setting you tune. |
| Hard attempt ceiling | `10` | Hardcoded constant `MaximumNumberOfTickerRelayRetries`. It is an upper bound on *total* attempts, including ticker-driven [hedges](hedge.md). It is separate from the error-retry limit and is not available as a flag. |
| Overall budget | `--default-processing-timeout` (default `30s`) | Ends retries even if attempts remain. |
| Per-attempt window | `--min-relay-timeout` floor, or `lava-relay-timeout` header | When the window passes, the next node is tried in parallel, and the attempt in flight keeps running. See [Timeout](timeout.md). |

The cap you control is `--set-relay-retry-limit`. The error-retry path stops after
that many errors (default 2). The hardcoded `10` is only the ceiling that the
ticker/hedge path can reach. Most relays stop much sooner.

## Turning retries down or off

Retries are on by default and tolerate `--set-relay-retry-limit` errors (default 2). To change this, set the flag:

- `--set-relay-retry-limit 0` - **disable retries**. The first error is returned immediately.
- `--set-relay-retry-limit 5` - tolerate more errors before giving up.

This is a global startup flag, not a per-relay control. No per-request header turns off retry for a single call.

## Batch requests

**By default, a JSON-RPC batch request gets no automatic retry and no failover.** If the node that received the batch returns an error, that result goes back to the client. The router does not resend the batch to another node, either as a retry or as a [hedge](hedge.md).

This is on purpose. A batch can include a write, such as `eth_sendRawTransaction`, next to reads. Resending the batch would resend the write. To retry a failed batch, have the client resend only the sub-requests that are safe to repeat.

There is one exception. If every attempt so far failed only because the node was rate-limited (`429`), nothing ran. The batch then moves to another node like any other rate-limited request.

Three startup flags control batch handling:

| Flag | Default | Effect |
|---|---|---|
| `--disable-batch-request-retry` | `true` | Batches get no retry or failover. Set it to `false` to retry batches like single requests. Only do this if your clients never put writes in a batch. |
| `--batch-node-error-on-any` | `false` | Decides when a batch response counts as a node error. By default, a batch is an error only if **no** sub-request succeeded, so one success hides failed sub-requests. Set it to `true` to count a batch as an error if **any** sub-request failed. |
| `--max-batch-request-size` | `0` (unlimited) | Largest batch accepted. A larger batch is rejected before it reaches a node, with [`PROTOCOL_BATCH_SIZE_EXCEEDED`](../../reference/error-codes.md) (`1022`). |

With the default `--disable-batch-request-retry true`, `--batch-node-error-on-any` does not change whether a batch is retried. It still decides whether the batch response counts as a node error.

## When retries don't help

Some failures look retryable on the wire but do not recover when the router switches nodes. For example:

- A bad request (malformed JSON, unknown method), which is always terminal.
- A consensus-level error returned by every healthy node (the chain itself rejected it).
- A method your nodes do not support.

The classifier handles these cases without using up the budget.

## Rate-limited upstreams

A `429` is retryable, but the node that returned it is treated differently from a node
that failed. The relay moves to another node, as with any other retryable error. A
rate-limited node is healthy but busy, so the attempt counts as neither a failure nor a
success (no availability or latency sample). The node is also **held off**: selection
skips it for the rest of this relay, and for later relays, until the hold-off expires.

- **How long.** If the upstream sent `Retry-After`, the hold-off is at least that long
  (capped at 1h). Otherwise it starts at 30s and doubles on each consecutive `429` from
  the same URL, capped at 30m. Up to 20% jitter is added so a fleet held off by the same
  vendor does not come back in one burst.
- **Account-wide caps.** When two different URLs of the same provider are held off at
  once, the whole provider is held off on every chain. A vendor cap is usually
  per-account, and per-URL hold-offs alone would keep overloading the account through
  its other chains.
- **Any answer clears it.** Once the node answers a request, with a success or a real
  error, its hold-off and strike count are cleared.
- **You still get an answer.** If every candidate is held off, the router uses the one
  whose hold-off expires soonest. The router never creates its own `429` for the client,
  and never forwards `Retry-After`. A `lava-select-provider` pin and existing sticky
  sessions bypass the hold-off, because an explicit request takes priority.

The same hold-off also covers spec re-verification, recovery probes and WebSocket
subscriptions, so a rate-limited node is not re-probed on a fixed schedule either.

## Pinning to one node

The `lava-select-provider` header pins the request to a specific upstream. If that upstream fails, retry runs **on the rest of the pool**. Pinning does not turn off retry. See [Directives](../../api/directives.md).

## Observability

| Metric | Meaning |
|---|---|
| `smartrouter_retries_total` | retry attempts triggered (beyond the first try) |
| `smartrouter_retries_success_total` / `smartrouter_retries_failed_total` | retried requests that succeeded / failed |
| `smartrouter_retry_attempts` | histogram of attempts per retried request (buckets 1…10) |
| `smartrouter_rate_limit_holdoffs_total` | hold-off events by `provider` and `event` (`recorded` / `escalated` / `cleared`). This is the signal that an upstream is rate-limiting you |
| `smartrouter_rate_limit_holdoff_seconds` | histogram of applied hold-off durations, per `provider` |
| Tracing | each retry attempt is a span; use the trace ID in the response headers to correlate them |

See the [Metrics reference](../../reference/metrics.md#retries) for labels and types, and
[Rate-limit hold-off](../../reference/metrics.md#rate-limit-hold-off) for the hold-off pair.
