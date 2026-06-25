# Circuit breaker

Protects against the case where the **node pool itself is exhausted** — every retry returns "no nodes available" and the relay would otherwise loop until the overall timeout fires.

## What it does

When the relay state machine sees consecutive `PairingListEmptyError`s — meaning every healthy node has already been tried and excluded for this relay — the circuit breaker trips. Instead of continuing to attempt and retry, the relay fails fast with a clear error.

| Parameter | Default | Meaning |
|---|---|---|
| `EnableCircuitBreaker` | `true` for SmartRouter | toggles the breaker |
| `CircuitBreakerThreshold` | `2` | consecutive pairing-empty errors before tripping |

The breaker is **per-relay**, not per-node — it doesn't take a node out of rotation. It just stops the current request from looping. Node-level cooldowns (taking a misbehaving upstream out of rotation for a window) are handled by the [provider optimizer](../projects/selection-policies.md) via QoS scoring.

## When it kicks in

Three common scenarios:

1. **All nodes excluded by integrity.** Every node is too far behind chain head and `EnableWaitForCatchup` is off — the lag filter empties the pool. After 2 attempts at refilling, the breaker trips.
2. **All nodes errored.** Every retry attempt has come back retryable, exhausting the pool.
3. **Misconfiguration.** Endpoint definitions don't match the request — no node is eligible at all. Surfacing the breaker error quickly is better than letting the timeout hide the misconfig.

## Why this is configurable

Lowering the threshold (e.g. `CircuitBreakerThreshold: 1`) makes failures surface immediately — useful in dev, where you want a clear error to debug a misconfiguration. Raising it (`5`+) lets transient pool emptiness self-heal.

The default of `2` is a balance: one false-positive doesn't trip the breaker, sustained failure does.

## Smart Router only

`StateMachineConfig` notes circuit breaker is enabled in the SmartRouter state machine, not the consumer state machine ([`protocol/relaycore/interfaces.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/relaycore/interfaces.go)). If you're running anything else built on the relay state machine, the breaker may not apply.

## Configuration

Currently configured at the state-machine-construction level rather than through YAML. To change the threshold, the change is in code, not config. A future release will expose this as a YAML knob.

## Observability

The breaker has no dedicated counter; observe it through logs, traces, and the error/CSM series:

| Signal | Meaning |
|---|---|
| Logs | `pairing list empty` warnings precede a trip |
| Tracing | trip is a span event with the consecutive-error count |
| `smartrouter_total_errored` | a tripped relay counts as an errored relay |
| `smartrouter_csm_blocked_providers` | when this gauge equals the pool size, every node is excluded — the condition that trips the breaker |

See the [Metrics reference](../../reference/metrics.md#csm-state-store-sizes-diagnostics) for the CSM diagnostics gauges.
