---
title: "Examples"
description: "Ready-to-run example configurations for popular chains."
---

# Examples

Every chain bundled in the repo's [`specs/`](https://github.com/Magma-Devs/smart-router/tree/main/specs) has a **ready-to-run example config** under [`config/smartrouter_examples/`](https://github.com/Magma-Devs/smart-router/tree/main/config/smartrouter_examples). Copy one to get started, then replace its upstreams with your own when you are ready.

Each example points at public RPC vendors ([PublicNode](https://publicnode.com) and each chain's official/community endpoints), so it runs with **no API key**.

The per-chain pages below cover each example: the endpoint, the method surface, a client snippet, and the exact run command.

## Bundled chains

| Chain | `chain-id` | Interface(s) | Example config | Page |
| --- | --- | --- | --- | --- |
| Ethereum | `ETH1` | jsonrpc | `smartrouter_eth.yml` | [Ethereum](../ethereum.md) |
| Solana | `SOLANA` | jsonrpc | `smartrouter_solana.yml` | [Solana](../solana.md) |
| Bitcoin | `BTC` | jsonrpc | `smartrouter_bitcoin.yml` | [Bitcoin](../bitcoin.md) |
| Hyperliquid | `HYPERLIQUID` | jsonrpc | `smartrouter_hyperliquid.yml` | [Hyperliquid](../hyperliquid.md) |
| Cosmos Hub | `COSMOSHUB` | rest, grpc, tendermintrpc | `smartrouter_cosmos.yml` | [Cosmos](../cosmos.md) |
| Aptos | `APT1` | rest | `smartrouter_aptos.yml` | [Aptos](../aptos.md) |

To run every chain at once, use [`smartrouter_multichain.yml`](https://github.com/Magma-Devs/smart-router/blob/main/config/smartrouter_examples/smartrouter_multichain.yml). It serves **all six chains together**, each on its own port: ETH1 `3360`, Solana `3361`, Bitcoin `3362`, Hyperliquid `3363`, Cosmos Hub REST/Tendermint/gRPC on `3364`/`3365`/`3366`, and Aptos `3367`. All of them use public RPC vendors (PublicNode + each chain's official/community endpoint):

```bash
SR_CONFIG=config/smartrouter_examples/smartrouter_multichain.yml \
  docker compose -f docker/docker-compose.yml up --build
```

The repo also has cached variants (`smartrouter_eth_cached.yml`, `smartrouter_multichain_cached.yml`). They have the same shape, plus the cache sidecar.

## Run any example

You run every example the same way. Pass the config as a positional argument and point `--use-static-spec` at the bundled specs:

=== "Docker Compose"

    ```bash
    SR_CONFIG=config/smartrouter_examples/smartrouter_eth.yml \
      docker compose -f docker/docker-compose.yml up --build
    ```

=== "Local binary"

    ```bash
    smartrouter config/smartrouter_examples/smartrouter_eth.yml --use-static-spec specs/
    ```

For another chain, change the filename to that chain's config. Then send a request to the listener it opens (port `3360` by default). Each chain page has a call you can copy and paste.

!!! tip "Most examples are HTTP-only"
    The Solana, Bitcoin, Hyperliquid (jsonrpc) and Aptos (rest) examples have no
    websocket leg, so add `--skip-websocket-verification` when you run them. Only
    the Ethereum example pairs each https url with a wss one, because the ETH1
    spec needs websocket for subscriptions. It runs without the extra flag.

See [Run Smart Router](../../../deployment/index.md) for the cache and dashboard overlays, and [The config file](../../../configuration/config-file.md) for the config format.
