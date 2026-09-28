# Building a Stremio Addon as a Popcorn Time Alternative

> This document captures the design rationale and implementation plan for
> StreamForge as a **Stremio-compatible multi-source resolver** — a
> legitimate alternative to Popcorn Time's UX that does not embed a
> torrent client or distribute copyrighted streams.

The clean way to build this is as a **Stremio-compatible multi-source
resolver**, rather than embedding a torrent client or distributing
copyrighted streams.

The resulting system can provide the **Popcorn Time-style UX** — one
title → many sources → normalized quality/language/subtitle metadata →
ranked stream list — while restricting adapters to sources you are
authorized to access, public-domain media, or services/APIs that
explicitly permit this use.

Stremio's addon protocol is a good fit: an addon exposes `/manifest.json`
plus resources such as `catalog`, `meta`, `stream`, and `subtitles`; the
`stream` endpoint returns multiple `Stream` objects for a title.

## 1. Target architecture

```text
                         ┌─────────────────────┐
                         │       Stremio        │
                         └──────────┬──────────┘
                                    │
                             /manifest.json
                                    │
                ┌───────────────────▼───────────────────┐
                │           Popcorn-style Addon          │
                │                                         │
                │  catalog / meta / stream / subtitles   │
                └───────────────────┬───────────────────┘
                                    │
                           Resolve(title ID)
                                    │
                     ┌──────────────▼──────────────┐
                     │       Source Orchestrator    │
                     │                              │
                     │ normalize → query → merge    │
                     │ score → dedupe → emit        │
                     └──────────────┬──────────────┘
                                    │
          ┌─────────────────────────┼────────────────────────┐
          │                         │                        │
          ▼                         ▼                        ▼
 ┌────────────────┐       ┌────────────────┐       ┌────────────────┐
 │ Public-domain   │       │ Licensed API   │       │ User-provided  │
 │ adapter         │       │ adapter        │       │ source adapter │
 └───────┬────────┘       └───────┬────────┘       └───────┬────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                   │
                          normalized sources
                                   │
                         ┌────────▼─────────┐
                         │  Source Registry  │
                         └────────┬─────────┘
                                   │
                         ┌────────▼─────────┐
                         │ Ranking / Policy  │
                         └────────┬─────────┘
                                   │
                    ┌─────────────▼─────────────┐
                    │  Stremio Stream Objects    │
                    └───────────────────────────┘
```

The important architectural distinction is:

```text
Source discovery
      ≠ Source authorization
      ≠ Stream resolution
      ≠ Stream ranking
      ≠ Playback
```

The addon should **not become a downloader/proxy** unless there is a
legitimate reason to proxy an authorized source.

## 2. Recommended repository

```text
stremio-source-aggregator/
│
├── package.json
├── tsconfig.json
├── Dockerfile
├── compose.yaml
├── README.md
├── LICENSE
│
├── src/
│   ├── index.ts
│   │
│   ├── addon/
│   │   ├── manifest.ts
│   │   ├── catalog.ts
│   │   ├── meta.ts
│   │   ├── streams.ts
│   │   └── subtitles.ts
│   │
│   ├── domain/
│   │   ├── MediaId.ts
│   │   ├── MediaTitle.ts
│   │   ├── Source.ts
│   │   ├── Stream.ts
│   │   ├── Subtitle.ts
│   │   └── Resolution.ts
│   │
│   ├── orchestrator/
│   │   ├── resolver.ts
│   │   ├── normalize.ts
│   │   ├── dedupe.ts
│   │   ├── rank.ts
│   │   ├── timeout.ts
│   │   └── circuit-breaker.ts
│   │
│   ├── adapters/
│   │   ├── SourceAdapter.ts
│   │   ├── public-domain/
│   │   │   └── adapter.ts
│   │   ├── licensed-api/
│   │   │   └── adapter.ts
│   │   └── user-source/
│   │       └── adapter.ts
│   │
│   ├── metadata/
│   │   ├── imdb.ts
│   │   ├── tmdb.ts
│   │   └── cache.ts
│   │
│   ├── config/
│   │   └── config.ts
│   │
│   └── observability/
│       ├── logger.ts
│       ├── metrics.ts
│       └── health.ts
│
├── test/
│   ├── manifest.test.ts
│   ├── normalization.test.ts
│   ├── dedupe.test.ts
│   ├── ranking.test.ts
│   ├── resolver.test.ts
│   └── protocol.test.ts
│
└── docs/
    ├── architecture.md
    ├── source-adapter-contract.md
    ├── ranking.md
    └── deployment.md
```

