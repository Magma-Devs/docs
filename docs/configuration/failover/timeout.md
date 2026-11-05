---
title: "Timeout"
description: "Configure per-request and per-provider timeouts."
---

# Timeout

Two timeouts apply to every relay: an **overall budget** for the whole request, and a **per-attempt window** that sets when the next node is tried. Hedging and retries run inside the budget.

## The two timeouts

| Timeout | Default | Set by |
|---|---|---|
| Overall (whole relay) | `30s` | `--default-processing-timeout` CLI flag |
| Per-attempt window | `1s` floor | `--min-relay-timeout` CLI flag, or `lava-relay-timeout` header |

If both are set:

- The **overall** timeout caps the whole relay, including all retries and hedges. When it fires, the client gets the most useful result available (the best partial response, or a timeout error). It is never shorter than the per-attempt window.
- The **per-attempt window** is how long a node is expected to take. When it passes with no answer, Smart Router sends the same request to another node. This is a [hedge](hedge.md). The first attempt is **not** cancelled. It keeps running, and whichever attempt answers first wins. The window is the more important setting for tuning tail latency.

## What happens when the window passes

The window starts the next attempt. It does not end the current one. An attempt ends only when the request ends: a node answers, the [retry policy](retry.md) stops, or the overall budget runs out.

A method that is slower than its window still succeeds, as long as it answers within the overall budget. Until September 2026, the window also cancelled the attempt. A method slower than the window could then fail on every node, even with most of the budget unused. That no longer happens.

A node that has still not answered when the overall budget runs out counts as unresponsive and loses score. A node that was cancelled because another node answered first is not penalized.

If a write (for example `eth_sendRawTransaction`) ends before any node answers, the client gets an HTTP 500. The error says the transaction status is unclear, not that it failed. The write may already have been broadcast, so check on-chain before you resubmit it.

## The header override

Clients can override the per-attempt timeout for a specific request:

```
lava-relay-timeout: 12s
```

Format: any Go duration (`500ms`, `5s`, `1m30s`). The router limits the override:

| Header value | Per-attempt timeout used |
|---|---|
| zero, negative, or not a duration | ignored; the server-derived default applies |
| under `300ms` | `300ms` (*not* the `--min-relay-timeout` floor, so a client can still go below that floor) |
| `300ms` up to the request's own budget | the value as sent |
| above the request's own budget | the request's own budget, or up to `--max-caller-relay-timeout` if the operator set it higher |

The request's own budget is the overall timeout it gets with no header. It is `--default-processing-timeout`, doubled for methods of 50 CU or more, or multiplied by six for hanging, stateful or 100+ CU methods. A method whose own timeout is longer gets that longer value. `--max-caller-relay-timeout` defaults to `0`, so by default the header cannot make the router hold a request any longer than it would without the header.

A value at or above the request's own budget turns [hedging](hedge.md) off for that request, because the per-attempt timeout is also the hedge interval. [Retry](retry.md) after a failed attempt still works, but a node that stops answering holds the request for the whole budget.

The response carries `Lava-Relay-Timeout-Applied` with the per-attempt timeout actually used.

See [Directives](../../api/directives.md).

## When to tune

| Symptom | Adjust |
|---|---|
| p99 latency dominated by one slow attempt | lower `--min-relay-timeout` (hedge sooner) |
| Heavy methods (`debug_*`) hedged on every call | raise `lava-relay-timeout` per request (up to the method's own budget), not the global floor. To go beyond that budget, set `--max-caller-relay-timeout` |
| Whole-relay timeouts in logs | raise `--default-processing-timeout`, or find out why retries do not succeed |
| Many clients hit timeouts on the first attempt | raise `--min-relay-timeout` |

## Common pitfalls

- **Setting the window ≥ overall.** The router does not crash. It raises the overall budget to match the window, so the window never passes before the request ends, and no hedge is ever sent.
- **Setting the window below upstream RTT.** Healthy nodes still answer, but every request gets hedged, so you pay for extra upstream calls on each one. If `smartrouter_hedge_total` tracks your request rate on healthy upstreams, raise the floor.
- **Header override below the floor.** The header is *not* clamped to `--min-relay-timeout`, only to `300ms`. If a client sends `lava-relay-timeout: 100ms`, the attempt gets `300ms` even when `--min-relay-timeout` is `1s`. The flag only sets the server-derived default, not an explicit override.
- **Header override above the budget.** A client that asks for more than the request's own budget gets that budget, unless the operator set `--max-caller-relay-timeout`. Check `Lava-Relay-Timeout-Applied` on the response to see what was used.

## Observability

There is no dedicated timeout counter. Timeouts show up in the latency, retry and error series:

| Metric | Meaning |
|---|---|
| `smartrouter_end_to_end_latency_milliseconds` | router-level end-to-end relay latency (histogram; ms buckets to 30 000) |
| `rpc_endpoint_end_to_end_latency_milliseconds` | per-endpoint latency; use it to find the slow upstream |
| `smartrouter_hedge_total` | hedges sent because an attempt outlived its window |
| `smartrouter_retries_total` | retries triggered when an attempt returns an error |
| `smartrouter_total_errored` | relays that ultimately failed, including overall-budget exhaustion |
| Tracing | each attempt span has a duration and an outcome status |

See the [Metrics reference](../../reference/metrics.md#core-relay-health) for labels and types.
