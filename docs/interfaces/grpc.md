---
title: "gRPC"
description: "How Smart Router serves gRPC: what the listener accepts, reflection and descriptors, which metadata passes, how it reads a node's status, how writes and streaming work, and the statuses the router sends itself."
---

# gRPC

A gRPC listener forwards each call to a node as the caller's bytes and returns the
node's reply unchanged. Cosmos Hub serves gRPC. This page covers what the listener
accepts, how the router learns a node's services, which metadata passes each way, how
it reads a node's status, how writes and streaming work, and the statuses the router
sends itself.

## How the router serves a gRPC call

| What comes in | What the router does |
| --- | --- |
| A unary call to any service and method | Forwards your request bytes to a node on the same method path. The router does not decode the message. |
| A call to a method the chain's spec does not list | Forwards it anyway. If that node refuses it, for example with `UNIMPLEMENTED`, the refusal is the answer and no other node is asked. |
| A method the chain's spec marks as a write, for example `cosmos.tx.v1beta1.Service/BroadcastTx` | Sends it to several nodes at once. See [Writes](#writes). |
| A server-streaming call to a method the chain's spec declares as a subscription | Opens a stream. See [Streaming](#streaming). |
| Any other server-streaming call | Refused with `UNKNOWN`. See [Streaming](#streaming). |
| A client-streaming call | The router reads only the first message and sends it as a unary call. |
| Server reflection, for example `grpcurl list` | Answered by the router. See [Reflection and descriptors](#reflection-and-descriptors). |
| `grpc.health.v1.Health` | Answered by the router. It never reaches a node. |
| gRPC-Web | Served on the same port. |
| A JSON request body (first byte `{` or `[`) | Converted to protobuf with the method's descriptor. The reply is protobuf. |
| `GET` on the health path (default `/lava/health`) | `200 Healthy` or `503 Unhealthy` |
| `OPTIONS` | `204`, with the CORS headers |

You set the interface per listener with `api-interface: "grpc"` in the
[config file](../configuration/config-file.md).

- The listener speaks HTTP/2 without TLS. With `tls-enabled: true` it uses a
  self-signed certificate made at start. With grpcurl, use `-plaintext` without TLS, or
  `-insecure` with it.
- A message can be up to 512 MB, in both directions.
- A node URL must start with `grpc://` or `grpcs://`.

## Reflection and descriptors

Forwarding a call needs no descriptor. The chain's spec decides how a method is treated:
its compute units, whether it is a write, how its block is read, whether it is a
subscription, and which headers pass.

The router needs a method's descriptor for a few things: answering reflection, reading
the block from a request or a reply, finding streaming methods, serving a stream, and
converting a JSON body. Descriptors come from the node's own server reflection, or from
a descriptor file, as set by `grpc-config` below. At start, the router asks each node
for its services. It waits up to 15 seconds for this, then starts anyway.

**The router answers reflection itself.** It serves reflection v1 and v1alpha from a
snapshot of one node, so `grpcurl list` and `grpcurl describe` work against the router.

- The list shows that node's services, not the spec's.
- The node is the first one with a current snapshot, primary nodes before backups.
- The snapshot is refreshed every 10 minutes.
- Reflection is never forwarded to a node.
- With `descriptor-source: file`, reflection works even when the node serves none.

### `grpc-config`

Each gRPC node URL can carry a `grpc-config` block.

| Field | Default | What it does |
| --- | --- | --- |
| `descriptor-source` | `reflection` | `reflection`: descriptors come from the node's server reflection. `file`: only the descriptor file is used, so a node without reflection works. `hybrid`: the descriptor file first, then reflection for anything the file lacks. |
| `descriptor-set-path` | none | A binary `FileDescriptorSet`. It is read once, so a change needs a restart. Required for `file`. With `hybrid` and no file, only reflection is used. |
| `reflection-timeout` | `5s` | Time for one descriptor lookup. Must be between `100ms` and `30s`. |
| `allow-insecure` | `false` | Allows a `grpc://` URL. A `grpc://` URL needs it even with `auth-config.use-tls`. This is a different field from `auth-config.allow-insecure`, which skips certificate checks. |

## Metadata

**From you to the node:**

- The router forwards only the headers the chain's spec declares for gRPC. For Cosmos
  Hub, that is `x-cosmos-block-height` and `grpc-metadata-x-cosmos-block-height`.
- [Request headers](../api/directives.md) such as `lava-stickiness` are read by the
  router and not forwarded.
- The router adds the node URL's `auth-headers` and, when tracing is on, the trace
  headers.
- The client's IP is not sent. `ip-forwarding` has no effect on gRPC.
- A header value gRPC cannot send (a byte outside printable ASCII, on a key that does
  not end in `-bin`) is refused with `UNKNOWN` before any node is called.
- On a stream, none of your metadata goes to the node. The URL's auth headers still do.

**From the node to you:**

- The router passes only the node's `Content-Type`, `Content-Encoding`, `Retry-After`
  and `Date`, plus the headers the chain's spec declares for replies.
- The node's trailers are not forwarded.
- The router adds its own [response headers](../api/directives.md#response-headers). On
  success they come as response headers, and on an error as trailers.

**Block height.** On Cosmos Hub, `x-cosmos-block-height` sets the block a request asks
for: `latest`, `earliest` or a number. The router uses it to pick a node that holds that
block, and in the cache key. The header is forwarded to the node, and the node's own
`x-cosmos-block-height` comes back to you. The router never writes this header itself.

## How the router reads a gRPC reply

Any status other than `OK` is a node error. The router does not read the reply body.

So a Cosmos `BroadcastTx` reply whose `tx_response.code` is not `0` is not an error on
gRPC: the status is `OK`, and it is an answer. On [REST](rest.md#how-the-router-reads-a-rest-reply)
the same reply is a node error. See [Writes](#writes).

On Cosmos chains, three message rules run first: `account sequence mismatch` is
`CHAIN_INVALID_SEQUENCE` (3012), `insufficient fee` is `CHAIN_INSUFFICIENT_FEE` (3013),
and `account not found` is `CHAIN_ACCOUNT_NOT_FOUND` (3107). None is retried or counts
against the node. So a `NOT_FOUND` that says `account not found` is not retried.

The general rules follow, and the first match decides. *Counts against the node* means
the reply is evidence that the node is broken: the node is marked unhealthy and its
consecutive-failure count goes up (see [`--bench-after`](../reference/cli.md)).

| Node's status | Code | Retried on another node? | Counts against the node? |
| --- | --- | --- | --- |
| `INVALID_ARGUMENT` (3) | `USER_INVALID_PARAMS` (4003) | No | No |
| `NOT_FOUND` (5), `OUT_OF_RANGE` (11) | `NODE_DATA_NOT_HELD` (2017) | Yes | No |
| `UNIMPLEMENTED` (12) | `NODE_UNIMPLEMENTED` (2008) | Yes \* | No |
| `ABORTED` (10) | `NODE_ABORTED` (2019) | No | No |
| A message with `too many requests`, `rate limit`, `ratelimit` or `enhance_your_calm` | `NODE_RATE_LIMITED` (2005) | Yes, and the node is held off | No |
| `UNAVAILABLE` (14), sent by the node | `NODE_SERVICE_UNAVAILABLE` (2006) | Yes | Yes |
| A message with `unimplemented`, `not implemented` or `service not found` | `NODE_UNIMPLEMENTED` (2008) | Yes | No |
| A message that contains an HTTP status number | The same code as the HTTP rows on [JSON-RPC](jsonrpc.md#how-the-router-reads-a-json-rpc-reply), for example `500` is `NODE_INTERNAL_ERROR` (2003) and `404` is `NODE_ENDPOINT_NOT_FOUND` (2009) | As on JSON-RPC | As on JSON-RPC |
| `RESOURCE_EXHAUSTED` (8) with a retry delay (`grpc-retry-pushback-ms` or `retry-after`) | `NODE_RATE_LIMITED` (2005) | Yes, and the node is held off for that delay | No |
| Any other status, for example `PERMISSION_DENIED` (7), `UNAUTHENTICATED` (16), `INTERNAL` (13) | `UNKNOWN_ERROR` (0) | Yes | No, but it lowers the node's availability score |

\* Retried on another node, except for a method the spec does not list: then the first
refusal is the answer.

The HTTP numbers are matched anywhere in the message: `401`, `404`, `405`, `413`, `429`,
`500` to `504`, `520` to `527`, and `530`.

**When the node never answered**, the router reads the failure itself. All of these are
retried and count against the node.

| Failure | Code |
| --- | --- |
| The router's own deadline passed, including a `DEADLINE_EXCEEDED` that echoes it | `PROTOCOL_CONTEXT_DEADLINE` (1007) |
| Connection refused | `PROTOCOL_CONNECTION_REFUSED` (1002) |
| The node's name does not resolve | `PROTOCOL_DNS_FAILURE` (1003) |
| Network or host unreachable | `PROTOCOL_NETWORK_UNREACHABLE` (1009) |
| Any other failure to reach the node, for example a failed TLS handshake | `PROTOCOL_PROVIDER_UNAVAILABLE` (1012) |

A call the router cancelled itself, for example because you went away or another node
answered first, does not count against the node. A `DEADLINE_EXCEEDED` the node sends
before the router's deadline is the node's own error, and falls in the last row of the
first table.

**When every node fails**, you get one node's own status: the first error that is not
retried, or else the first node error.

## Writes

A write is a method the chain's spec puts in the write category. On Cosmos Hub that is
`cosmos.tx.v1beta1.Service/BroadcastTx`. It is sent to several nodes at once, as on
every interface (see [Writes on every interface](index.md#writes-on-every-interface)).

- The first `OK` reply answers you.
- If no node accepted the write and one of them may have received it, you get `UNKNOWN`
  with a message that contains `transaction status unclear`.
- A node error that arrives after another node accepted the write does not count against
  that node.

!!! warning "On gRPC, a refused transaction can answer you"
    A Cosmos node that refuses a transaction at its first check still replies `OK`, with
    a `tx_response.code` that is not `0`. The router does not read that code, so the
    first such reply can answer you even when another node accepted the transaction.
    Read `tx_response.code` in the reply, and look the transaction hash up before you
    sign a new one.

## Streaming

The router serves a server-streaming call only for a method the chain's spec declares as
a subscription. Cosmos Hub declares none, so it has no streaming. Sui's spec declares
three: `sui.rpc.v2.SubscriptionService/SubscribeCheckpoints`, `SubscribeEvents` and
`SubscribeTransactions`.

- **Other server-streaming calls** are refused with `UNKNOWN`. The router tries other
  nodes up to its retry limit, and the nodes are not marked unhealthy. Two kinds of call
  are not caught and go out as a unary call instead: a method the spec does not list,
  and a call whose descriptor the router has not loaded yet.
- **Shared.** Clients that call the same method with the same request bytes share one
  stream on the node. Each client gets its own subscription id, in the response header
  `x-lava-grpc-sub-id`. The node's stream closes when the last client leaves.
- **Messages.** The router decodes each message from the node with the method's
  descriptor and encodes it again for each client. A message carries no metadata.
- **Starting.** If the stream cannot start, for example because no node or no descriptor
  is available, you get `UNKNOWN` with `failed to start gRPC subscription`. The router
  does not try another node.

| What happens on the node's side | What your stream gets |
| --- | --- |
| The stream ends normally | It ends with `OK` |
| The node refuses with `INVALID_ARGUMENT`, `NOT_FOUND`, `OUT_OF_RANGE`, `ALREADY_EXISTS`, `FAILED_PRECONDITION` or `UNIMPLEMENTED` | It ends with the node's status and message |
| The node refuses with `PERMISSION_DENIED`, `UNAUTHENTICATED` or `RESOURCE_EXHAUSTED` | It ends with `UNAVAILABLE`, `upstream refused the subscription`. A rate-limited node is also held off. |
| Any other error | The router opens the stream again on the same node, with a growing delay, and you stay attached. After more than 5 restores without progress it gives up: `UNAVAILABLE`, `upstream subscription lost`. A restore that stays up for 30 seconds counts as progress. |
| You fall 100 messages behind | It ends with `UNAVAILABLE` |
| The router shuts down | It ends with `UNAVAILABLE`, `router is shutting down` |

## Replies the router writes

When the router speaks for itself, you get one of these statuses.

| Status | When |
| --- | --- |
| `UNKNOWN` (2), message `Failed to SendRelay ErrMsg: {"Error_GUID":"<guid>","Error":"<reason>"}` | A request refused before any node is called, no node answered, a refused streaming call, a write whose outcome is unclear, or a failed cross-validation. Any router headers, for example the cross-validation ones, come as trailers. |
| `UNKNOWN` (2), message starting with `failed to start gRPC subscription` | A stream could not start |
| `UNAVAILABLE` (14) | The method name could not be read, or the router gave up a stream |
| `CANCELED`, `DEADLINE_EXCEEDED` | You cancelled a stream, or its deadline passed |

`Error_GUID` matches the `Lava-Guid` header.

A node's error reaches you with its status code and message only. Its status details and
trailers are dropped, and secrets in the message are removed.

## Example requests and replies

The router listens on `3361` in these examples. Replies are shortened with `...`. They
follow the behaviour on this page and were not captured from a running router.

**List the services.** The router answers from one node's reflection.

```bash
grpcurl -plaintext 127.0.0.1:3361 list
```

```text
cosmos.auth.v1beta1.Query
cosmos.bank.v1beta1.Query
cosmos.base.tendermint.v1beta1.Service
...
```

**A read.** The node's reply reaches you unchanged.

```bash
grpcurl -plaintext 127.0.0.1:3361 cosmos.base.tendermint.v1beta1.Service/GetLatestBlock
```

```json
{"blockId": {...}, "block": {...}}
```

**A read at a height.** `x-cosmos-block-height` sends the request to a node that holds
that block.

```bash
grpcurl -plaintext -H 'x-cosmos-block-height: 1000000' \
  -d '{"address":"cosmos1...","denom":"uatom"}' \
  127.0.0.1:3361 cosmos.bank.v1beta1.Query/Balance
```

```json
{"balance": {"denom": "uatom", "amount": "..."}}
```

**A request the router refuses.** A router refusal arrives as `UNKNOWN`, with the
reason inside the message.

```text
ERROR:
  Code: Unknown
  Message: Failed to SendRelay ErrMsg: {"Error_GUID":"<guid>","Error":"<reason>"}
```