> **Note:** this repository is `streamforge-stremio` (engine name
> **StreamForge**); `stremio-source-aggregator` above is the generic
> layout this design was originally sketched against. The directory
> shape maps directly onto StreamForge's own `src/` layout described in
> the top-level README — `orchestrator/` corresponds to StreamForge's
> `resolver/` + `application/resolver.ts`, and `adapters/` corresponds
> to StreamForge's `adapters/`.

I would use **TypeScript + the official Stremio addon SDK** for the
first implementation. The SDK exposes `addonBuilder`, `serveHTTP`,
resource handlers, and the HTTP protocol machinery.

## 3. Core domain model

Don't let external source formats leak into the addon.

```ts
export type MediaType = "movie" | "series";

export interface MediaRef {
  type: MediaType;
  id: string;
  imdbId?: string;
  tmdbId?: string;
  season?: number;
  episode?: number;
}

export interface SourceCandidate {
  sourceId: string;

  media: MediaRef;

  url: string;

  quality?: {
    width?: number;
    height?: number;
    label?: string;
  };

  container?: string;
  codec?: string;

  language?: string[];
  subtitles?: string[];

  bitrate?: number;
  sizeBytes?: number;

  isLive?: boolean;

  metadata: {
    title?: string;
    releaseYear?: number;
  };

  capabilities: {
    directPlayback: boolean;
    authorized: boolean;
    stableUrl: boolean;
  };
}
```

The critical invariant is:

```text
SourceCandidate
      |
      +-- authorized === true
      |
      +-- directPlayback === true
      |
      +-- valid URL
      |
      +-- known media identity
      |
      └── eligible for Stremio
```

An adapter that cannot establish authorization should return:

```json
{
  "eligible": false,
  "reason": "authorization_unknown"
}
```

rather than silently turning an unknown source into a playable stream.

## 4. Adapter contract

This is the most important interface in the system.

```ts
export interface SourceAdapter {
  readonly id: string;
  readonly name: string;

  supports(media: MediaRef): boolean;

  resolve(
    media: MediaRef,
    ctx: ResolveContext
  ): Promise<SourceCandidate[]>;

  health?(): Promise<HealthResult>;
}
```

Context:

```ts
export interface ResolveContext {
  signal: AbortSignal;

  timeoutMs: number;

  locale?: string;
  preferredLanguages?: string[];
  userConfig?: Record<string, unknown>;
}
```

This lets you add sources without modifying the resolver.

```text
              SourceAdapter
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
    Adapter A   Adapter B   Adapter C
        │           │           │
        └───────────┼───────────┘
                     ▼
              SourceCandidate[]
```

## 5. Parallel aggregation

Never query sources sequentially.

Bad:

```text
A → wait → B → wait → C → wait
```

Instead:

```text
               ┌→ A
    request ───┼→ B
               ├→ C
               └→ D
```

Implementation:

```ts
export async function resolveSources(
  media: MediaRef,
  adapters: SourceAdapter[],
  ctx: ResolveContext
): Promise<SourceCandidate[]> {
  const applicable = adapters.filter(a => a.supports(media));

  const results = await Promise.allSettled(
    applicable.map(adapter => adapter.resolve(media, ctx))
  );

  const candidates: SourceCandidate[] = [];

  for (const result of results) {
    if (result.status === "fulfilled") {
      candidates.push(...result.value);
    }
  }

  return candidates;
}
```

One broken provider therefore does not destroy the whole request.

## 6. Timeout isolation

A particularly important property for a multi-source addon:

```text
global timeout = 4s

Source A ─────── 300ms ─── OK
Source B ─────── 900ms ─── OK
Source C ─────── 4s ────── TIMEOUT
Source D ─────── 500ms ─── OK
```

Source C should not prevent A/B/D from appearing.

```ts
export async function withTimeout<T>(
  promise: Promise<T>,
  ms: number
): Promise<T> {
  return Promise.race([
    promise,

    new Promise<T>((_, reject) =>
      setTimeout(() => reject(new Error("source_timeout")), ms)
    )
  ]);
}
```

