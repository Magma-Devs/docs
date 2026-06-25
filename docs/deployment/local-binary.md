# Local binary

Run Smart Router as a native binary on the host — no Docker. Best when you want the
smallest footprint, are wiring it into your own process manager (systemd, supervisor),
or are developing against the router.

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

`make install` produces a single `smartrouter` binary. The cache is the same binary's
`cache` subcommand — there's nothing else to build.

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

- The **config file is positional** — there's no `--config` flag.
- `--use-static-spec` accepts a local directory (the bundled `specs/`) **or** a
  GitHub/GitLab URL to resolve chains that aren't bundled (e.g. `LAV1`). Repeatable.
- See the [CLI reference](../reference/cli.md) for every flag.

Don't have a config yet? The [wizard](wizard.md) writes one (and can run it for you).

## Run the cache (optional)

The cache is a separate process. Start it, then point the router at it with
`cache-be:` in the config (the [cache section](docker-compose.md#add-the-cache) explains
why it's a config key, not a flag):

```bash
# terminal 1 — cache server (address is positional)
smartrouter cache 127.0.0.1:20100 --metrics_address 127.0.0.1:5555

# terminal 2 — router, with cache-be: "127.0.0.1:20100" in the config
smartrouter config/smartrouter_examples/smartrouter_eth_cached.yml \
  --use-static-spec specs/
```

See the [cache subcommand flags](../reference/cli.md#cache-subcommand-flags) for TTL and
sizing options.
