---
title: "Bitcoin"
description: "Run Smart Router for Bitcoin — example config and supported JSON-RPC methods."
---

# Bitcoin

Bitcoin mainnet over Bitcoin Core JSON-RPC.

## Endpoint

| | |
|---|---|
| Default port | `3360` (override per `endpoints[]` entry) |
| Calling convention | `POST /` with a JSON-RPC body |
| `chain-id` | `BTC` |
| Spec | [`specs/btc.json`](https://github.com/Magma-Devs/smart-router/blob/main/specs/btc.json) |

## Supported method families

Bitcoin speaks Bitcoin Core's JSON-RPC, not the Ethereum one.

| Family | Examples |
|---|---|
| Blocks | `getblockcount`, `getblockhash`, `getblock`, `getblockheader`, `getbestblockhash`, `getblockchaininfo` |
| Transactions | `getrawtransaction`, `decoderawtransaction`, `sendrawtransaction`, `gettxout` |
| Network / node | `getnetworkinfo`, `getmempoolinfo`, `estimatesmartfee`, `getmininginfo` |

The full method list lives in the spec file linked above.

## Run this example

The repo ships a ready-to-run config at [`config/smartrouter_examples/smartrouter_bitcoin.yml`](https://github.com/Magma-Devs/smart-router/blob/main/config/smartrouter_examples) — a single public upstream on PublicNode (`bitcoin-rpc.publicnode.com`), no API key needed. Bitcoin Core's JSON-RPC has no websocket surface, so run it with `--skip-websocket-verification`:

=== "Docker Compose"

    ```bash
    SR_CONFIG=config/smartrouter_examples/smartrouter_bitcoin.yml \
      docker compose -f docker/docker-compose.yml up --build
    ```

=== "Local binary"

    ```bash
    smartrouter config/smartrouter_examples/smartrouter_bitcoin.yml \
      --use-static-spec specs/ --skip-websocket-verification
    ```

Then call it:

```bash
# current block height
curl -X POST http://127.0.0.1:3360 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"1.0","method":"getblockcount","params":[],"id":1}'
```

## Connect a client

=== "curl"

    ```bash
    # block hash at height 800000
    curl -X POST http://127.0.0.1:3360 \
      -H 'Content-Type: application/json' \
      -d '{"jsonrpc":"1.0","method":"getblockhash","params":[800000],"id":1}'
    ```

=== "Python (requests)"

    ```python
    import requests
    r = requests.post(
        "http://127.0.0.1:3360",
        json={"jsonrpc": "1.0", "method": "getblockchaininfo", "params": [], "id": 1},
    )
    print(r.json()["result"]["blocks"])
    ```

Point at your own upstreams by editing the `node-urls` in the config — see [The config file](../../configuration/config-file.md).
