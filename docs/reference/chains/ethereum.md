---
title: "Ethereum"
description: "Run Smart Router for Ethereum: example config and supported methods."
---

# Ethereum

Smart Router serves Ethereum mainnet over JSON-RPC. This page covers the supported methods, the example config, and how to connect a client.

## Endpoint

| | |
|---|---|
| Default port | `3360` (override per `endpoints[]` entry) |
| Calling convention | `POST /` with a JSON-RPC body |
| Spec | [`specs/ethereum.json`](https://github.com/Magma-Devs/smart-router/blob/main/specs/ethereum.json) |

## Supported method families

| Family | Examples |
|---|---|
| Standard | `eth_blockNumber`, `eth_call`, `eth_getBalance`, `eth_getBlockByNumber`, `eth_getLogs`, `eth_estimateGas`, `eth_gasPrice`, `eth_feeHistory`, `eth_sendRawTransaction` |
| Tracing (`debug` add-on) | `debug_traceTransaction`, `debug_traceCall`, `debug_traceBlockByNumber`, `debug_storageRangeAt`, `debug_getRawBlock`, `debug_getRawReceipts` |
| Tracing (`trace` add-on) | `trace_call`, `trace_block`, `trace_transaction`, `trace_get` |
| Account abstraction (ERC-4337) | `eth_estimateUserOperationGas`, `eth_sendUserOperation`, etc. (node-dependent) |
| Network / client | `web3_*`, `net_*` |

The spec file linked above has the full method list.

## Upstream capabilities

Some methods only work on upstreams with specific capabilities. Mark these capabilities as add-ons in your config. The router then routes matching methods only to capable upstreams. If no upstream declares an add-on, the upstreams you have serve the matching requests. If a request explicitly asked for the extension, it gets a [`Lava-Extension-Unavailable`](../../api/directives.md#response-headers) response header that says so.

| Add-on | Required for |
|---|---|
| `debug` | `debug_*` tracing methods |
| `trace` | `trace_*` methods (`trace_call`, `trace_block`, …) |
| `archive` | deep `eth_getLogs` and historical state (also extends the `debug` / `trace` collections for old blocks) |
| `bundler` | ERC-4337 user-operation methods |

## Connect a client

=== "viem"

    ```ts
    import { createPublicClient, http } from 'viem';
    import { mainnet } from 'viem/chains';

    const client = createPublicClient({
      chain: mainnet,
      transport: http('http://127.0.0.1:3360'),
    });

    const block = await client.getBlockNumber();
    ```

=== "ethers v6"

    ```ts
    import { JsonRpcProvider } from 'ethers';
    const provider = new JsonRpcProvider('http://127.0.0.1:3360');
    const block = await provider.getBlockNumber();
    ```

=== "web3.py"

    ```python
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:3360'))
    print(w3.eth.block_number)
    ```

=== "curl"

    ```bash
    curl -X POST http://127.0.0.1:3360 \
      -H 'Content-Type: application/json' \
      -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
    ```

## Migrating from Alchemy / Infura / QuickNode

Replace the node URL with your Smart Router URL. The JSON-RPC protocol is the same, so your existing client code does not change.

If you used vendor-specific extensions (Alchemy enhanced APIs, QuickNode add-ons, etc.), check whether your upstream nodes expose the equivalent methods. The chain spec decides which methods are covered, and the spec is maintained in the catalog. If a method you need is not covered, [request it](https://github.com/Magma-Devs/smart-router/issues).

## Run this example

The repo has a ready-to-run config at [`config/smartrouter_examples/smartrouter_eth.yml`](https://github.com/Magma-Devs/smart-router/blob/main/config/smartrouter_examples). It uses two public upstreams (PublicNode, Tenderly) over HTTP + WS and needs no API key:

=== "Docker Compose"

    ```bash
    SR_CONFIG=config/smartrouter_examples/smartrouter_eth.yml \
      docker compose -f docker/docker-compose.yml up --build
    ```

=== "Local binary"

    ```bash
    smartrouter config/smartrouter_examples/smartrouter_eth.yml --use-static-spec specs/
    ```

It listens on port `3360`. Send it a request with any of the [client snippets above](#connect-a-client).
