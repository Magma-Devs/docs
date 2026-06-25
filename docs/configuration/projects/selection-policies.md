# RPC Node selection

Smart Router doesn't pick RPC nodes randomly. Every relay flows through a QoS-weighted selector that scores nodes on latency, sync freshness, and reliability — then picks one according to the **strategy** you configure.

## How selection works

1. The chain parser identifies the request's category (latest vs. archive, heavy vs. light, free vs. paid).
2. The provider optimizer narrows the pool to upstreams that support the relevant API interface and category.
3. The weighted selector scores each candidate on:
    - **Latency** — recent observed response times.
    - **Sync** — how close the node is to the chain head.
    - **Availability** — recent error and timeout rates.
4. The active strategy adjusts those weights (see below).
5. A weighted-random pick is made, with a configurable minimum-selection floor that keeps every healthy node in rotation.

Source: [`protocol/provideroptimizer/provider_optimizer.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/provideroptimizer/provider_optimizer.go), [`weighted_selector.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/provideroptimizer/weighted_selector.go).

## Strategies

| Strategy (`--strategy` value) | Optimizes for | When to use |
|---|---|---|
| `balanced` *(default)* | latency + sync + availability | most workloads |
| `latency` | lowest response time | latency-sensitive reads (UI, fast quote) |
| `sync-freshness` | node closest to chain head | indexers, mempool watchers |
| `accuracy` | response correctness (favors nodes passing cross-validation) | financial / critical reads |
| `distributed` | spread across nodes | avoiding hot spots, fairness |
| `cost` | cheapest per compute unit | high-volume non-critical traffic |
| `privacy` | node diversity per stream | minimising correlation across calls |

## Configuring it

Pick a strategy at startup with the `--strategy` flag:

```bash
smartrouter config.yml --use-static-spec specs/ --strategy latency
```

To tune the underlying score weights directly (the strategy presets adjust these), use
the `--qos-*` flags — `--qos-latency-weight`, `--qos-sync-weight`,
`--qos-availability-weight`, `--qos-stake-weight`, and `--qos-min-selection-chance` (the
floor that keeps every healthy node in rotation). See the
[CLI reference](../../reference/cli.md#rpc-node-selection-qos).

## Per-request override

Pin a single request to a specific node with the `Lava-Provider-Address` header. The optimizer is bypassed for that request; failover policies still apply. See [Directives](../../api/directives.md).

## Related

- [Failover & retry](../failover/index.md) — what happens when the picked node fails or returns suspect data
- [Hedge](../failover/hedge.md) — race two nodes in parallel
- [Cross-validation](../failover/consensus.md) — require agreement across RPC nodes
