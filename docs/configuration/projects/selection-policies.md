---
title: "RPC node selection"
description: "QoS-weighted provider selection by latency, sync status and availability, tuned per method category."
---

# RPC Node selection

Smart Router sends every relay through a QoS-weighted selector. The selector scores RPC nodes on latency, sync freshness and reliability, then picks one according to the **strategy** you configure.

## How selection works

1. The chain parser identifies the request's category (latest vs. archive, heavy vs. light, free vs. paid).
2. The provider optimizer narrows the pool to upstreams that support the relevant API interface and category.
3. The weighted selector scores each candidate on:
    - **Latency** - recent observed response times.
    - **Sync** - how close the node is to the chain head.
    - **Availability** - recent error and timeout rates.
4. The active strategy adjusts those weights (see below).
5. The selector makes a weighted-random pick. A configurable minimum-selection floor keeps every healthy node in rotation.

Source: [`protocol/provideroptimizer/provider_optimizer.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/provideroptimizer/provider_optimizer.go), [`weighted_selector.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/provideroptimizer/weighted_selector.go).

## Strategies

| Strategy (`--strategy` value) | Optimizes for | When to use |
|---|---|---|
| `balanced` *(default)* | latency + sync + availability | most workloads |
| `latency` | lowest response time | latency-sensitive reads (UI, fast quote) |
| `sync-freshness` | node closest to chain head | indexers, mempool watchers |
| `accuracy` | higher accuracy at higher cost; diversifies node selection (like `distributed`; no direct link to cross-validation) | financial / critical reads |
| `distributed` | spread across nodes | avoiding hot spots, fairness |
| `cost` | cheapest per compute unit | high-volume non-critical traffic |
| `privacy` | pins to a single provider per stream *(not fully implemented)* | minimising correlation across calls |

## Configuring it

Pick a strategy at startup with the `--strategy` flag:

```bash
smartrouter config.yml --use-static-spec specs/ --strategy latency
```

To tune the score weights directly, use the `--qos-*` flags:
`--qos-latency-weight`, `--qos-sync-weight`, `--qos-availability-weight`,
`--qos-stake-weight`, and `--qos-min-selection-chance` (the floor that keeps every
healthy node in rotation). You set these weights separately from `--strategy`. A
strategy changes the shape of each node's per-score curve. It does **not** adjust the
weights. See the [CLI reference](../../reference/cli.md#rpc-node-selection-qos).

## Per-request override

To send a single request to a specific node, set the `lava-select-provider` header. The optimizer is skipped for that request, but failover policies still apply. See [Directives](../../api/directives.md).

## Related

- [Failover & retry](../failover/index.md) - what happens when the picked node fails or returns suspect data
- [Hedge](../failover/hedge.md) - race two nodes in parallel
- [Cross-validation](../failover/cross-validation.md) - require agreement across RPC nodes
