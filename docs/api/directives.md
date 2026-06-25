# Directives

Override Smart Router's default behaviour for a single request by setting HTTP headers. Use them when the default routing, caching, or timeout policy isn't what you want for this specific call.

## Request headers at a glance

| Header | Effect |
|---|---|
| `Lava-Provider-Address` | [Pin](#pin-to-a-specific-node) the request to one named upstream. |
| `lava-select-provider` | [Route](#steer-node-selection) to one named node. |
| `lava-providers-block` | [Exclude](#steer-node-selection) named nodes (comma-separated). |
| `lava-extension` | [Force an extension](#override-the-extension) such as `archive`. |
| `lava-force-cache-refresh` | [Bypass the cache](#force-a-cache-refresh) and refresh the entry. |
| `lava-relay-timeout` | [Override the per-attempt timeout](#override-the-per-attempt-timeout) (Go duration). |
| `lava-cross-validation-max-participants` + `lava-cross-validation-agreement-threshold` | [Request cross-validation](#request-cross-validation). |
| `lava-debug-relay` | [Verbose per-attempt logging](#enable-debug-logging-for-one-request) for this request. |

Each is detailed below. The router's [response headers](#response-headers) carry metadata back.

## Pin to a specific node

```
Lava-Provider-Address: <upstream-name>
```

Bypasses the QoS optimizer for this request. The named upstream serves it directly. If it fails, [failover](../configuration/failover/index.md) policies still apply against the rest of the pool.

**When to use:** debugging an upstream, sticky requests within a session, A/B comparing responses.

```bash
curl -X POST http://127.0.0.1:3360 \
  -H 'Content-Type: application/json' \
  -H 'Lava-Provider-Address: my-eth-upstream-1' \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

## Force a cache refresh

```
lava-force-cache-refresh: true
```

Bypasses the cache for this request. The relay goes upstream, the response is returned, and the cache entry is refreshed.

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

Sets the timeout for each upstream attempt of this request. Format: any Go duration string (`500ms`, `5s`, `1m30s`). Subject to the floor set by `--min-relay-timeout` (default 1s).

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
| `lava-select-provider` | Route this request to one named node (like `Lava-Provider-Address`). |
| `lava-providers-block` | Comma-separated nodes to **exclude** from selection for this request. Selection picks from the rest of the pool. |

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
  -H 'Lava-Provider-Address: my-eth-upstream-2' \
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

When cross-validation runs, the router also returns `lava-cross-validation-status`, `lava-cross-validation-agreeing-providers`, `lava-cross-validation-disagreeing-providers`, and — on failure — `lava-cross-validation-failure-reason` (`no-agreement`, `insufficient-responses`, `diversity-unmet`, or a structural `insufficient-capacity` / `insufficient-groups`).

## Operator restrictions

Whether each directive is honoured can be restricted server-side. Public-facing deployments often disable `Lava-Provider-Address` to prevent clients from pinning traffic to one upstream. See [Configuration](../configuration/index.md).
