---
title: "Integrity"
description: "Validate response integrity before returning it to the client."
---

# Integrity

A pre-request check that filters out nodes too far behind the chain head. Protects against single-node data quality issues caused by lag.

## How it works

Before sending a relay, Smart Router compares each candidate node's most recently observed block height against the "seen block" — the freshest height observed across the pool. Nodes behind by more than `EndpointLagThreshold` are dropped from the selection pool for that request.

| Parameter | Default | Meaning |
|---|---|---|
| `EndpointLagThreshold` | derived per-chain (≥ 10 blocks) | max blocks an endpoint can be behind before being skipped |
| `EnableWaitForCatchup` | `false` | wait for endpoints to catch up instead of skipping |
| `MaxWaitTime` | derived per-chain (500ms–5s) | max wait if `EnableWaitForCatchup` is on |

Defaults are computed from the chain spec's block-time and finalization parameters — see [`consistency_config.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/relaycore/consistency_config.go). On Ethereum, this works out to ~10 blocks. On fast chains, more.

The lag check is conservative: with `EnableWaitForCatchup: false` (the default), lagging nodes are simply skipped, so the user never sees their stale state. With `EnableWaitForCatchup: true`, the relay waits up to `MaxWaitTime` for a node to catch up.

## When integrity helps

| Scenario | Integrity catches |
|---|---|
| Node lagging during a deploy or restart | pre-request lag check skips it |
| Node serving stale state from a hot fork | pre-request lag check (if seen block is fresher elsewhere) |
| Node intermittently returning malformed responses | parser errors are routed via [retry](retry.md), not integrity |

## What integrity doesn't do

- It doesn't catch *wrong* data when nodes all agree on the wrong answer. For that, see [cross-validation](cross-validation.md).
- It doesn't validate signatures, Merkle proofs, or anything cryptographic. The reorg-aware cache handles those concerns separately.
- It doesn't check responses *after* they return — once a node passes the lag filter, its response is accepted (subject to [retry](retry.md) on transport-level errors).

## Configuration

The pre-request thresholds are derived from the chain spec. To override per-chain, edit the spec values that feed `NewConsistencyValidationConfig`:

- `allowed_block_lag_for_qos_sync` — feeds `EndpointLagThreshold = max(2 × this, finalization_distance, 10)`.
- `block_distance_for_finalized_data` — also feeds the threshold.
- `average_block_time` — feeds `MaxWaitTime = clamp(2 × this, 500ms, 5s)`.

The `EnableWaitForCatchup` flag is not currently exposed as a CLI/YAML knob.

## Observability

The pre-request lag filter has no dedicated counter; observe it through the consistency series and traces:

| Metric | Meaning |
|---|---|
| `smartrouter_consistency_total` | requests enforcing consistency (seen-block) |
| `smartrouter_consistency_success_total` / `smartrouter_consistency_failed_total` | consistency-enforced requests that succeeded / failed |
| `rpc_endpoint_latest_block` | per-endpoint head — compare across endpoints to see which are lagging |
| Tracing | lag check emits span events with `lag_blocks` and decision (`skipped` / `kept` / `waited`) |

See the [Metrics reference](../../reference/metrics.md#consistency) for labels and types.
