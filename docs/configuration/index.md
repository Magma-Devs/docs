---
title: "Configure"
description: "Configure routing, node selection, caching, and the failover pipeline for Smart Router."
---

# Configuration

You configure Smart Router with a YAML file, a directory of chain specs, and CLI flags. Use this page to find where each setting lives and which page explains it.

At startup, the router reads:

1. A single YAML file that defines listeners (endpoints) and upstream node URLs.
2. A directory of JSON **chain specs** describing methods, categories, and parser rules.

```bash
smartrouter path/to/config.yml --use-static-spec specs/
```

Working examples ship under [`config/smartrouter_examples/`](https://github.com/Magma-Devs/smart-router/tree/main/config/smartrouter_examples). The fastest way to a real config is to copy one and edit it. You can also let the [config wizard](../deployment/wizard.md) build one for you interactively and health-check it.

## Where things are configured

You configure the router in two places. The **YAML file** defines *what* the router
serves (listeners + upstreams). **CLI flags** tune *how* it behaves at runtime.

| Concern | Where | See |
|---|---|---|
| Listeners & upstream nodes | YAML (`endpoints`, `direct-rpc`) | [The config file](config-file.md) |
| Upstream auth & secrets | YAML (`auth-config`, `${VAR}`) | [Authentication](authentication.md) |
| RPC node selection strategy | `--strategy` + `--qos-*` flags | [RPC Node selection](projects/selection-policies.md) |
| Failover (retry / hedge / timeout / consensus) | CLI flags + chain-spec values | [Failover & retry](failover/index.md) |
| Cache | `cache-be:` in YAML (or `--cache-be`) | [Cache](../deployment/cache/index.md) |
| Cache on Redis / Valkey | `resp-cache:` in YAML | [Redis / Valkey backend](../deployment/cache/redis.md) |
| Read-only second cache tier | `secondary-cache-be:` in YAML (or `--secondary-cache-be`) | [Secondary cache](../deployment/cache/secondary.md) |
| Metrics & tracing | `--metrics-listen-address`, OTel env | [Metrics](../reference/metrics.md) |
| Every flag | - | [CLI reference](../reference/cli.md) |

Smart Router leaves client-side concerns to a reverse proxy in front of the router, on
purpose. These are inbound auth, CORS policy beyond the `--cors-*` flags, and
per-client rate limiting. See [Authentication → Authenticating your clients](authentication.md#authenticating-your-clients).

## Chain specs

Chain specs live in [`specs/`](https://github.com/Magma-Devs/smart-router/tree/main/specs). Smart Router ships with a few ready-to-use chain specs (Ethereum, Arbitrum, Base, Lava, Solana) and three reusable building blocks for the Cosmos ecosystem. It resolves the rest from the catalog at startup. See [Supported chains](../reference/chains/index.md).

Pass the spec directory at startup with `--use-static-spec specs/`.

## Secrets

Never commit a config with real keys. Sample configs are templates. Keep upstream API
keys out of YAML: use `${VAR}` placeholders and render them from a gitignored `.env`.
See [Authentication](authentication.md).
