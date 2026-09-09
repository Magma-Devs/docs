---
title: "Sticky sessions"
description: "Send related requests to the same upstream node, so a sequence of calls sees one consistent view of the chain."
---

# Sticky sessions

Send a session id with your requests and Smart Router routes every request carrying that id to the **same upstream node**, across every router replica.

Use it when a sequence of calls has to agree with each other. Nodes in a pool do not advance in lockstep, so two related calls answered by two different nodes can disagree — and that disagreement can look like missing data rather than an error.

## The problem it solves

An indexer follows the chain head and fetches each block under it:

```
1. eth_blockNumber                -> 21000000
2. eth_getBlockByNumber(21000000) -> the block
```

If call 1 is answered by a node that is ahead, and call 2 lands on a node that is a few blocks behind, the second node has no such block yet and returns an empty result:

```
eth_blockNumber                -> node-A (head 21000000) -> 21000000
eth_getBlockByNumber(21000000) -> node-B (head 20999997) -> null
```

Nothing has failed. The response is a normal `200` with `"result": null`, so no retry is triggered and the caller records a gap in the chain that does not exist.

With a session id on both calls, they go to the same node and agree:

```
eth_blockNumber                -> node-A (head 21000000) -> 21000000
eth_getBlockByNumber(21000000) -> node-A                 -> the block
```

## Usage

```
lava-stickiness: <your-session-id>
```

The value is any string you choose — a worker id, a batch id, a user id. Requests sharing a value share an upstream.

```bash
# Both calls carry the same id, so both are served by the same node.
SESSION="ingest-batch-42"

HEAD=$(curl -sX POST http://127.0.0.1:3360 \
  -H 'Content-Type: application/json' \
  -H "lava-stickiness: $SESSION" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' | jq -r .result)

curl -X POST http://127.0.0.1:3360 \
  -H 'Content-Type: application/json' \
  -H "lava-stickiness: $SESSION" \
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getBlockByNumber\",\"params\":[\"$HEAD\",false],\"id\":2}"
```

!!! warning "Send the id on **every** call in the sequence"
    A common mistake is to send it only on the second call. The first call then goes to any
    node, so the head can come from a node the pinned request never reaches — and the original
    problem returns with the header apparently in use.

## How it works

1. The first request for a session id picks a node using the normal [selection](projects/selection-policies.md) rules.
2. That choice is written to the cache backend, where every replica can read it.
3. Later requests with the same id — on any replica — are routed to that node.
4. The choice is claimed **first-writer-wins**: if two replicas pick at the same moment, one write wins and the other adopts it, so the fleet does not disagree.

A session's choice lasts about two router epochs (30 minutes at the default `--epoch-duration`), after which the next request picks again.

## When to use it

| Scenario | Sticky session? |
|---|---|
| Two or more calls that must agree — read the head, then fetch that block | **Yes** — this is what it is for |
| Node-side state tied to one node — an `eth_newFilter` id, a subscription handle | **Yes** |
| Read-your-own-write after `eth_sendRawTransaction` | **Yes** |
| Independent single reads with no relationship to each other | No — pinning costs you the optimizer's choice for nothing |
| A specific node you already know by name | No — use [`lava-select-provider`](../api/directives.md#pin-to-a-specific-node) |

## Configuration

Sticky sessions work across router replicas only when **both** of these are true:

| Requirement | How |
|---|---|
| A cache backend is configured | `cache-be:` in the [config file](config-file.md), or the [Redis / Valkey backend](../deployment/cache/redis.md) |
| Shared state is enabled | `--shared-state` ([CLI flags](../reference/cli.md)) |

With either missing, each replica keeps its own private table. The header still works **within** a single replica, so behind a load balancer the same id can reach a different node on each one — which is the behaviour sticky sessions exist to prevent.

## What happens when the session cannot be honoured

The guarantee is **route to the session's node, or fail** — never quietly serve the request from a different one. Substituting a node silently is the problem this feature exists to remove, so the router does not do it, even when another node could answer.

In practice that means a request fails if the session's node cannot serve it, or if the cache backend holding the session's choice is unreachable.

!!! info "Requests without the header are never affected"
    This applies only to traffic carrying `lava-stickiness`. Everything else is served as usual.

## Interaction with other directives

| Directive | Behaviour |
|---|---|
| [`lava-select-provider`](../api/directives.md#pin-to-a-specific-node) | Wins. Naming a node explicitly is the more specific instruction. |
| [Cross-validation](failover/cross-validation.md) | Wins. Cross-validation needs several nodes, which is incompatible with pinning to one. |
| [`lava-extension`](../api/directives.md#override-the-extension) | A session id used for both plain and `archive` calls gets an independent node for each. |
| [Retry](failover/retry.md) | A retry after a genuine error deliberately goes to a different node. |

## Trade-offs

- **Availability**: the guarantee is fail-closed, so a request fails rather than being served by another node. Traffic without the header is unaffected.
- **Node selection**: a session stays on the node chosen first, even if another becomes a better choice during the session. The choice is remade about every two epochs.
- **Latency**: the first request for a session on each replica costs one lookup against the cache backend. The rest are answered from that replica's own memory.

## Observability

| Metric | Meaning |
|---|---|
| `smartrouter_csm_sticky_claims_total{outcome="local_hit"}` | answered from this replica's own memory, no round trip — the steady state |
| `{outcome="adopted"}` | used a choice another replica made. **Zero across a multi-replica fleet means replicas are not sharing** — check the cache backend and `--shared-state` |
| `{outcome="claimed"}` | this replica made the choice |
| `{outcome="lost_race"}` | chose at the same moment as a peer and adopted its winner |
| `{outcome="error"}` | the cache backend could not be reached, so the request failed |
| `{outcome="no_candidate"}` | no upstream was available to choose from — a pool problem, not a cache one |
| `{outcome="invalidated"}` | a stored choice was dropped because its node could not serve |
| `smartrouter_csm_sticky_sessions` | live session choices held by this replica |

`error`, `no_candidate` and `invalidated` are the series that climb when something is wrong. An alert built only on `error` will read healthy while sticky requests fail for the other two reasons.

See the [Metrics reference](../reference/metrics.md#smart-router-metrics) for labels and types.

## Related

- [Request headers](../api/directives.md) — every per-request directive
- [RPC node selection](projects/selection-policies.md) — how a node is chosen when no session id is present
- [Cache](../deployment/cache/index.md) — the backend that carries session choices between replicas
