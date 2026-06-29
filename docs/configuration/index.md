---
title: "Configure"
description: "Configure routing, node selection, caching, and the failover pipeline for Smart Router."
---

# Configuration

Smart Router is driven by:

1. A single YAML file that defines listeners (endpoints) and upstream node URLs.
2. A directory of JSON **chain specs** describing methods, categories, and parser rules.

```bash
smartrouter path/to/config.yml --use-static-spec specs/
```

Working examples ship under [`config/smartrouter_examples/`](https://github.com/Magma-Devs/smart-router/tree/main/config/smartrouter_examples). The fastest path to a real config is to copy one and edit it — or let the [config wizard](../deployment/wizard.md) build (and health-check) one for you interactively.

## Where things are configured

Two surfaces: the **YAML file** defines *what* the router serves (listeners + upstreams);
**CLI flags** tune *how* it behaves at runtime.

| Concern | Where | See |
|---|---|---|
| Listeners & upstream nodes | YAML (`endpoints`, `direct-rpc`) | [The config file](config-file.md) |
| Upstream auth & secrets | YAML (`auth-config`, `${VAR}`) | [Authentication](authentication.md) |
| RPC node selection strategy | `--strategy` + `--qos-*` flags | [RPC Node selection](projects/selection-policies.md) |
| Failover (retry / hedge / timeout / consensus) | CLI flags + chain-spec values | [Failover & retry](failover/index.md) |
| Cache | `cache-be:` in YAML (or `--cache-be`) | [Add the cache](../deployment/docker-compose.md#add-the-cache) |
| Metrics & tracing | `--metrics-listen-address`, OTel env | [Metrics](../reference/metrics.md) |
| Every flag | — | [CLI reference](../reference/cli.md) |

Client-side concerns — inbound auth, CORS policy beyond the `--cors-*` flags, and
per-client rate limiting — are deliberately left to a reverse proxy in front of the
router. See [Authentication → Authenticating your clients](authentication.md#authenticating-your-clients).

## Chain specs

Chain specs live in [`specs/`](https://github.com/Magma-Devs/smart-router/tree/main/specs). Smart Router ships with a handful of ready-to-use chain specs (Ethereum, Arbitrum, Base, Lava, Solana) plus three reusable building blocks for the Cosmos ecosystem, and resolves the rest from the catalog at startup — see [Supported chains](../reference/chains/index.md).

Pass the spec directory at startup with `--use-static-spec specs/`.

## Secrets

Sample configs are templates — never commit one with real keys. Keep upstream API keys
out of YAML with `${VAR}` placeholders rendered from a gitignored `.env`. See
[Authentication](authentication.md).
