---
title: "Cosmos"
description: "Run Smart Router for Cosmos: example config across Tendermint RPC and REST."
---

# Cosmos

Smart Router serves Cosmos Hub mainnet (`cosmoshub-4`) over REST, gRPC, and Tendermint RPC. This page covers the supported methods, the example config, and how to connect a client.

The setup includes the full Cosmos-ecosystem method surface (Cosmos SDK, CosmWasm, IBC, Tendermint).

## Endpoints

The default Cosmos setup runs three listeners, one per API interface:

| Port | Interface | Calling convention |
|---|---|---|
| `3360` | REST | `GET /cosmos/...`, `GET /ibc/...` |
| `3361` | gRPC | gRPC services from the Cosmos SDK proto trees |
| `3362` | Tendermint RPC | URI (`/status?...`) or JSON-RPC over POST |

| | |
|---|---|
| `chain-id` | `COSMOSHUB` |
| Spec | [`specs/cosmoshub.json`](https://github.com/Magma-Devs/smart-router/blob/main/specs/cosmoshub.json) (imports `COSMOSSDK50` + `COSMOSWASM`, which pull in `COSMOSSDK` → `IBC` + `TENDERMINT`) |

## Supported method families

| Family | Examples |
|---|---|
| Cosmos SDK | `/cosmos/auth/`, `/cosmos/bank/`, `/cosmos/staking/`, `/cosmos/gov/`, `/cosmos/distribution/`, `/cosmos/slashing/`, `/cosmos/tx/`, etc. |
| CosmWasm | `/cosmwasm/wasm/v1/contract/...`, smart-contract queries |
| IBC | `/ibc/apps/transfer/`, `/ibc/core/channel/`, `/ibc/core/client/`, `/ibc/core/connection/` |
| Tendermint RPC | `status`, `block`, `tx`, `abci_query`, `validators`, `broadcast_tx_*`, etc. |

## Connect a client

=== "REST - curl"

    ```bash
    # Latest block (Cosmos REST)
    curl http://127.0.0.1:3360/cosmos/base/tendermint/v1beta1/blocks/latest

    # Total supply
    curl http://127.0.0.1:3360/cosmos/bank/v1beta1/supply
    ```

=== "Tendermint RPC - curl"

    ```bash
    # URI style
    curl http://127.0.0.1:3362/status

    # JSON-RPC style
    curl -X POST http://127.0.0.1:3362 \
      -H 'Content-Type: application/json' \
      -d '{"jsonrpc":"2.0","method":"status","params":[],"id":1}'
    ```

=== "gRPC - grpcurl"

    ```bash
    grpcurl -plaintext 127.0.0.1:3361 list
    grpcurl -plaintext 127.0.0.1:3361 \
      cosmos.bank.v1beta1.Query/TotalSupply
    ```

=== "cosmjs"

    ```ts
    import { StargateClient } from '@cosmjs/stargate';
    const client = await StargateClient.connect('http://127.0.0.1:3362');
    const height = await client.getHeight();
    ```

## Other Cosmos chains

The spec catalog already covers the major Cosmos-SDK chains: Osmosis, Juno, Celestia, Stargaze, Secret, Stride, and more (see [Supported chains](index.md)). They all build on the shared Cosmos / CosmWasm / IBC / Tendermint method surface. To serve one, point your config at its spec and upstreams. You do not need to write a spec.

If a Cosmos chain you need is not in the catalog, [request it](https://github.com/Magma-Devs/smart-router/issues) and Magma will add the spec.

## Run this example

The repo has a ready-to-run config at [`config/smartrouter_examples/smartrouter_cosmos.yml`](https://github.com/Magma-Devs/smart-router/blob/main/config/smartrouter_examples/smartrouter_cosmos.yml). It opens all three Cosmos Hub listeners (REST `3360`, gRPC `3361`, Tendermint RPC `3362`). Each listener is backed by two distinct public vendor groups (PublicNode + Polkachu), and the config needs no API key:

=== "Docker Compose"

    ```bash
    SR_CONFIG=config/smartrouter_examples/smartrouter_cosmos.yml \
      docker compose -f docker/docker-compose.yml up --build
    ```

=== "Local binary"

    ```bash
    smartrouter config/smartrouter_examples/smartrouter_cosmos.yml --use-static-spec specs/
    ```

Then send a request with any of the [client snippets above](#connect-a-client). To use your own upstreams, edit the `node-urls` in the config.
