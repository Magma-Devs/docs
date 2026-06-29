---
title: "Dashboard"
description: "Run the Smart Router monitoring dashboard to watch routing, cache, and provider health in real time."
---

# Dashboard

The [Smart Router Dashboard](https://github.com/Magma-Devs/smart-router-dashboard) is an
optional web UI for monitoring and managing a running router. It pairs a Next.js frontend
with a small backend that reads from Prometheus.

## What it gives you

- **Real-time metrics** — node health, latency, request volume, cache hit rate, and the
  rest of the [router metric series](../reference/metrics.md), read live from Prometheus.
- **Live testing** — fire test requests at your chains from the browser to confirm a
  config works end to end.
- **Configuration management** — view/manage Helm values, plus a config wizard in debug
  mode.
- **Authentication** — HTTP Basic auth gates the whole UI and API.

## Run it

The dashboard ships as a Compose overlay that brings up Prometheus, the dashboard
backend, and the frontend together — all from prebuilt GHCR images, no source checkout:

```bash
docker compose -f docker/docker-compose.dashboard.yml up
```

| URL | Service |
| --- | --- |
| <http://localhost:3000> | Dashboard UI |
| <http://localhost:8000> | Dashboard API (`/docs` for the OpenAPI UI) |
| <http://localhost:9090> | Prometheus |
| <http://localhost:3360> | router ETH1 JSON-RPC |
| <http://localhost:7779> | router metrics (scraped by Prometheus) |

## Authentication

The UI and every backend endpoint (except the auth-status check) require HTTP Basic
credentials. Defaults are `admin` / `password` — **change them for anything but local
use**:

```bash
DASHBOARD_USERNAME=alice DASHBOARD_PASSWORD='a-strong-secret' \
  docker compose -f docker/docker-compose.dashboard.yml up
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `DASHBOARD_USERNAME` | `admin` | Basic-auth user. |
| `DASHBOARD_PASSWORD` | `password` | Basic-auth password. |
| `DASHBOARD_TAG` | `latest` | GHCR image tag for the backend + frontend. |

## How it fits together

```
browser ──▶ frontend (:3000) ──▶ backend (:8000) ──▶ Prometheus (:9090) ──▶ router (:7779/metrics)
```

The dashboard is read-only with respect to traffic — it observes the router via
Prometheus and issues test relays; it isn't in the request path. For the raw metric and
alerting reference behind the panels, see [Observability](../reference/observability/index.md).
