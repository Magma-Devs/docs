---
title: "Run Smart Router"
description: "Ways to run Smart Router — a native local binary, the Docker Compose stack, or the interactive config wizard."
---

# Run Smart Router

Smart Router runs on your own infrastructure — the router, and an optional cache sidecar,
are the same single binary. There are no external dependencies beyond the upstream RPC
nodes you configure.

Pick how you want to run it:

| Method | Best for |
| --- | --- |
| [**Config wizard**](wizard.md) | The fastest start — an interactive TUI picks chains, collects upstreams, health-checks everything, writes the config, and brings up the stack in one pass. Start here if you don't have a config yet. |
| [**Docker Compose**](docker-compose.md) | A config you already have (or copied from the examples), run with one `docker compose` command. Adds an optional cache overlay; the [dashboard](dashboard.md) runs from its own repo. |
| [**Local binary**](local-binary.md) | Native process, no Docker — smallest footprint, or wiring into your own service manager. |

!!! note "Looking for a managed option?"
    These docs cover the **self-hosted** Smart Router. If you'd rather not operate it
    yourself, [talk to us](https://magmadevs.com/contact).

## Prerequisites

All three methods start from a clone of the repo — it carries the compose files, example
configs, and bundled `specs/`:

```bash
git clone https://github.com/Magma-Devs/smart-router.git
cd smart-router
```

- **Docker Compose / wizard** need **Docker** with Compose v2 (`docker compose`, not the
  legacy `docker-compose`). The image builds from source in-image — no host Go needed.
- **Local binary** needs **Go 1.26+** to `make install`.

## What you need to run it

- **CPU**: 2+ cores is a good starting point; the router is mostly I/O bound.
- **Memory**: 1–2 GiB baseline.
- **Disk**: negligible — the router is stateless.
- **Network**: low-latency egress to your upstream nodes, with outbound TLS allowed
  (most public nodes require HTTPS / TLS gRPC).

## In production

- **Externalise secrets** — never bake API keys into images or commit them to YAML. See
  [Authentication](../configuration/authentication.md).
- **Observability** — scrape `:7779` (see [Metrics](../reference/metrics.md)); set
  `OTEL_EXPORTER_OTLP_ENDPOINT` for [tracing](../configuration/index.md).
- **Health checks** — each listener answers a basic chain-id query; the metrics server
  exposes an aggregate `:7779/metrics/overall-health` probe (`200 Health status OK` /
  `503 Unhealthy`), and the cache exposes `/metrics` on its metrics port. See
  [Confirm it's healthy](docker-compose.md#confirm-its-healthy).
- **Tuning** — node selection, failover, and timeouts are all configurable; see the
  [CLI reference](../reference/cli.md) and [Failover & retry](../configuration/failover/index.md).
