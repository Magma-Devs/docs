---
title: "Request headers"
description: "Headers you send with one request to bypass the cache, pin a specific provider, or override routing while debugging."
---

# Directives

Directives are request headers that change how Smart Router handles one request. Use them when the default routing, caching, or timeout policy is not what you want for that call.

You send them as HTTP headers, or as call metadata on a gRPC listener ([Over gRPC](#over-grpc)).

## Request headers at a glance

| Header | Effect |
|---|---|
| `lava-select-provider` | [Prefer](#pin-to-a-specific-node) one named upstream. The cache is still checked first. |
| `lava-stickiness` | [Keep a session](#keep-a-session-on-one-node) on one upstream across replicas. |
| `lava-providers-block` | [Exclude](#steer-node-selection) named nodes (comma-separated). |
| `lava-extension` | [Force an extension](#override-the-extension) such as `archive`. |
| `lava-force-cache-refresh` | [Bypass the cache](#force-a-cache-refresh) and refresh the entry. |
| `lava-relay-timeout` | [Override the per-attempt timeout](#override-the-per-attempt-timeout) (Go duration). |
| `lava-cross-validation-max-participants` + `lava-cross-validation-agreement-threshold` | [Request cross-validation](#request-cross-validation). |
| `lava-debug-relay` | [Verbose per-attempt logging](#enable-debug-logging-for-one-request) for this request. |

Each header has its own section below. The router sends metadata back in [response headers](#response-headers).

## Pin to a specific node

```
lava-select-provider: <upstream-name>
```

This header sets a **preference** for one named upstream at node selection. It skips the QoS optimizer. When the request reaches selection, the named upstream serves it. If that upstream fails, [failover](../configuration/failover/index.md) policies still apply to the rest of the pool.

!!! warning "The cache answers first - a pinned request may never reach the named node"
    The router checks the response cache **before** node selection runs, and pinning does
    *not* bypass it. For a cacheable method with a warm cache entry, the response carries
    `Lava-Provider-Address: Cached` and the router never contacts the named node. This is
    true even when that node is unreachable.

    So a pinned request is **not a node health check**. For any cacheable method (and most
    reads are cacheable), you cannot tell an unreachable node from a healthy one: you get
    HTTP 200 and a real answer in both cases. When the point of the request is the *node*
    and not the data, pair the pin with [`lava-force-cache-refresh`](#force-a-cache-refresh).

!!! warning "`Lava-Provider-Address` is a response header, not a request directive"
    To pin a request, send **`lava-select-provider`**. The router only sends
    `Lava-Provider-Address` on the *response*, to name the node that served the request
    (see [Response headers](#response-headers)). If you send it as a *request* header, it
    has no effect and the router silently ignores it.

**When to use:** debugging an upstream, sticky requests within a session, or an A/B comparison of responses.

```bash
curl -X POST http://127.0.0.1:3360 \
  -H 'Content-Type: application/json' \
  -H 'lava-select-provider: my-eth-upstream-1' \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

To pin a gRPC call, send the same header as call metadata. See [Over gRPC](#over-grpc).

To reach the node itself, also send `lava-force-cache-refresh`, so the cache cannot answer
in the node's place. Do this for a health check, or to compare two nodes on the same query:

```bash
curl -X POST http://127.0.0.1:3360 \
  -H 'Content-Type: application/json' \
  -H 'lava-select-provider: my-eth-upstream-1' \
  -H 'lava-force-cache-refresh: true' \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

If the node is unreachable, the request then fails with an error instead of returning a cached answer.

## Keep a session on one node

```
lava-stickiness: <your-session-id>
```

This header sends every request with the same id to the same upstream, on every router replica. The value is any string you choose, such as a worker id, a batch id, or a user id.

Unlike with `lava-select-provider`, you do not name the node. The router picks one on the first request and keeps the rest of the session on it.

**When to use:** a sequence of calls whose answers have to agree with each other. For example, you read the chain head and then fetch that block. A node a few blocks behind would return an empty result for a block that exists.

!!! warning "Send the id on **every** call in the sequence"
    If you send it only on the later call, the first call is not pinned. Different nodes
    can then answer the two calls, which is the problem this header exists to prevent.

```bash
curl -X POST http://127.0.0.1:3360 \
  -H 'Content-Type: application/json' \
  -H 'lava-stickiness: ingest-batch-42' \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

To work across replicas, the header needs a cache backend and `--shared-state`. Without them, it only applies within a single replica. If the chosen node cannot serve a request, the request fails. No other node serves it. See [Sticky sessions](../configuration/sticky-sessions.md) for the full behaviour and limits.

## Force a cache refresh

```
lava-force-cache-refresh: true
```

This header bypasses the cache for this request. The relay goes upstream, and the router returns the response and refreshes the cache entry.

The header's **presence** triggers the refresh, not its value. `lava-force-cache-refresh: false` (or any other value) still forces it. Send the header only when you want a refresh.

**When to use:** a known-stale entry, a suspected reorg, a check after a deploy, and any request whose purpose is to reach a *specific node* and not to get data (see [the pin caveat](#pin-to-a-specific-node)).

```bash
curl -X POST http://127.0.0.1:3360 \
  -H 'Content-Type: application/json' \
  -H 'lava-force-cache-refresh: true' \
  -d '{"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":["0x1234567",false],"id":1}'
```

## Override the per-attempt timeout

```
lava-relay-timeout: 12s
```

This header sets the timeout for each upstream attempt of this request. That is how long the router waits on one node before it also tries the next one. The value is any Go duration string (`500ms`, `5s`, `1m30s`). The router keeps the value within these bounds:

- The router ignores a zero or negative value, and also a value that does not parse. The request then keeps the router's own timeout.
- The router raises a value under `300ms` to `300ms`. It does *not* raise the value to the `--min-relay-timeout` floor, so a client can still ask for less than that floor.
- The router lowers a value above the request's own budget to that budget. The own budget is what the request gets with no header. It is `--default-processing-timeout`, doubled for methods of 50 CU or more. Hanging, stateful or 100+ CU methods get six times the flag value. A method whose own timeout is longer than that keeps its own timeout (Bitcoin's `sendrawtransaction` gets about 20 minutes). An operator can let clients go further, up to `--max-caller-relay-timeout` (default `0`: no extension).

A value at or above the request's own budget turns hedging off for that request. The attempt timeout is also the hedge interval, so the two become equal. Retrying after a failed attempt still works, but a node that stops answering holds the request for the whole budget.

The response carries [`Lava-Relay-Timeout-Applied`](#response-headers) with the timeout the router actually used.

**When to use:** known-fast methods where you do not want to wait (hedge sooner), or known-slow methods (`debug_traceTransaction` on a deep block) within their own budget.

## Enable debug logging for one request

```
lava-debug-relay: true
```

This header writes verbose per-attempt logs for this request only. The global log level does not change.

**When to use:** investigating a specific failure that users can see, without flooding the logs.

## Steer node selection

These headers change which upstream(s) the request can use:

```
lava-select-provider: my-eth-upstream-2
lava-providers-block: my-eth-upstream-3,my-eth-upstream-4
```

| Header | Effect |
|---|---|
| `lava-select-provider` | Prefer one named node for this request (the [pin](#pin-to-a-specific-node) header). A cache hit still answers before selection runs. |
| `lava-providers-block` | Comma-separated nodes to **exclude** from selection for this request. Selection picks from the rest of the pool. |

You can exclude any number of nodes. The router ignores spaces around the commas. The exclusion also applies to backup nodes. If the list covers every node that could serve the request, the request fails. The router never falls back to a node you excluded.

**When to use:** to avoid a node you have seen misbehave, or to force a comparison against a specific one. Failover still applies across the nodes that remain eligible.

## Override the extension

```
lava-extension: archive
```

This header forces a request onto an extension (e.g. `archive`). Without it, the router infers the extension from the requested block. The value is case-insensitive. Only nodes whose config declares the matching add-on are eligible. See the per-chain [Upstream capabilities](../reference/chains/ethereum.md#upstream-capabilities).

If **no** node on the router declares the add-on, the router does not refuse the request. An ordinary node serves it without the extension, and the response carries `Lava-Extension-Unavailable` naming what was dropped. Treat such an answer as coming from a node without the extension. For `archive`, a historical query may come back incomplete or empty. The router also logs a warning once per extension, so the operator can add a node that supports it.

**When to use:** a historical query the router would otherwise route to a non-archive node.

## Request cross-validation

```
lava-cross-validation-max-participants: 3
lava-cross-validation-agreement-threshold: 2
```

These headers send this request to `max-participants` nodes in parallel. The router returns only when `agreement-threshold` of them return matching responses. You must send both headers together. Operator policy applies: an operator can mandate, cap, or forbid cross-validation per method. See [Cross-validation](../configuration/failover/cross-validation.md).

**When to use:** reads that must be correct (`eth_getLogs`, `debug_*`, `eth_call` at a fixed block), where one lying node is not acceptable. It multiplies upstream cost, so pair it with caching.

## Combining directives

You can send several directive headers on one request:

```bash
curl -X POST http://127.0.0.1:3360 \
  -H 'Content-Type: application/json' \
  -H 'lava-select-provider: my-eth-upstream-2' \
  -H 'lava-relay-timeout: 30s' \
  -H 'lava-debug-relay: true' \
  -d '{"jsonrpc":"2.0","method":"debug_traceTransaction","params":["0x..."],"id":1}'
```

## Over gRPC

A gRPC listener reads the same directives from **call metadata**. gRPC sends metadata as HTTP/2 headers, and the router parses it the same way as the headers of an HTTP request. Use the same names as above:

```bash
grpcurl -plaintext \
  -H 'lava-select-provider: my-cosmos-upstream-1' \
  127.0.0.1:3361 \
  cosmos.bank.v1beta1.Query/TotalSupply
```

In code, attach the metadata to the call:

=== "Go"

    ```go
    ctx := metadata.AppendToOutgoingContext(ctx, "lava-select-provider", "my-cosmos-upstream-1")
    resp, err := client.TotalSupply(ctx, &banktypes.QueryTotalSupplyRequest{})
    ```

=== "Python"

    ```python
    response = stub.TotalSupply(request, metadata=[("lava-select-provider", "my-cosmos-upstream-1")])
    ```

The [response headers](#response-headers) come back as response metadata with lowercase names. `lava-provider-address` names the upstream that served the call, and `grpcurl -v` prints it.

## Response headers

Smart Router adds metadata to every response about how the relay was served. These headers are the main signal for debugging routing and failover from the client side.

| Header | Meaning |
|---|---|
| `Lava-Provider-Address` | The node that finally served the response. The literal value **`Cached`** means the [cache](../deployment/cache/index.md) answered and the router contacted *no* node, even when the request named one with `lava-select-provider`. |
| `Lava-Retries` | Number of retry attempts made for this relay. |
| `Provider-Latest-Block` | Latest block the serving node reported. |
| `Lava-Guid` | Unique request id. Use it to find the request in logs and traces. |
| `Lava-Errored-Providers` | Nodes that errored on this request. |
| `Lava-Node-Errors-providers` | Nodes that returned a node-level error. |
| `lava-identified-node-error` | The body is a node error that the router recognised, not a router failure. Present whether the error came from a live node or from a cache replay. **Not always a fault signal:** on an XRP Ledger `submit` it also marks a ledger verdict such as `tefPAST_SEQ`. In that case the node answered correctly and is not penalised. |
| `Lava-Reported-Providers` | Nodes reported as misbehaving. |
| `Smart-Router-Version` | Router build serving the request. |
| `Lava-Extension-Unavailable` | Comma-separated extensions requested with [`lava-extension`](#override-the-extension) that no node on this router offers. The response was served **without** them. Absent when every requested extension was honoured. |
| `Lava-Relay-Timeout-Applied` | The per-attempt timeout the router used, as a Go duration, after [bounding `lava-relay-timeout`](#override-the-per-attempt-timeout). Only present on a request that sent that header. When the router ignored the value, it carries the router's own timeout. Absent when the request failed without any reply. |
| `lava-selection-stats` | Node-selection debug stats. Only present when the router runs with `--enable-selection-stats`. |

When cross-validation runs, the router also returns `lava-cross-validation-status`, `lava-cross-validation-agreeing-providers`, `lava-cross-validation-disagreeing-providers` and `lava-cross-validation-pending-providers` (queried providers whose answer had not arrived when the reply was built). On failure, it also returns `lava-cross-validation-failure-reason` (`no-agreement`, `insufficient-responses`, `diversity-unmet`, `group-quorum-unmet`, or a structural `insufficient-capacity` / `insufficient-groups`).

A failed quorum also returns `lava-cross-validation-plurality-size` and `lava-cross-validation-plurality-providers`. They show how many providers returned the most common response, and which ones (sorted, comma-separated). The providers list is empty on a tie. The size is `0` when no non-empty response arrived. These headers name who came closest, not who was right, so `lava-cross-validation-disagreeing-providers` still lists every provider that answered. A structural `insufficient-capacity` / `insufficient-groups` failure queries no provider and returns neither header.

## Operator restrictions

Smart Router honours the request directives above as a fixed set. There is no per-header, server-side setting to disable one directive, such as node pinning. The only restriction an operator can configure is **cross-validation policy**: an operator can mandate, cap, or forbid cross-validation per `(chain, interface, method)` in the config file. See [Cross-validation](../configuration/failover/cross-validation.md) and [the config file](../configuration/config-file.md#cross-validation).
