---
title: "JSON-RPC"
description: "How Smart Router serves JSON-RPC: what the listener accepts, how it reads a node's reply, which errors it retries, how batches, writes and subscriptions work, and the replies the router writes itself."
---

# JSON-RPC

A JSON-RPC listener sends each request to a node byte for byte and returns the node's
reply unchanged. Ethereum, Solana, Bitcoin and Hyperliquid are served this way. This
page covers what the listener accepts, how the router reads a node's reply, which errors
it retries, how batches, writes and subscriptions work, and the few replies the router
writes itself.

## How the router serves a JSON-RPC request

| What comes in | What the router does |
| --- | --- |
| `POST` on any path, with a JSON-RPC body | Sends the body to a node byte for byte, so the node sees your own `id`. The request goes to the node's URL from the config file, whatever path you used. |
| A batch (a JSON array) | Sends the whole array to one node. See [Batches](#batches). |
| A method the chain's spec marks as a write | Sends it to several nodes at once. See [Writes](#writes). |
| A method the chain's spec does not list, or a request with no `method` | Sends it to a node anyway. If that node refuses it as unknown, the refusal is the answer and no other node is asked. |
| A `GET` with a WebSocket upgrade, on any path | Opens a WebSocket. Requests on it are served like a `POST`, and subscriptions work. See [Subscriptions](#subscriptions). |
| A `GET` without an upgrade | `405` with `Allow: POST`. On `/ws` and `/websocket` the answer is `426 Upgrade Required`. On the health path (default `/lava/health`) it is the health answer. |
| `OPTIONS`, `DELETE` | `204`. No node is called. |

You set the interface per listener with `api-interface: "jsonrpc"` in the
[config file](../configuration/config-file.md). A chain whose spec has subscriptions,
such as Ethereum or Solana, also needs a `ws://` or `wss://` node URL, unless you start
the router with `--skip-websocket-verification`.

## Requests the router answers itself

The router answers these without calling a node. In some of them the `id` is fixed
instead of copied from your request.

| Request | Status | Reply |
| --- | --- | --- |
| The body is not valid JSON | `200` | `-32700` `Parse error`, `id: -1` |
| JSON that is not a JSON-RPC request, for example a `method` that is not a string | `500` | `-32000` with the reason |
| The chain's spec has no API set for the request | `200` | `-32601` `Method not found`, `id: 1` |
| A method the spec lists but disables | `500` | `-32000`, message `api is disabled` |
| A batch larger than `--max-batch-request-size` (default: no limit) | `429` | Code `429`, `Batch request size exceeded`, `id: 1` |
| An empty batch, or a batch element whose `params` is not an array or an object | `500` | `-32000` with the reason |
| XRP Ledger: `submit` or `submit_multisigned` inside a batch | `400` | `-32600` `Invalid Request`, asking you to send it as a single request |

The full shape of these replies is under [Replies the router writes](#replies-the-router-writes).

## How the router reads a JSON-RPC reply

- A reply with an `error` object is a node error. `"error": null` is ignored.
- `"result": null` is an answer. It reaches you and is not retried.
- A reply with neither `result` nor `error`, an empty body, or a body that is not a JSON
  object is a broken reply, and the router asks another node.
- The router reads the HTTP status too. Any `5xx` is a node error, whatever the body. A
  `429` means the node is rate limited.
- Chain-specific rules run first, for Solana, the Bitcoin family, Cosmos SDK chains,
  Starknet, NEAR and XRP Ledger. EVM chains use only the general rules below. See
  [How classification works](../reference/error-codes.md#how-classification-works).

The general rules run in this order, and the first match decides: the error code, then
the message, then the HTTP status. So a code such as `-32603` decides before its message
is read, while `-32000` and codes the table does not name are read by their message.

*Counts against the node* means the reply is evidence that the node is broken: the node
is marked unhealthy and its consecutive-failure count goes up (see
[`--bench-after`](../reference/cli.md)).

| Reply | Code | Retried on another node? | Counts against the node? |
| --- | --- | --- | --- |
| **Error codes** | | | |
| `-32601` | `NODE_METHOD_NOT_FOUND` (2001) | Yes \* | No |
| `-32600` whose message says `unsupported method`, or `-32004` | `NODE_METHOD_NOT_SUPPORTED` (2002) | Yes \* | No |
| `-32700` | `USER_PARSE_ERROR` (4001) | No | No |
| `-32600` | `USER_INVALID_REQUEST` (4002) | No | No |
| `-32602` | `USER_INVALID_PARAMS` (4003) | No | No |
| `-32603` | `NODE_INTERNAL_ERROR` (2003) | Yes | Yes |
| `-32001` | `NODE_RESOURCE_NOT_FOUND` (2012) | Yes | No |
| `-32002` | `NODE_RESOURCE_UNAVAILABLE` (2013) | Yes | No |
| `-32003` | `CHAIN_TX_REJECTED` (3014) | No | No |
| `-32005` | `NODE_LIMIT_EXCEEDED` (2011) | No, and the node is held off | No |
| **Messages** (any other code, `-32000` included) | | | |
| `method not found`, `unknown method`, `method does not exist`, `invalid method` | `NODE_METHOD_NOT_FOUND` (2001) | Yes \* | No |
| `method not supported`, `pending state is not supported`, a method, RPC, endpoint or API that `is not available`, or `blocked` next to a method or RPC | `NODE_METHOD_NOT_SUPPORTED` (2002) | Yes \* | No |
| `rate limit`, `too many requests`, `enhance_your_calm`, or code `429` | `NODE_RATE_LIMITED` (2005) | Yes, and the node is held off | No |
| `node is syncing`, `node is still syncing`, `catching up to the chain` | `NODE_SYNCING` (2007) | Yes | Yes |
| Data the node does not hold: `block not found` (3201), `transaction not found` (3202), `receipt not found` (3203), `missing trie node` or `historical state` (3204) | `CHAIN_*` | Yes | No |
| Bad input: a block number or hash such as `invalid block number` or `hex string without 0x prefix` (4004), an address such as `invalid address` (4005), hex such as `invalid hex` (4007) | `USER_*` | No | No |
| The chain refused the transaction: `nonce too low` (3001), `nonce too high` (3002), `insufficient funds` (3003), `intrinsic gas too low` (3004), `exceeds block gas limit` (3005), `transaction underpriced` or `fee too low` (3006), `already known` (3007), `replacement transaction underpriced` (3008), `txpool is full` (3009), `oversized data` or `tx too large` (3010), `max fee per gas less than block base fee` (3011), `invalid signature` (3016) | `CHAIN_*` | No | No |
| Execution failed: `execution reverted` (3101), `out of gas` (3102), `stack limit reached` (3103), `invalid opcode` (3104), `write protection` (3105), `max code size exceeded` (3106), `out of counters` (3108) | `CHAIN_*` | No | No |
| `response is too big`, `exceeded max limit` | `CHAIN_LOG_RESPONSE_TOO_LARGE` (3207) | No | No |
| `unexpected end of JSON input` | `PROTOCOL_CONNECTION_RESET` (1005) | Yes | Yes |
| `all attempts exhausted`, or `-32000` with none of the messages above | `NODE_SERVER_ERROR` (2004) | Yes | Yes |
| **HTTP status** | | | |
| `401` | `NODE_UNAUTHORIZED` (2016) | Yes \* | No |
| `404` | `NODE_ENDPOINT_NOT_FOUND` (2009) | Yes \* | No |
| `405` | `NODE_METHOD_NOT_ALLOWED` (2010) | Yes \* | No |
| `413` | `USER_REQUEST_TOO_LARGE` (4006) | No | No |
| `429` | `NODE_RATE_LIMITED` (2005) | Yes, and the node is held off for its `Retry-After` | No |
| `500` | `NODE_INTERNAL_ERROR` (2003) | Yes | Yes |
| `501` | `NODE_UNIMPLEMENTED` (2008) | Yes \* | No |
| `502` | `NODE_BAD_GATEWAY` (2015) | Yes | Yes |
| `503` | `NODE_SERVICE_UNAVAILABLE` (2006) | Yes | Yes |
| `504`, `522`, `524` | `NODE_GATEWAY_TIMEOUT` (2014) | Yes | Yes |
| `520`, `521`, `523`, `525`, `526`, `527`, `530` | `NODE_SERVER_ERROR` (2004) | Yes | Yes |
| **No match** | | | |
| An error in the reply body that no row names, for example a `400` or `403` | `UNKNOWN_ERROR` (0) | Yes | No, but it lowers the node's availability score |
| A `5xx` that no row names, or a `2xx` whose body is not JSON | `UNKNOWN_ERROR` (0) | Yes | Yes |

\* Retried on another node, except for a method the spec does not list: then the first
refusal is the answer.

The table shows the main wording of each message. The full list is in
[`error_classifier.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/common/error_classifier.go).
The codes are explained in [Error codes](../reference/error-codes.md).

The HTTP statuses differ from REST. On JSON-RPC a `401` is `NODE_UNAUTHORIZED` and a
`404` is `NODE_ENDPOINT_NOT_FOUND`, and other `4xx` statuses have no row of their own.
Every `5xx` also lowers the node's availability score.

**When every node fails**, you get one node's own reply: the first error that is not
retried, or else the first node error. If every attempt failed with an HTTP error status,
you get that node's status and body unchanged. A node's answer is preferred over a `429`,
and a `429` over no answer at all. The router writes its own reply only when no node
answered.

## Batches

- The router sends the whole array to one node as one request and returns the node's
  array as the node sent it.
- A failed batch is not retried on another node, unless every attempt was rate limited.
  This is the default of `--disable-batch-request-retry`. See
  [Batch requests](../configuration/failover/retry.md#batch-requests).
- A batch counts as a node error only when no element succeeded, so one successful
  element makes the whole reply an answer. With `--batch-node-error-on-any`, any failed
  element makes the batch a node error.
- The router reads the messages of the failed elements, not their codes, so only the
  message rows of the table apply to a batch.
- A batch that contains a write is sent like a write, to several nodes at once. Because
  one successful element makes the reply an answer, a node whose reads succeeded can
  answer you even if its write failed. Check the result of every element.

## Writes

A write is a method the chain's spec puts in the write category: `eth_sendRawTransaction`
and `eth_sendTransaction` on Ethereum, `sendTransaction` on Solana, `sendrawtransaction`
and `submitpackage` on Bitcoin. It is sent to several nodes at once, as on every
interface (see [Writes on every interface](index.md#writes-on-every-interface)).

- The first node that accepts the write answers you. The router keeps delivering it to
  the other nodes for up to 5 seconds after that.
- A node error that arrives after another node accepted the write does not count against
  that node.
- If no node accepted the write and one of them may have received it (a timeout, or a
  connection that broke after the write went out), you get a `500` with `-32000` and a
  message that starts with `transaction status unclear:`. It tells you to check the chain
  before you send the transaction again.
- The reply carries `lava-stateful-api: true` and
  [`lava-fast-tx-participants`](../api/directives.md#response-headers). It never carries
  `Lava-Retries`.
- On EVM chains, after `eth_sendRawTransaction`, the sender's `eth_getTransactionCount`
  with `pending` and lookups by the transaction hash prefer the node that accepted the
  write for `--read-your-writes-window` (default `30s`). See
  [Cache and read-your-writes](../configuration/failover/backup.md#cache-and-read-your-writes).

## Subscriptions

Subscriptions run over the WebSocket only, for the methods the chain's spec marks as
subscriptions: `eth_subscribe` on Ethereum, and on Solana `accountSubscribe`,
`blockSubscribe`, `logsSubscribe`, `programSubscribe`, `rootSubscribe`,
`signatureSubscribe`, `slotSubscribe`, `slotsUpdatesSubscribe` and `voteSubscribe`. The
matching unsubscribe method ends each one. Any other method sent over the WebSocket is
served like a `POST`.

- **Node URL.** A subscription needs a `ws://` or `wss://` node URL. Without one, a
  subscribe fails with `WebSocket subscriptions not available: no ws:// or wss://
  endpoints configured for chain <id>`.
- **Shared.** Clients that subscribe with the same method and the same params share one
  subscription on the node. Each client gets its own subscription id, and every
  notification it receives carries that id. Repeating the same subscribe on the same
  connection returns the id you already have.
- **Unsubscribe.** Send the chain's unsubscribe method with your id. You can remove only
  your own subscription. The node is told only when the last client leaves. Closing the
  WebSocket ends all your subscriptions.
- **When the node's connection drops**, the router reconnects and subscribes again with
  the same method and params. You keep your id. After more than 5 restores without
  progress, the router gives up; a restore that stays up for 30 seconds counts as
  progress. Then the notifications stop: no message is sent and the WebSocket stays open.
  An error the node sends on the subscription also ends it, with no restore.
- **Over HTTP**, a subscribe method is not refused. It goes to one node like a read, and
  the node's reply reaches you as is, without a retry.

| Limit | Default | When it is reached |
| --- | --- | --- |
| Subscribes per minute, per WebSocket connection | 10 | The subscribe is refused |
| Unsubscribes per minute, per WebSocket connection | 20 | The unsubscribe is refused |
| Notifications waiting for one client | 100 | The router drops the client and closes its WebSocket with code `1013` |
| WebSocket connections per client address | No limit (`--limit-parallel-websocket-connections-per-ip`) | The connection is closed with `Too Many Open Connections` |
| Messages per second, per connection | No limit (`--rate-limit-websocket-requests-per-connection`) | Each message over the limit gets error code `429` |
| Idle time | 20 minutes (`--limit-websocket-connection-idle-time`) | The connection is closed |

## Replies the router writes

| Case | Status | Body |
| --- | --- | --- |
| The body is not valid JSON | `200` | `{"jsonrpc":"2.0","id":-1,"error":{"code":-32700,"message":"Parse error","data":"Failed to parse the request body as JSON"}}` |
| The spec has no API set for the request | `200` | `{"jsonrpc":"2.0","id":1,"error":{"code":-32601,"message":"Method not found","data":""}}` |
| A batch over the size limit | `429` | `{"jsonrpc":"2.0","id":1,"error":{"code":429,"message":"Batch request size exceeded","data":""}}` |
| No node answered | `502`, or `504` for a timeout | `{"jsonrpc":"2.0","id":<your id>,"error":{"code":-32000,"message":"no answer from upstream: <cause>","data":{"guid":"<guid>","router_error_code":<code>,"router_error_name":"<name>"}}}` |
| Any other refusal or router failure, including a write whose outcome is unclear | `500` | `{"jsonrpc":"2.0","id":<your id>,"error":{"code":-32000,"message":"<reason>","data":{"guid":"<guid>","error":"<reason>"}}}` |
| Over the WebSocket: a message over the rate limit | - | Code `429`, `Too Many Requests`, with your `id` |
| Over the WebSocket: unsubscribing an id that is not yours | - | `-32603` `Internal error`, data `subscription not found`, with your `id` |
| Over the WebSocket: any other failure | - | `{"Error_Received":"{\"Error_GUID\":\"<guid>\",\"Error\":\"<reason>\"}"}`. This one is not shaped like JSON-RPC. |

`guid` matches the `Lava-Guid` header. `router_error_code` and `router_error_name` are
the [error code](../reference/error-codes.md) of the failure.

The router also changes a node's reply in three cases:

- On Bitcoin-family chains (BTC, LTC, DOGE, BCH, DASH, ZCASH and their testnets), a
  successful reply is rewritten as JSON-RPC 1.0: no `jsonrpc` field, and `error` and
  `result` are always present.
- Secrets in a node's error reply are removed.
- A reply served from the cache carries your request's `id`.

## Example requests and replies

The router listens on `3360` in these examples. Bodies are shortened with `...`. They
follow the behaviour on this page and were not captured from a running router.

**A read.** The node's reply reaches you unchanged, with your `id`.

```bash
curl -s http://127.0.0.1:3360 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":7,"method":"eth_blockNumber","params":[]}'
```

```json
{"jsonrpc":"2.0","id":7,"result":"0x..."}
```

**A write.** The router sends it to several nodes at once and returns the first node
that accepts it. The headers name the nodes.

```bash
curl -i http://127.0.0.1:3360 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":8,"method":"eth_sendRawTransaction","params":["0x..."]}'
```

```http
HTTP/1.1 200 OK
lava-stateful-api: true
lava-fast-tx-participants: [node-a node-b]

{"jsonrpc":"2.0","id":8,"result":"0x<transaction hash>"}
```

**A body that is not JSON.** The router answers without calling a node, with `id: -1`.

```bash
curl -s http://127.0.0.1:3360 -H 'Content-Type: application/json' -d '{"jsonrpc":'
```

```json
{"jsonrpc":"2.0","id":-1,"error":{"code":-32700,"message":"Parse error","data":"Failed to parse the request body as JSON"}}
```

**A subscription.** Open a WebSocket on any path and subscribe. Each notification
carries the subscription id the router gave you.

```json
> {"jsonrpc":"2.0","id":1,"method":"eth_subscribe","params":["newHeads"]}
< {"jsonrpc":"2.0","id":1,"result":"<your subscription id>"}
< {"jsonrpc":"2.0","method":"eth_subscription","params":{"subscription":"<your subscription id>","result":{...}}}
```
