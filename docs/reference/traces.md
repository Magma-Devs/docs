---
title: "Traces"
description: "OpenTelemetry traces covering inbound listener, provider selection, retries, hedging, and cache lookups."
---

# Traces

Smart Router emits OpenTelemetry spans covering the whole relay lifecycle — inbound
listener → node selection → each attempt (retry / hedge) → cache lookup → outbound
response. Spans propagate W3C trace context, so a request keeps its trace id end to end
across the router.

## Configuration

Tracing is **standard OpenTelemetry, driven by environment variables** — not CLI flags.
The SDK reads them directly. Tracing is active whenever the SDK is enabled and an
exporter is selected (both true by default).

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://otel-collector:4318"
export OTEL_SERVICE_NAME="smartrouter"
smartrouter config.yml --use-static-spec specs/
```

| Env var | Purpose |
| --- | --- |
| `OTEL_SDK_DISABLED` | `true` disables the SDK entirely. |
| `OTEL_TRACES_EXPORTER` | `otlp` (default) · `none` · `console`. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Collector URL (default `localhost:4318` HTTP / `:4317` gRPC). |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | Traces-specific endpoint override. |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` or `grpc`. |
| `OTEL_EXPORTER_OTLP_HEADERS` | Auth headers (`k=v,k=v`). |
| `OTEL_EXPORTER_OTLP_INSECURE` | Disable TLS to the collector. |
| `OTEL_TRACES_SAMPLER` / `OTEL_TRACES_SAMPLER_ARG` | Sampler strategy + argument (default: parent-based always-on). |
| `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` | Resource identity. |

Each OTLP variable also has a `TRACES_`-prefixed per-signal variant, and mTLS is
supported via `OTEL_EXPORTER_OTLP_CLIENT_KEY` / `_CLIENT_CERTIFICATE` / `_CERTIFICATE`.

!!! warning "Disable it if you have no collector"
    With no endpoint set, the SDK falls back to the default `localhost:4317/4318` and the
    exporter logs connection errors. If you don't run a collector, set
    `OTEL_SDK_DISABLED=true` or `OTEL_TRACES_EXPORTER=none`.

## Recording request/response bodies

The one Smart Router-specific tracing flag is **`--otel-trace-body`** — record the
request and response bodies as span attributes (size capped via
`OTEL_SPAN_ATTRIBUTE_VALUE_LENGTH_LIMIT`, default unlimited).

Leave it **off in production** — bodies can contain addresses, signed transactions, and
other sensitive data.

## Usage events (a separate stream)

Distinct from spans, `--usage-otel-enabled` emits per-relay **usage + QoS events** as
OTLP *logs* (off by default; the relay path pays nothing when off). Tune the queue, batch
size, and flush interval with the `--usage-otel-*` flags — see the
[CLI reference](cli.md#metrics-telemetry).
