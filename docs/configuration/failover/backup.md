---
title: "Primary and backup nodes"
description: "How the primary and backup tiers relate: when a backup gets traffic, when traffic returns to the primaries, add-ons only a backup serves, and what the caller gets when neither tier can serve."
---

# Primary and backup nodes

Smart Router has two tiers of upstream nodes:

- **Primaries**, under `direct-rpc`, serve all traffic.
- **Backups**, under `backup-direct-rpc`, are an emergency fallback. A request reaches a backup only when **no primary can take that request**.

The tier is chosen again on every request and on every attempt inside a request. Nothing switches a router "over to backup": the next request starts with the primaries again. What does carry over between requests is the state of each node: whether it is blocked, switched off after repeated failures, or held off after a rate limit.

```yaml
direct-rpc:                     # primaries: all traffic
  - name: "own-node"
    chain-id: "ETH1"
    api-interface: "jsonrpc"
    node-urls:
      - url: "https://eth.internal.example:8545"

backup-direct-rpc:              # backups: only when no primary can take the request
  - name: "paid-provider"
    chain-id: "ETH1"
    api-interface: "jsonrpc"
    node-urls:
      - url: "https://eth-mainnet.paid.example/v2/KEY"
```

Every listener needs at least one primary for its chain and interface. A router with backups but no primaries does not start.

## When a backup gets traffic

For each attempt, the router first picks from the primaries. A primary drops out of that pick for any of the reasons below. When every primary has dropped out, the attempt goes to a backup.

