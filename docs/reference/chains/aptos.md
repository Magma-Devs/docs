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
curl http://127.0.0.1:3360/
```

!!! note "The `/v1` prefix lives in the node-url, not your request path"
    The example config's upstream URLs already end in `/v1`
    (`https://aptos-rest.publicnode.com/v1`), and the router forwards your
    request path onto that base. So call the listener at the **root** —
    `GET /`, `GET /accounts/0x1`, `GET /blocks/by_height/{n}` — **not**
    `GET /v1/...` (that would resolve to `/v1/v1/...` upstream and 404).

## Connect a client

=== "curl"

    ```bash
    # account resources — note the root-relative path (no /v1 prefix)
    curl http://127.0.0.1:3360/accounts/0x1/resources
    ```

=== "Aptos TS SDK"

    ```ts
    import { Aptos, AptosConfig } from '@aptos-labs/ts-sdk';

    // The SDK appends /v1 itself, so point it at a node-url that does NOT
    // bake in /v1 — drop the /v1 from the example config's upstreams and use
    // the bare listener here.
    const aptos = new Aptos(new AptosConfig({ fullnode: 'http://127.0.0.1:3360' }));
    const info = await aptos.getLedgerInfo();
    ```

Point at your own upstreams by editing the `node-urls` in the config — see [The config file](../../configuration/config-file.md).
