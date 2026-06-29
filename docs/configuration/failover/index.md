---
title: "Failover & retry"
description: "The configurable failover pipeline — retry, hedge, timeout, integrity checks, and circuit breaking."
---

# Failover & retry

The umbrella for everything Smart Router does when a relay misbehaves: an RPC node is slow, returns an error, or falls behind chain head. Each policy is independent; they compose during a single relay's lifetime.

## Policies

| Policy | Trigger | What it does |
|---|---|---|
| [**Retry**](retry.md) | upstream returns a retryable error | rotates to a different node; tolerates `--set-relay-retry-limit` errors (default 2) |
| [**Hedge**](hedge.md) | request hasn't returned within a tick | fires a parallel attempt to another node; first response wins |
| [**Timeout**](timeout.md) | per-attempt or overall budget exceeded | aborts; lets retry rotate |
| [**Integrity**](integrity.md) | out-of-sync node | pre-request lag check skips lagging nodes before they're picked |
| [**Circuit breaker**](circuit-breaker.md) | the node pool is exhausted | trips the relay early instead of retrying forever |

For catching *wrong* data by comparing answers across nodes, see [Cross-validation](cross-validation.md) — a related correctness control that lives alongside failover.

## How they compose

![Failover pipeline — request flows through integrity, selection, attempt, and branches to success, retry, hedge, or circuit-breaker trip](../../assets/diagrams/failsafe-flow.svg)

The overall timeout (`--default-processing-timeout`) wraps the whole pipeline; if it fires, whatever's most useful is returned. Per-attempt timeouts (`--min-relay-timeout` floor or `lava-relay-timeout` header) bound each individual try.

The orchestrator is the relay state machine in [`protocol/relaycore/unified_relay_state_machine.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/relaycore/unified_relay_state_machine.go). The retryable-vs-terminal classifier is in [`protocol/common/error_registry.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/common/error_registry.go) — see [Error codes](../../reference/error-codes.md).

## What's tunable

Smart Router's failover policies fall into three groups:

| Group | Examples | Where tuned |
|---|---|---|
| CLI flags | `--set-relay-retry-limit`, `--default-processing-timeout`, `--min-relay-timeout` | startup args |
| Per-request headers | `lava-relay-timeout`, `lava-select-provider` | HTTP headers — see [Request headers](../../api/directives.md) |
| Chain-derived defaults | integrity lag threshold, hedge tick | computed from the chain spec; not currently exposed as YAML |

Where a knob isn't tunable, that's called out on the policy's page.

## Observability

Every policy emits Prometheus metrics on the `--metrics-listen-address` endpoint (default `:7779`). Each policy page below names the metric series it emits; the full catalogue is in the [Metrics reference](../../reference/metrics.md). OpenTelemetry traces cover the full relay lifecycle — set `OTEL_EXPORTER_OTLP_ENDPOINT` to point at your collector.
