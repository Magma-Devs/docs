---
title: "Connect your app"
description: "Endpoint URLs and ready-to-paste client samples for viem, ethers, web3.py, and cosmjs."
---

# Connect your app

Once Smart Router is running, point your client at its URL. Your client uses the same protocol it would use with any other RPC endpoint.

The protocols are JSON-RPC for Ethereum, REST or gRPC for Cosmos, and Tendermint RPC for Tendermint chains. You do not need a custom SDK, and there is no proprietary protocol.

Smart Router opens **one HTTP listener per chain × API interface**. Your client connects to that listener and uses the chain's native protocol. To change behaviour for a single request (pin a node, skip cache, request cross-validation), see [Request headers](directives.md).

## URL format

```
http://<host>:<port><chain-specific-path>
```

| Component | What it is |
|---|---|
| `<host>:<port>` | a listener you defined in `endpoints[]` of your YAML config |
| `<chain-specific-path>` | the path the chain itself expects: `/` for Ethereum JSON-RPC, `/cosmos/...` for Cosmos REST, `/status` for Tendermint RPC |

## Default ports

The example configs use these ports:

| Chain × interface | Default port |
|---|---|
| Ethereum (JSON-RPC) | `3360` |
| Lava REST | `3360` |
| Lava gRPC | `3361` |
| Lava Tendermint RPC | `3362` |

Each `endpoints[]` entry has a `network-address` field (e.g. `0.0.0.0:3360`). You can change it as needed.

## Pointing a client at it

=== "Ethereum - viem"

    ```ts
    import { createPublicClient, http } from 'viem';
    import { mainnet } from 'viem/chains';

    const client = createPublicClient({
      chain: mainnet,
      transport: http('http://127.0.0.1:3360'),
    });
    ```

=== "Ethereum - ethers v6"

    ```ts
    import { JsonRpcProvider } from 'ethers';
    const provider = new JsonRpcProvider('http://127.0.0.1:3360');
    ```

=== "Ethereum - web3.py"

    ```python
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:3360'))
    ```

=== "Cosmos REST - curl"

    ```bash
    curl http://127.0.0.1:3360/cosmos/base/tendermint/v1beta1/blocks/latest
    ```

=== "Cosmos gRPC - grpcurl"

    ```bash
    grpcurl -plaintext 127.0.0.1:3361 \
      cosmos.bank.v1beta1.Query/TotalSupply
    ```

=== "Cosmos - cosmjs"

    ```ts
    import { StargateClient } from '@cosmjs/stargate';
    const client = await StargateClient.connect('http://127.0.0.1:3362');
    ```

## TLS

The router listens on plain HTTP. For TLS termination, and also for client authentication, CORS, and rate limiting, put a reverse proxy in front (NGINX, HAProxy, or your cloud load balancer). See [Authentication → Authenticating your clients](../configuration/authentication.md#authenticating-your-clients).

## CORS, auth, rate limiting

**CORS** is configurable on the router with the `--cors-*` flags. See the
[CLI reference](../reference/cli.md#cors-http). **Client authentication** and **rate
limiting** are not built into the router. Put a reverse proxy in front for those. See
[Authentication → Authenticating your clients](../configuration/authentication.md#authenticating-your-clients).

## Forwarded client IP

The router honours `X-Forwarded-For`. If you put a proxy in front, set the header upstream, and the router uses it for IP-based logic (rate limiting, audit logs).
