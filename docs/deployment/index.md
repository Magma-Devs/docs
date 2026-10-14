---
title: "Run Smart Router"
description: "Ways to run Smart Router: a native local binary, the Docker Compose stack, or the interactive config wizard."
---

# Run Smart Router

Smart Router runs on your own infrastructure. This page helps you pick one of three ways
to run it and lists what you need.

The router and the optional cache sidecar are the same single binary. There are no
external dependencies beyond the upstream RPC nodes you configure.

Pick how you want to run it:

| Method | Best for |
| --- | --- |
| [**Config wizard**](wizard.md) | The fastest start. An interactive TUI picks chains, collects upstreams, health-checks everything, writes the config, and brings up the stack in one pass. Start here if you don't have a config yet. |
| [**Docker Compose**](docker-compose.md) | Running a config you already have (or one copied from the examples) with one `docker compose` command. You can add an optional cache overlay. The [dashboard](dashboard.md) runs from its own repo. |
| [**Local binary**](local-binary.md) | A native process with no Docker. Use it for the smallest footprint, or to wire it into your own service manager. |

!!! note "Looking for a managed option?"
    These docs cover the **self-hosted** Smart Router. If you'd rather not operate it
    yourself, [talk to us](https://magmadevs.com/contact).

## Prerequisites

All three methods start from a clone of the repo, which has the compose files, example
configs, and bundled `specs/`:

```bash
git clone https://github.com/Magma-Devs/smart-router.git
cd smart-router
```

- **Docker Compose / wizard** need **Docker** with Compose v2 (`docker compose`, not the
  legacy `docker-compose`). The source is built inside the image, so you don't need Go
  on the host.
- **Local binary** needs **Go 1.26+** to `make install`.

## What you need to run it

- **CPU**: start with 2+ cores. The router is mostly I/O bound.
- **Memory**: 1–2 GiB baseline.
- **Disk**: very little, because the router is stateless.
- **Network**: low-latency egress to your upstream nodes, with outbound TLS allowed
  (most public nodes require HTTPS / TLS gRPC).

## In production

- **Externalise secrets**: never put API keys into images or commit them to YAML. See
  [Authentication](../configuration/authentication.md).
- **Observability**: scrape `:7779` (see [Metrics](../reference/metrics.md)). Set
  `OTEL_EXPORTER_OTLP_ENDPOINT` for [tracing](../configuration/index.md).
- **Health checks**: each listener answers a basic chain-id query. The metrics server
  exposes an aggregate `:7779/metrics/overall-health` probe (`200 Health status OK` /
  `503 Unhealthy`). The cache exposes `/metrics` on its metrics port. See
  [Confirm it's healthy](docker-compose.md#confirm-its-healthy).
- **Tuning**: you can configure node selection, failover, and timeouts. See the
  [CLI reference](../reference/cli.md) and [Failover & retry](../configuration/failover/index.md).
