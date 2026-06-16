# Supported chains

Smart Router is **chain-agnostic** — every chain it serves is described by a JSON spec. Specs declare the chain's API methods, parser rules, finality parameters, and capability flags. Pass a directory of specs at startup:

```bash
smartrouter config.yml --use-static-spec specs/
```

## Where specs live

There are two sources, served by the same loader:

| Source | What's in it | Use when |
|---|---|---|
| **Bundled** — [`specs/`](https://github.com/Magma-Devs/smart-router/tree/main/specs) in this repo | 2 production chains + 3 reusable Cosmos building blocks (the ones used by the example configs) | quickest start; what `./scripts/pre_setups/init_smartrouter_*.sh` uses |
| **Catalog** — [`Magma-Devs/lava-specs`](https://github.com/Magma-Devs/lava-specs) | 75 specs spanning every major ecosystem, kept up-to-date | production deployments serving any chain beyond Ethereum + Lava |

Smart Router ships with a spec fetcher ([`utils/specfetcher`](https://github.com/Magma-Devs/smart-router/tree/main/utils/specfetcher)) that pulls a chain spec directly from a GitHub URL at startup — point it at any subdirectory of `lava-specs`, no manual copy step needed.

## Browse chains

The [`Magma-Devs/lava-specs`](https://github.com/Magma-Devs/lava-specs) catalog holds **75 spec files** spanning **67 mainnets and 64 testnets**. Search or filter by ecosystem below; each card shows the chain's networks (Mainnet / Testnet) and the API protocols it exposes. The **↗** opens the chain's spec on GitHub.

<div id="chains-explorer" data-icon-base="../../assets/chains/"></div>

## Building blocks (composed by other specs, not served directly)

These specs are imported by the chain specs above to share common API surfaces; they have no chain of their own.

| Spec | Role |
|---|---|
| [`cosmossdk.json`](https://github.com/Magma-Devs/lava-specs/blob/main/cosmossdk.json) | base Cosmos SDK surface |
| [`cosmossdk_full.json`](https://github.com/Magma-Devs/lava-specs/blob/main/cosmossdk_full.json) | Cosmos chains needing extended methods |
| [`cosmossdkv45.json`](https://github.com/Magma-Devs/lava-specs/blob/main/cosmossdkv45.json) | older Cosmos SDK v0.45 chains |
| [`cosmossdkv50.json`](https://github.com/Magma-Devs/lava-specs/blob/main/cosmossdkv50.json) | newer Cosmos SDK v0.50 chains |
| [`cosmoswasm.json`](https://github.com/Magma-Devs/lava-specs/blob/main/cosmoswasm.json) | CosmWasm-enabled chains |
| [`tendermint.json`](https://github.com/Magma-Devs/lava-specs/blob/main/tendermint.json) | every Tendermint-based chain |
| [`ibc.json`](https://github.com/Magma-Devs/lava-specs/blob/main/ibc.json) | every IBC-capable chain |
| [`ethermint.json`](https://github.com/Magma-Devs/lava-specs/blob/main/ethermint.json) | EVM-on-Cosmos base, imported by Evmos |

## Need a chain that isn't listed?

The spec catalog is maintained by Magma — Smart Router loads specs from it. If the chain you need isn't listed, [open an issue](https://github.com/Magma-Devs/smart-router/issues) describing the chain, the API interface (JSON-RPC / REST / gRPC / Tendermint RPC), and one or two upstream providers we can use as a reference, and we'll add it to the catalog.
