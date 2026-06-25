# Supported chains

Smart Router serves any chain described by a JSON [chain spec](specs.md) — no code
change, no rebuild. It ships knowing a handful of chains out of the box and resolves the
rest from the [`Magma-Devs/lava-specs`](https://github.com/Magma-Devs/lava-specs) catalog
at startup.

New here? Read [Chain specs](specs.md) first — what a spec is and how the router loads
it. The pages for [Ethereum](ethereum.md) and [Lava](lava.md) cover those two in detail.

## Browse chains

The catalog holds **75 spec files** spanning **67 mainnets and 64 testnets**. Search or
filter by ecosystem below; each card shows the chain's networks (Mainnet / Testnet) and
the API protocols it exposes. The **↗** opens the chain's spec on GitHub.

<div id="chains-explorer" data-icon-base="../../assets/chains/"></div>

## Need a chain that isn't listed?

The catalog is maintained by Magma. If the chain you need isn't there,
[open an issue](https://github.com/Magma-Devs/smart-router/issues) describing the chain,
the API interface (JSON-RPC / REST / gRPC / Tendermint RPC), and one or two reference
upstream nodes, and we'll add it to the catalog.
