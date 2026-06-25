# The config file

A Smart Router config is a single YAML file with two required lists — the **listeners**
it opens (`endpoints`) and the **upstreams** it routes to (`direct-rpc`) — plus a few
optional top-level keys. Everything else (node selection, failover, timeouts) is
tuned with [CLI flags](../reference/cli.md), not the file.

You point the router at it positionally:

```bash
smartrouter path/to/config.yml --use-static-spec specs/
```

Working examples live under
[`config/smartrouter_examples/`](https://github.com/Magma-Devs/smart-router/tree/main/config/smartrouter_examples) —
the fastest way to a real config is to copy one and edit it, or let the
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
share its `chain-id` + `api-interface`. A listener with no matching node won't
serve; a node with no matching listener is never used.

## Top-level keys

| Key | Required | What it is |
| --- | --- | --- |
| `endpoints` | yes | The listeners the router opens — one per chain × API interface. |
| `direct-rpc` | yes | The upstream node pool. |
| `backup-direct-rpc` | no | Emergency-fallback nodes, only used once the primary pool is exhausted. Same shape as `direct-rpc`. |
| `cache-be` | no | Address of the [cache](../deployment/docker-compose.md#add-the-cache) sidecar, e.g. `cache:20100`. Omit to disable caching. |
| `metrics-listen-address` | no | Prometheus `/metrics` address, e.g. `0.0.0.0:7779`. `disabled` turns metrics off. Overridden by `--metrics-listen-address`. |
| `cross-validation` | no | Per-method operator policies for [cross-validation](#cross-validation) (mandate, cap, or forbid). |

!!! warning "Deprecated keys removed"
    The old `static-providers` / `backup-providers` keys are gone — use `direct-rpc` /
    `backup-direct-rpc`.

## `endpoints[]` — listeners

Each entry opens one listening socket for one chain + interface.

| Field | Required | Description |
| --- | --- | --- |
| `network-address` | yes | `host:port` to listen on, e.g. `0.0.0.0:3360`. |
| `chain-id` | yes | Spec chain id (`ETH1`, `ARBITRUM`, `LAVA`, …). Must resolve from `--use-static-spec`. |
| `api-interface` | yes | `jsonrpc`, `rest`, `grpc`, or `tendermintrpc` — must be supported by the chain spec. |

```yaml
endpoints:
  - network-address: "0.0.0.0:3360"
    chain-id: "LAVA"
    api-interface: "rest"
  - network-address: "0.0.0.0:3361"
    chain-id: "LAVA"
    api-interface: "grpc"
```

## `direct-rpc[]` — upstream nodes

Each entry is one named backend serving one chain + interface, with one or more URLs.

| Field | Required | Description |
| --- | --- | --- |
| `name` | yes | Human label — shows up in logs and as the Prometheus `endpoint_id`. |
| `chain-id` | yes | Chain this backend serves; must match an `endpoints[]` entry. |
| `api-interface` | yes | Interface this backend serves; must match the listener. |
| `node-urls` | yes | One or more URL entries (below). |
| `stake` | no | Optional weight (in ulava) for selection scoring. Omit (or `0`) to apply the default static-node boost. |
| `group-label` | no | Optional provider-group id (e.g. `tier-1`, `external`) for [cross-validation](failover/consensus.md) group-diversity policies. No effect unless a policy requires group spread. |

```yaml
direct-rpc:
  - name: "eth-lava-build"
    chain-id: "ETH1"
    api-interface: "jsonrpc"
    node-urls:
      - url: "https://eth1.lava.build"
      - url: "wss://eth1.lava.build/websocket"
```

### `node-urls[]` — per-URL options

| Field | Description |
| --- | --- |
| `url` | Connection URL. Schemes: `http(s)://`, `ws(s)://`, `grpc(s)://`. A `jsonrpc` backend on an ETH1-derived spec needs a paired `wss://` url. |
| `timeout` | Per-URL request timeout, e.g. `10s`. Defaults to the spec value. |
| `addons` | Add-ons this URL serves, e.g. `["archive", "debug"]`. The router only routes matching methods here. |
| `methods` | Restrict this URL to a specific method list. When set, only those methods route here. |
| `internal-path` | Path override when proxying through a gateway. |
| `ip-forwarding` | Forward the client IP via `X-Forwarded-For` to the upstream. |
| `skip-verifications` | Skip chain-tracker startup checks for this URL, e.g. `["pruning", "tx-indexing"]`. |
| `auth-config` | Per-URL authentication — see [Authentication](authentication.md). |
| `grpc-config` | gRPC descriptor settings (below). |

```yaml
    node-urls:
      - url: "https://base.lava.build"
        timeout: 10s
        addons: ["bundler", "debug"]
        auth-config:
          auth-headers:
            x-api-key: "${RPC_KEY_BASE}"
      - url: "wss://base.lava.build/websocket"
```

### `grpc-config` — gRPC descriptors

Only relevant for `grpc` interfaces.

| Field | Default | Description |
| --- | --- | --- |
| `descriptor-source` | `reflection` | `reflection` (server reflection), `file` (a compiled descriptor set), or `hybrid` (reflection, then file). |
| `descriptor-set-path` | — | Path to a protobuf `FileDescriptorSet`. Required for `file` / `hybrid`. |
| `reflection-timeout` | `5s` | Timeout for reflection queries. |
| `allow-insecure` | `false` | Permit non-TLS `grpc://`. Dev/test only. |

## Cross-validation

An optional top-level block sets per-method operator policies for
[cross-validation](failover/consensus.md) — to **mandate** it (with floors/caps clients
can't weaken), or **forbid** clients from requesting it. Without this block,
cross-validation is purely client-driven via the
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
| `max-participants` / `agreement-threshold` / `min-groups` | Bounds — each takes `{ floor, cap }`. A client header may raise within the cap but can't drop below the floor. |
| `per-group-quorum` | Require each of `min-groups` groups to independently reach the threshold (needs `min-groups > 1`). |
| `forbid-caller-cv` | Disable cross-validation for this method even if a client sends the headers. Mutually exclusive with `enabled`. |

## Secrets

Never commit API keys. Put them in upstream URLs or `auth-config` as `${VAR}`
placeholders and render them at run time — see [Authentication](authentication.md). The
rendered URL embeds the full key and is a bearer credential, so generated configs
default to the gitignored `config/local/`.

## See also

- [Authentication](authentication.md) — `auth-config`, `${VAR}` secrets, mTLS.
- [CLI reference](../reference/cli.md) — every runtime flag.
- [Supported chains](../reference/chains/index.md) — valid `chain-id` / `api-interface` values.