In production, use `AbortController` so the underlying HTTP request is
actually cancelled.

## 7. Deduplication

Multiple providers may return the same underlying stream.

Normalize URLs before comparing them:

```ts
function canonicalizeUrl(input: string): string {
  const url = new URL(input);

  url.hash = "";

  return url.toString();
}
```

Then:

```ts
const key = [
  candidate.media.type,
  candidate.media.imdbId,
  candidate.media.season,
  candidate.media.episode,
  canonicalizeUrl(candidate.url)
].join("|");
```

Use a `Map`:

```ts
const unique = new Map<string, SourceCandidate>();

for (const candidate of candidates) {
  const key = sourceKey(candidate);

  if (!unique.has(key)) {
    unique.set(key, candidate);
  }
}

return [...unique.values()];
```

Don't deduplicate merely by title.

This is dangerous:

```text
"Movie Name"
```

because remakes, regional releases and similarly named works exist.

Prefer:

```text
IMDb ID + season + episode + canonical stream identity
```

## 8. Ranking engine

Stremio expects streams ordered from highest to lowest quality.

I would keep ranking deterministic:

```ts
interface RankInput {
  authorized: boolean;
  resolution: number;
  bitrate: number;
  languageMatch: number;
  directPlayback: boolean;
  sourceReliability: number;
}
```

Example:

```ts
function score(x: RankInput): number {
  return (
    x.authorized * 1_000_000 +
    x.directPlayback * 100_000 +
    x.languageMatch * 10_000 +
    x.resolution * 100 +
    x.bitrate +
    x.sourceReliability
  );
}
```

The authorization term dominates deliberately.

You don't want:

```text
4K unauthorized source > 1080p authorized source
```

Your policy engine should eliminate the first source before ranking.

## 9. Stremio manifest

A minimal production-oriented manifest:

```ts
export const manifest = {
  id: "org.example.multisource",
  version: "1.0.0",

  name: "MultiSource",
  description:
    "Multi-source media resolver for authorized and public-domain sources.",

  resources: ["catalog", "meta", "stream", "subtitles"],

  types: ["movie", "series"],

  idPrefixes: ["tt"],

  catalogs: [
    {
      type: "movie",
      id: "multisource-movies",
      name: "MultiSource Movies",
      extra: [
        {
          name: "search",
          isRequired: false
        }
      ]
    }
  ],

  behaviorHints: {
    configurable: true,
    p2p: false
  },

  config: [
    {
      key: "language",
      type: "select",
      title: "Preferred language",
      options: ["en", "fr", "ar"],
      default: "en"
    }
  ]
};
```

The `resources`, `types`, `idPrefixes`, catalogs and configuration fields
follow the Stremio manifest model.

## 10. Stremio addon server

```ts
import { addonBuilder, serveHTTP } from "stremio-addon-sdk";

import { manifest } from "./addon/manifest.js";
import { resolve } from "./orchestrator/resolver.js";

const builder = new addonBuilder(manifest);

builder.defineStreamHandler(async args => {
  const media = parseStremioId(args);

  const streams = await resolve(media);

  return {
    streams,
    cacheMaxAge: 300,
    staleRevalidate: 60,
    staleError: 600
  };
});

serveHTTP(builder.getInterface(), {
  port: Number(process.env.PORT ?? 7000)
});
```

Stremio supports cache-related properties such as `cacheMaxAge`,
`staleRevalidate`, and `staleError` on stream responses.

## 11. Convert internal sources to Stremio streams

Keep this conversion at the boundary.

```ts
function toStremioStream(candidate: SourceCandidate) {
  const quality = candidate.quality?.label ?? "Unknown";

  const languages = candidate.language?.join(", ") ?? "";

  return {
    name: `${candidate.sourceId} • ${quality}`,

    description: [languages, candidate.codec, candidate.container]
      .filter(Boolean)
      .join(" • "),

    url: candidate.url,

    behaviorHints: {
      bingeGroup: `${candidate.sourceId}-${quality}`
    }
  };
}
```

So the architecture becomes:

```text
External API
     ↓
Adapter-specific JSON
     ↓
SourceCandidate
     ↓
validation
     ↓
dedupe
     ↓
ranking
     ↓
Stremio Stream
```

## 12. Series IDs

This is an easy place to introduce bugs.

A series request may look conceptually like:

