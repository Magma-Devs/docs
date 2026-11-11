---
title: "Interfaces"
description: "Which interfaces Smart Router serves, how a client calls each one, where a node puts its errors, how writes and subscriptions work, and which chains use it."
---

# Interfaces

An interface is the protocol a client uses to talk to the router. You set it per
listener with `api-interface` in the [config file](../configuration/config-file.md).
How the router handles requests, node replies, writes and its own replies depends on
the interface.

## Interfaces the router serves

A write goes to every eligible node at once, whatever the interface. The Writes column
lists what counts as a write on each interface.

| Interface | How a client calls it | Where a node puts its errors | Writes | Subscriptions | Example chains | Page |
| --- | --- | --- | --- | --- | --- | --- |
| `jsonrpc` | `POST` with a JSON-RPC body. WebSocket on `/ws`, `/websocket` or the bare URL. Any other `GET` gets `405`. | JSON-RPC `error` object | Methods the chain's spec marks as writes, for example `eth_sendRawTransaction` (Ethereum), `sendTransaction` (Solana), `sendrawtransaction` (Bitcoin) | Over WebSocket, for the methods the spec declares: `eth_subscribe` (Ethereum), `accountSubscribe`, `slotSubscribe` and other `*Subscribe` methods (Solana) | Ethereum, Solana, Bitcoin, Hyperliquid | |
| `rest` | Any HTTP method on the API path. The query string and body are passed on. | HTTP status outside 2xx. On a Cosmos transaction reply, a `tx_response.code` that is not `0`. | Requests the chain's spec marks as writes, for example `POST /cosmos/tx/v1beta1/txs` (Cosmos) | None | Cosmos Hub, Aptos | [REST](rest.md) |
| `grpc` | gRPC calls to the listener | gRPC status other than `OK` | Methods the chain's spec marks as writes, for example `cosmos.tx.v1beta1.Service/BroadcastTx` (Cosmos) | Server-streaming methods, only when the chain's spec declares them. Otherwise a streaming call is refused. | Cosmos Hub | |
| `tendermintrpc` | `POST` with a JSON-RPC body, or a URI-style `GET` such as `/status`. WebSocket on `/ws`, `/websocket` or the bare URL. | JSON-RPC `error` object, or a `response.code` that is not `0` with a `log`, inside `result` | `broadcast_tx_sync`, `broadcast_tx_async`, `broadcast_tx_commit` | Over WebSocket: `subscribe` | Cosmos Hub | |
| `graphql` | `POST` with a JSON object body. `OPTIONS` gets `204`; any other method gets `405`. | HTTP status outside 2xx, or an `errors` list inside an HTTP 200 | Any mutation, for example `executeTransaction` (Sui) | None. A subscription is refused with `400`. | Sui | [GraphQL](graphql.md) |
