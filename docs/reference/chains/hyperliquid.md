---
title: "Hyperliquid"
description: "Run Smart Router for Hyperliquid: example config and supported methods."
---

# Hyperliquid

Smart Router serves Hyperliquid EVM mainnet over JSON-RPC. This page covers the supported methods, the example config, and how to connect a client.

## Endpoint

| | |
|---|---|
| Default port | `3360` (override per `endpoints[]` entry) |
| Calling convention | `POST /` with a JSON-RPC body |
| `chain-id` | `HYPERLIQUID` |
| Spec | [`specs/hyperliquid.json`](https://github.com/Magma-Devs/smart-router/blob/main/specs/hyperliquid.json) |

## Method surface

Hyperliquid's EVM exposes the standard Ethereum JSON-RPC method surface (`eth_*`, `net_*`, `web3_*`). Its `eth_chainId` is `0x3e7` (999). For the shared `eth_*` families, see [Ethereum → Supported method families](ethereum.md#supported-method-families). The spec file linked above has the full method list.

## Run this example

The repo has a ready-to-run config at [`config/smartrouter_examples/smartrouter_hyperliquid.yml`](https://github.com/Magma-Devs/smart-router/blob/main/config/smartrouter_examples). It uses a single public upstream on the official Hyperliquid EVM RPC (`rpc.hyperliquid.xyz/evm`) and needs no API key. It has no websocket leg, so run it with `--skip-websocket-verification`:

=== "Docker Compose"

    ```bash
    SR_CONFIG=config/smartrouter_examples/smartrouter_hyperliquid.yml \
      docker compose -f docker/docker-compose.yml up --build
    ```

=== "Local binary"

    ```bash
    smartrouter config/smartrouter_examples/smartrouter_hyperliquid.yml \
      --use-static-spec specs/ --skip-websocket-verification
    ```

Then call it:

```bash
curl -X POST http://127.0.0.1:3360 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

## Connect a client

=== "viem"

    ```ts
    import { createPublicClient, http, defineChain } from 'viem';

    const hyperliquid = defineChain({
      id: 999,
      name: 'Hyperliquid',
      nativeCurrency: { name: 'HYPE', symbol: 'HYPE', decimals: 18 },
      rpcUrls: { default: { http: ['http://127.0.0.1:3360'] } },
    });

    const client = createPublicClient({ chain: hyperliquid, transport: http() });
    const block = await client.getBlockNumber();
    ```

=== "ethers v6"

    ```ts
    import { JsonRpcProvider } from 'ethers';
    const provider = new JsonRpcProvider('http://127.0.0.1:3360');
    const block = await provider.getBlockNumber();
    ```

To use your own upstreams, edit the `node-urls` in the config. See [The config file](../../configuration/config-file.md).
