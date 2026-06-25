# Supported chains

Smart Router serves any chain described by a JSON [chain spec](specs.md) — no code
change, no rebuild. It ships knowing a handful of chains out of the box and resolves the
rest from the [`Magma-Devs/lava-specs`](https://github.com/Magma-Devs/lava-specs) catalog
at startup.

New here? Read [Chain specs](specs.md) first — what a spec is and how the router loads
it. Then see [Examples](examples/index.md) for ready-to-run configs and per-chain
walkthroughs — [Ethereum](ethereum.md), [Arbitrum](arbitrum.md), [Base](base.md),
[Lava](lava.md), and [Solana](solana.md).

## Browse chains

The catalog holds **67 spec files** spanning **59 mainnets and 60 testnets**. Search or
filter by ecosystem below; each card shows the chain's networks (Mainnet / Testnet) and
the API protocols it exposes. The **↗** opens the chain's spec on GitHub.

<div id="chains-explorer" data-icon-base="../../assets/chains/"></div>

## Need a chain that isn't listed?

The catalog is maintained by Magma. If the chain you need isn't there,
[open an issue](https://github.com/Magma-Devs/smart-router/issues) describing the chain,
the API interface (JSON-RPC / REST / gRPC / Tendermint RPC), and one or two reference
upstream nodes, and we'll add it to the catalog.
