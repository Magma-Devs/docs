# Directives

Override Smart Router's default behaviour for a single request by setting HTTP headers. Use them when the default routing, caching, or timeout policy isn't what you want for this specific call.

## Request headers at a glance

| Header | Effect |
|---|---|
| `lava-select-provider` | [Pin](#pin-to-a-specific-node) the request to one named upstream. |
| `lava-providers-block` | [Exclude](#steer-node-selection) named nodes (comma-separated, **max 2**). |
| `lava-extension` | [Force an extension](#override-the-extension) such as `archive`. |
| `lava-force-cache-refresh` | [Bypass the cache](#force-a-cache-refresh) and refresh the entry. |
| `lava-relay-timeout` | [Override the per-attempt timeout](#override-the-per-attempt-timeout) (Go duration). |
| `lava-cross-validation-max-participants` + `lava-cross-validation-agreement-threshold` | [Request cross-validation](#request-cross-validation). |
| `lava-debug-relay` | [Verbose per-attempt logging](#enable-debug-logging-for-one-request) for this request. |

Each is detailed below. The router's [response headers](#response-headers) carry metadata back.

## Pin to a specific node

```
lava-select-provider: <upstream-name>
```

Routes this request to one named upstream, bypassing the QoS optimizer. The named upstream serves it directly. If it fails, [failover](../configuration/failover/index.md) policies still apply against the rest of the pool.

!!! warning "`Lava-Provider-Address` is a response header, not a request directive"
    To pin a request, send **`lava-select-provider`**. `Lava-Provider-Address` is only
    emitted by the router on the *response* to name the node that served the request
    (see [Response headers](#response-headers)) — sending it as a *request* header has no
    effect and is silently ignored.

**When to use:** debugging an upstream, sticky requests within a session, A/B comparing responses.

```bash
curl -X POST http://127.0.0.1:3360 \
  -H 'Content-Type: application/json' \
  -H 'lava-select-provider: my-eth-upstream-1' \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

## Force a cache refresh

```
lava-force-cache-refresh: true
```

Bypasses the cache for this request. The relay goes upstream, the response is returned, and the cache entry is refreshed.

The refresh triggers on the header's **presence**, not its value — `lava-force-cache-refresh: false` (or any value) still forces it. Send the header only when you mean it.

**When to use:** known-stale entry, suspected reorg, post-deploy verification.

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

Sets the timeout for each upstream attempt of this request. Format: any Go duration string (`500ms`, `5s`, `1m30s`). The value is used **verbatim** — unlike the server-side default it is *not* clamped to the `--min-relay-timeout` floor, so a client can ask for less.

**When to use:** known-slow methods (`debug_traceTransaction` on a deep block), or known-fast methods you don't want to wait for.

## Enable debug logging for one request

```
lava-debug-relay: true
```

Emits verbose per-attempt logs for this request only — without changing the global log level.

**When to use:** investigating a specific user-visible failure without flooding logs.

## Steer node selection

A few headers override which upstream(s) the request can use:

```
lava-select-provider: my-eth-upstream-2
lava-providers-block: my-eth-upstream-3,my-eth-upstream-4
```

| Header | Effect |
|---|---|
| `lava-select-provider` | Route this request to one named node (the [pin](#pin-to-a-specific-node) header). |
| `lava-providers-block` | Comma-separated nodes to **exclude** from selection for this request. Selection picks from the rest of the pool. |

!!! warning "`lava-providers-block` accepts at most 2 nodes"
    A list of **3 or more** addresses is silently ignored — *no* nodes are excluded and
    no error is returned. Keep the exclude list to two entries.

**When to use:** pin away from a node you've seen misbehave, or force a comparison against a specific one. Failover still applies across whatever nodes remain eligible.

## Override the extension

```
lava-extension: archive
```

Forces a request onto an extension (e.g. `archive`) instead of letting the router infer it from the requested block. The value is case-insensitive. Only nodes whose config declares the matching add-on are eligible — see the per-chain [Upstream capabilities](../reference/chains/ethereum.md#upstream-capabilities).

**When to use:** a historical query the router would otherwise route to a non-archive node.

## Request cross-validation

```
lava-cross-validation-max-participants: 3
lava-cross-validation-agreement-threshold: 2
```

Fans this request out to `max-participants` nodes in parallel and only returns once `agreement-threshold` of them return matching responses. Both headers are required together. Subject to operator policy (an operator can mandate, cap, or forbid cross-validation per method). See [Cross-validation](../configuration/failover/consensus.md).

**When to use:** correctness-critical reads (`eth_getLogs`, `debug_*`, `eth_call` at a fixed block) where one lying node is unacceptable. It multiplies upstream cost — pair with caching.

## Combining directives

Headers stack:

```bash
curl -X POST http://127.0.0.1:3360 \
  -H 'Content-Type: application/json' \
  -H 'lava-select-provider: my-eth-upstream-2' \
  -H 'lava-relay-timeout: 30s' \
  -H 'lava-debug-relay: true' \
  -d '{"jsonrpc":"2.0","method":"debug_traceTransaction","params":["0x..."],"id":1}'
```

## Response headers

Smart Router annotates every response with metadata about how the relay was served. These are the primary signal for debugging routing and failover from the client side.

| Header | Meaning |
|---|---|
| `Lava-Provider-Address` | The node that ultimately served the response. |
| `Lava-Retries` | Number of retry attempts made for this relay. |
| `Provider-Latest-Block` | Latest block the serving node reported. |
| `Lava-Guid` | Unique request id — correlate with logs and traces. |
| `Lava-Errored-Providers` | Nodes that errored on this request. |
| `Lava-Node-Errors-providers` | Nodes that returned a node-level error. |
| `Lava-Reported-Providers` | Nodes reported as misbehaving. |
| `Smart-Router-Version` | Router build serving the request. |
| `lava-selection-stats` | Node-selection debug stats — only when the router runs with `--enable-selection-stats`. |

When cross-validation runs, the router also returns `lava-cross-validation-status`, `lava-cross-validation-agreeing-providers`, `lava-cross-validation-disagreeing-providers`, and — on failure — `lava-cross-validation-failure-reason` (`no-agreement`, `insufficient-responses`, `diversity-unmet`, `group-quorum-unmet`, or a structural `insufficient-capacity` / `insufficient-groups`).

## Operator restrictions

Smart Router honours the request directives above as a fixed set — there is no per-header server-side toggle to disable an individual directive such as node pinning. The one operator-configurable restriction is **cross-validation policy**: an operator can mandate, cap, or forbid cross-validation per `(chain, interface, method)` in the config file. See [Cross-validation](../configuration/failover/consensus.md) and [the config file](../configuration/config-file.md#cross-validation).
