---
title: "Config file"
description: "Reference for the Smart Router YAML config file: projects, upstreams, selection, and failover."
---

# The config file

A Smart Router config is a single YAML file that lists the **listeners** the router
opens (`endpoints`) and the **upstreams** it routes to (`direct-rpc`). Use this page to
look up a key in that file.

Both lists are required. A few other top-level keys are optional. You tune everything
else (node selection, failover, timeouts) with [CLI flags](../reference/cli.md), not
the file.

Pass the file to the router as a positional argument:

```bash
smartrouter path/to/config.yml --use-static-spec specs/
```

Working examples live under
[`config/smartrouter_examples/`](https://github.com/Magma-Devs/smart-router/tree/main/config/smartrouter_examples).
The fastest way to a real config is to copy one and edit it, or to let the
[wizard](../deployment/wizard.md) generate one.

## A minimal config

```yaml
metrics-listen-address: "0.0.0.0:7779"

endpoints:
  - network-address: "0.0.0.0:3360"
    chain-id: "ETH1"
    api-interface: "jsonrpc"

direct-rpc:
  - name: "eth-publicnode"
    chain-id: "ETH1"
    api-interface: "jsonrpc"
    node-urls:
      - url: "https://ethereum-rpc.publicnode.com"
      - url: "wss://ethereum-rpc.publicnode.com"
```

The router pairs each `endpoints[]` listener with the `direct-rpc[]` nodes that
share its `chain-id` + `api-interface`. A listener with no matching node does not
serve. A node with no matching listener is never used.

## Top-level keys

| Key | Required | What it is |
| --- | --- | --- |
| `endpoints` | yes | The listeners the router opens, one per chain × API interface. |
| `direct-rpc` | yes | The upstream node pool. |
| `backup-direct-rpc` | no | Emergency-fallback nodes. The router uses them only after the primary pool is exhausted. Same shape as `direct-rpc`. |
| `cache-be` | no | Address of the [cache](../deployment/cache/index.md) sidecar, e.g. `cache:20100`. Omit it to disable caching. |
| `resp-cache` | no | Block that configures a [Redis / Valkey cache backend](../deployment/cache/redis.md) instead of the sidecar. When both are set, it takes precedence over `cache-be`. |
| `secondary-cache-be` | no | Address of an optional read-only [secondary cache](../deployment/cache/secondary.md). The router checks it when the primary cache misses. `secondary-cache-timeout` and `secondary-cache-mode` tune it. |
| `metrics-listen-address` | no | Prometheus `/metrics` address, e.g. `0.0.0.0:7779`. `disabled` turns metrics off. `--metrics-listen-address` overrides it. |
| `cross-validation` | no | Per-method operator policies for [cross-validation](#cross-validation) (mandate, cap, or forbid). |

!!! warning "Deprecated keys removed"
    The old `static-providers` / `backup-providers` keys have been removed. Use
    `direct-rpc` / `backup-direct-rpc`.

## `endpoints[]` - listeners

Each entry opens one listening socket for one chain + interface.

| Field | Required | Description |
| --- | --- | --- |
| `network-address` | yes | `host:port` to listen on, e.g. `0.0.0.0:3360`. |
| `chain-id` | yes | Spec chain id (`ETH1`, `SOLANA`, `COSMOSHUB`, …). Must resolve from `--use-static-spec`. |
| `api-interface` | yes | `jsonrpc`, `rest`, `grpc`, `tendermintrpc`, or `graphql`. The chain spec must support it. A `graphql` listener accepts HTTP `POST` only (any path; other methods get `405`) and serves no subscriptions. |
| `tls-enabled` | no | Serve this listener over TLS using a self-signed certificate. Default `false`. |
| `health-check-path` | no | HTTP path that returns `200` for liveness probes. Default `/lava/health`. |

```yaml
endpoints:
  - network-address: "0.0.0.0:3360"
    chain-id: "COSMOSHUB"
    api-interface: "rest"
  - network-address: "0.0.0.0:3361"
    chain-id: "COSMOSHUB"
    api-interface: "grpc"
```

## `direct-rpc[]` - upstream nodes

Each entry is one named backend that serves one chain + interface, with one or more URLs.

| Field | Required | Description |
| --- | --- | --- |
| `name` | yes | Human-readable label. It shows up in logs and as the Prometheus `endpoint_id`. |
| `chain-id` | yes | Chain this backend serves. Must match an `endpoints[]` entry. |
| `api-interface` | yes | Interface this backend serves. Must match the listener. |
| `node-urls` | yes | One or more URL entries (below). |
| `stake` | no | Optional weight (in ulava) for selection scoring. Omit it (or set `0`) to apply the default static-node boost. |
| `group-label` | no | Optional provider-group id (e.g. `tier-1`, `external`) for [cross-validation](failover/cross-validation.md) group-diversity policies. Has no effect unless a policy requires group spread. |

```yaml
direct-rpc:
  - name: "eth-publicnode"
    chain-id: "ETH1"
    api-interface: "jsonrpc"
    node-urls:
      - url: "https://ethereum-rpc.publicnode.com"
      - url: "wss://ethereum-rpc.publicnode.com"
```

### `node-urls[]` - per-URL options

| Field | Description |
| --- | --- |
| `url` | Connection URL. Schemes: `http(s)://`, `ws(s)://`, `grpc(s)://`. A `jsonrpc` backend on an ETH1-derived spec needs a paired `wss://` url. A `graphql` backend's url is the full GraphQL endpoint, path included (e.g. `https://graphql.mainnet.sui.io/graphql`): the router POSTs to it as-is. |
| `timeout` | Per-URL request timeout, e.g. `10s`. Defaults to the spec value. |
| `addons` | Add-ons this URL serves, e.g. `["archive", "debug"]`. The router only routes matching methods here. |
| `methods` | Restrict this URL to a specific method list. When set, only those methods route here. |
| `internal-path` | Path override when proxying through a gateway. |
| `ip-forwarding` | Forward the client IP via `X-Forwarded-For` to the upstream. |
| `skip-verifications` | Skip chain-tracker startup checks for this URL, e.g. `["pruning", "tx-indexing"]`. |
| `auth-config` | Per-URL authentication. See [Authentication](authentication.md). |
| `grpc-config` | gRPC descriptor settings (below). |
| `accept-encoding` | `identity` (default) or `gzip`. `gzip` asks this upstream to compress its replies. See [Compressed upstream replies](#accept-encoding-compressed-upstream-replies). |

```yaml
    node-urls:
      - url: "https://your-eth-provider.example.com"
        timeout: 10s
        addons: ["bundler", "debug"]
        auth-config:
          auth-headers:
            x-api-key: "${RPC_KEY_ETH}"
      - url: "wss://your-eth-provider.example.com/websocket"
```

### `accept-encoding` - compressed upstream replies

By default the router asks every upstream for uncompressed replies
(`Accept-Encoding: identity`). Set `accept-encoding: gzip` on a URL to ask that
upstream for gzip instead. The router decompresses each reply before it validates,
caches or returns it, so clients get the same response either way. A separate flag,
[`--response-compression`](../reference/cli.md#cors-http), sets what clients receive.

With gzip, the router spends more CPU and reads fewer bytes. Decompressing costs CPU
on every reply, which is why gzip is off by default. It helps when replies are large
and reading them is the bottleneck. For example, a Solana `getBlock` reply is several
megabytes of JSON, and gzip makes it four to six times smaller, so the router reads
that much less through TLS and HTTP/2. Measure it against your upstream before you
rely on it. The saving depends on how well that upstream's replies compress, and an
upstream may not compress at all.

```yaml
    node-urls:
      - url: "https://solana-mainnet.gateway.tatum.io"
        accept-encoding: gzip
        auth-config:
          auth-headers:
            x-api-key: "${RPC_KEY_SOLANA}"
```

- Values are `identity` and `gzip`, and case does not matter. Any other value stops
  the router at startup.
- Only `http(s)://` URLs use it. `ws(s)://` and `grpc(s)://` URLs ignore it.
- An upstream that answers uncompressed anyway is read as it is.

### `grpc-config` - gRPC descriptors

These settings apply only to `grpc` interfaces.

| Field | Default | Description |
| --- | --- | --- |
| `descriptor-source` | `reflection` | `reflection` (server reflection), `file` (a compiled descriptor set), or `hybrid` (reflection, then file). |
| `descriptor-set-path` | - | Path to a protobuf `FileDescriptorSet`. Required for `file` / `hybrid`. |
| `reflection-timeout` | `5s` | Timeout for reflection queries. |
| `allow-insecure` | `false` | Allow non-TLS `grpc://`. For dev/test only. |

## Cross-validation

This optional top-level block sets per-method operator policies for
[cross-validation](failover/cross-validation.md). A policy can **mandate** it (with
floors/caps that clients cannot weaken), or **forbid** clients from requesting it.
Without this block, only clients turn cross-validation on, through the
[request headers](../api/directives.md#request-cross-validation).

```yaml
cross-validation:
  policies:
    # Mandate consensus for a sensitive read, capped so clients can't fan out wider.
    - chain-id: "ETH1"
      api-interface: "jsonrpc"
      method: "eth_getLogs"
      enabled: true
      agreement-threshold: { floor: 2 }
      max-participants: { floor: 3, cap: 5 }
    # Forbid clients from cross-validating a non-deterministic method.
    - chain-id: "ETH1"
      api-interface: "jsonrpc"
      method: "eth_blockNumber"
      forbid-caller-cv: true
```

| Field | Description |
| --- | --- |
| `chain-id` / `api-interface` / `method` | Which requests the policy applies to (method casing is preserved). |
| `enabled` | Mandate cross-validation for this method. |
| `max-participants` / `agreement-threshold` / `min-groups` | Bounds. Each takes `{ floor, cap }`. A client header can raise the value up to the cap, but cannot go below the floor. |
| `per-group-quorum` | Require each of `min-groups` groups to reach the threshold on its own (needs `min-groups > 1`). |
| `forbid-caller-cv` | Disable cross-validation for this method, even if a client sends the headers. Cannot be combined with `enabled`. |

## Secrets

Never commit API keys. Put them in upstream URLs or `auth-config` as `${VAR}`
placeholders, and render them at run time. See [Authentication](authentication.md).
The rendered URL contains the full key and is a bearer credential, so generated
configs go to the gitignored `config/local/` by default.

## See also

- [Authentication](authentication.md) - `auth-config`, `${VAR}` secrets, mTLS.
- [CLI reference](../reference/cli.md) - every runtime flag.
- [Supported chains](../reference/chains/index.md) - valid `chain-id` / `api-interface` values.
