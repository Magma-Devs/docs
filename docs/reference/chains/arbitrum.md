# Arbitrum

Arbitrum One over JSON-RPC.

## Endpoint

| | |
|---|---|
| Default port | `3360` (override per `endpoints[]` entry) |
| Calling convention | `POST /` with a JSON-RPC body |
| `chain-id` | `ARBITRUM` |
| Spec | [`specs/arbitrum.json`](https://github.com/Magma-Devs/smart-router/blob/main/specs/arbitrum.json) |

## Method surface

The Arbitrum spec **imports `ETH1`**, so it serves the same Ethereum JSON-RPC method surface (`eth_*`, `net_*`, `web3_*`, plus `debug_*`/`trace_*` on capable upstreams) with Arbitrum-specific additions (e.g. `arbtrace_*`, `arbblock`-style fields). See [Ethereum → Supported method families](ethereum.md#supported-method-families) and [Upstream capabilities](ethereum.md#upstream-capabilities) — the same add-ons (`debug`, `trace`, `archive`) apply.

## Run this example

The repo ships a ready-to-run config at [`config/smartrouter_examples/smartrouter_arbitrum.yml`](https://github.com/Magma-Devs/smart-router/blob/main/config/smartrouter_examples) — a single upstream on the Lava public gateway (`arbitrum.lava.build`, HTTP + WS), no API key needed:

=== "Local binary"

    ```bash
    smartrouter config/smartrouter_examples/smartrouter_arbitrum.yml --use-static-spec specs/
    ```

=== "Docker Compose"

    ```bash
    SR_CONFIG=config/smartrouter_examples/smartrouter_arbitrum.yml \
      docker compose -f docker/docker-compose.yml up --build
    ```

Then call it:

```bash
curl -X POST http://127.0.0.1:3360 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

## Connect a client

=== "viem"

    ```ts
    import { createPublicClient, http } from 'viem';
    import { arbitrum } from 'viem/chains';

    const client = createPublicClient({
      chain: arbitrum,
      transport: http('http://127.0.0.1:3360'),
    });

    const block = await client.getBlockNumber();
    ```

=== "ethers v6"

    ```ts
    import { JsonRpcProvider } from 'ethers';
    const provider = new JsonRpcProvider('http://127.0.0.1:3360');
    const block = await provider.getBlockNumber();
    ```

Point at your own upstreams by editing the `node-urls` in the config — see [The config file](../../configuration/config-file.md).
