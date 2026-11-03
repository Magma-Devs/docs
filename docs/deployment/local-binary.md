---
title: "Local binary"
description: "Build and run the Smart Router binary natively on your host machine."
---

# Local binary

Run Smart Router as a native binary on the host, without Docker. Use this for the
smallest footprint, to wire it into your own process manager (systemd, supervisor), or
to develop against the router.

## Build & install

You need **Go 1.26+**. From a clone of the
[smart-router](https://github.com/Magma-Devs/smart-router) repo:

```bash
git clone https://github.com/Magma-Devs/smart-router.git
cd smart-router

make install   # go install -> $GOBIN (usually ~/go/bin)
# or
make build     # builds ./build/smartrouter without installing
```

`make install` produces a single `smartrouter` binary. The cache is the `cache`
subcommand of the same binary, so there is nothing else to build.

## Run the router

Point it at a config file and a spec source:

```bash
smartrouter config/smartrouter_examples/smartrouter_eth.yml \
  --use-static-spec specs/ \
  --metrics-listen-address :7779

# Smoke-test it
curl -X POST http://localhost:3360 \
     -H 'content-type: application/json' \
     -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

A JSON-RPC result without an error means the listener is live. The metrics server also
answers `:7779/metrics/overall-health`. See [Confirm it's healthy](docker-compose.md#confirm-its-healthy)
for the full set of checks.

- The **config file is positional**. There is no `--config` flag.
- `--use-static-spec` accepts a local directory (the bundled `specs/`) **or** a
  GitHub/GitLab URL to resolve chains that aren't bundled (e.g. `LAV1`). You can pass it
  more than once.
- See the [CLI reference](../reference/cli.md) for every flag.

If you don't have a config yet, the [wizard](wizard.md) writes one and can run it for you.

## Run the cache (optional)

The cache runs as a separate process. Start it, then point the router at it with
`cache-be:` in the config (the [cache section](docker-compose.md#add-the-cache) explains
why it is a config key, not a flag):

```bash
# terminal 1 - cache server (address is positional)
smartrouter cache 127.0.0.1:20100 --metrics_address 127.0.0.1:5555

# terminal 2 - router, with cache-be: "127.0.0.1:20100" in the config
smartrouter config/smartrouter_examples/smartrouter_eth_cached.yml \
  --use-static-spec specs/
```

See the [cache subcommand flags](../reference/cli.md#cache-subcommand-flags) for TTL and
sizing options.
