<p class="eyebrow">GETTING STARTED</p>

# Quickstart

Smart Router is a centralised RPC routing gateway. Point it at upstream RPC endpoints; it serves your traffic with QoS-based node selection, caching, hedging, retries, and cross-validation.

<div class="grid cards card-grid" markdown>

-   ![Quickstart](assets/illustrations/quickstart.svg){.card-illustration}

    **Run your first relay**

    Install the binary, point it at an RPC, send a curl request. Three commands.

    [Get started →](#three-steps-to-a-running-router)

-   ![Connect your app](assets/illustrations/api.svg){.card-illustration}

    **Integrate with your app**

    Endpoint URLs, header directives, viem / ethers / web3.py / cosmjs samples.

    [Connect your app →](api/url.md)

-   ![Configure](assets/illustrations/configure.svg){.card-illustration}

    **Configure routing & failover**

    Selection strategies, retry, hedging, consensus, timeouts.

    [Configuration →](configuration/index.md)

-   ![Supported chains](assets/illustrations/chains.svg){.card-illustration}

    **Supported chains**

    Ethereum, Lava, and 75+ chains across every major ecosystem out of the box.

    [Supported chains →](reference/chains/index.md)

</div>

!!! tip "Want it managed?"
    These docs cover the **self-hosted** Smart Router. If you'd rather not operate it yourself, [talk to us](https://magmadevs.com/contact).

## Three steps to a running router

!!! tip "In a hurry? Use the wizard"
    `make wizard` launches an interactive TUI that picks chains, collects upstreams,
    health-checks everything, writes the config, and brings up the stack in one pass.
    See [Config wizard](deployment/wizard.md).

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

## Where to next

- **Integrating with an app** → [Connect your app](api/url.md)
- **Operating the router** → [Configuration](configuration/index.md), [Deployment](deployment/index.md)
- **Evaluating** → [Why Smart Router?](why.md)