| A primary is... | Does that move the attempt to a backup? |
|---|---|
| already asked by this request (answered with an error, or still running) | **Yes**, once every primary has been asked |
| blocked, because every one of its URLs was switched off after repeated failures | **Yes** |
| missing the add-on or extension the request needs (for example `debug` or `archive`) | **Yes**, on the first attempt. See [Methods only a backup serves](#methods-only-a-backup-serves) |
| behind the chain tip, for a request at `latest` | **Yes** |
| excluded by the caller with `lava-providers-block` | **Yes** |
| not connected, or at its session limit | **Yes** |
| **rate-limited (held off after a `429`)** | **No.** A held-off primary is skipped only while another primary is ready. When every primary is held off, the one whose hold-off ends soonest is used. See [Rate-limited upstreams](retry.md#rate-limited-upstreams) |
| **slow** | **Not directly.** After the [per-attempt window](timeout.md) the router asks the next primary while the slow attempt keeps running. A backup is asked only once every primary is busy on the request |
| named by `lava-select-provider` | **No.** A pinned request never goes to a backup. See [Pinning](#pinning) |

A URL is switched off after `--bench-after` consecutive failures (default `50`). A provider is blocked when all of its URLs are switched off. Only failures that are the node's fault count: a rate limit, an unsupported method or a caller mistake does not.

### Errors: the retry limit can end a request before any backup

A request stops when it has seen more than `--set-relay-retry-limit` errors (default `2`), counting errors from every node, rate limits included. The limit does not know a backup is still untried. So when every primary fails at the same time, a backup is reached only if the limit allows as many errors as there are primaries:

| Primaries | All fail fast (5xx, refused connection, node error), default limit `2` |
|---|---|
| 1 or 2 | the backup is asked next and can answer |
| 3 or more | **the request stops after the third error.** No backup is asked, and the caller gets a node's error (see [What the caller gets](#what-the-caller-gets-when-neither-tier-can-serve)) |

This is how the router is designed: the limit bounds how much one request costs. It changes once the failing primaries are blocked. A blocked primary is not selected at all, so later requests go straight to the backups. That takes `--bench-after` failures per URL.

If you run three or more primaries and want an error burst to reach the backups right away, raise `--set-relay-retry-limit` to at least the number of primaries. Each extra retry is one more upstream call.

A non-retryable error, such as `execution reverted` or a malformed request, ends the request at once on any tier. See [Retry](retry.md#whats-retryable).

### Quiet nodes: the window and the budget

A primary that never answers is not an error, so it does not count against the retry limit. Instead, attempts go out one per-attempt window apart, and a backup is asked after every primary has had its window:

```
t = 0       primary 1   (quiet, keeps running)
t = 1 × W   primary 2   (quiet, keeps running)
t = 2 × W   primary 3   (quiet, keeps running)
t = 3 × W   backup 1    answers
```

For `N` primaries and a window `W`, a backup answers about `N × W` after the start, **if that is still inside the request's budget**. The default window floor is `1s` (`--min-relay-timeout`; heavier methods get a longer window) and the default budget is `30s` (`--default-processing-timeout`). With those defaults, for a typical read, three quiet primaries reach a backup after about 3 seconds. If you raise the window, for example to `10s`, three quiet primaries use up the 30-second budget and the request ends with no backup asked.

Keep `N × W` below the budget. A caller can also shorten the window for one request with [`lava-relay-timeout`](timeout.md#the-header-override).

### Writes and batches

- **A write** (for example `eth_sendRawTransaction`) is sent to every primary at once. Backups are added to that broadcast only with `--stateful-to-backup`, which is off by default. Without the flag, a write still goes to a single backup when no primary can be selected at all. With `--strategy cost` there is no broadcast: the write goes to one node.
- **A JSON-RPC batch** gets no retry and no failover by default (`--disable-batch-request-retry`). It can still be served by a backup on its first attempt, when no primary can take it. See [Batch requests](retry.md#batch-requests).

## When traffic goes back to the primaries

Because the tier is chosen per request, traffic returns to a primary as soon as that primary can be selected again:

| What took the primary out | When it comes back |
|---|---|
| it was busy or failed on one request | at once: the next request starts with the primaries |
| its URLs were switched off after repeated failures | the background prober (every `--probe-loop-interval`, default `5s`) switches a URL back on after 3 healthy probes in a row. The URL then gets a short trial: 3 new failures switch it off again, not another 50 |
| it was rate-limited | when the hold-off expires (30 seconds at first, doubling for repeated `429`s), or as soon as it answers a request |
| it was behind the tip | when its block moves forward |

At each epoch boundary (`--epoch-duration`, default `15m`) the router re-checks every node. A blocked node is let back in only when its probe passes.

Among backups, the [node selection](../projects/selection-policies.md) optimizer picks one per attempt, so a retry asks a different backup. While the primaries are healthy, backups get no client traffic. The exceptions are writes with `--stateful-to-backup` and [read-your-writes](#cache-and-read-your-writes) reads. The prober still checks backups in the background.

## Methods only a backup serves

A common setup puts an expensive archive or debug node only in the backup tier, so ordinary traffic stays on your own nodes. Declare the add-on on the backup's URL:

```yaml
backup-direct-rpc:
  - name: "paid-archive"
    chain-id: "ETH1"
    api-interface: "jsonrpc"
    node-urls:
      - url: "https://eth-archive.paid.example/v2/KEY"
        addons: ["archive", "debug"]
```

The router's list of supported add-ons is built from both tiers. When no primary declares an add-on, a request that needs it skips the primaries and goes **straight to a backup that declares it, on the first attempt**. No primary has to fail first.

| Request | Where it goes |
|---|---|
| an add-on method only the backup declares, for example `debug_traceTransaction` | the backup, on the first attempt |
| a read of an old block, deeper than the spec's archive rule (the router adds `archive` itself) | the backup, on the first attempt |
| a request with [`lava-extension: archive`](../../api/directives.md#override-the-extension) | the backup, on the first attempt |
| an ordinary request | the primaries |

Once an attempt has gone to an archive node, the request is never downgraded. If the archive backup fails, the retry goes to another archive node, or the request ends with the archive node's error. A switched-off archive backup is lent to the request as a [last chance](#what-the-caller-gets-when-neither-tier-can-serve) rather than skipped.

!!! warning "When the archive backup is not in rotation"
    The router decides that `archive` is offered from the config file, before it checks the nodes. If the only node tagged `archive` is out of rotation, because it was unreachable at startup or failed its archive check, an archive request is answered by an ordinary primary. A deep-block read gets the pruned node's error or an empty result. A request with `lava-extension: archive` currently gets that answer **without** `Lava-Extension-Unavailable`. This is a known issue and will be fixed to set the header. Until then, run `smartrouter health --include-backup` after each deploy to confirm the archive backup passed its checks.

Things to know about this setup:

- **The router adds `archive` only when it can read the block.** Methods that name a block or transaction by hash, such as `eth_getTransactionReceipt` or `debug_traceTransaction`, and [EIP-1898](https://eips.ethereum.org/EIPS/eip-1898) block objects are not routed to archive automatically. Send `lava-extension: archive` for those.
- **An archive backup still takes ordinary failover traffic.** When every primary is out, a plain request can be served by any backup, including the archive one. For an add-on collection such as `debug` you can prevent that with `standalone-addons: true` on the URL: that URL then serves only its add-ons. `standalone-addons` has no effect on `archive`, because `archive` is an extension of the normal API rather than a separate set of methods.
- **Check that the backup passed its checks.** Backups are verified at startup the same way primaries are, add-on by add-on. A backup that fails its `archive` or `debug` check does not serve that add-on. Run `smartrouter health <config> --include-backup` (without `--include-backup`, `health` checks primaries only).
- **When no node in either tier declares an add-on**, a request for it fails with `No Providers For Addon` and no node is contacted. When no node declares the `archive` extension, the request is served by an ordinary node, and a caller who asked for it with `lava-extension` gets `Lava-Extension-Unavailable: archive` on the reply.

## What the caller gets when neither tier can serve

The reply depends on whether any node produced an answer. If one did, the router returns it with the usual [response headers](../../api/directives.md#response-headers). If none did, the reply is a router error with **no `Lava-*` headers**. The request id is then only in the body, at `error.data.guid`.

These are JSON-RPC replies. REST and gRPC carry the same outcome in their own error format.

| Situation | HTTP status | Body |
|---|---|---|
| every node answered with a node error inside HTTP 200 | `200` | the node's error, unchanged. `lava-identified-node-error: true` |
| every node returned HTTP 5xx | the node's status | the node's body when it is a JSON-RPC error; otherwise a router error with `data.upstream_status` and `data.upstream_body` |
| every node refused or dropped the connection | `502` | `no answer from upstream: …` |
| every node was rate-limited (`429`) | `503` | a router error. The node's `Retry-After` is not forwarded |
| no node answered before the budget ended | `500` | `context deadline exceeded`, no `Lava-*` headers |
| a write that no node answered | `500` | `transaction status unclear: …`. The write may already be on chain, so check before you resend it |
| no node could be selected at all | `500` | `No pairings available.`, no `Lava-*` headers |
| an add-on no node declares | `500` | `No Providers For Addon`, no `Lava-*` headers |
| an extension no node declares (`lava-extension: archive`) | `200` | an ordinary node's answer, with `Lava-Extension-Unavailable` |

Before it gives up on blocked nodes, the router lends one switched-off URL to the request as a last chance: blocked primaries first, then blocked backups. So when everything is blocked, the caller usually gets that node's own answer or error rather than `No pairings available.`.

**No header says that a backup served a reply.** `Lava-Provider-Address` names the node, so to see a backup you have to know which names are backups. When the request was retried, the header lists every node asked, in order, and the node whose answer was returned is last. See [Observability](#observability).

## How failover works with other features

### Pinning

[`lava-select-provider`](../../api/directives.md#pin-to-a-specific-node) names a **primary**. A backup cannot be pinned: naming one fails the request with `Selected provider not available`. A pin also never falls through to the backups. If the pinned primary is blocked or unknown, the request fails without trying any other node. If the pinned primary was asked and returned an error, the retry goes through normal selection, which can reach a backup.

### Sticky sessions

A [sticky session](../sticky-sessions.md) binds a session to a **primary**. Backups are never bound.

- When the bound primary is blocked, or this request already tried it, the binding is dropped and the session is bound to another primary.
- When no primary is left, sticky requests are served by the backups **without** a binding. Two calls in the same session can land on different backups.
- With `--shared-state`, a binding shared across router pods is kept even when its primary is down, and requests in that session fail with `Selected provider not available` until the binding expires, about two epochs after it was made. Requests without the sticky header are served by the other primaries or the backups in the meantime. During such an outage a **new** session can also be bound to a primary that is down; this is a known issue.
- After the primaries recover, the next sticky request is bound to a primary again. It may be a different one from before.

### WebSocket and gRPC subscriptions

Subscriptions fail over differently from requests:

- **One upstream per subscribe.** A new subscription picks one upstream, primaries first. If it cannot connect to that upstream, the subscribe fails and the client gets the error; the router does not try another node within the same subscribe. Clients should retry a failed subscribe.
- **Backups only when no primary is registered.** A new subscription goes to a backup only when the router has no primary for the chain in rotation. A primary whose URLs are down at runtime stays in rotation for subscriptions until the next re-check removes it, which takes up to two epochs (30 minutes at the default `--epoch-duration`). Until then new subscriptions keep going to it and fail, while ordinary requests are already served by the backups.
- **Same upstream for a WebSocket connection.** Later subscriptions on the same WebSocket connection go to the upstream the connection first used, even if it has since gone down. Open a new connection to subscribe elsewhere.
- **No move back.** A subscription stays on its upstream for its whole life. One opened on a backup does not move to a primary when the primaries recover. If the upstream drops the connection, the router reconnects to the same upstream; if that fails, the subscription ends and the client has to subscribe again.

### Cross-validation

[Cross-validation](cross-validation.md) draws only on the primaries. When the primaries that can be selected are fewer than the policy needs, the request is refused at once with `insufficient-capacity`. Backups are not added to make up the number. A policy whose `max-participants` equals your number of primaries is therefore refused while any one primary is blocked.

### Cache and read-your-writes

- The [cache](../../deployment/cache/index.md) is checked before any node is picked. A cached answer is served even when every node in both tiers is down (`Lava-Provider-Address: Cached`). Answers from a backup are cached exactly like answers from a primary.
- **Read-your-writes** (`--read-your-writes-window`, default `30s`): for a short time after a write, a read that names the written transaction or its sender prefers the node that accepted the write, **including a backup**. It is a preference for the first attempt only, and it applies within one router pod.

## Recipes

### A paid provider as backup only

Put your own nodes under `direct-rpc` and the paid provider under `backup-direct-rpc`, as in the example at the top. Normal traffic, including writes, stays on your nodes. Then check:

- **The retry limit.** With three or more primaries, raise `--set-relay-retry-limit` to the number of primaries if an error burst should reach the paid provider at once. Otherwise it is reached only after the primaries are blocked.
- **The window.** Keep `N × --min-relay-timeout` below `--default-processing-timeout`, so quiet primaries leave time for a backup.
- **Writes.** Leave `--stateful-to-backup` off unless writes should also go to the paid provider while your nodes are up.
- **Archive and debug.** If the paid provider is also your only archive or debug node, those requests go to it on every call. See the next recipe.

### Archive only on the backup

Declare `archive` (and `debug`, `trace`) only on the backup's URL, as in [Methods only a backup serves](#methods-only-a-backup-serves). Do **not** set `archive` on a primary that is pruned. Then:

- Deep-block reads and `lava-extension: archive` requests go to the backup, and nothing else does while your primaries are healthy.
- Send `lava-extension: archive` for by-hash methods and EIP-1898 block objects.
- Run `smartrouter health <config> --include-backup` after a deploy, and confirm the backup passed its `archive` check.

## Observability

| Signal | What it tells you |
|---|---|
| `Lava-Provider-Address` on a reply | the node that answered. Compare it with your backup names |
| `rpc_endpoint_total_relays_serviced{endpoint_id="<backup name>"}` | requests each backup served |
| `smartrouter_csm_blocked_providers` | how many primaries are blocked. When it reaches your primary count, the backups carry the traffic |
| `smartrouter_endpoint_serving_tier` | `2` primaries registered, `1` only backups registered, `0` none. It follows registration at startup and at each epoch, **not** runtime failover: it stays `2` while blocked primaries leave all traffic to the backups |
| `smartrouter health <config> --include-backup` | whether each backup URL and add-on passes its checks |

See the [Metrics reference](../../reference/metrics.md) for labels.
