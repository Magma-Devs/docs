---
title: "GraphQL interface"
description: "How Smart Router serves GraphQL: what it accepts and refuses, how it reads a node's reply, what a write returns, and what your client gets back."
---

# GraphQL interface

Smart Router serves GraphQL chains on a listener with `api-interface: graphql`. Today that is
Sui mainnet (`chain-id: SUI`). This page covers what the router accepts, what it refuses before
calling a node, how it reads a node's reply, what a write returns, and every reply the router
writes itself.

!!! info "A node's reply reaches you unchanged"
    The router sends your request body to the node byte for byte. It passes the node's reply
    back as the node sent it, errors and `Content-Type` included. It only removes its own
    credentials from any text a node echoes back. The router writes a reply itself only in the
    cases listed under [Replies the router writes](#replies-the-router-writes).

## Calling the endpoint

| | |
| --- | --- |
| Method | `POST`, any path, with a JSON object body: `query`, and optionally `operationName`, `variables`, `extensions` |
| `OPTIONS` | `204` |
| Any other method (`GET`, `PUT`, `PATCH`, `DELETE`, `HEAD`) | `405` with `Allow: POST`. No node is called. |
| Batch (a JSON array body) | Refused with `400`. No node is called. |
| Subscription | Refused with `400`. No node is called. |
| Upstream url | The node's full GraphQL endpoint, path included. See [The config file](../configuration/config-file.md). |

```bash
curl -s http://127.0.0.1:<port>/graphql \
  -H 'content-type: application/json' \
  -d '{"query":"{ chainIdentifier epoch { epochId } }"}'
```

## Requests the router refuses

The router checks every request before it calls a node, in the order below. The first check
that fails refuses the request, and no node is called.

| Refused when | Reply |
| --- | --- |
| The body is not a JSON object (an array, or not JSON) | `400`, `REQUEST_REFUSED` |
| A body key (`query`, `operationName`, `variables`, `extensions`) is repeated, or differs only by letter case; `query` is missing or empty; `variables` is not an object | `400`, `REQUEST_REFUSED` |
| `query` does not parse | `400`, code `GRAPHQL_PARSE_FAILED` |
| The query is nested more than 256 levels, has more than 300 root fields, or nests fragments more than 32 levels | `400`, `REQUEST_REFUSED` |
| A fragment is cyclic or undefined | `400`, `REQUEST_REFUSED` |
| The document has several operations and no `operationName`; `operationName` is not in the document; the operation is a subscription | `400`, `REQUEST_REFUSED` |
| One document holds both a query and a mutation; a mutation has more than one root field (`__typename` not counted) | `400`, `REQUEST_REFUSED`, `Lava-Write-Outcome: not_sent` |

## How the router reads your request

The router reads a request the way the GraphQL node will run it, so that routing, compute
units, caching and metrics match what the node does.

- **Write or read.** A document that holds any mutation is a write, whatever `operationName`
  selects. On Sui, `executeTransaction` is the write; `simulateTransaction` is a read.
- **Method names** are the root fields of the selected operation, after `@skip` and `@include`
  are applied. A field repeated under one response key counts once.
- **Variables.** A variable's declared default applies when the request does not send it.
- **Checkpoint.** On Sui, a checkpoint argument pins the read only as a whole number. A string
  such as `"100"` is not a pin.

## How the router reads a node's reply

A GraphQL node usually answers HTTP `200` and puts any failure inside the body, in an `errors`
list. So the router reads the body to decide what the reply means: an answer, an error in your
request, or a node that could not serve it. The first row that matches decides.

*Counts against the node* means the reply is evidence the node is broken. It advances the
node's consecutive-failure count (see [`--bench-after`](../reference/cli.md)).

| Reply | Read as | Asked on another node? | Counts against the node? |
| --- | --- | --- | --- |
| A write whose `executeTransaction` has `effects`, under any HTTP status | Accepted (see [Writes](#writes)) | No | No |
| HTTP `429` | Node rate limited | Yes, and the node is held off | No |
| HTTP `401`, `402`, `403` | The node refused the router (credentials, plan) | Yes | No |
| A `2xx` that is not a GraphQL reply: `{}`, `{"data": null}` with no errors, `errors: []` with no data, a body that is not JSON | Node fault | Yes | Yes |
| `GRAPHQL_VALIDATION_FAILED`, `BAD_USER_INPUT` | An error in your request | No, returned as is | No |
| An error with no code, no `path` and no `data`, on a query | An error in your request | No, returned as is | No |
| `GRAPHQL_PARSE_FAILED` from a node | Node fault (the router already parsed the same query) | Yes | Yes |
| `INTERNAL_SERVER_ERROR`, `UNAVAILABLE`, `REQUEST_TIMEOUT`, `DEADLINE_EXCEEDED` | Node fault | Yes | Yes |
| `FEATURE_UNAVAILABLE` | The node cannot serve this | Yes | No |
| An error with no code, with a `path` or beside data | Unknown | Yes | No |
| A `2xx` with `data` and no errors | Answer | No | No |
| `501`, or any other `4xx` with no GraphQL body (`400`, `404`, `413`, `422`, ...) | The node cannot serve this | Yes | No |
| `408`, any other `5xx`, a timeout, a dropped connection | Node fault | Yes | Yes |

A chain can name messages that mean something else. On Sui, for example, some
`BAD_USER_INPUT` messages mean the node is behind, so the router asks another node. Those
chain rules come before the rows above. An error code that is missing, unknown or written as a
number counts as no code, and the reply is still read.

**Partial replies.** When a reply has both `data` and `errors`, each error is read on its own.
The router asks another node if any error is not an error in your request. Otherwise you get
the reply as is. A partial reply is never cached.

**Nulls are answers.** A `null` field is the node's answer and is never turned into an error.
One Sui exception: a `null` from `transaction(digest)` makes the router ask one more node, then
return the `null` if that node agrees. A node that is behind may not hold a transaction yet.

**`lava-identified-node-error`** marks every reply that is not a clean answer. A transaction
that failed on chain (`effects.status` is `FAILURE`) ran and paid gas, so it is an answer and
carries no such header.

**When every node fails**, you get one of the nodes' own replies. If every node answered `429`,
you get a `429` with its `Retry-After`. If one node answered `503` with a body and the others
`429`, you get the `503` and its body. The router writes its own reply only when no node sent
any reply at all.

## Writes

A write (an `executeTransaction` mutation on Sui) is sent once to each node, or to the pinned
node only when you [pin](../api/directives.md#pin-to-a-specific-node) one. It is never sent
again, never cached and never hedged, including when every node answered `429`. The first copy a
node accepts answers you.

Every write reply carries `Lava-Write-Outcome`, and `Lava-Tx-Hash` when the router can compute
the transaction digest from your request.

| A node's reply to its copy | Outcome |
| --- | --- |
| `executeTransaction` has `effects`, whether `SUCCESS` or `FAILURE`, under any HTTP status | `accepted` |
| HTTP `429`, `401`, `402`, `403`; the node refused it before it reached the network; a quota error inside a `2xx` | `rejected` |
| No connection was made | `not_sent` |
| Anything else: a timeout, a `5xx`, an error with no code, `effects: null` | `unknown` (it may have run) |

Across the copies, the strongest outcome wins: `accepted`, then `unknown`, then `rejected`, then
`not_sent`.

### When the outcome is unknown

If no copy was accepted and at least one may have run, you get a `500` from the router:

```json
{
  "errors": [{
    "message": "Status unknown - this transaction may have been broadcast. Look up <digest> before signing anything new. Re-sending the same signed bytes is safe. If you replace it, reuse the same input objects.",
    "extensions": {
      "code": "OUTCOME_UNKNOWN",
      "router_error": "OUTCOME_UNKNOWN",
      "guid": "<same as the Lava-Guid header>",
      "write_outcome": "unknown",
      "tx_hash": "<digest>"
    }
  }]
}
```

The nodes' own error messages may be added, with credentials removed, in
`extensions.node_errors`. When the router cannot compute the digest, `tx_hash` is absent and the
message says how to find the transaction without it.

!!! warning "On `OUTCOME_UNKNOWN`, look the digest up before you sign again"
    One node may have submitted the transaction even though no node confirmed it. If your client
    treats the `500` as a failure and signs a new transaction with fresh coins, it can pay twice.
    Look up `tx_hash` first. If the transaction is there, stop. Re-sending the same signed bytes
    is safe. A client that does not read `extensions.code` still gets a `500`.

## Replies the router writes

When the router refuses a request or speaks for itself, you get one GraphQL error, with
`Content-Type: application/json` and no `data` key:

```json
{"errors":[{"message":"<plain text>","extensions":{"code":"<router error>","router_error":"<router error>","guid":"<guid>"}}]}
```

`extensions.guid` equals the `Lava-Guid` header. `code` equals the router error, except for a
query that does not parse, where `code` is `GRAPHQL_PARSE_FAILED`.

| Case | Status | Router error |
| --- | --- | --- |
| A query that does not parse | `400` | `REQUEST_REFUSED` (code `GRAPHQL_PARSE_FAILED`) |
| Any other refusal before a node is called | `400` | `REQUEST_REFUSED` |
| A method other than `POST` or `OPTIONS` | `405`, `Allow: POST` | `REQUEST_REFUSED` |
| A write whose outcome is unknown | `500` | `OUTCOME_UNKNOWN` |
| No node sent any reply (connection refused or dropped) | `502` | `NO_PROVIDER_ANSWER` |
| Every node timed out | `504` | `NO_PROVIDER_ANSWER` |
| No node can take the request | `503` | `PROVIDER_UNAVAILABLE` |
| The router's own per-client rate limit | `429`, `Retry-After` | - |

A `429` from a node's vendor is a node reply, and reaches you as the node sent it.

## Caching

The router caches a read only when it is a clean answer that every node would give: no errors,
no root field that is `null` or `[]`. It never caches:

- writes;
- a reply with any error, partial replies included;
- a `null` or `[]` root field;
- on Sui, `simulateTransaction`, `serviceConfig` and introspection (`__schema`, `__type`),
  because nodes run different versions.

A field that carries no block, such as `chainIdentifier`, next to a read of the latest data
keeps the request a "latest" read, cached under the
[latest-block rules](../deployment/cache/index.md).

## Node health

A GraphQL node is held off, taken out and brought back by the same rules as on every other
interface. A head poll counts as healthy only when it is a clean answer: a poll answered `200`
with an error, or with no usable head, is a failed poll. A rate limit on a head poll slows that
poll only and does not hold off your requests to the node.
