---
title: "REST"
description: "How Smart Router serves REST: how it forwards a request, which node statuses it retries, which count against the node, and what the caller gets."
---

# REST

A REST listener sends each HTTP request to a node that serves the chain's REST API and
returns the node's reply unchanged. This page lists how the router reads every HTTP
status: which ones it retries on another node, which count against the node, and which
go back to the caller.

## How the router serves a REST request

| What comes in | What the router does |
| --- | --- |
| Any HTTP method on any path, for example `GET /cosmos/base/tendermint/v1beta1/blocks/latest` | Sends the same method, path and query string to a node. Methods that carry a body send the body too. |
| A write: a request the chain's spec marks as a write, for example `POST /cosmos/tx/v1beta1/txs` | Sends it to several nodes at once (see [Writes on every interface](index.md#writes-on-every-interface)). The first node that accepts it answers the caller. |
| A WebSocket upgrade | Not served. A REST listener has no WebSocket route, so a REST chain has no subscriptions. |

You set the interface per listener with `api-interface: "rest"` in the
[config file](../configuration/config-file.md).

## How the router reads a REST reply

A REST node has no error object, so the router reads the HTTP status: **every status
outside 2xx is a node error**. The body still reaches the caller unchanged.

A 2xx reply is a node error in one case: a Cosmos transaction reply whose
`tx_response.code` is not `0`. The router takes the error message from
`tx_response.raw_log`.

The rules run from specific to general. A body that names what went wrong is matched
first, whatever the status. The status alone is the fallback. *Counts against the node*
means the reply is evidence that the node is broken: the node is marked unhealthy and its
consecutive-failure count goes up (see [`--bench-after`](../reference/cli.md)).

| Reply | Code | Retried on another node? | Counts against the node? |
| --- | --- | --- | --- |
| Body says `endpoint not found`, `route not found` or `path not found`, any status | `NODE_ENDPOINT_NOT_FOUND` (2009) | Yes | No |
| Body says `method not allowed`, any status | `NODE_METHOD_NOT_ALLOWED` (2010) | Yes | No |
| Body says the block is beyond the node's head (`larger than the current largest block`, `requested block height is bigger then the chain length`, or a 400 with `unknown block`) | `CHAIN_BLOCK_NOT_FOUND` (3201) | Yes | No |
| 500 with `is not available, lowest height` (Cosmos, pruned height) | `CHAIN_STATE_PRUNED` (3204) | Yes | No |
| 500 with `unable to retrieve header and parent` (Substrate sidecar, unknown block) | `CHAIN_BLOCK_NOT_FOUND` (3201) | Yes | No |
| 500 with `transaction not found` (MultiversX) | `CHAIN_TX_NOT_FOUND` (3202) | Yes | No |
| 500 with `decoding bech32 failed` (Cosmos, malformed address) | `USER_INVALID_PARAMS` (4003) | No | No |
| **404** | `NODE_DATA_NOT_HELD` (2017) | **Yes** | No |
| **401, 402, 403, 407, 426, 451** | `NODE_ACCESS_DENIED` (2018) | **Yes** | No |
| 405 | `NODE_METHOD_NOT_ALLOWED` (2010) | Yes | No |
| 501 | `NODE_UNIMPLEMENTED` (2008) | Yes | No |
| 410 | `CHAIN_STATE_PRUNED` (3204) | Yes | No |
| 429 | `NODE_RATE_LIMITED` (2005) | Yes, and the node is held off | No |
| 408, 503 | `NODE_SERVICE_UNAVAILABLE` (2006) | Yes | Yes |
| 500, any other body | `NODE_INTERNAL_ERROR` (2003) | Yes | Yes |
| 502 | `NODE_BAD_GATEWAY` (2015) | Yes | Yes |
| 504, 522, 524 | `NODE_GATEWAY_TIMEOUT` (2014) | Yes | Yes |
| 520, 521, 523, 525, 526, 527, 530 | `NODE_SERVER_ERROR` (2004) | Yes | Yes |
| 409 | `CHAIN_TX_ALREADY_KNOWN` (3007) | No | No |
| 400, 406, 411, 412, 414, 415, 416, 417, 428, 431 | `USER_INVALID_REQUEST` (4002) | No | No |
| 422 | `USER_INVALID_PARAMS` (4003) | No | No |
| 413 | `USER_REQUEST_TOO_LARGE` (4006) | No | No |
| Any other status, including 3xx | `UNKNOWN_ERROR` (0) | Yes | No, but it lowers the node's availability score |

The codes are explained in [Error codes](../reference/error-codes.md).

## Statuses the router retries on another node

### A 404 is retried

A plain 404 means "not here": the node does not hold the data, has not seen it yet, or a
gateway in front of it does not route the path. Another node may answer, so the router
tries one. The node that answered 404 is not scored. The reply then carries a
`Lava-Retries` header that counts the extra attempt (see
[Response headers](../api/directives.md#response-headers)).

A 404 whose body names a missing endpoint, route or path is a route refusal,
`NODE_ENDPOINT_NOT_FOUND`. It is also retried on another node, and the node that refused
is not scored.

### A 401, 402, 403, 407, 426 or 451 is retried

These statuses are the endpoint refusing the router itself: its credentials, its plan or
quota, a WAF or IP rule, a proxy that wants credentials, a protocol it will not speak, or
a region it will not serve. Each provider has its own credentials and rules, so another
provider can serve the same request. The router tries one and does not count the refusal
against the node.

### A 429 is retried, and the node is held off

A 429 is `NODE_RATE_LIMITED`. The router tries another node and holds the rate-limited
node off. The node is busy, not broken, so it is not marked unhealthy.

## When a 500 counts against the node

A 500 is read as the caller's answer only when its body is one of the forms in the table
above. Any other 500 is `NODE_INTERNAL_ERROR` and counts against the node. A broken node
that answers 500 with an empty or HTML body is still taken out of rotation.

## Writes are not retried

The retries on this page are for reads. A write goes to several nodes at once and is not
sent again, unless every node it went to was rate limited (a 429 or a rate-limit error).
A rate-limited node turns a write away before it runs it, so sending the write again
cannot run it twice. The first node that accepts the write answers the caller, whatever
the other nodes replied. `Lava-Retries` is always `0` for a write, so the header is
absent.

On GraphQL a write is never sent again, even when every node was rate limited. See
[Writes](graphql.md#writes) on the GraphQL page.

## Example requests and replies

The router listens on `3360` in these examples. Bodies are shortened with `...`.

**A read.** The node's status and body reach the caller unchanged.

```bash
curl -i http://127.0.0.1:3360/cosmos/base/tendermint/v1beta1/blocks/latest
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"block_id": {...}, "block": {...}}
```

**A 404 that was retried.** The first node did not hold the transaction, so the router
tried a second node. Neither node held it, so the caller gets a 404, and
`Lava-Retries: 1` counts the extra attempt.

```bash
curl -i http://127.0.0.1:3360/cosmos/tx/v1beta1/txs/<hash>
```

```http
HTTP/1.1 404 Not Found
Lava-Retries: 1

{...}
```

**A write.** The router sends it to every eligible node at once and returns the reply of
the first node that accepts it. There is no `Lava-Retries` header.

```bash
curl -i -X POST http://127.0.0.1:3360/cosmos/tx/v1beta1/txs \
  -H 'Content-Type: application/json' \
  -d '{"tx_bytes": "...", "mode": "BROADCAST_MODE_SYNC"}'
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"tx_response": {"code": 0, "txhash": "...", ...}}
```