```text
tt1234567:2:7
     │    │ │
     │    │ └─ episode
     │    └─── season
     └──────── series
```

Parser:

```ts
export function parseStremioId(args: { type: string; id: string }): MediaRef {
  const parts = args.id.split(":");

  if (args.type === "movie") {
    return {
      type: "movie",
      id: parts[0],
      imdbId: parts[0]
    };
  }

  if (args.type === "series") {
    return {
      type: "series",
      id: parts[0],
      imdbId: parts[0],
      season: Number(parts[1]),
      episode: Number(parts[2])
    };
  }

  throw new Error("unsupported_media_type");
}
```

## 13. Resolver pipeline

I would make the resolver explicit rather than one giant function.

```text
                MediaRef
                    │
                    ▼
              Identity check
                    │
                    ▼
             Adapter selection
                    │
                    ▼
            Parallel resolution
                    │
                    ▼
             Candidate validation
                    │
                    ▼
                 Dedup
                    │
                    ▼
               Policy filter
                    │
                    ▼
                 Ranking
                    │
                    ▼
              Stremio mapping
                    │
                    ▼
                streams[]
```

Implementation:

```ts
export async function resolve(media: MediaRef) {
  const adapters = registry.findApplicable(media);

  const candidates = await resolveSources(media, adapters, createContext());

  const valid = candidates.filter(validateCandidate);

  const unique = deduplicate(valid);

  const permitted = policyFilter(unique);

  const ranked = rank(permitted);

  return ranked.map(toStremioStream);
}
```

This separation makes testing dramatically easier.

## 14. Source reliability

Do not use permanent hardcoded rankings such as:

```text
Source A = 100
Source B = 80
Source C = 50
```

Instead collect operational evidence:

```text
Source
  │
  ├── success rate
  ├── timeout rate
  ├── response latency
  ├── malformed-response rate
  ├── availability
  └── recent failures
```

Then maintain a bounded rolling score.

```ts
interface SourceHealth {
  successes: number;
  failures: number;
  timeouts: number;
  latencyMs: number;
}
```

For example:

```ts
reliability = successes / max(1, successes + failures + timeouts);
```

This is not a statement that one provider is inherently "better"; it is
simply an operational measurement for the resolver.

## 15. Circuit breaker

Without one, an unavailable provider can consume resources on every
request.

```text
CLOSED
  │
  │ repeated failures
  ▼
OPEN
  │
  │ cooldown
  ▼
HALF_OPEN
  │
  ├── success → CLOSED
  │
  └── failure → OPEN
```

Example:

```ts
class CircuitBreaker {
  private failures = 0;
  private openedAt = 0;

  constructor(
    private threshold = 5,
    private cooldownMs = 30_000
  ) {}

  canRequest(): boolean {
    if (this.failures < this.threshold) {
      return true;
    }

    return Date.now() - this.openedAt > this.cooldownMs;
  }

  success() {
    this.failures = 0;
    this.openedAt = 0;
  }

  failure() {
    this.failures++;

    if (this.failures >= this.threshold) {
      this.openedAt = Date.now();
    }
  }
}
```

## 16. Metadata architecture

Don't make every source independently resolve titles.

Use a canonical identity layer:

```text
                User/Stremio ID
                       │
                       ▼
                Identity Resolver
                       │
           ┌───────────┴───────────┐
           ▼                       ▼
       IMDb ID                  TMDB ID
           │                       │
           └───────────┬───────────┘
                       ▼
                 Canonical Media
                       │
       ┌───────────────┼────────────────┐
       ▼               ▼                ▼
   Source A        Source B         Source C
```

For example:

```ts
interface CanonicalMedia {
  imdbId?: string;
  tmdbId?: string;

  title: string;
  year?: number;

  type: "movie" | "series";
}
```

The addon can therefore query adapters using stable IDs whenever
possible.

## 17. Cache layers

Use three different caches.

```text
L1: identity cache
    IMDb → canonical metadata

L2: source-result cache
    media + source → candidates

L3: health cache
    source → operational state
```

Don't cache everything for the same duration.

Example:

```text
Identity metadata      24h
Source resolution       5m
Source health           30s
Negative resolution     30s
```

The Stremio protocol itself supports HTTP caching semantics for addon
responses.

## 18. Failure semantics

This should be explicit.

