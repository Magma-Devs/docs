---
title: "Observability"
description: "Metrics, traces, logs, and profiling across the full Smart Router request lifecycle."
---

# Observability

Use these pages to monitor Smart Router in production and find out what it is doing.
They cover four topics:

| Topic | What's in it |
| --- | --- |
| [Metrics](../metrics.md) | Every Prometheus metric exposed, with types and labels, plus PromQL recipes and suggested alerts. |
| [Traces](../traces.md) | OpenTelemetry spans over the full relay lifecycle, configured with standard OTel env vars. |
| [Profiling](../profiling.md) | Continuous CPU / memory / mutex / block profiles to Pyroscope (or one-off `pprof`). |
| [Error codes](../error-codes.md) | The internal error taxonomy seen in logs and the `smartrouter_errors_total` metric, with retryability. |

The prebuilt [dashboard overlay](../../deployment/docker-compose.md#add-the-dashboard)
graphs the metric series with no extra setup. Most signals are off until you connect the
router to a collector, Pyroscope, or Prometheus. Each of these pages explains how to turn
its signal on.
