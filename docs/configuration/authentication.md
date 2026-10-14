---
title: "Authentication"
description: "Secure your Smart Router endpoints with authentication and access control."
---

# Authentication

This page shows how Smart Router authenticates to your upstream nodes, with API keys or
mTLS set per URL. Authenticating your own clients is a separate concern that the router
leaves to a reverse proxy or API gateway.

Smart Router has two separate authentication concerns, and they are easy to confuse:

1. **Upstream auth** - how the router authenticates to your *paid RPC nodes*
   (Alchemy, Infura, a private node). You configure it per URL with `auth-config`.
   **This page.**
2. **Client auth** - how *your clients* authenticate to the router. Smart Router has no
   built-in client auth or rate limiting in v1. Put a reverse proxy or API gateway in
   front for that. See [the note below](#authenticating-your-clients).

## Upstream authentication (`auth-config`)

Smart Router supports the three ways paid nodes usually expect a key: in a **header**,
in a **query parameter**, or **inside the URL**. You set it per `node-urls[]` entry.

### API key in a header

This is the common case (Alchemy `Authorization: Bearer`, custom `x-api-key`, and so on):

```yaml
node-urls:
  - url: "https://your-eth-provider.example.com"
    auth-config:
      auth-headers:
        x-api-key: "${RPC_KEY_ETH}"
```

`auth-headers` is a map, so you can send several headers. Every request to that URL
carries them.

### API key in a query parameter

```yaml
node-urls:
  - url: "https://site.com/eth"
    auth-config:
      auth-query: "apikey=${RPC_KEY}"
```

The router appends the query string to every request to that URL.

### API key in the URL path

Some nodes put the key directly in the path (`https://eth-mainnet.example.com/v2/<KEY>`).
That needs no `auth-config`: put the key in `url`. The key is now part of the URL, so
treat the whole config (and any rendered endpoint URL the dashboard prints) as a
bearer credential.

## Keeping secrets out of YAML

The router reads YAML **literally**. It does not expand `${ENV}` itself, so you render
the config before launch. The usual way (and what the [wizard](../deployment/wizard.md)
emits) is:

1. Write `${VAR}` placeholders in a `*.template.yml`.
2. Keep the real values in a gitignored `.env`.
3. Render the runnable `*.yml` with `envsubst` before launch.

```bash
# .env  (gitignored)
RPC_KEY_BASE=sk_live_abc123

# render template -> runnable config
set -a; . ./.env; envsubst < smartrouter.template.yml > smartrouter.yml
```

Generated configs go to `config/local/` (gitignored) by default, because the rendered
file contains live keys. Never commit the rendered `*.yml` or the `.env`.

## mTLS to an upstream

For nodes that require client certificates, put the PEM paths in `auth-config`:

```yaml
node-urls:
  - url: "grpcs://secure-node.example.com:443"
    auth-config:
      use-tls: true
      key-pem: "/etc/smartrouter/certs/client-key.pem"
      cert-pem: "/etc/smartrouter/certs/client-cert.pem"
      cacert-pem: "/etc/smartrouter/certs/ca.pem"
```

| Field | Description |
| --- | --- |
| `use-tls` | Force TLS for this URL. An `https://` / `grpcs://` scheme already does this, but this field makes it explicit. |
| `allow-insecure` | Accept self-signed / expired certs. **Dev/test only.** |
| `key-pem` | Client private key (PEM) for mTLS. |
| `cert-pem` | Client certificate (PEM) for mTLS. |
| `cacert-pem` | Trusted root CA (PEM) to verify the server. |

## Authenticating *your* clients

Smart Router does not authenticate inbound client requests, enforce API keys, or
rate-limit per client in v1. It leaves these to the edge on purpose. Put NGINX, a
cloud load balancer, or an API gateway in front to handle client auth, CORS, and rate
limiting. Behind a proxy, the router does honour `X-Forwarded-For` for IP-based logic.

For per-request *behaviour* overrides that clients can send (pinning a node, forcing
a cache refresh, requesting cross-validation), see [Directives](../api/directives.md).