```text
NO_SOURCE
SOURCE_TIMEOUT
SOURCE_UNAUTHORIZED
SOURCE_INVALID
SOURCE_RATE_LIMITED
MEDIA_NOT_FOUND
IDENTITY_AMBIGUOUS
ALL_SOURCES_FAILED
```

Don't collapse everything into:

```text
[]
```

internally.

Internally:

```ts
type ResolveResult =
  | {
      kind: "success";
      candidates: SourceCandidate[];
    }
  | {
      kind: "partial";
      candidates: SourceCandidate[];
      failures: SourceFailure[];
    }
  | {
      kind: "failure";
      failures: SourceFailure[];
    };
```

Only convert to the Stremio-compatible response at the final boundary.

## 19. Observability

For every resolution:

```text
request_id
media_id
media_type
source
start_time
duration_ms
result
candidate_count
failure_reason
```

Example:

```json
{
  "request_id": "01J...",
  "media": "tt1234567",
  "source": "public-domain",
  "duration_ms": 312,
  "result": "success",
  "candidate_count": 3
}
```

Never log:

```text
API passwords
API keys
authorization headers
user tokens
private source credentials
```

## 20. Configuration

Environment:

```text
PORT=7000

LOG_LEVEL=info

REQUEST_TIMEOUT_MS=3500

SOURCE_A_ENABLED=true
SOURCE_B_ENABLED=true

CACHE_TTL_SECONDS=300

PREFERRED_LANGUAGE=en
```

User-facing Stremio configuration can control:

```text
Preferred language
Preferred subtitle language
Maximum resolution
Minimum resolution
Source categories
External-service credentials
```

Credentials should never be embedded in the manifest.

Stremio's manifest supports configurable user data and configuration
fields.

## 21. Security boundary

Treat every source adapter as hostile input.

```text
                Internet
                    │
                    ▼
           ┌─────────────────┐
           │ Source Adapter   │
           └────────┬────────┘
                    │
              untrusted data
                    │
                    ▼
           ┌─────────────────┐
           │ Validator        │
           └────────┬────────┘
                    │
             normalized data
                    │
                    ▼
           ┌─────────────────┐
           │ Policy Engine    │
           └────────┬────────┘
                    │
                    ▼
              Stremio output
```

Validate:

- URL scheme
- hostname
- content type
- redirects
- maximum response size
- JSON structure
- timeout
- malformed metadata
- unexpected protocols

For a public deployment, also consider SSRF protection if adapters are
allowed to accept arbitrary user-configured URLs.

## 22. What I would explicitly NOT build

To keep the project legitimate and technically maintainable, don't make
the core architecture depend on:

```text
✗ scraping unauthorized streaming sites
✗ circumventing paywalls
✗ bypassing DRM
✗ credential theft
✗ hidden APIs
✗ torrent-index scraping for copyrighted releases
✗ automatic downloading of copyrighted movies
✗ proxying arbitrary third-party URLs without authorization
```

Instead:

```text
✓ public-domain repositories
✓ licensed content APIs
✓ user-owned media servers
✓ authorized streaming services
✓ explicitly permitted source APIs
✓ local files / NAS
✓ legitimate subtitle APIs
```

The Stremio protocol itself is neutral: it is designed to aggregate
multimedia sources, and an addon can return multiple streams for a
title.

## 23. Local media source

A particularly useful adapter is a user's own library:

```text
Stremio
   │
   ▼
Addon
   │
   ▼
Local Media Adapter
   │
   ├── Jellyfin
   ├── Plex
   ├── Emby
   ├── WebDAV
   └── user-owned HTTP library
```

This gives the Popcorn-Time-like aggregation experience without
requiring the addon to host copyrighted material.

The adapter contract remains identical:

```ts
class UserLibraryAdapter implements SourceAdapter {
  readonly id = "user-library";
  readonly name = "User Library";

  supports(media: MediaRef) {
    return true;
  }

  async resolve(media: MediaRef, ctx: ResolveContext) {
    // query user's authorized media server
    // return SourceCandidate[]
  }
}
```

## 24. Subtitles

Treat subtitles as another independent aggregation problem:

```text
                 MediaRef
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
       Source A   Source B    Source C
         │           │           │
         └───────────┼───────────┘
                     ▼
              SubtitleCandidate
                     │
                  dedupe
                     │
                language rank
                     │
                     ▼
               Stremio subtitle
```

