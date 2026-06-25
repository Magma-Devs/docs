# Solana

Solana mainnet over JSON-RPC.

## Endpoint

| | |
|---|---|
| Default port | `3360` (override per `endpoints[]` entry) |
| Calling convention | `POST /` with a JSON-RPC body |
| `chain-id` | `SOLANA` |
| Spec | [`specs/solana.json`](https://github.com/Magma-Devs/smart-router/blob/main/specs/solana.json) |

## Supported method families

Solana speaks its own JSON-RPC, not the Ethereum one.

| Family | Examples |
|---|---|
| State / accounts | `getAccountInfo`, `getBalance`, `getMultipleAccounts`, `getProgramAccounts`, `getTokenAccountBalance` |
| Blocks / slots | `getSlot`, `getBlock`, `getBlockHeight`, `getBlockTime`, `getBlocks`, `getLatestBlockhash` |
| Transactions | `getTransaction`, `getSignatureStatuses`, `sendTransaction`, `simulateTransaction` |
| Network / node | `getHealth`, `getVersion`, `getEpochInfo`, `getClusterNodes`, `getGenesisHash` |

The full method list lives in the spec file linked above.

!!! note "Slot vs. block height"
    Solana's `context.slot` and `lastValidBlockHeight` diverge by the skip rate
    (tens of millions on mainnet). Smart Router tracks the **slot** on both the
    chain-tracker and consistency sides so cross-node consistency checks compare
    like units.

## Run this example

The repo ships a ready-to-run config at [`config/smartrouter_examples/smartrouter_solana.yml`](https://github.com/Magma-Devs/smart-router/blob/main/config/smartrouter_examples) — a single upstream on the Lava public gateway (`solana.lava.build`), no API key needed. The example is HTTP-only, so run it with `--skip-websocket-verification`:

=== "Docker Compose"

    ```bash
    SR_CONFIG=config/smartrouter_examples/smartrouter_solana.yml \
      docker compose -f docker/docker-compose.yml up --build
    ```

=== "Local binary"

    ```bash
    smartrouter config/smartrouter_examples/smartrouter_solana.yml \
      --use-static-spec specs/ --skip-websocket-verification
    ```

Then call it:

```bash
# current slot
curl -X POST http://127.0.0.1:3360 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"getSlot","params":[],"id":1}'
```

## Connect a client

=== "@solana/web3.js"

    ```ts
    import { Connection } from '@solana/web3.js';
    const connection = new Connection('http://127.0.0.1:3360');
    const slot = await connection.getSlot();
    ```

=== "curl"

    ```bash
    curl -X POST http://127.0.0.1:3360 \
      -H 'Content-Type: application/json' \
      -d '{"jsonrpc":"2.0","method":"getBalance","params":["11111111111111111111111111111111"],"id":1}'
    ```

Point at your own upstreams by editing the `node-urls` in the config — see [The config file](../../configuration/config-file.md).
