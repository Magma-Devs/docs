---
title: "Retry"
description: "Retry failed responses automatically on a different provider."
---

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

A retry re-sends the **same request** to a different node. It does not change what the request asks for: no extension such as `archive` is added on retry, so the retry pool is the same pool the first attempt drew from, minus the nodes that already failed. Each request starts with its own retry budget; nothing is remembered between requests.

Archive routing is decided once, before the first attempt, from the block the request names. Requests whose block the router cannot read are not routed to archive automatically: methods that name a block or transaction by hash (such as `eth_getTransactionReceipt` or `debug_traceTransaction`), and [EIP-1898](https://eips.ethereum.org/EIPS/eip-1898) block objects such as `{"blockHash": …}` or `{"blockNumber": …}`. To send one of those to an archive node, set the [`lava-extension: archive`](../../api/directives.md#override-the-extension) directive.

## Limits

| Limit | Value | Notes |
|---|---|---|
| Error-retry limit | `--set-relay-retry-limit` (default `2`) | Errors tolerated before the relay gives up. `0` disables retries entirely. This is the knob you tune. |
| Hard attempt ceiling | `10` | Hardcoded constant `MaximumNumberOfTickerRelayRetries` — an upper bound on *total* attempts including ticker-driven [hedges](hedge.md), separate from the error-retry limit and not exposed as a flag. |
| Overall budget | `--default-processing-timeout` (default `30s`) | Ends retries even if attempts remain. |
| Per-attempt window | `--min-relay-timeout` floor, or `lava-relay-timeout` header | When the window passes, the next node is tried in parallel; the attempt in flight keeps running. See [Timeout](timeout.md). |

The cap you actually control is `--set-relay-retry-limit`: the error-retry path stops
after that many errors (default 2). The hardcoded `10` is only the ceiling the
ticker/hedge path can reach — most relays stop far sooner.

## Turning retries down or off

Retries are on by default, tolerating `--set-relay-retry-limit` errors (default 2). Change that with the flag:

- `--set-relay-retry-limit 0` — **disable retries**: the first error surfaces immediately.
- `--set-relay-retry-limit 5` — tolerate more errors before giving up.

This is a global startup flag, not a per-relay control — there's no per-request header to disable retry for a single call.

## Batch requests

**By default, a JSON-RPC batch request gets no automatic retry and no failover.** If the node that received the batch returns an error, that result goes back to the client. The router does not resend the batch to another node, either as a retry or as a [hedge](hedge.md).

This is deliberate. A batch can include a write, such as `eth_sendRawTransaction`, next to reads. Resending the batch would resend the write. To retry a failed batch, have the client resend only the sub-requests that are safe to repeat.

There is one exception. If every attempt so far failed only because the node was rate-limited (`429`), nothing ran, so the batch moves to another node like any other rate-limited request.

Three startup flags control batch handling:

| Flag | Default | Effect |
|---|---|---|
| `--disable-batch-request-retry` | `true` | Batches get no retry or failover. Set it to `false` to retry batches like single requests; only do this if your clients never put writes in a batch. |
| `--batch-node-error-on-any` | `false` | Decides when a batch response counts as a node error. By default, a batch is an error only if **no** sub-request succeeded; one success hides failed sub-requests. Set it to `true` to count a batch as an error if **any** sub-request failed. |
| `--max-batch-request-size` | `0` (unlimited) | Largest batch accepted. A larger batch is rejected before it reaches a node, with [`PROTOCOL_BATCH_SIZE_EXCEEDED`](../../reference/error-codes.md) (`1022`). |

With the default `--disable-batch-request-retry true`, `--batch-node-error-on-any` doesn't change whether a batch is retried. It still decides whether the batch response counts as a node error.

## When retries don't help

Some classes of failure look retryable on the wire but won't recover by switching nodes — for example:

- A bad request (malformed JSON, unknown method) — always terminal.
- A consensus-level error returned by every healthy node (the chain itself rejected it).
- A method your nodes genuinely don't support.

The classifier handles these cases without burning the budget.

## Rate-limited upstreams

A `429` is retryable — the relay rotates to another node like any other retryable
error — but the node that said it is treated differently from one that failed. A
rate-limited node is healthy and busy, so the attempt is scored as neither a failure nor
a success (no availability or latency sample), and the node is **held off**: selection
skips it for the rest of this relay and for later relays until the hold-off expires.

- **How long.** If the upstream sent `Retry-After`, the hold-off is at least that long
  (capped at 1h). Otherwise it starts at 30s and doubles on each consecutive `429` from
  the same URL, capped at 30m. Up to 20% jitter is added so a fleet held off by the same
  vendor does not come back in one burst.
- **Account-wide caps.** When two different URLs of the same provider are held off at
  once, the whole provider is held off on every chain — a vendor cap is usually
  per-account, and per-URL hold-offs alone would keep hammering the account through its
  other chains.
- **Any answer clears it.** Once the node answers a request — success or a genuine error
  — its hold-off and strike count are dropped.
- **You still get an answer.** If every candidate is held off, the one that expires
  soonest is used anyway; the router never synthesizes a `429` to the client, and
  `Retry-After` is never forwarded. A `lava-select-provider` pin and existing sticky
  sessions bypass the hold-off — an explicit ask outranks it.

The same hold-off covers spec re-verification, recovery probes, and WebSocket
subscriptions, so a node that said stop is not re-probed on a fixed cadence either.

## Pinning to one node

The `lava-select-provider` header pins the request to a specific upstream. If that upstream fails, retry kicks in **on the rest of the pool** — pinning isn't a way to disable retry. See [Directives](../../api/directives.md).

## Observability

| Metric | Meaning |
|---|---|
| `smartrouter_retries_total` | retry attempts triggered (beyond the first try) |
| `smartrouter_retries_success_total` / `smartrouter_retries_failed_total` | retried requests that succeeded / failed |
| `smartrouter_retry_attempts` | histogram of attempts per retried request (buckets 1…10) |
| `smartrouter_rate_limit_holdoffs_total` | hold-off events by `provider` and `event` (`recorded` / `escalated` / `cleared`) — the signal that an upstream is rate-limiting you |
| `smartrouter_rate_limit_holdoff_seconds` | histogram of applied hold-off durations, per `provider` |
| Tracing | each retry attempt is a span; correlate via the trace ID in response headers |

See the [Metrics reference](../../reference/metrics.md#retries) for labels and types, and
[Rate-limit hold-off](../../reference/metrics.md#rate-limit-hold-off) for the hold-off pair.
