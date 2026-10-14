---
title: "Circuit breaker"
description: "Trip a circuit breaker to stop routing traffic to unhealthy providers until they recover."
---

# Circuit breaker

The circuit breaker fails a relay fast when the **node pool itself is exhausted** and every retry returns "no nodes available". Without it, the relay would loop until the overall timeout fires.

## What it does

The circuit breaker trips when the relay state machine sees consecutive `PairingListEmptyError`s. This error means every healthy node has already been tried and excluded for this relay. The relay then fails fast with a clear error, instead of continuing to retry.

| Parameter | Default | Meaning |
|---|---|---|
| `EnableCircuitBreaker` | `true` for SmartRouter | turns the breaker on or off |
| `CircuitBreakerThreshold` | `2` | consecutive pairing-empty errors before tripping |

The breaker is **per-relay**, not per-node. It does not take a node out of rotation. It only stops the current request from looping. Node-level cooldowns (taking a misbehaving upstream out of rotation for a period) are handled by the [provider optimizer](../projects/selection-policies.md) through QoS scoring.

## When it kicks in

The breaker usually trips in one of three cases:

1. **All nodes excluded by integrity.** Every node is too far behind the chain head and `EnableWaitForCatchup` is off, so the lag filter empties the pool. After 2 attempts to refill it, the breaker trips.
2. **All nodes errored.** Every retry attempt has returned a retryable error, and the pool is exhausted.
3. **Misconfiguration.** Endpoint definitions do not match the request, so no node is eligible at all. The breaker error shows this quickly, instead of a timeout that hides the misconfiguration.

## Why this is configurable

A lower threshold (e.g. `CircuitBreakerThreshold: 1`) makes failures show immediately. This is useful in development, where you want a clear error to debug a misconfiguration. A higher threshold (`5`+) gives a pool that is empty for a short time the chance to recover.

The default of `2` is a balance: one false positive does not trip the breaker, but sustained failure does.

## Smart Router only

`StateMachineConfig` notes that the circuit breaker is enabled in the SmartRouter state machine, not the consumer state machine ([`protocol/relaycore/interfaces.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/relaycore/interfaces.go)). If you run anything else built on the relay state machine, the breaker may not apply.

## Configuration

The breaker is currently configured when the state machine is built, not through YAML. To change the threshold, you change the code, not the config. A future release will expose this as a YAML setting.

## Observability

The breaker has no dedicated counter. Use logs, traces, and the error and CSM series to observe it:

| Signal | Meaning |
|---|---|
| Logs | `pairing list empty` warnings appear before a trip |
| Tracing | a trip is a span event with the consecutive-error count |
| `smartrouter_total_errored` | a tripped relay counts as an errored relay |
| `smartrouter_csm_blocked_providers` | when this gauge equals the pool size, every node is excluded. This is the condition that trips the breaker |

See the [Metrics reference](../../reference/metrics.md#csm-state-store-sizes-diagnostics) for the CSM diagnostics gauges.
