---
title: "Profiling"
description: "Profile Smart Router to find CPU and memory hotspots."
---

# Profiling

Use profiling to diagnose CPU, memory, or contention issues in Smart Router. The router
can send continuous profiles to [Pyroscope](https://pyroscope.io/), or expose Go's
`pprof` server for one-off captures.

## Continuous profiling (Pyroscope)

When you give the router a Pyroscope server address, it streams CPU, heap, goroutine,
mutex, and block profiles to it continuously:

```bash
smartrouter config.yml --use-static-spec specs/ \
  --pyroscope-address http://pyroscope:4040 \
  --pyroscope-app-name smartrouter \
  --pyroscope-tags "instance=router-1,region=us-east"
```

| Flag | Default | Purpose |
| --- | --- | --- |
| `--pyroscope-address` | - | Pyroscope server URL. Profiling is off until this is set. |
| `--pyroscope-app-name` | `smartrouter` | Application name shown in Pyroscope. |
| `--pyroscope-tags` | - | Comma-separated `key=value` tags (instance, region, …) for filtering. |
| `--pyroscope-mutex-profile-fraction` | `5` | Mutex profile sampling rate (1 in N events). |
| `--pyroscope-block-profile-rate` | `1` | Block profile rate (ns; `1` records all blocking events). |

Use the tags to tell replicas apart in the Pyroscope UI. When you run more than one
router, set at least `instance`.

## One-off profiling (pprof)

If you do not have a Pyroscope server, expose Go's standard `pprof` HTTP server and
capture profiles when you need them:

```bash
smartrouter config.yml --use-static-spec specs/ --pprof-address localhost:6060

# capture a 30s CPU profile
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30
```

Bind it to localhost (or put it behind your network controls), because the `pprof`
endpoints have no authentication.
