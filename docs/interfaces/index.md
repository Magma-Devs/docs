---
title: "Interfaces"
description: "Which interfaces Smart Router serves, how a client calls each one, where a node puts its errors, how writes and subscriptions work, and which chains use it."
---

# Interfaces

An interface is the protocol a client uses to talk to the router. You set it per
listener with `api-interface` in the [config file](../configuration/config-file.md).
How the router handles requests, node replies, writes and its own replies depends on
the interface. Each interface has its own page.

## Interfaces the router serves

| Interface | How a client calls it | Where a node puts its errors | Writes | Subscriptions | Example chains | Page |
| --- | --- | --- | --- | --- | --- | --- |
| `jsonrpc` | `POST` with a JSON-RPC body, or a WebSocket upgrade on any path. A `GET` without an upgrade gets `405`. | JSON-RPC `error` object, or an HTTP `5xx` or `429` | Methods the chain's spec marks as writes, for example `eth_sendRawTransaction` (Ethereum), `sendTransaction` (Solana), `sendrawtransaction` (Bitcoin) | Over WebSocket, for the methods the spec declares: `eth_subscribe` (Ethereum), `accountSubscribe`, `slotSubscribe` and other `*Subscribe` methods (Solana) | Ethereum, Solana, Bitcoin, Hyperliquid | [JSON-RPC](jsonrpc.md) |
| `rest` | Any HTTP method on the API path. The query string and body are passed on. | HTTP status outside 2xx. On a Cosmos transaction reply, a `tx_response.code` that is not `0`. | Requests the chain's spec marks as writes, for example `POST /cosmos/tx/v1beta1/txs` (Cosmos) | None | Cosmos Hub, Aptos | [REST](rest.md) |
| `grpc` | gRPC calls to the listener, over HTTP/2. gRPC-Web on the same port. | gRPC status other than `OK` | Methods the chain's spec marks as writes, for example `cosmos.tx.v1beta1.Service/BroadcastTx` (Cosmos) | Server-streaming methods the chain's spec declares as subscriptions | Cosmos Hub | [gRPC](grpc.md) |
| `tendermintrpc` | `POST` with a JSON-RPC body, a URI-style `GET` such as `/status` (the router turns it into JSON-RPC), or a WebSocket upgrade on any path | JSON-RPC `error` object, an HTTP `5xx` or `429`, or a `response.code` that is not `0` with a `log`, inside `result` | `broadcast_tx_sync`, `broadcast_tx_async`, `broadcast_tx_commit`, `broadcast_evidence` | Over WebSocket: `subscribe` | Cosmos Hub | [Tendermint RPC](tendermintrpc.md) |
| `graphql` | `POST` with a JSON object body. `OPTIONS` gets `204`; any other method gets `405`. | HTTP status outside 2xx, or an `errors` list inside an HTTP 200 | Any mutation, for example `executeTransaction` (Sui) | None. A subscription is refused with `400`. | Sui | [GraphQL](graphql.md) |

## Writes on every interface

A write is a request the chain's spec puts in the write category. The Writes column
above lists them. On every interface:

- The router sends a write to every eligible primary node at once, up to 10. Backup
  nodes get it too only with `--stateful-to-backup` (see
  [Primary and backup nodes](../configuration/failover/backup.md)).
- A write goes to one node only when you [pin it to a node](../api/directives.md#pin-to-a-specific-node),
  keep a [sticky session](../configuration/sticky-sessions.md), or run with
  `--strategy cost`.
- The first node that accepts the write answers you. The
  [`lava-fast-tx-participants`](../api/directives.md#response-headers) header names the
  nodes it went to.
- The router does not send a write again, unless every node it went to was rate limited.
  On GraphQL a write is never sent again.
- When no node accepted the write and one of them may have run it, the router tells you
  so instead of returning a node error. Each interface page shows that reply.

What counts as "accepted" depends on the interface. On gRPC and Tendermint RPC, a
transaction the chain refused at its first check still arrives as a normal reply, so it
can answer you. See [Writes](grpc.md#writes) on the gRPC page and
[Writes](tendermintrpc.md#writes) on the Tendermint RPC page.
