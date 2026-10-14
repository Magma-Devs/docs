---
title: "Chain specs"
description: "How chain specs declare API methods, parser rules, finality parameters, and capability flags."
---

# Chain specs

Smart Router is **chain-agnostic**: every chain it serves is described by a **JSON
spec**. Read this page to learn what a spec contains and how the router loads specs.

The router has no chain logic built in. The spec tells it how to talk to a chain: which
RPC methods exist, how to parse each one, where finality sits, and which capabilities
(archive, debug, …) a node must have to serve a given method.

So adding a chain never needs a code change or a new build. It is one more spec file
that the router loads at startup.

## What a spec defines

| Part | What it's for |
| --- | --- |
| **API methods** | Every RPC method the chain exposes, per interface (`jsonrpc` / `rest` / `grpc` / `tendermintrpc` / `graphql`). |
| **Parser rules** | How to read a method's request and response, for example which param holds the block number. The router uses this to cache, route, and apply [consistency](../../configuration/failover/integrity.md) correctly. |
| **Categories** | Flags for each method: read or write (stateful), whether it is cacheable, and which addon/extension it needs (archive, debug). The router uses them for [node selection](../../configuration/projects/selection-policies.md) and caching. |
| **Finality parameters** | Block times and finalization distance. The router uses them for the integrity lag gate and for the cache TTLs of finalized and non-finalized data. |
| **Imports** | A spec can import another spec and inherit its methods and addons (for example, Arbitrum imports `ETH1`). The router resolves imports transitively. |

## How specs are loaded

Pass a spec source at startup with `--use-static-spec`. You can repeat the flag. If two
sources define the same chain id, the later source overrides the earlier one:

```bash
# a local directory
smartrouter config.yml --use-static-spec specs/

# or straight from a GitHub/GitLab repo - no manual copy
smartrouter config.yml \
  --use-static-spec https://github.com/Magma-Devs/lava-specs/tree/main
```

In Docker, the `SR_SPEC` env var sets the same value. The built-in
[spec fetcher](https://github.com/Magma-Devs/smart-router/tree/main/utils/specfetcher)
pulls specs from a remote URL at boot and caches them. So when you point at the catalog,
a chain that is not in the bundled `specs/` still resolves.

## Where specs come from

| Source | What's in it | Use when |
|---|---|---|
| **Bundled** - [`specs/`](https://github.com/Magma-Devs/smart-router/tree/main/specs) in the repo | A few production chains and reusable Cosmos building blocks (the example configs use these) | the quickest start; the `init_smartrouter_*` scripts use these |
| **Catalog** - [`Magma-Devs/lava-specs`](https://github.com/Magma-Devs/lava-specs) | The full set, covering every major ecosystem, kept up to date | production deployments that serve any chain beyond the bundled ones |

## Building blocks

Some specs describe no chain of their own. They exist only to be **imported** by chain
specs that share an API surface. The router never serves these specs directly.

| Spec | Role |
|---|---|
| [`cosmossdk.json`](https://github.com/Magma-Devs/lava-specs/blob/main/cosmossdk.json) | base Cosmos SDK surface |
| [`cosmossdk_full.json`](https://github.com/Magma-Devs/lava-specs/blob/main/cosmossdk_full.json) | Cosmos chains that need extended methods |
| [`cosmossdkv45.json`](https://github.com/Magma-Devs/lava-specs/blob/main/cosmossdkv45.json) | older Cosmos SDK v0.45 chains |
| [`cosmossdkv50.json`](https://github.com/Magma-Devs/lava-specs/blob/main/cosmossdkv50.json) | newer Cosmos SDK v0.50 chains |
| [`cosmoswasm.json`](https://github.com/Magma-Devs/lava-specs/blob/main/cosmoswasm.json) | CosmWasm-enabled chains |
| [`tendermint.json`](https://github.com/Magma-Devs/lava-specs/blob/main/tendermint.json) | every Tendermint-based chain |
| [`ibc.json`](https://github.com/Magma-Devs/lava-specs/blob/main/ibc.json) | every IBC-capable chain |
| [`ethermint.json`](https://github.com/Magma-Devs/lava-specs/blob/main/ethermint.json) | EVM-on-Cosmos base, imported by Evmos |

## Need a chain that isn't listed?

If the chain you need is not in the catalog,
[open an issue](https://github.com/Magma-Devs/smart-router/issues) and Magma will add it.
Magma maintains the catalog. In the issue, include the chain, the API interface
(JSON-RPC / REST / gRPC / Tendermint RPC), and one or two reference upstream nodes.
