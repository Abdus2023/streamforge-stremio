# Deployment & Operations

[⇧ Architecture index](../architecture.md) · [⇆ Document map](./README.md)

> **Scope.** Local development, containers, environment/secrets handling, networking, health checks, graceful shutdown, and resource limits from an *operations* point of view. Does not repeat the runtime architecture itself (see `06-runtime.md`) — only how it is deployed and operated.

> **Primary dependencies:** `06-runtime.md`, `09-control-plane.md`

> **Status.** Unless a section explicitly states otherwise with a concrete repository reference (file path, commit, or CI run), everything below is **DESIGNED** or **PROPOSED** architecture, not implemented code. This document was migrated from the original `docs/architecture.md` monolith; section order is preserved from that document, numbering has been dropped in favor of descriptive headings, and some very long single sections in the monolith may appear here still bearing internal editorial framing (e.g. first-person design narration) that predates the doc-split.

## Sections in this document

- [Deployment](#deployment)
- [Container](#container)
- [Container health](#container-health)
- [Compose](#compose)
- [First operational dashboard](#first-operational-dashboard)

---

## Deployment

A simple container:

```dockerfile
FROM node:22-alpine

WORKDIR /app

COPY package*.json ./

RUN npm ci --omit=dev

COPY dist ./dist

ENV NODE_ENV=production
ENV PORT=7000

EXPOSE 7000

CMD ["node", "dist/index.js"]
```

Deployment:

```text
                    Internet
                        │
                        ▼
                  HTTPS / TLS
                        │
                 reverse proxy
                        │
                        ▼
               Stremio Addon
                  port 7000
                        │
           ┌────────────┼────────────┐
           ▼            ▼            ▼
         cache        adapters     health
```

For a public addon, HTTPS is strongly preferable.

## Container

Keep it minimal.

```dockerfile
FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./

RUN npm ci

COPY tsconfig.json ./
COPY src ./src

RUN npm run build


FROM node:22-alpine

WORKDIR /app

ENV NODE_ENV=production

COPY package*.json ./

RUN npm ci --omit=dev

COPY --from=build /app/dist ./dist

EXPOSE 7000

USER node

CMD ["node", "dist/index.js"]
```

The `USER node` requirement is important.

There is no reason for the addon process to run as root.

## Container health

Add:

```dockerfile
HEALTHCHECK \
  --interval=30s \
  --timeout=3s \
  --retries=3 \
  CMD wget \
    -q \
    -O /dev/null \
    http://127.0.0.1:7001/health/live \
    || exit 1
```

This assumes the health server uses a separate port.

That separation is useful:

```text
7000 → addon protocol
7001 → operational health
```

## Compose

```yaml
services:
  addon:
    build: .
    ports:
      - "7000:7000"
      - "7001:7001"
    environment:
      PORT: "7000"
      HEALTH_PORT: "7001"
```

Do not expose internal provider credentials through Compose files
committed to the repository.

Use environment injection/secrets at deployment time.

## First operational dashboard

Even without Prometheus, expose internal counters:

```text
requests
successful resolutions
empty resolutions
partial resolutions
failed resolutions

adapter calls
timeouts
network errors
circuit opens

cache hits
cache misses
stale hits

candidates observed
candidates rejected
candidates emitted
```

Later this can become Prometheus/OpenTelemetry.

Don't introduce that complexity before the semantics are stable.