Don't bind subtitles to a particular stream unless necessary.

## 25. Testing strategy

This project benefits enormously from contract testing.

### Manifest

```text
manifest.json
    │
    ├── valid ID
    ├── valid version
    ├── resources
    ├── types
    └── catalogs
```

### Resolver

```text
given:
  A → 1080p
  B → 720p
  C → timeout

expect:
  A
  B

not:
  C
```

### Dedup

```text
A → URL X
B → URL X
C → URL Y

expect:
  X
  Y
```

### Identity

```text
movie: tt123

series: tt123:2:7
```

### Failure

```text
all adapters fail
       ↓
valid Stremio response
       ↓
streams: []
```

### Partial success

```text
A → success
B → timeout
C → malformed

expect: A
```

## 26. Property tests

There are useful invariants here.

```text
Invariant 1
Every emitted stream must have a valid URL.
```

```text
Invariant 2
No unauthorized candidate can reach the Stremio boundary.
```

```text
Invariant 3
Deduplication never produces duplicate canonical URLs.
```

```text
Invariant 4
A failing adapter cannot prevent successful adapters from producing results.
```

```text
Invariant 5
Ranking never changes eligibility.
```

That last one is important:

```text
eligibility
    ↓
  filter

ranking
    ↓
 ordering
```

not:

```text
ranking
    ↓
somehow decide legality
```

## 27. Deployment

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

## 28. Health endpoint

Separate addon health from source health.

```text
GET /health

{
  "status": "ok",
  "version": "1.0.0",
  "sources": {
    "public-domain": "healthy",
    "licensed-api": "degraded",
    "user-library": "disabled"
  }
}
```

The Stremio protocol doesn't require this endpoint; it is purely
operational.

## 29. The resulting system

The final behavior becomes:

```text
                    USER
                      │
                      ▼
                   Stremio
                      │
                      ▼
                Movie / Episode
                      │
                      ▼
               MultiSource Addon
                      │
                      ▼
               Identity Resolver
                      │
           ┌──────────┴──────────┐
           │                     │
        Movie                 Episode
           │                     │
           └──────────┬──────────┘
                      ▼
               Source Registry
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
    Source A       Source B       Source C
        │             │             │
        └─────────────┼─────────────┘
                      ▼
                 normalization
                      │
                   validation
                      │
                    dedupe
                      │
                 policy filter
                      │
                    ranking
                      │
                      ▼
               ┌──────────────┐
               │ Stream #1    │
               │ Stream #2    │
               │ Stream #3    │
               │ Stream #4    │
               └──────┬───────┘
                      │
                      ▼
                   Stremio
```

## Recommended implementation sequence

Given the preference for **freeze → formalize → implement → test →
release gate**, this should be built in these gates:

```text
G0  Scope + source legality contract
  ↓
G1  Stremio manifest
  ↓
G2  SourceAdapter interface
  ↓
G3  One known-good authorized/public-domain source
  ↓
G4  Resolver + timeout isolation
  ↓
G5  normalization + deduplication
  ↓
G6  deterministic ranking
  ↓
G7  metadata + series handling
  ↓
G8  subtitles
  ↓
G9  cache + circuit breaker
  ↓
G10 observability
  ↓
G11 contract/property tests
  ↓
G12 Docker deployment
  ↓
G13 second/third source adapters
  ↓
RELEASE
```

The key design decision is to make **the source adapter contract the
stable boundary**. Stremio is then just one presentation/protocol
layer:

```text
                 ┌──────────────────────┐
                 │    Source adapters    │
                 └──────────┬───────────┘
                             │
                     SourceCandidate
                             │
                  ┌──────────▼───────────┐
                  │  Aggregation Kernel   │
                  │                       │
                  │ identity              │
                  │ validation            │
                  │ deduplication         │
                  │ policy                │
                  │ ranking               │
                  │ caching               │
                  └──────────┬───────────┘
                             │
                      normalized result
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
           Stremio         REST/API       CLI/UI
           adapter
```

That gives you something more durable than a conventional "Stremio
scraper": **a general media-source aggregation kernel with a Stremio
protocol adapter on top**. Stremio's current protocol explicitly
supports this model of aggregating streams from different sources, and
its SDK provides the corresponding stream-handler abstraction.
