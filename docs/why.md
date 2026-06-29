# Why Smart Router?

RPC proxies have been built in-house thousands of times — along with the failover, caching, and monitoring that surround them. Smart Router is that layer as a standard, actively maintained component.

<p class="intro-lede">Instead of building and maintaining your own RPC proxy, you get multi-chain support across EVM and non-EVM networks, automatic failover, data cross-validation, built-in observability, caching, and more.</p>

![Smart Router topology — your app to upstreams via Smart Router with shared cache](assets/diagrams/topology.svg)

## Failover

Smart Router's failovers kick in under different scenarios, or "incidents" — for example, if an upstream is unavailable, returns errors, returns stale data, takes too long, or times out.

[Failover & retry →](configuration/failover/index.md)

## Cross-validation

Reads can be sent to several upstreams in parallel and returned successfully only once the quorum criteria are reached. This stops conflicting or potentially malicious responses from flowing downstream.

[Cross-validation →](configuration/failover/cross-validation.md)

## Caching

A block-aware cache serves repeat reads without hitting an upstream, while avoiding serving stale data. It can be shared across router replicas, significantly reducing upstream calls and latency.

[Cache →](deployment/cache.md)

## Transaction broadcasting

Write methods (`eth_sendRawTransaction` and equivalents) are broadcast to all eligible upstreams in parallel to increase the success rate and speed of transactions.

[Write fan-out →](configuration/failover/hedge.md)

## Multi-chain

Serves all standard blockchain API formats: JSON-RPC, REST, gRPC, Tendermint, and WebSocket. Supports EVM chains, Solana, UTXO chains, Cosmos chains, and other custom networks. Chains are defined by JSON specs, so adding one requires no code change.

[Supported chains →](reference/chains/index.md)

## Observability

Prometheus metrics, OpenTelemetry traces, structured logs, and a typed error taxonomy cover the full request lifecycle — along with a prebuilt dashboard for easy, immediate observability out of the box.

[Observability →](reference/observability/index.md) · [Metrics →](reference/metrics.md) · [Dashboard →](deployment/dashboard.md)

## Enterprise

These docs cover the self-hosted, source-available edition. Enterprise support, SLAs, and custom features are available under a separate license.

[Talk to us →](https://magmadevs.com/contact)
