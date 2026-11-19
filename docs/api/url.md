---
title: "Connect your app"
description: "Endpoint URLs, ready-to-paste client samples for viem, ethers, web3.py, and cosmjs, and the WebSocket subscription id."
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

## Subscriptions over WebSocket

Subscriptions (`eth_subscribe`, Solana's `accountSubscribe` and the rest, Tendermint's `subscribe`) run over a WebSocket on the same listener:

```
ws://<host>:<port>/ws
```

`/websocket` works too.

### The subscription id is the router's

The id in the subscribe reply is issued by the router, not by the node. The router shares one node subscription among all the clients that ask for the same thing. When a node connection drops, it subscribes again. Through all of that, each client keeps the id it was given. The node's own id is never sent to you. Every notification carries your id in `params.subscription`, and you unsubscribe with it.

The id's shape follows the chain:

| The chain's nodes name subscriptions with | You get | Example |
|---|---|---|
| A string (Ethereum and other EVM chains, Substrate) | A string: `rs_`, a 6-character hex hash, `_`, then a counter of at least 5 digits | `"rs_a1b2c3_00042"` |
| A number (Solana) | A JSON number, so you can pass it straight back to `accountUnsubscribe` and the rest | `1099512085310` |
| A query (Tendermint) | No id. The subscription is named by its query, and you unsubscribe with the same query | `tm.event='NewBlock'` |

!!! warning "A string id is not `0x` hex"
    geth and most EVM nodes return a `0x` hex id, such as `"0x9cef478923ff08bf67fde6c64013158d"`. The router returns `rs_…` instead. A client, proxy or validator that requires a `0x` hex quantity rejects it, and the subscription is lost. Accept any string.

How to handle the id:

- **Treat it as opaque.** Store it as you got it, and send it back unchanged. Do not parse it. Only the shape above is stable, not what the hash or the counter mean.
- **Use it on the connection that created it.** An unsubscribe sent on another WebSocket connection is refused.
- **Do not count with it.** The counter in a string id is shared by all clients, not yours alone, and a numeric id is not sequential.

## TLS

The router listens on plain HTTP. For TLS termination, and also for client authentication, CORS, and rate limiting, put a reverse proxy in front (NGINX, HAProxy, or your cloud load balancer). See [Authentication → Authenticating your clients](../configuration/authentication.md#authenticating-your-clients).

## CORS, auth, rate limiting

**CORS** is configurable on the router with the `--cors-*` flags. See the
[CLI reference](../reference/cli.md#cors-http). **Client authentication** and **rate
limiting** are not built into the router. Put a reverse proxy in front for those. See
[Authentication → Authenticating your clients](../configuration/authentication.md#authenticating-your-clients).

## Forwarded client IP

The router honours `X-Forwarded-For`. If you put a proxy in front, set the header upstream, and the router uses it for IP-based logic (rate limiting, audit logs).
