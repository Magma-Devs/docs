---
title: "Quick start"
description: "Get Smart Router running in three commands — clone the repo, start it with Docker Compose, and send your first JSON-RPC relay."
---

<p class="eyebrow">GETTING STARTED</p>

# Quick start

Smart Router is a reliability and security layer that sits between your app and the chain. It monitors your RPC upstreams and optimizes routing in real time — so teams can easily manage complex RPC setups using a standard solution, rather than building one in-house. Any chain, any provider.

## Three steps to a running router

### 1. Get the code

```bash
git clone https://github.com/Magma-Devs/smart-router.git
cd smart-router
```

### 2. Run

```bash
docker compose -f docker/docker-compose.yml up --build
```

This builds the image and starts the Ethereum example on port 3360. Pick another chain with `SR_CONFIG` (see [Examples](reference/chains/examples/index.md)), or run a native binary / the wizard instead — see [Run Smart Router](deployment/index.md).

### 3. Make a request

```bash
curl -X POST http://127.0.0.1:3360 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

That request now flows through the full pipeline — upstream selection, retry, hedging, and caching — instead of hitting a single RPC directly.

??? tip "In a hurry? Use the wizard"
    `make wizard` launches an interactive TUI that picks chains, collects upstreams,
    health-checks everything, writes the config, and brings up the stack in one pass.
    See [Config wizard](deployment/wizard.md).

## Where to next

<div class="grid cards card-grid-compact" markdown>

-   **Connect your app**

    Point viem, ethers, web3.py, or cosmjs at your endpoint.

    [Connect your app →](api/url.md)

-   **Configure routing & failover**

    Tune upstream selection, retry, hedging, timeouts, and consensus.

    [Configuration →](configuration/index.md)

-   **Supported chains**

    Ethereum, Lava, and 75+ chains, each configured by a chain spec.

    [Browse chains →](reference/chains/index.md)

-   **Why Smart Router?**

    The problems it solves and how it compares to a plain proxy.

    [Read the overview →](why.md)

</div>
