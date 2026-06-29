---
title: "Observability"
description: "Metrics, traces, logs, and profiling across the full Smart Router request lifecycle."
---

# Observability

How to watch Smart Router in production and diagnose what it's doing. Four pillars:

| Topic | What's in it |
| --- | --- |
| [Metrics](../metrics.md) | Every Prometheus metric exposed, with types and labels — plus PromQL recipes and suggested alerts. |
| [Traces](../traces.md) | OpenTelemetry spans over the full relay lifecycle, configured via standard OTel env vars. |
| [Profiling](../profiling.md) | Continuous CPU / memory / mutex / block profiles to Pyroscope (or one-off `pprof`). |
| [Error codes](../error-codes.md) | The internal error taxonomy seen in logs and the `smartrouter_errors_total` metric, with retryability. |

The prebuilt [dashboard overlay](../../deployment/docker-compose.md#add-the-dashboard)
graphs the metric series out of the box. Most signals are off until you point the router
at a collector / Pyroscope / Prometheus — each page below covers how to turn it on.
