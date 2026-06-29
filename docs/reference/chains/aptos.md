# Aptos

Aptos mainnet over the REST fullnode API.

## Endpoint

| | |
|---|---|
| Default port | `3360` (override per `endpoints[]` entry) |
| Calling convention | REST — `GET /v1/...`, `POST /v1/view`, etc. |
| `chain-id` | `APT1` |
| Spec | [`specs/aptos.json`](https://github.com/Magma-Devs/smart-router/blob/main/specs/aptos.json) |

## Supported method families

Aptos exposes a REST API (not JSON-RPC). Paths are served under `/v1`.

| Family | Examples |
|---|---|
| Ledger / blocks | `GET /v1` (ledger info), `GET /v1/blocks/by_height/{height}`, `GET /v1/blocks/by_version/{version}` |
| Accounts | `GET /v1/accounts/{address}`, `GET /v1/accounts/{address}/resources`, `GET /v1/accounts/{address}/modules` |
| Transactions | `GET /v1/transactions`, `GET /v1/transactions/by_hash/{hash}`, `POST /v1/transactions`, `POST /v1/transactions/simulate` |
| View / state | `POST /v1/view`, `GET /v1/accounts/{address}/resource/{type}` |

The full method list lives in the spec file linked above.

## Run this example

The repo ships a ready-to-run config at [`config/smartrouter_examples/smartrouter_aptos.yml`](https://github.com/Magma-Devs/smart-router/blob/main/config/smartrouter_examples) — two public upstreams (PublicNode and the Aptos Labs fullnode), no API key needed. REST has no websocket leg, so run it with `--skip-websocket-verification`:

=== "Docker Compose"

    ```bash
    SR_CONFIG=config/smartrouter_examples/smartrouter_aptos.yml \
      docker compose -f docker/docker-compose.yml up --build
    ```

=== "Local binary"

    ```bash
    smartrouter config/smartrouter_examples/smartrouter_aptos.yml \
      --use-static-spec specs/ --skip-websocket-verification
    ```

Then call it:

```bash
# ledger info (chain id, block height, ledger version)
curl http://127.0.0.1:3360/v1
```

## Connect a client

=== "curl"

    ```bash
    # account resources
    curl http://127.0.0.1:3360/v1/accounts/0x1/resources
    ```

=== "Aptos TS SDK"

    ```ts
    import { Aptos, AptosConfig } from '@aptos-labs/ts-sdk';

    const aptos = new Aptos(new AptosConfig({ fullnode: 'http://127.0.0.1:3360/v1' }));
    const info = await aptos.getLedgerInfo();
    ```

Point at your own upstreams by editing the `node-urls` in the config — see [The config file](../../configuration/config-file.md).
