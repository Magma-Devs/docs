---
title: "Error codes"
description: "Reference of Smart Router error codes and what each one means."
---

# Error codes

Smart Router classifies every upstream failure into an internal **error code** used
for logging, metrics, and retry decisions. Each code has a name, a layer, and a
**retryable** flag that the failover state machine reads when deciding whether to
rotate to another node.

!!! info "These codes are internal — clients never see them"
    Smart Router is a transparent hop: your client always receives the **original**
    error from the upstream node, unmodified (the same JSON-RPC / HTTP / gRPC error
    you'd get talking to the node directly). Lava error codes appear only in the
    router's **logs** and in the [`smartrouter_errors_total`](metrics.md#classified-errors-smartrouter_errors_)
    metric. Use this
    page to interpret those logs and metrics — not to handle codes on the wire.

The registry lives in
[`protocol/common/error_registry.go`](https://github.com/Magma-Devs/smart-router/blob/main/protocol/common/error_registry.go).

## The four layers at a glance

| Layer | Range | Category | Means | Typical retryable? |
| --- | --- | --- | --- | --- |
| [`PROTOCOL_*`](#layer-a-protocol-errors-protocol_-10001999) | 1000s | Internal | The router's own plumbing — connection, session, consistency. | Mostly **yes** |
| [`NODE_*`](#layer-b-node-errors-node_-20002999) | 2000s | External | The node responded with an error (5xx, rate-limit, syncing, method-not-found). | Mixed |
| [`CHAIN_*`](#layer-c-blockchain-errors-chain_-30003999) | 3000s | External | The chain's execution/state layer (revert, nonce, block-not-found). | Mixed |
| [`USER_*`](#layer-d-user-errors-user_-40004999) | 4000s | External | The client sent a bad request (malformed JSON, invalid params). | **No** |

**Rule of thumb:** `PROTOCOL_*` / `NODE_*` 5xx are infra noise that failover absorbs;
a spike in `CHAIN_*` or `USER_*` usually means a client or contract problem, not your
deployment.

## Where you'll see these

In **logs** (structured fields on every classified failure):

```json
{"level":"warn","error_name":"NODE_RATE_LIMITED","error_category":"external",
 "retryable":true,"chain_id":"ETH1","chain_error_code":429,
 "chain_error_message":"429 Too Many Requests","provider":"eth-publicnode"}
```

In **metrics** (`smartrouter_errors_total`, labelled by name/category/retryability/chain):

```promql
# Which errors are firing, by name?
sum by (error_name) (rate(smartrouter_errors_total[5m]))

# Terminal (non-retryable) errors only — these reach the client
sum by (error_name) (rate(smartrouter_errors_total{retryable="false"}[5m]))
```

## Debugging with error codes

| You see… | Likely cause | Next step |
| --- | --- | --- |
| `NODE_RATE_LIMITED` climbing | A node is throttling you | Add upstreams, or check your node plan; failover already spreads load. |
| `PROTOCOL_NO_PROVIDERS` | The pool emptied for a relay | Every node was excluded — check health and the [circuit breaker](../configuration/failover/circuit-breaker.md). |
| `CHAIN_STATE_PRUNED` on historical queries | Hitting a non-archive node | Mark archive upstreams with the `archive` addon; see [config](../configuration/config-file.md). |
| `NODE_METHOD_NOT_FOUND` | Method isn't on that node's surface | Terminal + cached; confirm the chain spec actually exposes it. |
| `USER_*` spike | Clients sending bad requests | Not an infra issue — inspect the offending client. |
| `CHAIN_EXECUTION_REVERTED` | Contract reverted | Expected for failing `eth_call` / sims — terminal, not retried. |

## How classification works

Errors are classified with a two-level, chain-family-aware lookup:

1. **Tier 2 — chain-specific** matchers run first. They exist only where a chain's
   error means something with *different* retryability than the generic pattern
   (e.g. Solana `-32009` vs `-32007`, Bitcoin warmup, Starknet class errors).
2. **Tier 1 — generic semantic** matchers are the fallback, partitioned by transport
   (`jsonrpc` / `rest` / `grpc`) so an EVM chain never evaluates gRPC matchers and
   vice-versa.

Connection-level failures (timeouts, refused, reset, context cancellation) are
detected before either tier and always take precedence. Anything unmatched becomes
`UNKNOWN_ERROR` (code `0`, retryable).

### Retry, CU, and caching

`retryable` is the primary signal: a `retryable: No` classification short-circuits
retries on **every** terminal error, not just unsupported methods. Two sub-categories
carry extra behaviour:

- **Unsupported method** (`NODE_METHOD_NOT_FOUND`, `NODE_UNIMPLEMENTED`,
  `NODE_ENDPOINT_NOT_FOUND`, `NODE_METHOD_NOT_ALLOWED`) → zero retries, **zero CU**,
  response is cached, no node scoring. The node won't be hit again for it.
- **Rate limit** (`NODE_RATE_LIMITED`) → back off without marking the endpoint
  unhealthy (it's busy, not broken).
- **User-input errors** (`USER_*`) are non-retryable but charge **normal CU** — the
  response isn't cached because the next request from the same client may be valid, so
  the node still does real work.

---

## Layer A — Protocol errors (`PROTOCOL_*`, 1000–1999)

Category: **Internal**. Raised from within the Lava protocol itself — not from nodes
or chains.

| Code | Name | Description | Retryable |
| --- | --- | --- | --- |
| 1001 | `PROTOCOL_CONNECTION_TIMEOUT` | Network operation timed out connecting to node | Yes |
| 1002 | `PROTOCOL_CONNECTION_REFUSED` | Node connection refused | Yes |
| 1003 | `PROTOCOL_DNS_FAILURE` | DNS resolution failed | Yes |
| 1004 | `PROTOCOL_TLS_MISMATCH` | HTTP/HTTPS protocol mismatch | No |
| 1005 | `PROTOCOL_CONNECTION_RESET` | Connection reset by peer | Yes |
| 1006 | `PROTOCOL_CONNECTION_CLOSED` | Connection closed (EOF) | Yes |
| 1007 | `PROTOCOL_CONTEXT_DEADLINE` | Context deadline expired before the relay completed | Yes |
| 1008 | `PROTOCOL_CONTEXT_CANCELED` | Request context canceled (client disconnect or relay race resolved) | No |
| 1009 | `PROTOCOL_NETWORK_UNREACHABLE` | Network or host unreachable (no route) | Yes |
| 1010 | `PROTOCOL_NO_PROVIDERS` | No nodes/pairings available | No |
| 1011 | `PROTOCOL_ALL_ENDPOINTS_DISABLED` | All node endpoints disabled | No |
| 1012 | `PROTOCOL_PROVIDER_UNAVAILABLE` | Node service unavailable (gRPC UNAVAILABLE) | Yes |
| 1013 | `PROTOCOL_PROVIDER_ABORTED` | Node aborted (gRPC ABORTED) | Yes |
| 1014 | `PROTOCOL_PROVIDER_DATA_LOSS` | Node data loss (gRPC DATA_LOSS) | Yes |
| 1015 | `PROTOCOL_INSUFFICIENT_PROVIDERS` | Insufficient providers available for addon or cross-validation | No |
| 1020 | `PROTOCOL_RATE_LIMITED` | Lava-side rate limit exceeded | No |
| 1021 | `PROTOCOL_MAX_CU_EXCEEDED` | Maximum compute units exceeded for session | No |
| 1022 | `PROTOCOL_BATCH_SIZE_EXCEEDED` | Batch request size exceeded limit | No |
| 1023 | `PROTOCOL_CU_MISMATCH` | CU accounting inconsistency or security violation | No |
| 1030 | `PROTOCOL_SESSION_NOT_FOUND` | Session does not exist | No |
| 1031 | `PROTOCOL_EPOCH_MISMATCH` | Epoch mismatch or too old | No |
| 1032 | `PROTOCOL_CONSUMER_BLOCKED` | Consumer is blocklisted | No |
| 1033 | `PROTOCOL_CONSUMER_NOT_REGISTERED` | Consumer not registered | No |
| 1034 | `PROTOCOL_RELAY_NUMBER_MISMATCH` | Relay number mismatch | No |
| 1035 | `PROTOCOL_SESSION_OUT_OF_SYNC` | Session out of sync | No |
| 1036 | `PROTOCOL_INVALID_RELAY_REQUEST` | Relay request validation failed (wrong provider/specID/chainID/seen block/content hash) | No |
| 1037 | `PROTOCOL_REQUEST_BLOCK_MISMATCH` | Block height mismatch between consumer request and provider state | Yes |
| 1038 | `PROTOCOL_SESSION_ACCOUNTING_FAILED` | Session accounting (OnSessionDone/OnSessionFailure) failed | No |
| 1039 | `PROTOCOL_SUBSCRIPTION_CLEANUP_FAILED` | Subscription consumer removal (RemoveConsumer) failed | No |
| 1040 | `PROTOCOL_FINALIZATION_ERROR` | Node finalization data incorrect | Yes |
| 1041 | `PROTOCOL_CONSISTENCY_ERROR` | Response consistency validation failed | Yes |
| 1042 | `PROTOCOL_HASH_CONSENSUS_ERROR` | Conflicting response hashes detected | Yes |
| 1043 | `PROTOCOL_NO_RESPONSE_TIMEOUT` | Relay race timeout — no node returned within the deadline | Yes |
| 1044 | `PROTOCOL_RELAY_PROCESSING_FAILED` | Relay response processing failed on consumer side | Yes |
| 1050 | `PROTOCOL_SUBSCRIPTION_NOT_FOUND` | Subscription not found | No |
| 1051 | `PROTOCOL_SUBSCRIPTION_INIT_FAILED` | Failed to initialize subscription | No |
| 1052 | `PROTOCOL_WEBSOCKET_IDLE_TIMEOUT` | WebSocket idle timeout | No |
| 1053 | `PROTOCOL_SUBSCRIPTION_ALREADY_EXISTS` | Subscription already exists for this consumer/key | No |

---

## Layer B — Node errors (`NODE_*`, 2000–2999)

Category: **External**. Returned by the blockchain node itself (not execution/state
errors). "Standard code" is the protocol-level code the matcher keys off.

| Code | Name | Description | Retryable | Standard code |
| --- | --- | --- | --- | --- |
| 2001 | `NODE_METHOD_NOT_FOUND` | Method does not exist on this node (unknown to the API surface) | No | JSON-RPC -32601 |
| 2002 | `NODE_METHOD_NOT_SUPPORTED` | Method exists but is disabled on this node; retryable on a different node | Yes | JSON-RPC -32004 |
| 2003 | `NODE_INTERNAL_ERROR` | Internal node error | Yes | JSON-RPC -32603 |
| 2004 | `NODE_SERVER_ERROR` | Generic server error | Yes | JSON-RPC -32000 |
| 2005 | `NODE_RATE_LIMITED` | Rate limited by node | Yes | HTTP 429 |
| 2006 | `NODE_SERVICE_UNAVAILABLE` | Node temporarily unavailable | Yes | HTTP 503 |
| 2007 | `NODE_SYNCING` | Node is syncing/catching up | Yes | message match |
| 2008 | `NODE_UNIMPLEMENTED` | gRPC method unimplemented | No | gRPC 12 |
| 2009 | `NODE_ENDPOINT_NOT_FOUND` | REST endpoint not found | No | HTTP 404 |
| 2010 | `NODE_METHOD_NOT_ALLOWED` | REST method not allowed | No | HTTP 405 |
| 2011 | `NODE_LIMIT_EXCEEDED` | Request exceeds node limit (e.g. `eth_getLogs` range) | No | JSON-RPC -32005 |
| 2012 | `NODE_RESOURCE_NOT_FOUND` | Resource not found at node level | Yes | JSON-RPC -32001 |
| 2013 | `NODE_RESOURCE_UNAVAILABLE` | Resource exists but unavailable | Yes | JSON-RPC -32002 |
| 2014 | `NODE_GATEWAY_TIMEOUT` | Gateway timeout from node | Yes | HTTP 504 |
| 2015 | `NODE_BAD_GATEWAY` | Bad gateway from node | Yes | HTTP 502 |
| 2016 | `NODE_UNAUTHORIZED` | Upstream rejected router credentials (HTTP 401) | No | HTTP 401 |
| 2101 | `NODE_BITCOIN_WARMUP` | Node still warming up (Bitcoin -28) | Yes | — |
| 2102 | `NODE_BITCOIN_INITIAL_DOWNLOAD` | Node in initial block download (Bitcoin -10) | Yes | — |
| 2103 | `NODE_BITCOIN_NOT_CONNECTED` | Node has no peers (Bitcoin -9) | Yes | — |
| 2150 | `NODE_SOLANA_UNHEALTHY` | Solana node behind/unhealthy (-32005) | Yes | — |

---

## Layer C — Blockchain errors (`CHAIN_*`, 3000–3999)

Category: **External**. From the blockchain execution/state layer — transaction
failures, state queries, etc. Tier-2 (chain-specific) codes exist only where
retryability differs from the generic pattern.

### Transaction errors (3000–3099)

| Code | Name | Description | Retryable | Chains |
| --- | --- | --- | --- | --- |
| 3001 | `CHAIN_NONCE_TOO_LOW` | Nonce/sequence too low | No | EVM, Cosmos, Starknet, XRP, NEAR |
| 3002 | `CHAIN_NONCE_TOO_HIGH` | Nonce too high | No | EVM |
| 3003 | `CHAIN_INSUFFICIENT_FUNDS` | Insufficient funds for transfer/gas | No | Universal |
| 3004 | `CHAIN_GAS_TOO_LOW` | Intrinsic gas too low | No | EVM |
| 3005 | `CHAIN_GAS_LIMIT_EXCEEDED` | Exceeds block gas limit | No | EVM |
| 3006 | `CHAIN_TX_UNDERPRICED` | Transaction gas price too low | No | EVM |
| 3007 | `CHAIN_TX_ALREADY_KNOWN` | Transaction already in mempool | No | EVM, Starknet, XRP |
| 3008 | `CHAIN_TX_REPLACEMENT_UNDERPRICED` | Replacement tx gas too low | No | EVM |
| 3009 | `CHAIN_MEMPOOL_FULL` | Mempool/tx pool is full | No | EVM, Cosmos |
| 3010 | `CHAIN_TX_TOO_LARGE` | Transaction exceeds size limit | No | EVM, Solana |
| 3011 | `CHAIN_MAX_FEE_BELOW_BASE` | Max fee per gas below base fee | No | EVM (EIP-1559) |
| 3012 | `CHAIN_INVALID_SEQUENCE` | Invalid sequence (Cosmos nonce equivalent) | No | Cosmos |
| 3013 | `CHAIN_INSUFFICIENT_FEE` | Insufficient fee | No | Cosmos |
| 3014 | `CHAIN_TX_REJECTED` | Transaction rejected by network rules | No | Universal |
| 3015 | `CHAIN_DOUBLE_SPEND` | Double spend / UTXO already spent | No | Bitcoin/UTXO |
| 3016 | `CHAIN_INVALID_SIGNATURE` | Invalid transaction signature | No | Universal |

### Execution errors (3100–3199)

| Code | Name | Description | Retryable | Chains |
| --- | --- | --- | --- | --- |
| 3101 | `CHAIN_EXECUTION_REVERTED` | Smart contract execution reverted | No | EVM, Starknet, NEAR, TON |
| 3102 | `CHAIN_OUT_OF_GAS` | Out of gas during execution | No | EVM, Cosmos, TON |
| 3103 | `CHAIN_STACK_OVERFLOW` | Stack limit reached | No | EVM, TON |
| 3104 | `CHAIN_INVALID_OPCODE` | Invalid opcode encountered | No | EVM, TON |
| 3105 | `CHAIN_WRITE_PROTECTION` | Write in STATICCALL context | No | EVM |
| 3106 | `CHAIN_CONTRACT_SIZE_EXCEEDED` | Contract bytecode exceeds 24KB EIP-170 limit | No | EVM |
| 3107 | `CHAIN_ACCOUNT_NOT_FOUND` | Account/contract does not exist | No | Cosmos |
| 3108 | `CHAIN_ZKEVM_OUT_OF_COUNTERS` | Polygon zkEVM prover exceeded circuit counter budget | No | EVM (Polygon zkEVM) |

### State / data errors (3200–3299)

| Code | Name | Description | Retryable | Chains |
| --- | --- | --- | --- | --- |
| 3201 | `CHAIN_BLOCK_NOT_FOUND` | Block not found | Yes | Universal |
| 3202 | `CHAIN_TX_NOT_FOUND` | Transaction not found | Yes | Universal |
| 3203 | `CHAIN_RECEIPT_NOT_FOUND` | Transaction receipt not found | Yes | EVM (Cosmos-EVM variant) |
| 3204 | `CHAIN_STATE_PRUNED` | State pruned/missing trie node | Yes | EVM |
| 3205 | `CHAIN_DATA_NOT_AVAILABLE` | Historical data not available | Yes | Universal |
| 3206 | `CHAIN_BLOCK_TOO_OLD` | Block results only for recent blocks | Yes | Cosmos |
| 3207 | `CHAIN_LOG_RESPONSE_TOO_LARGE` | Log query returned too many results | No | EVM |

Chain-specific Tier-2 ranges also exist for **Solana** (3300–3319), **Starknet**
(3320–3339), **Bitcoin/UTXO** (3340–3359), and **NEAR** (3360–3379) — see the
[registry source](https://github.com/Magma-Devs/smart-router/blob/main/protocol/common/error_registry.go)
for the full list. Most are non-retryable; the retryable exceptions are the Solana
`CHAIN_SOLANA_LEDGER_JUMP`, `CHAIN_SOLANA_BLOCK_STATUS_UNAVAILABLE`, and
`CHAIN_SOLANA_MIN_CONTEXT_SLOT_NOT_REACHED`; the Starknet `CHAIN_STARKNET_BLOCK_NOT_FOUND`,
`CHAIN_STARKNET_TX_HASH_NOT_FOUND`, and `CHAIN_STARKNET_UNEXPECTED_ERROR`; and the NEAR
block/chunk garbage-collection codes (`CHAIN_NEAR_UNKNOWN_BLOCK`, `CHAIN_NEAR_UNKNOWN_CHUNK`,
`CHAIN_NEAR_NOT_SYNCED_YET`).

---

## Layer D — User errors (`USER_*`, 4000–4999)

Category: **External**. Malformed or invalid client requests — classified by nature of
the error, regardless of whether Lava catches it pre-forwarding or the node returns it.
All non-retryable; all charge **normal CU** (responses aren't cached).

| Code | Name | Description | Retryable | Standard code |
| --- | --- | --- | --- | --- |
| 4001 | `USER_PARSE_ERROR` | Invalid JSON in request | No | JSON-RPC -32700 |
| 4002 | `USER_INVALID_REQUEST` | Not a valid JSON-RPC/REST/gRPC object | No | JSON-RPC -32600 |
| 4003 | `USER_INVALID_PARAMS` | Invalid method parameters | No | JSON-RPC -32602 |
| 4004 | `USER_INVALID_BLOCK_FORMAT` | Invalid block number format (e.g. non-hex) | No | message match |
| 4005 | `USER_INVALID_ADDRESS` | Invalid address format | No | message match |
| 4006 | `USER_REQUEST_TOO_LARGE` | Request body exceeds size limit | No | HTTP 413 |
| 4007 | `USER_INVALID_HEX` | Invalid hex encoding | No | message match |

---

## Chain families

Tier-2 classification keys off a chain's **family**. An unregistered chain id resolves
to the `Unknown` sentinel — Tier-2 lookups intentionally miss and classification falls
through to the transport-scoped Tier-1 matchers.

| Family | Example chain ids |
| --- | --- |
| `EVM` | ETH1, SEP1, HOL1, ARBITRUM, POLYGON, BASE, OPTM, AVAX, BSC, BLAST, FTM250, SONIC, … |
| `Solana` | SOLANA, SOLANAT, KOII, KOIIT |
| `Bitcoin` | BTC, BTCT, LTC, LTCT, DOGE, DOGET, BCH, BCHT |
| `CosmosSDK` | COSMOSHUB, LAVA, LAV1, AXELAR, EVMOS, OSMOSIS, JUN1, CELESTIA, … |
| `Starknet` | STRK, STRKS |
| `Aptos` | APT1 |
| `Sui` | SUIT |
| `NEAR` | NEAR, NEART |
| `XRP` | XRP, XRPT |
| `Stellar` | XLM, XLMT |
| `TON` | TON, TONT |
| `Tron` | TRX, TRXT |
| `Cardano` | CARDANO, CARDANOT |
| `Unknown` | sentinel — Tier-2 misses, falls through to Tier-1 |
