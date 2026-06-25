# Chain specs

Smart Router is **chain-agnostic**. It has no chain logic baked in — every chain it
serves is described by a **JSON spec**. The spec is what teaches the router how to talk
to a chain: which RPC methods exist, how to parse each one, where finality sits, and
which capabilities (archive, debug, …) a node must have to serve a given method.

This is why adding a chain never means a code change or a new build — it's just another
spec file the router loads at startup.

## What a spec defines

| Part | What it's for |
| --- | --- |
| **API methods** | Every RPC method the chain exposes, per interface (`jsonrpc` / `rest` / `grpc` / `tendermintrpc`). |
| **Parser rules** | How to read a method's request/response — e.g. which param holds the block number — so the router can cache, route, and apply [consistency](../../configuration/failover/integrity.md) correctly. |
| **Categories** | Per-method flags: read vs. write (stateful), whether it's cacheable, which addon/extension it needs (archive, debug). These drive [node selection](../../configuration/projects/selection-policies.md) and caching. |
| **Finality parameters** | Block times and finalization distance — feed the integrity lag gate and finalized-vs-not cache TTLs. |
| **Imports** | A spec can import another (e.g. Arbitrum imports `ETH1`), inheriting its methods and addons. The router resolves imports transitively. |

## How specs are loaded

Pass a spec source at startup with `--use-static-spec` (repeatable; later sources
override earlier ones for the same chain id):

```bash
# a local directory
smartrouter config.yml --use-static-spec specs/

# or straight from a GitHub/GitLab repo — no manual copy
smartrouter config.yml \
  --use-static-spec https://github.com/Magma-Devs/lava-specs/tree/main
```

The same value backs the Docker `SR_SPEC` env var. The built-in
[spec fetcher](https://github.com/Magma-Devs/smart-router/tree/main/utils/specfetcher)
pulls specs from a remote URL at boot and caches them, so a chain that isn't in the
bundled `specs/` still resolves when you point at the catalog.

## Where specs come from

| Source | What's in it | Use when |
|---|---|---|
| **Bundled** — [`specs/`](https://github.com/Magma-Devs/smart-router/tree/main/specs) in the repo | A handful of production chains + reusable Cosmos building blocks (what the example configs use) | quickest start; what the `init_smartrouter_*` scripts use |
| **Catalog** — [`Magma-Devs/lava-specs`](https://github.com/Magma-Devs/lava-specs) | The full set spanning every major ecosystem, kept up to date | production deployments serving any chain beyond the bundled ones |

## Building blocks

Some specs describe no chain of their own — they exist purely to be **imported** by chain
specs that share an API surface. The router never serves these directly.

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

The catalog is maintained by Magma. If the chain you need isn't there,
[open an issue](https://github.com/Magma-Devs/smart-router/issues) with the chain, the
API interface (JSON-RPC / REST / gRPC / Tendermint RPC), and one or two reference
upstream nodes, and we'll add it.
