# Examples

Every chain bundled in the repo's [`specs/`](https://github.com/Magma-Devs/smart-router/tree/main/specs) ships a **ready-to-run example config** under [`config/smartrouter_examples/`](https://github.com/Magma-Devs/smart-router/tree/main/config/smartrouter_examples). Each one points at that chain's Lava public gateway (`<chain>.lava.build`), so it runs with **no API key** — copy it, swap in your own upstreams when you're ready, and go.

The per-chain pages below walk through each one — endpoint, method surface, a client snippet, and the exact run command.

## Bundled chains

| Chain | `chain-id` | Interface(s) | Example config | Page |
| --- | --- | --- | --- | --- |
| Ethereum | `ETH1` | jsonrpc | `smartrouter_eth.yml` | [Ethereum](../ethereum.md) |
| Arbitrum One | `ARBITRUM` | jsonrpc | `smartrouter_arbitrum.yml` | [Arbitrum](../arbitrum.md) |
| Base | `BASE` | jsonrpc | `smartrouter_base.yml` | [Base](../base.md) |
| Lava | `LAVA` | rest, grpc, tendermintrpc | `smartrouter_lava.yml` | [Lava](../lava.md) |
| Solana | `SOLANA` | jsonrpc | `smartrouter_solana.yml` | [Solana](../solana.md) |

Want everything at once? [`smartrouter_multichain.yml`](https://github.com/Magma-Devs/smart-router/blob/main/config/smartrouter_examples/smartrouter_multichain.yml) serves **all five chains together**, each on its own port — ETH1 `3360`, Arbitrum `3361`, Base `3362`, Solana `3363`, and Lava REST/Tendermint/gRPC on `3364`/`3365`/`3366` — all via `*.lava.build`:

```bash
SR_CONFIG=config/smartrouter_examples/smartrouter_multichain.yml \
  docker compose -f docker/docker-compose.yml up --build
```

The repo also ships cached variants (`smartrouter_eth_cached.yml`, `smartrouter_multichain_cached.yml`) — same shape, plus the cache sidecar.

## Run any example

Every example is run the same way — pass the config positionally and point `--use-static-spec` at the bundled specs:

=== "Docker Compose"

    ```bash
    SR_CONFIG=config/smartrouter_examples/smartrouter_eth.yml \
      docker compose -f docker/docker-compose.yml up --build
    ```

=== "Local binary"

    ```bash
    smartrouter config/smartrouter_examples/smartrouter_eth.yml --use-static-spec specs/
    ```

Swap the filename for any chain above. Then send a request to the listener it opens (port `3360` by default) — each chain page has a copy-paste call.

!!! tip "Solana is HTTP-only in its example"
    The Solana example has no websocket leg, so add `--skip-websocket-verification`
    when you run it. The EVM examples (Ethereum, Arbitrum, Base) pair each https url
    with a wss one and need no extra flag.

See [Run Smart Router](../../../deployment/index.md) for the cache and dashboard overlays, and [The config file](../../../configuration/config-file.md) for the config format.
