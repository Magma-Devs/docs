---
title: "Dashboard"
description: "Run the Smart Router monitoring dashboard to watch routing, cache, and provider health in real time."
---

# Dashboard

The [Smart Router Dashboard](https://github.com/Magma-Devs/smart-router-dashboard) is an
optional web UI for observing a running router. It lives in its own repository and ships
a **self-contained stack** — router + Prometheus + dashboard — so there's nothing to wire
up from the router repo.

## What it gives you

- **Real-time metrics** — chain and upstream health, latency, request volume, error
  rates (with code / category / retryability breakdowns), and the rest of the
  [router metric series](../reference/metrics.md), read live from Prometheus. Request
  counts are **client-scoped** — one per caller request, excluding cross-validation
  fan-out and the router's own probes — and panels for lazily-registered families
  (cache, retries, hedge, cross-validation, WebSocket) light up automatically the
  first time the feature fires.
- **Live testing** — fire test requests at your chains from the browser (HTTP and
  WebSocket) to confirm a config works end to end, with copy-paste snippets for every
  method and per-request badges for the serving upstream, cache hits, retries, and
  cross-validation agreement.
- **Topology view** — chains, upstreams, and endpoints read from the mounted values
  file; upstream URLs are masked to scheme + host.
- **Optional authentication** — off by default (open, zero-dependency); flip on Auth.js
  sign-in backed by Postgres when you need it.

## Run it

```bash
git clone https://github.com/Magma-Devs/smart-router-dashboard
cd smart-router-dashboard
make up          # router + Prometheus + api (:8000) + web (:3000) + logs (Grafana :3001)
make up-cache    # same, plus the relay-cache sidecar wired in via --cache-be
```

| URL | Service |
| --- | --- |
| <http://localhost:3000> | Dashboard UI |
| <http://localhost:8000> | Dashboard API (`/docs` for the OpenAPI UI) |
| <http://localhost:9090> | Prometheus |
| <http://localhost:3001> | Grafana logs (`admin`/`admin`; anonymous viewer enabled) |
| <http://localhost:3360> | router ETH1 JSON-RPC (WebSocket at `ws://localhost:3360/ws`) |
| <http://localhost:7779> | router metrics (scraped by Prometheus) |

Already running a router on the host's `:7779`? Bring up just the dashboard + Prometheus
with `docker compose up` (no router profile). Full configuration — authentication, the
values file, the logs profile, and pointing it at an existing router — is in the
[dashboard README](https://github.com/Magma-Devs/smart-router-dashboard/blob/main/README.md).

## How it fits together

```
browser ──▶ web (:3000) ──▶ api (:8000) ──▶ Prometheus (:9090) ──▶ router (:7779/metrics)
```

The dashboard is read-only with respect to traffic — it observes the router via
Prometheus and issues test relays; it isn't in the request path. For the raw metric and
alerting reference behind the panels, see [Observability](../reference/observability/index.md).
