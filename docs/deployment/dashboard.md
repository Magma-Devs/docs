---
title: "Dashboard"
description: "Run the Smart Router monitoring dashboard to watch routing, cache, and provider health in real time."
---

# Dashboard

The [Smart Router Dashboard](https://github.com/Magma-Devs/smart-router-dashboard) is an
optional web UI for observing a running router. It has its own repository and a
**self-contained stack** (router + Prometheus + dashboard), so there is nothing to wire
up from the router repo.

## What it gives you

- **Real-time metrics**: chain and upstream health, latency, request volume, error
  rates (broken down by code, category, and retryability), and the rest of the
  [router metric series](../reference/metrics.md), read live from Prometheus. Request
  counts are **client-scoped**: one per caller request, not counting cross-validation
  fan-out or the router's own probes. Panels for lazily-registered families (cache,
  retries, hedge, cross-validation, WebSocket) start showing data automatically the
  first time the feature runs.
- **Live testing**: send test requests to your chains from the dashboard (HTTP and
  WebSocket) to confirm a config works end to end. You get copy-paste snippets for every
  method, and badges on each request for the serving upstream, cache hits, retries, and
  cross-validation agreement. The dashboard's API sends each test to the router, so it
  works from any browser that can open the dashboard. See [Live testing](#live-testing).
- **Topology view**: chains, upstreams, and endpoints, read from the mounted values
  file. Upstream URLs are masked to scheme + host.
- **Optional authentication**: off by default (open, zero-dependency). When you need it,
  turn on Auth.js sign-in backed by Postgres.

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

If a router already runs on the host's `:7779`, start only the dashboard + Prometheus
with `docker compose up` (no router profile), and set
`ROUTER_RELAY_HOST=host.docker.internal` so [live testing](#live-testing) reaches it. The
[dashboard README](https://github.com/Magma-Devs/smart-router-dashboard/blob/main/README.md)
has the full configuration: authentication, the values file, the logs profile, and how to
point it at an existing router.

## Live testing

The **Try now** drawer sends each test request to the dashboard's API, and the API sends
it to the router's listener. Your browser never dials the router, so a test works even
where the router's address admits only listed sources. The drawer marks such a request
`sent from server`, and the snippets still print the router's own address, which is what
your client calls.

Two settings on the API decide where a test goes:

| Variable | Default | What it does |
| --- | --- | --- |
| `ROUTER_RELAY_HOST` | `localhost`; `router` in the compose stack | Where the router listens, as the API reaches it. The port is the listener's own, read from the mounted config. |
| `ROUTER_RELAY_ENABLED` | `true` | `false` turns this off: the browser sends the test itself, to the address shown in the drawer. |

An API that cannot reach the router at `ROUTER_RELAY_HOST` answers every test with a
`502`.

!!! warning "With authentication off, anyone who can reach the dashboard API can send requests through the router"
    The API answers anyone who can reach it unless authentication is on, and that
    includes these test requests. If your router admits only listed addresses and the
    dashboard API is reachable from elsewhere, turn authentication on or set
    `ROUTER_RELAY_ENABLED=false`.

## How it fits together

```
browser ──▶ web (:3000) ──▶ api (:8000) ──▶ Prometheus (:9090) ──▶ router (:7779/metrics)
                                 └────────▶ router (:3360, the tests you send)
```

The dashboard is not in the request path. It is read-only with respect to traffic: it
observes the router through Prometheus and sends the test relays you ask for. For the raw
metric and alerting reference behind the panels, see
[Observability](../reference/observability/index.md).
