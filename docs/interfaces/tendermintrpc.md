---
title: "Tendermint RPC"
description: "How Smart Router serves Tendermint RPC (CometBFT): JSON-RPC over POST, URI-style GET and WebSocket, how it reads a node's reply, how broadcasts and subscriptions work, and the replies the router writes itself."
---

# Tendermint RPC

A Tendermint RPC listener serves a Cosmos chain's CometBFT RPC in three forms: JSON-RPC
over `POST`, URI-style `GET`, and WebSocket. The router reads a node's reply the same way
as on [JSON-RPC](jsonrpc.md), plus one rule of its own. Cosmos Hub serves it on port
`3362`. This page covers what the listener accepts, how the router reads a node's reply,
how broadcasts and subscriptions work, and the replies the router writes itself.

## How the router serves a Tendermint RPC request

| What comes in | What the router does |
| --- | --- |
| `POST` on any path, with a JSON-RPC body | Sends the body to a node byte for byte, so the node sees your own `id`. The path and query string are not passed on: the request goes to the node's URL from the config file. |
| A URI-style `GET`, for example `/status` or `/block?height=5` | Turns it into a JSON-RPC request and sends it to the node as a `POST`: the path is the method, each query value is a string parameter, and the `id` is `1`. See [URI requests](#uri-requests). |
| A batch (a JSON array) | Sends the whole array to one node, as on [JSON-RPC](jsonrpc.md#batches). |
| `broadcast_tx_sync`, `broadcast_tx_async`, `broadcast_tx_commit`, `broadcast_evidence` | Sends it to several nodes at once. See [Writes](#writes). |
| A method the chain's spec does not list | Sends it to a node anyway. If that node refuses it as unknown, the refusal is the answer and no other node is asked. |
| A `GET` with a WebSocket upgrade, on any path | Opens a WebSocket. Requests on it are served like a `POST`, and subscriptions work. See [Subscriptions](#subscriptions). |
| `GET /ws` or `GET /websocket` without an upgrade | `426 Upgrade Required` |
| `GET` on the health path (default `/lava/health`) | The health answer |
| `OPTIONS`, `DELETE` | `204`. No node is called. |

You set the interface per listener with `api-interface: "tendermintrpc"` in the
[config file](../configuration/config-file.md). Subscriptions need a `ws://` or `wss://`
node URL.

### URI requests

A URI-style `GET` such as `/block?height=5` becomes a JSON-RPC request to the node like
this one:

```json
{"jsonrpc":"2.0","id":1,"method":"block","params":{"height":"5"}}
```

- Every value is sent as a string, exactly as it is in the URL after URL decoding. A
  quoted value keeps its quotes.
- A key that appears twice becomes one value, joined with commas.
- A pair that cannot be decoded, such as `?height=%zz`, is dropped without an error.
- The router does not check the values. The node judges them.
- The node's reply carries `id: 1`, because that is the `id` the router sent.

## Requests the router answers itself

The router answers these without calling a node.

| Request | Status | Reply |
| --- | --- | --- |
| The body is not valid JSON | `500` | The plain text `Internal Error` |
| An empty batch, or a batch that mixes two add-ons | `500` | The plain text `Internal Error` |
| A batch larger than `--max-batch-request-size` (default: no limit) | `429` | Code `429`, `Batch request size exceeded`, `id: 1` |
| A method the spec lists but disables | `500` | Error code `555`, see below |

The shape of a router error depends on the request:

- **`POST` with one JSON object that has an `id`:**
  `{"jsonrpc":"2.0","id":<your id>,"error":{"code":555,"message":"Rpc Error","data":"{\"Error_GUID\":\"<guid>\",\"Error\":\"<reason>\"}"}}`
- **`POST` whose body is not one JSON object, or has no `id`:** the plain text
  `Internal Error`, even though the `Content-Type` says JSON.
- **`GET`:** `{"error":"{\"Error_GUID\":\"<guid>\",\"Error\":\"<reason>\"}"}`

`Error_GUID` matches the `Lava-Guid` header.

## How the router reads a Tendermint RPC reply

The router reads a reply as on JSON-RPC:

- A reply with an `error` object is a node error. The router reads its `code` and
  `message`, never its `data`.
- Any HTTP `5xx` is a node error, whatever the body. A `429` means the node is rate
  limited.
- A reply that is not a JSON-RPC envelope, for example HTML, or a body with neither
  `result` nor `error`, is a broken reply, and the router asks another node.

**One rule is Tendermint's own.** A reply whose `result.response.code` is not `0`, with
a `log` that is not empty, is a node error, and the `log` is its message. In practice
this is how `abci_query` reports an application error. A non-zero code with an empty
`log` is an answer.

The router then matches the error the same way as on JSON-RPC: first the Cosmos rules,
then the general JSON-RPC rules.

- **Cosmos rules:** `account sequence mismatch` is `CHAIN_INVALID_SEQUENCE` (3012),
  `insufficient fee` is `CHAIN_INSUFFICIENT_FEE` (3013), and `account not found` is
  `CHAIN_ACCOUNT_NOT_FOUND` (3107). None is retried or counts against the node.
- **General rules:** the error code, then the message, then the HTTP status. They are in
  the table under [How the router reads a JSON-RPC reply](jsonrpc.md#how-the-router-reads-a-json-rpc-reply),
  with what each one means for retries and for the node.

There are no rules written for Tendermint messages. A reply about a pruned height, or a
transaction already in the mempool, has no row of its own here. It is read by its
JSON-RPC error code, so a `-32603` is `NODE_INTERNAL_ERROR`: retried, and counted
against the node.

**When every node fails**, you get one node's own reply: the first error that is not
retried, or else the first node error. If every attempt failed with an HTTP error status,
you get that node's status and body unchanged. The router writes its own reply only when
no node answered.

## Writes

`broadcast_tx_sync`, `broadcast_tx_async`, `broadcast_tx_commit` and
`broadcast_evidence` are writes. They are sent to several nodes at once, as on every
interface (see [Writes on every interface](index.md#writes-on-every-interface)).
`check_tx` is a read.

- `broadcast_tx_sync` and `broadcast_tx_commit` wait longer than other requests: the
  router adds twice the chain's average block time to their timeout.
- The first reply that is not a node error answers you.
- If no node accepted the write and one of them may have received it, you get a `500`
  whose error message contains `transaction status unclear`, in the error `555` shape
  above. It tells you to check the chain before you send the transaction again.
- A node error that arrives after another node accepted the write does not count against
  that node.

!!! warning "A refused transaction can answer you"
    A broadcast that the chain refuses still comes back as a normal reply. Its code is in
    `result.code` (`broadcast_tx_sync`, `broadcast_tx_async`), or in `result.check_tx.code`
    and `result.tx_result.code` (`broadcast_tx_commit`; `result.deliver_tx.code` on older
    nodes). The router does not read these
    codes, so the first refused reply can answer you even when another node accepted the
    transaction. Read the code in the reply, and look the transaction hash up before you
    sign a new one.

## Subscriptions

Subscriptions run over the WebSocket with `subscribe`, `unsubscribe` and
`unsubscribe_all`. A subscription is identified by its `query`.

- **Shared.** Clients that subscribe with the same query share one subscription on the
  node. The first client gets the node's reply to `subscribe`, with its own `id`. A
  client that joins later gets `{"jsonrpc":"2.0","id":<your id>,"result":<the node's
  first result>}`. Events arrive as the node sent them, with your subscribe `id`.
- **`unsubscribe`** takes the same `query` you subscribed with. A query that is not
  yours gets `-32603` `Internal error`, data `subscription not found`. If you are the
  last client on it, the router tells the node and returns the node's reply. Otherwise
  you get `{"jsonrpc":"2.0","id":<your id>,"result":true}`.
- **`unsubscribe_all`** ends every subscription on your connection and returns
  `{"jsonrpc":"2.0","id":<your id>,"result":{}}`. Closing the WebSocket does the same.
- **When the node's connection drops**, the router reconnects to the same node and
  subscribes again with the same query, and you stay attached. It waits between tries,
  from 100 ms up to 30 seconds, for up to 10 tries. After 5 restores that each lasted
  under 30 seconds, it gives up. Then the events stop: no message is sent and the
  WebSocket stays open. An error the node sends on the subscription also ends it, with no
  restore.
- **Over HTTP**, `subscribe` is not refused. It goes to one node like any read.
- **Limits** are the same as on [JSON-RPC](jsonrpc.md#subscriptions): 10 subscribes and
  20 unsubscribes per minute per connection, and a client that falls 100 events behind is
  dropped with close code `1013`.

## Replies the router writes

| Case | Status | Body |
| --- | --- | --- |
| A request refused before any node is called | See [Requests the router answers itself](#requests-the-router-answers-itself) | |
| No node answered, on `POST` | `502`, or `504` for a timeout | `{"jsonrpc":"2.0","id":<your id>,"error":{"code":-32000,"message":"no answer from upstream: <cause>","data":{"guid":"<guid>","router_error_code":<code>,"router_error_name":"<name>"}}}` |
| No node answered, on `GET` | `502`, or `504` for a timeout | `{"error":"no answer from upstream: <cause>"}` |
| A write whose outcome is unclear | `500` | The error `555` shape, with `transaction status unclear` in the reason |
| Over the WebSocket: a failed request | - | `{"Error_Received":"{\"Error_GUID\":\"<guid>\",\"Error\":\"<reason>\"}"}` |

A reply that is a node error carries the header `lava-identified-node-error: true`.
Secrets in a node's error reply are removed.

## Example requests and replies

The router listens on `3362` in these examples. Bodies are shortened with `...`. They
follow the behaviour on this page and were not captured from a running router.

**A JSON-RPC read.** The node's reply reaches you unchanged, with your `id`.

```bash
curl -s http://127.0.0.1:3362 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":3,"method":"status","params":{}}'
```

```json
{"jsonrpc":"2.0","id":3,"result":{"node_info":{...},"sync_info":{...},...}}
```

**A URI read.** The router sends it to the node as JSON-RPC with `id: 1`.

```bash
curl -s 'http://127.0.0.1:3362/block?height=5'
```

```json
{"jsonrpc":"2.0","id":1,"result":{"block_id":{...},"block":{...}}}
```

**A broadcast the chain refused.** It is a normal reply, so it can answer you. Read
`result.code`.

```bash
curl -s http://127.0.0.1:3362 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":4,"method":"broadcast_tx_sync","params":{"tx":"..."}}'
```

```json
{"jsonrpc":"2.0","id":4,"result":{"code":5,"log":"...","hash":"..."}}
```

**A subscription.** Open a WebSocket on any path and subscribe to a query.

```json
> {"jsonrpc":"2.0","id":1,"method":"subscribe","params":{"query":"tm.event='NewBlock'"}}
< {"jsonrpc":"2.0","id":1,"result":{}}
< {"jsonrpc":"2.0","id":1,"result":{"query":"tm.event='NewBlock'","data":{...},...}}
```
