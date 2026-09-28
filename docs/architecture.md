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

## 30. Turn the design into a real implementation

The next step is to stop treating this as an addon collection and
define a **conformance-oriented aggregation kernel**.

The core invariant should be:

```text
                    External Sources
                            │
                            ▼
                   ┌─────────────────┐
                   │ Source Adapters │
                   └────────┬────────┘
                            │
                            │ untrusted
                            ▼
                   ┌─────────────────┐
                   │ Normalization   │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ Validation      │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ Policy          │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ Deduplication   │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ Ranking         │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ Stremio Mapper  │
                   └────────┬────────┘
                            │
                            ▼
                        Stremio
```

The important property is that **Stremio must never receive raw
adapter output**.

## 31. Freeze the domain contract first

Create:

```text
src/domain/
├── media.ts
├── source.ts
├── candidate.ts
├── policy.ts
├── failure.ts
└── result.ts
```

### `media.ts`

```ts
export type MediaType = "movie" | "series";

export interface MediaRef {
  type: MediaType;

  /**
   * Canonical external identifier.
   * Normally IMDb in the first implementation.
   */
  id: string;

  imdbId?: string;
  tmdbId?: string;

  season?: number;
  episode?: number;
}
```

Add an invariant:

```ts
export function isEpisode(media: MediaRef): boolean {
  return (
    media.type === "series" &&
    Number.isInteger(media.season) &&
    Number.isInteger(media.episode) &&
    media.season! >= 1 &&
    media.episode! >= 1
  );
}
```

Do not silently convert:

```text
tt1234567
```

into an episode.

## 32. Candidate is not yet a stream

This distinction is fundamental.

```ts
export interface SourceCandidate {
  sourceId: string;

  media: MediaRef;

  location: {
    url: string;
  };

  mediaInfo: {
    container?: string;
    videoCodec?: string;
    audioCodec?: string;

    width?: number;
    height?: number;

    bitrate?: number;
    sizeBytes?: number;

    durationSeconds?: number;
  };

  language: {
    audio?: string[];
    subtitle?: string[];
  };

  provenance: {
    adapter: string;
    sourceRecordId?: string;
    observedAt: string;
  };

  capabilities: {
    directPlayback: boolean;
    seekable?: boolean;
    live?: boolean;
  };

  authorization: {
    status: "authorized" | "unknown" | "denied";
    basis?: string;
  };
}
```

This allows you to preserve uncertainty.

For example:

```text
authorization.status = unknown
```

must **not** become:

```text
authorized = true
```

## 33. Eligibility is a separate theorem

Define:

```ts
export interface EligibilityResult {
  eligible: boolean;

  reasons: string[];
}
```

Then:

```ts
export function evaluateEligibility(
  candidate: SourceCandidate
): EligibilityResult {
  const reasons: string[] = [];

  if (candidate.authorization.status !== "authorized") {
    reasons.push("source_not_authorized");
  }

  if (!candidate.capabilities.directPlayback) {
    reasons.push("direct_playback_unavailable");
  }

  if (!isHttpUrl(candidate.location.url)) {
    reasons.push("unsupported_url");
  }

  return {
    eligible: reasons.length === 0,
    reasons
  };
}
```

This gives you:

```text
OBSERVED
    ↓
NORMALIZED
    ↓
VALID
    ↓
ELIGIBLE
    ↓
RANKABLE
    ↓
EMITTABLE
```

rather than one boolean called `ready`.

## 34. URL validation

Do not accept arbitrary protocols.

```ts
const ALLOWED_PROTOCOLS = new Set(["http:", "https:"]);

export function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);

    return ALLOWED_PROTOCOLS.has(url.protocol);
  } catch {
    return false;
  }
}
```

For a user-owned local media adapter, you can explicitly support
additional protocols later.

Don't make the first implementation permissive and attempt to "secure
it later."

## 35. Adapter registry

```ts
export class SourceRegistry {
  private readonly adapters = new Map<string, SourceAdapter>();

  register(adapter: SourceAdapter): void {
    if (this.adapters.has(adapter.id)) {
      throw new Error(`duplicate_adapter:${adapter.id}`);
    }

    this.adapters.set(adapter.id, adapter);
  }

  all(): SourceAdapter[] {
    return [...this.adapters.values()];
  }

  applicable(media: MediaRef): SourceAdapter[] {
    return this.all().filter(adapter => adapter.supports(media));
  }
}
```

This gives you deterministic registration.

Example:

```ts
const registry = new SourceRegistry();

registry.register(new PublicDomainAdapter());

registry.register(new UserLibraryAdapter());

registry.register(new LicensedApiAdapter());
```

## 36. Adapter execution should produce evidence

Instead of:

```ts
Promise<SourceCandidate[]>
```

I recommend:

```ts
export interface AdapterExecution {
  adapterId: string;

  startedAt: string;
  completedAt: string;

  durationMs: number;

  candidates: SourceCandidate[];

  status:
    | "success"
    | "empty"
    | "timeout"
    | "rate_limited"
    | "invalid"
    | "error";

  failure?: SourceFailure;
}
```

Why?

Because:

```text
[]
```

can mean several radically different things:

```text
NO_RESULTS
SOURCE_UNREACHABLE
SOURCE_TIMED_OUT
SOURCE_RETURNED_INVALID_DATA
SOURCE_NOT_CONFIGURED
SOURCE_HAS_NO_MATCH
```

Those are not equivalent.

## 37. Resolver v2

```ts
export async function resolveMedia(
  media: MediaRef,
  registry: SourceRegistry,
  ctx: ResolveContext
): Promise<ResolutionResult> {
  const adapters = registry.applicable(media);

  const executions = await Promise.all(
    adapters.map(adapter => executeAdapter(adapter, media, ctx))
  );

  const allCandidates = executions.flatMap(execution => execution.candidates);

  const normalized = allCandidates.map(normalizeCandidate).filter(Boolean);

  const validated = normalized.filter(candidate =>
    validateCandidate(candidate!)
  );

  const eligible = validated.filter(
    candidate => evaluateEligibility(candidate!).eligible
  );

  const unique = deduplicate(eligible);

  const ranked = rank(unique);

  return {
    media,
    executions,
    candidates: ranked
  };
}
```

Now you can expose operational evidence separately from the Stremio
response.

## 38. Don't let ranking become business logic

A dangerous design is:

```text
source score
    ↓
if score > X
    ↓
allow source
```

Instead:

```text
                 Candidate
                     │
              ┌──────┴──────┐
              ▼             ▼
         Eligibility      Metadata
              │             │
              ▼             ▼
            FILTER       RANKING
              │             │
              └──────┬──────┘
                     ▼
                   OUTPUT
```

Eligibility answers:

Can this candidate be emitted?

Ranking answers:

In what order should already-eligible candidates appear?

This prevents ranking from becoming a hidden authorization mechanism.

## 39. Deterministic ranking

Define a tuple rather than a mysterious score.

```ts
interface RankingTuple {
  directPlayback: number;
  languageMatch: number;
  resolution: number;
  bitrate: number;
  reliability: number;
  sourceId: string;
}
```

Then compare lexicographically:

```ts
function compare(a: RankingTuple, b: RankingTuple): number {
  return (
    b.directPlayback - a.directPlayback ||
    b.languageMatch - a.languageMatch ||
    b.resolution - a.resolution ||
    b.bitrate - a.bitrate ||
    b.reliability - a.reliability ||
    a.sourceId.localeCompare(b.sourceId)
  );
}
```

The final `sourceId` tie-breaker is important.

Otherwise two equivalent streams can randomly change order between
executions.

## 40. Resolution normalization

Don't compare:

```text
"HD"
"1080p"
"Full HD"
"1920x1080"
```

as strings.

Normalize them:

```ts
export interface Resolution {
  width: number;
  height: number;
}

export function classifyResolution(resolution?: Resolution): string {
  if (!resolution) {
    return "unknown";
  }

  const pixels = resolution.width * resolution.height;

  if (pixels >= 3840 * 2160) {
    return "2160p";
  }

  if (pixels >= 1920 * 1080) {
    return "1080p";
  }

  if (pixels >= 1280 * 720) {
    return "720p";
  }

  if (pixels >= 854 * 480) {
    return "480p";
  }

  return "sd";
}
```

But preserve the raw observed dimensions as well.

```text
normalized meaning
        +
original evidence
```

is better than replacing the original data.

## 41. Source-specific normalization

Suppose Adapter A says:

```json
{
  "quality": "1080p"
}
```

Adapter B:

```json
{
  "width": 1920,
  "height": 1080
}
```

Adapter C:

```json
{
  "resolution": "Full HD"
}
```

All become:

```json
{
  "width": 1920,
  "height": 1080
}
```

But retain:

```json
{
  "raw": {
    "quality": "1080p"
  }
}
```

only inside adapter-local diagnostics if needed.

The domain layer should not become a dumping ground for
provider-specific fields.

## 42. Source adapters become tiny

This is one of the major architectural wins.

An adapter should mostly do:

```text
provider request
       ↓
provider response
       ↓
provider parser
       ↓
SourceCandidate
```

It should **not** do:

```text
provider request → dedupe → ranking → cache → global policy →
Stremio formatting → logging → retry policy
```

Those belong to the kernel.

## 43. Example adapter skeleton

```ts
export class PublicDomainAdapter implements SourceAdapter {
  readonly id = "public-domain";
  readonly name = "Public Domain";

  supports(media: MediaRef): boolean {
    return media.type === "movie" || media.type === "series";
  }

  async resolve(
    media: MediaRef,
    ctx: ResolveContext
  ): Promise<SourceCandidate[]> {
    const response = await fetchSource(media, ctx);

    return response.items.map(item => normalizeProviderItem(item, media));
  }
}
```

The adapter never constructs a Stremio `Stream`.

## 44. Stremio should be an output adapter

This is a useful abstraction:

```text
                   Aggregation Kernel
                           │
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
           Stremio       JSON API       CLI
           Adapter
```

The Stremio-specific code becomes tiny:

```ts
export function toStremio(candidates: SourceCandidate[]) {
  return candidates.map(candidate => ({
    name: buildName(candidate),

    description: buildDescription(candidate),

    url: candidate.location.url,

    behaviorHints: buildHints(candidate)
  }));
}
```

This makes the underlying system reusable.

## 45. Stremio response boundary

Only here should the external protocol shape appear.

```ts
builder.defineStreamHandler(async args => {
  const media = parseStremioMedia(args);

  const result = await resolveMedia(media, registry, createContext());

  return {
    streams: result.candidates.map(toStremioStream)
  };
});
```

Everything below this layer remains Stremio-independent.

## 46. Add a policy engine

This is where deployment-specific behavior belongs.

```ts
export interface SourcePolicy {
  allow(candidate: SourceCandidate): PolicyDecision;
}
```

```ts
export interface PolicyDecision {
  allowed: boolean;
  reasons: string[];
}
```

Example:

```ts
class DefaultPolicy implements SourcePolicy {
  allow(candidate: SourceCandidate): PolicyDecision {
    const reasons: string[] = [];

    if (candidate.authorization.status !== "authorized") {
      reasons.push("authorization_not_verified");
    }

    if (!candidate.capabilities.directPlayback) {
      reasons.push("not_direct_playback");
    }

    return {
      allowed: reasons.length === 0,

      reasons
    };
  }
}
```

Now a self-hosted installation can have:

```text
StrictPolicy
UserLibraryPolicy
PublicDomainPolicy
EnterprisePolicy
```

without changing the resolver.

## 47. Configuration must not alter the domain contract

For example:

```text
MAX_RESOLUTION=1080p
```

should mean:

```text
eligible candidates
        ↓
configuration filter
        ↓
ranking
```

not:

```text
adapter itself behaves differently
```

This makes configuration behavior testable.

## 48. Multi-source aggregation becomes compositional

Once the kernel works:

```text
                     ┌──────────────┐
                      │ Resolver     │
                      └──────┬───────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
      Public Domain     User Library     Licensed API
           │                 │                 │
           └─────────────────┼─────────────────┘
                             │
                        Candidates
                             │
                     Normalize/Validate
                             │
                        Policy Filter
                             │
                          Dedup
                             │
                          Rank
                             │
                         Stremio
```

Adding a fourth source should require:

```text
new adapter + adapter tests + registration
```

and **zero modifications to the core resolver**.

That is the extensibility test.

## 49. Conformance tests

Now we can make the architecture enforceable.

### Adapter contract

Every adapter must satisfy:

```ts
describe("SourceAdapter contract", () => {
  it("has a stable identifier");

  it("returns candidates matching requested media");

  it("does not emit malformed URLs");

  it("does not throw on empty results");

  it("respects AbortSignal");

  it("does not mutate the MediaRef");
});
```

### Resolver contract

```ts
describe("resolver", () => {
  it("isolates source failures");

  it("deduplicates candidates");

  it("never emits unauthorized candidates");

  it("produces deterministic ordering");

  it("preserves partial success");
});
```

## 50. Golden test

Create:

```text
test/fixtures/
└── resolution-case-001.json
```

```json
{
  "media": {
    "type": "movie",
    "id": "tt0000000"
  },

  "sources": [
    {
      "source": "a",
      "resolution": [1920, 1080],
      "authorized": true
    },
    {
      "source": "b",
      "resolution": [1280, 720],
      "authorized": true
    },
    {
      "source": "c",
      "resolution": [3840, 2160],
      "authorized": false
    }
  ],

  "expected": ["a", "b"]
}
```

This gives you a regression oracle.

The 4K source should not suddenly appear because somebody changed the
ranking implementation.

## 51. Failure matrix

| Failure | Other sources | Result |
| --- | --- | --- |
| One timeout | Continue | Partial |
| One HTTP 500 | Continue | Partial |
| One malformed response | Continue | Partial |
| One unauthorized candidate | Continue | Filter |
| All sources empty | N/A | Empty |
| All sources timeout | N/A | Failure |
| Identity invalid | N/A | Reject |
| Duplicate streams | Continue | Deduplicate |
| Invalid URL | Continue | Reject |
| Unsupported protocol | Continue | Reject |

This matrix should become automated tests.

## 52. Security test matrix

```text
SSRF
  ├── localhost
  ├── 127.0.0.1
  ├── private IPv4
  ├── IPv6 loopback
  ├── IPv6 private ranges
  ├── DNS rebinding
  └── redirect-to-private-address

URL parser
  ├── malformed URL
  ├── unsupported scheme
  ├── credentials embedded in URL
  └── oversized URL

HTTP
  ├── timeout
  ├── redirect chain
  ├── huge response
  └── invalid content-type
```

Especially important if you eventually allow users to configure
arbitrary source endpoints.

## 53. Rate limiting

A public addon should have two independent limits:

```text
                    Request
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
       per-IP limiter       source limiter
              │                   │
              ▼                   ▼
         addon abuse          provider abuse
```

Do not solve provider rate limits by simply making your entire addon
slower.

Use:

```text
concurrency limit + per-source rate limit + cache + circuit breaker
```

## 54. Concurrency control

If you eventually have 30 adapters, this:

```ts
await Promise.all(adapters.map(...));
```

can become excessive.

Use a bounded scheduler:

```text
30 adapters
    │
    ▼
┌──────────────┐
│ concurrency  │
│     = 6      │
└──────┬───────┘
       │
       ├── A
       ├── B
       ├── C
       ├── D
       ├── E
       └── F
```

Then:

```text
A completes → G starts
C completes → H starts
```

This matters particularly for low-resource deployments.

## 55. Latency budget

Define the budget before optimizing.

For example:

```text
total = 4 seconds

identity       500 ms
source queries 3000 ms
normalization   100 ms
ranking          50 ms
serialization    50 ms
buffer          300 ms
```

The exact numbers should be measured rather than assumed.

The important thing is that the budget exists.

## 56. Fast path

A mature implementation should eventually have:

```text
Request
   │
   ▼
cache lookup
   │
   ├── fresh → return
   │
   └── miss
        │
        ▼
     resolver
```

And potentially:

```text
stale cache
    │
    ├── return stale immediately
    │
    └── background refresh
```

But stale serving should be an explicit policy.

## 57. Don't hide stale data

Internally distinguish:

```text
FRESH
STALE_REVALIDATING
STALE
UNKNOWN
```

A stale result is not equivalent to a freshly observed result.

That matters for diagnostics.

## 58. Architecture after hardening

At this point the project becomes:

```text
┌───────────────────────────────────────────────────────┐
│                    Presentation                        │
│                                                         │
│                Stremio Protocol Adapter                │
└───────────────────────────┬───────────────────────────┘
                             │
┌───────────────────────────▼───────────────────────────┐
│                  Aggregation Kernel                     │
│                                                         │
│ Identity → Resolve → Normalize → Validate → Policy     │
│                         → Dedup → Rank → Cache          │
└───────────────────────────┬───────────────────────────┘
                             │
┌───────────────────────────▼───────────────────────────┐
│                    Adapter Layer                        │
│                                                         │
│ Public Domain │ User Library │ Licensed APIs │ ...      │
└───────────────────────────┬───────────────────────────┘
                             │
┌───────────────────────────▼───────────────────────────┐
│                     Evidence                            │
│                                                         │
│ request │ source result │ timing │ failure │ health    │
└─────────────────────────────────────────────────────────┘
```

This is the point where it stops being "a Stremio addon" in the narrow
sense.

It becomes a **media-source aggregation engine with a Stremio frontend
protocol**.

## 59. The next implementation gate

I would now freeze the following contract before writing the remaining
adapters:

```text
MEDIA IDENTITY
    ↓
SOURCE ADAPTER
    ↓
SOURCE CANDIDATE
    ↓
ADAPTER EXECUTION
    ↓
NORMALIZATION
    ↓
VALIDATION
    ↓
ELIGIBILITY
    ↓
POLICY
    ↓
DEDUPLICATION
    ↓
RANKING
    ↓
STREMIO STREAM
```

And explicitly prohibit these shortcuts:

```text
Candidate → Stream                 NO
Adapter → Stream                   NO
Ranking → Authorization            NO
Empty[] → "source unavailable"     NO
Unknown → Authorized               NO
Title string → Media identity      NO
Provider-specific fields → Core    NO
```

That gives us a stable foundation for the next layer: **a complete
runnable TypeScript repository, including `package.json`, `tsconfig`,
source registry, resolver, Stremio HTTP server, test suite, Docker
setup, health/metrics, and a first legitimate source adapter**.

## 60. Build the runnable repository

Now we can turn the frozen architecture into an actual implementation.

I would target:

```text
Node.js 22+
TypeScript
stremio-addon-sdk
Vitest
Fastify        ← operational endpoints only
Zod            ← external-input validation
Pino           ← structured logging
```

The important constraint remains:

```text
Stremio SDK
    ↓
thin protocol adapter

Aggregation kernel
    ↓
independent of Stremio
```

## 61. Repository v1

```text
stremio-source-aggregator/
│
├── package.json
├── package-lock.json
├── tsconfig.json
├── vitest.config.ts
├── Dockerfile
├── compose.yaml
├── .dockerignore
├── .gitignore
│
├── src/
│   ├── index.ts
│   │
│   ├── addon/
│   │   ├── manifest.ts
│   │   ├── parser.ts
│   │   ├── stream-handler.ts
│   │   └── metadata-handler.ts
│   │
│   ├── domain/
│   │   ├── media.ts
│   │   ├── candidate.ts
│   │   ├── failure.ts
│   │   └── result.ts
│   │
│   ├── adapters/
│   │   ├── interface.ts
│   │   ├── registry.ts
│   │   └── public-domain.ts
│   │
│   ├── resolver/
│   │   ├── resolver.ts
│   │   ├── execute.ts
│   │   ├── normalize.ts
│   │   ├── validate.ts
│   │   ├── policy.ts
│   │   ├── dedupe.ts
│   │   └── rank.ts
│   │
│   ├── runtime/
│   │   ├── context.ts
│   │   ├── timeout.ts
│   │   ├── breaker.ts
│   │   └── limiter.ts
│   │
│   ├── observability/
│   │   ├── logger.ts
│   │   ├── metrics.ts
│   │   └── health.ts
│   │
│   └── config/
│       └── config.ts
│
└── test/
    ├── media.test.ts
    ├── validation.test.ts
    ├── dedupe.test.ts
    ├── ranking.test.ts
    ├── resolver.test.ts
    └── addon.test.ts
```

## 62. `package.json`

```json
{
  "name": "stremio-source-aggregator",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "engines": {
    "node": ">=22"
  },
  "scripts": {
    "dev": "tsx watch src/index.ts",
    "build": "tsc -p tsconfig.json",
    "start": "node dist/index.js",
    "test": "vitest run",
    "test:watch": "vitest",
    "typecheck": "tsc --noEmit",
    "check": "npm run typecheck && npm test && npm run build"
  },
  "dependencies": {
    "stremio-addon-sdk": "^1.6.0",
    "zod": "^4.0.0",
    "pino": "^9.0.0"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "@types/stremio-addon-sdk": "^1.6.0",
    "tsx": "^4.0.0",
    "typescript": "^5.0.0",
    "vitest": "^3.0.0"
  }
}
```

Pin exact versions when you freeze the release rather than relying
indefinitely on ranges.

## 63. TypeScript configuration

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",

    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,

    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,

    "declaration": true,
    "sourceMap": true,

    "outDir": "dist",
    "rootDir": "src",

    "skipLibCheck": true
  },
  "include": ["src/**/*.ts"]
}
```

The useful part is not the particular flags. It is making the compiler
enforce the domain boundary.

## 64. Media identity

```ts
// src/domain/media.ts

export type MediaType = "movie" | "series";

export interface MediaRef {
  readonly type: MediaType;
  readonly id: string;

  readonly imdbId?: string;
  readonly tmdbId?: string;

  readonly season?: number;
  readonly episode?: number;
}

export function isEpisode(media: MediaRef): boolean {
  return (
    media.type === "series" &&
    Number.isInteger(media.season) &&
    Number.isInteger(media.episode) &&
    media.season! > 0 &&
    media.episode! > 0
  );
}
```

## 65. Candidate model

```ts
// src/domain/candidate.ts

import type { MediaRef } from "./media.js";

export interface SourceCandidate {
  readonly sourceId: string;

  readonly media: MediaRef;

  readonly location: {
    readonly url: string;
  };

  readonly mediaInfo: {
    readonly container?: string;
    readonly videoCodec?: string;
    readonly audioCodec?: string;

    readonly width?: number;
    readonly height?: number;

    readonly bitrate?: number;
    readonly sizeBytes?: number;
    readonly durationSeconds?: number;
  };

  readonly language: {
    readonly audio?: readonly string[];
    readonly subtitle?: readonly string[];
  };

  readonly provenance: {
    readonly adapter: string;
    readonly sourceRecordId?: string;
    readonly observedAt: string;
  };

  readonly capabilities: {
    readonly directPlayback: boolean;
    readonly seekable?: boolean;
    readonly live?: boolean;
  };

  readonly authorization: {
    readonly status: "authorized" | "unknown" | "denied";

    readonly basis?: string;
  };
}
```

Notice the deliberate use of `readonly`.

The resolver should consume candidates, not mutate them.

## 66. Adapter contract

```ts
// src/adapters/interface.ts

import type { MediaRef } from "../domain/media.js";

import type { SourceCandidate } from "../domain/candidate.js";

export interface ResolveContext {
  readonly signal: AbortSignal;

  readonly timeoutMs: number;

  readonly preferredLanguages: readonly string[];
}

export interface SourceAdapter {
  readonly id: string;
  readonly name: string;

  supports(media: MediaRef): boolean;

  resolve(media: MediaRef, ctx: ResolveContext): Promise<SourceCandidate[]>;
}
```

This interface is the principal extension point.

## 67. Registry

```ts
// src/adapters/registry.ts

import type { SourceAdapter } from "./interface.js";

import type { MediaRef } from "../domain/media.js";

export class SourceRegistry {
  private readonly map = new Map<string, SourceAdapter>();

  register(adapter: SourceAdapter): void {
    if (this.map.has(adapter.id)) {
      throw new Error(`duplicate_adapter:${adapter.id}`);
    }

    this.map.set(adapter.id, adapter);
  }

  all(): readonly SourceAdapter[] {
    return [...this.map.values()];
  }

  applicable(media: MediaRef): readonly SourceAdapter[] {
    return this.all().filter(adapter => adapter.supports(media));
  }
}
```

## 68. Adapter execution

Now preserve failures rather than throwing them away.

```ts
// src/resolver/execute.ts

import type { SourceAdapter, ResolveContext } from "../adapters/interface.js";

import type { MediaRef } from "../domain/media.js";

import type { SourceCandidate } from "../domain/candidate.js";

export type AdapterStatus = "success" | "empty" | "timeout" | "error";

export interface AdapterExecution {
  readonly adapterId: string;

  readonly status: AdapterStatus;

  readonly durationMs: number;

  readonly candidates: readonly SourceCandidate[];

  readonly error?: string;
}

export async function executeAdapter(
  adapter: SourceAdapter,
  media: MediaRef,
  ctx: ResolveContext
): Promise<AdapterExecution> {
  const started = performance.now();

  try {
    const candidates = await adapter.resolve(media, ctx);

    const durationMs = performance.now() - started;

    return {
      adapterId: adapter.id,

      status: candidates.length === 0 ? "empty" : "success",

      durationMs,
      candidates
    };
  } catch (error) {
    return {
      adapterId: adapter.id,

      status: "error",

      durationMs: performance.now() - started,

      candidates: [],

      error: error instanceof Error ? error.message : String(error)
    };
  }
}
```

## 69. Validation

```ts
// src/resolver/validate.ts

import type { SourceCandidate } from "../domain/candidate.js";

const protocols = new Set(["http:", "https:"]);

export function validateCandidate(candidate: SourceCandidate): boolean {
  try {
    const url = new URL(candidate.location.url);

    if (!protocols.has(url.protocol)) {
      return false;
    }
  } catch {
    return false;
  }

  if (!candidate.sourceId || !candidate.provenance.adapter) {
    return false;
  }

  if (
    candidate.media.type === "series" &&
    (!Number.isInteger(candidate.media.season) ||
      !Number.isInteger(candidate.media.episode))
  ) {
    return false;
  }

  return true;
}
```

## 70. Policy

```ts
// src/resolver/policy.ts

import type { SourceCandidate } from "../domain/candidate.js";

export interface PolicyDecision {
  readonly allowed: boolean;
  readonly reasons: readonly string[];
}

export function evaluatePolicy(candidate: SourceCandidate): PolicyDecision {
  const reasons: string[] = [];

  if (candidate.authorization.status !== "authorized") {
    reasons.push("authorization_not_verified");
  }

  if (!candidate.capabilities.directPlayback) {
    reasons.push("direct_playback_unavailable");
  }

  return {
    allowed: reasons.length === 0,

    reasons
  };
}
```

This is intentionally conservative.

## 71. Deduplication

```ts
// src/resolver/dedupe.ts

import type { SourceCandidate } from "../domain/candidate.js";

function canonicalUrl(value: string): string {
  const url = new URL(value);

  url.hash = "";

  return url.toString();
}

function key(candidate: SourceCandidate): string {
  return [
    candidate.media.type,
    candidate.media.id,
    candidate.media.season ?? "",
    candidate.media.episode ?? "",
    canonicalUrl(candidate.location.url)
  ].join("|");
}

export function deduplicate(
  candidates: readonly SourceCandidate[]
): SourceCandidate[] {
  const result = new Map<string, SourceCandidate>();

  for (const candidate of candidates) {
    const k = key(candidate);

    if (!result.has(k)) {
      result.set(k, candidate);
    }
  }

  return [...result.values()];
}
```

## 72. Ranking

Start simple.

```ts
// src/resolver/rank.ts

import type { SourceCandidate } from "../domain/candidate.js";

function resolution(candidate: SourceCandidate): number {
  return (
    (candidate.mediaInfo.width ?? 0) * (candidate.mediaInfo.height ?? 0)
  );
}

export function rank(
  candidates: readonly SourceCandidate[]
): SourceCandidate[] {
  return [...candidates].sort((a, b) => {
    const direct =
      Number(b.capabilities.directPlayback) -
      Number(a.capabilities.directPlayback);

    if (direct !== 0) {
      return direct;
    }

    const res = resolution(b) - resolution(a);

    if (res !== 0) {
      return res;
    }

    const bitrate = (b.mediaInfo.bitrate ?? 0) - (a.mediaInfo.bitrate ?? 0);

    if (bitrate !== 0) {
      return bitrate;
    }

    return a.sourceId.localeCompare(b.sourceId);
  });
}
```

Don't introduce a complicated ML ranking system yet.

First establish deterministic semantics.

## 73. Resolver

```ts
// src/resolver/resolver.ts

import type { MediaRef } from "../domain/media.js";

import type { SourceCandidate } from "../domain/candidate.js";

import type { ResolveContext } from "../adapters/interface.js";

import { SourceRegistry } from "../adapters/registry.js";

import { executeAdapter } from "./execute.js";

import { validateCandidate } from "./validate.js";

import { evaluatePolicy } from "./policy.js";

import { deduplicate } from "./dedupe.js";

import { rank } from "./rank.js";

export interface ResolutionResult {
  readonly media: MediaRef;

  readonly executions: readonly Awaited<ReturnType<typeof executeAdapter>>[];

  readonly candidates: readonly SourceCandidate[];
}

export async function resolveMedia(
  media: MediaRef,
  registry: SourceRegistry,
  ctx: ResolveContext
): Promise<ResolutionResult> {
  const adapters = registry.applicable(media);

  const executions = await Promise.all(
    adapters.map(adapter => executeAdapter(adapter, media, ctx))
  );

  const candidates = executions.flatMap(execution => execution.candidates);

  const valid = candidates.filter(validateCandidate);

  const permitted = valid.filter(
    candidate => evaluatePolicy(candidate).allowed
  );

  const unique = deduplicate(permitted);

  const ranked = rank(unique);

  return {
    media,
    executions,
    candidates: ranked
  };
}
```

This is the kernel.

## 74. First legitimate adapter

For the first adapter, use a **local/user-owned media library** rather
than trying to start with questionable web scraping.

Its contract can look like:

```text
User-owned media server
        │
        ▼
  authentication
        │
        ▼
 canonical media lookup
        │
        ▼
 playback URL
        │
        ▼
 SourceCandidate
```

This also gives us a clean integration test because the source
semantics are under our control.

## 75. Test adapter

Before connecting any external service, create:

```ts
// test/fixtures/adapter.ts

import type { SourceAdapter } from "../../src/adapters/interface.js";

export function fakeAdapter(candidates: any[]): SourceAdapter {
  return {
    id: "test",
    name: "Test",

    supports() {
      return true;
    },

    async resolve() {
      return candidates;
    }
  };
}
```

Now the resolver can be tested independently.

## 76. Resolver test

```ts
import { describe, expect, it } from "vitest";

import { SourceRegistry } from "../src/adapters/registry.js";

import { resolveMedia } from "../src/resolver/resolver.js";

describe("resolver", () => {
  it("aggregates successful sources", async () => {
    const registry = new SourceRegistry();

    registry.register(
      fakeAdapter([
        makeCandidate({
          sourceId: "a",
          width: 1920,
          height: 1080
        })
      ])
    );

    const result = await resolveMedia(
      {
        type: "movie",
        id: "tt0000000"
      },
      registry,
      testContext()
    );

    expect(result.candidates).toHaveLength(1);
  });
});
```

## 77. Add the failure test

```ts
it("preserves partial success", async () => {
  const registry = new SourceRegistry();

  registry.register(
    fakeAdapter([
      makeCandidate({
        sourceId: "working",
        width: 1920,
        height: 1080
      })
    ])
  );

  registry.register({
    id: "broken",
    name: "Broken",

    supports() {
      return true;
    },

    async resolve() {
      throw new Error("provider_failure");
    }
  });

  const result = await resolveMedia(movie(), registry, testContext());

  expect(result.candidates).toHaveLength(1);

  expect(
    result.executions.find(x => x.adapterId === "broken")?.status
  ).toBe("error");
});
```

That test captures one of the central architectural promises.

## 78. Add the authorization test

```ts
it("does not emit unauthorized candidates", async () => {
  const registry = new SourceRegistry();

  registry.register(
    fakeAdapter([
      makeCandidate({
        sourceId: "blocked",
        authorization: {
          status: "unknown"
        }
      }),

      makeCandidate({
        sourceId: "allowed",
        authorization: {
          status: "authorized"
        }
      })
    ])
  );

  const result = await resolveMedia(movie(), registry, testContext());

  expect(result.candidates.map(x => x.sourceId)).toEqual(["allowed"]);
});
```

This is a release-gate test, not merely a unit test.

## 79. Stremio adapter

Now the kernel is ready.

```ts
// src/addon/stream-handler.ts

import type { SourceCandidate } from "../domain/candidate.js";

function formatQuality(candidate: SourceCandidate): string {
  const { width, height } = candidate.mediaInfo;

  if (!width || !height) {
    return "Unknown";
  }

  return `${width}x${height}`;
}

export function toStremioStream(candidate: SourceCandidate) {
  return {
    name: candidate.sourceId,

    description: formatQuality(candidate),

    url: candidate.location.url
  };
}
```

Notice how stupid this function is.

That's desirable.

## 80. Manifest

Keep it equally boring:

```ts
export const manifest = {
  id: "org.example.multisource",

  version: "0.1.0",

  name: "MultiSource",

  description: "Authorized multi-source media aggregation.",

  resources: ["stream"],

  types: ["movie", "series"],

  idPrefixes: ["tt"]
};
```

Don't add catalog functionality until metadata semantics are actually
defined.

## 81. Stremio ID parser

```ts
export function parseMediaId(type: string, id: string): MediaRef {
  if (type === "movie") {
    return {
      type: "movie",
      id,
      imdbId: id
    };
  }

  if (type === "series") {
    const [imdbId, seasonRaw, episodeRaw] = id.split(":");

    const season = Number(seasonRaw);

    const episode = Number(episodeRaw);

    if (!imdbId || !Number.isInteger(season) || !Number.isInteger(episode)) {
      throw new Error("invalid_series_id");
    }

    return {
      type: "series",
      id: imdbId,
      imdbId,
      season,
      episode
    };
  }

  throw new Error(`unsupported_type:${type}`);
}
```

## 82. Assemble the addon

```ts
import { addonBuilder, serveHTTP } from "stremio-addon-sdk";

import { manifest } from "./addon/manifest.js";

import { SourceRegistry } from "./adapters/registry.js";

import { resolveMedia } from "./resolver/resolver.js";

const registry = new SourceRegistry();

// register adapters here

const builder = new addonBuilder(manifest);

builder.defineStreamHandler(async args => {
  const media = parseMediaId(args.type, args.id);

  const result = await resolveMedia(media, registry, createResolveContext());

  return {
    streams: result.candidates.map(toStremioStream)
  };
});

serveHTTP(builder.getInterface(), {
  port: Number(process.env.PORT ?? 7000)
});
```

## 83. But don't call this release-ready yet

There are still important missing gates:

```text
G0  Domain contract              ✓
G1  Adapter contract             ✓
G2  Resolver                     ✓
G3  Validation                   ✓
G4  Policy                       ✓
G5  Dedup                        ✓
G6  Deterministic ranking        ✓
G7  Stremio boundary             ✓

G8  Timeout cancellation         TODO
G9  Concurrency limiter          TODO
G10 Circuit breaker              TODO
G11 Cache                        TODO
G12 SSRF boundary                TODO
G13 Rate limiting                TODO
G14 Observability                TODO
G15 Health endpoint              TODO
G16 Metadata                     TODO
G17 Subtitles                    TODO
G18 Deployment                   TODO
G19 Integration tests            TODO
G20 Release evidence             TODO
```

The next important piece is **not another source adapter**.

It is runtime reliability.

## 84. Runtime reliability architecture

The execution path should become:

```text
                 Adapter
                     │
                     ▼
               Circuit breaker
                     │
                     ▼
               Rate limiter
                     │
                     ▼
              Concurrency gate
                     │
                     ▼
                Timeout
                     │
                     ▼
               HTTP request
                     │
                     ▼
                 Parser
                     │
                     ▼
              SourceCandidate
```

Each layer has one responsibility.

```text
Circuit breaker → should we call?
Rate limiter    → may we call now?
Concurrency     → do we have capacity?
Timeout         → how long may it run?
Parser          → what did it return?
Validator       → is it structurally valid?
Policy          → may it be emitted?
```

This is much easier to reason about than a giant `resolve()` function.

## 85. Release evidence

Given the architecture we have now, the release gate should eventually
produce something like:

```text
RELEASE CANDIDATE
─────────────────────────────────────
Version: 0.1.0

Typecheck                PASS
Unit tests               PASS
Integration tests        PASS
Manifest validation      PASS
Resolver conformance     PASS
Policy conformance       PASS
Dedup conformance        PASS
Ranking determinism      PASS
Failure isolation        PASS
Timeout cancellation     PASS
SSRF tests               PASS
Container build          PASS
Smoke test               PASS

Source adapters:
  test                     PASS
  user-library             PASS

Protocol:
  /manifest.json           PASS
  /stream                  PASS

STATUS: RELEASE-CANDIDATE
```

And importantly:

```text
NO EVIDENCE
     ↓
NO VERIFIED CLAIM
```

So "works" should mean a reproducible test artifact exists, not merely
that the code looks correct.

## Next layer

The natural continuation is to implement **G8–G15 as the runtime
substrate**:

```text
timeout cancellation
        ↓
bounded concurrency
        ↓
per-source rate limiting
        ↓
circuit breakers
        ↓
cache with stale/revalidate semantics
        ↓
SSRF-safe HTTP client
        ↓
structured metrics
        ↓
health/readiness endpoints
```

After that, the Stremio addon becomes a relatively thin shell around a
hardened aggregation engine rather than the engine itself.

## 86. Runtime substrate: make source resolution production-grade

The next layer should make the resolver **bounded, cancellable,
observable, and resistant to a bad source**.

The execution contract becomes:

```text
                   resolve(media)
                         │
                         ▼
                 ┌──────────────┐
                 │ Source       │
                 │ Registry     │
                 └──────┬───────┘
                        │
                  applicable[]
                        │
                        ▼
               ┌─────────────────┐
               │ Execution Guard │
               └────────┬────────┘
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
    concurrency     rate limit     breaker
         │              │              │
         └──────────────┼──────────────┘
                        ▼
                     timeout
                        │
                        ▼
                  adapter.resolve()
                        │
                        ▼
                     result
```

The key rule:

**A source adapter gets a bounded opportunity to produce evidence. It
does not get control over the resolver.**

## 87. Cancellation first

A timeout without cancellation is incomplete.

This is bad:

```ts
await Promise.race([adapter.resolve(), timeout()]);
```

because `adapter.resolve()` may continue running after the resolver has
already moved on.

Instead, propagate `AbortSignal`.

```ts
export interface ResolveContext {
  readonly signal: AbortSignal;
  readonly timeoutMs: number;
  readonly preferredLanguages: readonly string[];
}
```

HTTP requests should receive it:

```ts
const response = await fetch(url, { signal: ctx.signal });
```

## 88. Per-adapter timeout

Create:

```text
src/runtime/timeout.ts
```

```ts
export async function withTimeout<T>(
  operation: (signal: AbortSignal) => Promise<T>,
  timeoutMs: number,
  parentSignal?: AbortSignal
): Promise<T> {
  const controller = new AbortController();

  const onAbort = () => controller.abort(parentSignal?.reason);

  if (parentSignal) {
    if (parentSignal.aborted) {
      controller.abort(parentSignal.reason);
    } else {
      parentSignal.addEventListener("abort", onAbort, { once: true });
    }
  }

  const timer = setTimeout(() => {
    controller.abort(new Error("timeout"));
  }, timeoutMs);

  try {
    return await operation(controller.signal);
  } finally {
    clearTimeout(timer);

    parentSignal?.removeEventListener("abort", onAbort);
  }
}
```

Now:

```text
request cancellation
        │
        ├── client disconnects
        │
        ├── global timeout
        │
        └── source timeout
               │
               ▼
           AbortSignal
               │
               ▼
           HTTP request
```

## 89. Global versus source timeout

Don't use one timeout for everything.

Define:

```ts
export interface RuntimeLimits {
  readonly totalMs: number;
  readonly perSourceMs: number;
  readonly maxSources: number;
}
```

For example:

```text
Total request budget         4000 ms
           │
      ┌─────┴─────┐
      │           │
  source A      source B
   1200ms        1200ms
```

The source timeout should be smaller than the overall request budget.

## 90. Global cancellation

At the resolver level:

```ts
const controller = new AbortController();

const timer = setTimeout(
  () => controller.abort(new Error("resolution_timeout")),
  config.totalTimeoutMs
);

try {
  // resolve
} finally {
  clearTimeout(timer);
}
```

Now every source receives the same upper-level cancellation.

## 91. Concurrency limiter

Suppose you eventually have:

```text
25 source adapters
```

Calling all 25 simultaneously is unnecessary.

Implement a bounded scheduler.

```ts
export class Semaphore {
  private active = 0;

  private readonly queue: (() => void)[] = [];

  constructor(private readonly capacity: number) {}

  async acquire(): Promise<() => void> {
    if (this.active < this.capacity) {
      this.active++;
      return () => this.release();
    }

    await new Promise<void>(resolve => this.queue.push(resolve));

    this.active++;

    return () => this.release();
  }

  private release(): void {
    this.active--;

    const next = this.queue.shift();

    next?.();
  }
}
```

Usage:

```ts
const release = await semaphore.acquire();

try {
  return await adapter.resolve(media, ctx);
} finally {
  release();
}
```

## 92. Why the semaphore belongs outside adapters

The adapter should not know:

```text
"I am source #7 and the process allows six concurrent requests."
```

That's runtime policy.

Therefore:

```text
Adapter
    ↓
pure source-specific operation

Runtime
    ↓
global resource governance
```

This preserves adapter portability.

## 93. Per-source concurrency

You may eventually need both:

```text
global concurrency
        +
per-source concurrency
```

Example:

```text
Global = 8

Source A = max 2
Source B = max 2
Source C = max 1
Source D = max 3
```

This prevents one popular adapter from consuming the entire process.

## 94. Rate limiter

Rate limiting is different from concurrency.

```text
Concurrency: "How many requests may be running?"

Rate limit: "How frequently may requests start?"
```

A simple token bucket is appropriate.

```ts
export class TokenBucket {
  private tokens: number;

  private lastRefill = Date.now();

  constructor(
    private readonly capacity: number,
    private readonly refillPerSecond: number
  ) {
    this.tokens = capacity;
  }

  tryConsume(): boolean {
    this.refill();

    if (this.tokens < 1) {
      return false;
    }

    this.tokens--;

    return true;
  }

  private refill(): void {
    const now = Date.now();

    const elapsed = (now - this.lastRefill) / 1000;

    this.tokens = Math.min(
      this.capacity,
      this.tokens + elapsed * this.refillPerSecond
    );

    this.lastRefill = now;
  }
}
```

For the first release, returning a controlled `rate_limited` result is
preferable to an uncontrolled queue that can inflate latency.

## 95. Circuit breaker

Now make the earlier breaker production-safe.

```ts
type BreakerState = "closed" | "open" | "half-open";

export class CircuitBreaker {
  private state: BreakerState = "closed";

  private failures = 0;

  private openedAt = 0;

  constructor(
    private readonly threshold = 5,
    private readonly cooldownMs = 30_000
  ) {}

  getState(): BreakerState {
    this.transitionIfReady();

    return this.state;
  }

  allowRequest(): boolean {
    this.transitionIfReady();

    if (this.state === "open") {
      return false;
    }

    if (this.state === "half-open") {
      this.state = "open";
      return true;
    }

    return true;
  }

  success(): void {
    this.state = "closed";
    this.failures = 0;
    this.openedAt = 0;
  }

  failure(): void {
    this.failures++;

    if (this.failures >= this.threshold) {
      this.state = "open";
      this.openedAt = Date.now();
    }
  }

  private transitionIfReady(): void {
    if (
      this.state === "open" &&
      Date.now() - this.openedAt >= this.cooldownMs
    ) {
      this.state = "half-open";
    }
  }
}
```

The semantics are:

```text
CLOSED
  │
  │ repeated failures
  ▼
OPEN
  │
  │ cooldown
  ▼
HALF-OPEN
  │
  ├── success → CLOSED
  │
  └── failure → OPEN
```

## 96. Don't count every failure equally

A malformed provider response is different from a temporary network
failure.

Define:

```ts
type FailureClass =
  | "timeout"
  | "network"
  | "rate_limit"
  | "server"
  | "invalid_response"
  | "authorization"
  | "empty";
```

Then configure breaker behavior.

For example:

```text
timeout          → breaker failure
network          → breaker failure
HTTP 500         → breaker failure
invalid response → breaker failure

empty            → NOT breaker failure
authorization    → NOT necessarily breaker failure
```

An empty catalog doesn't mean the provider is broken.

## 97. Execution guard

Now combine the pieces.

```ts
interface SourceRuntime {
  readonly semaphore: Semaphore;
  readonly bucket: TokenBucket;
  readonly breaker: CircuitBreaker;
}
```

Execution:

```ts
async function executeGuarded(
  adapter: SourceAdapter,
  runtime: SourceRuntime,
  media: MediaRef,
  ctx: ResolveContext
) {
  if (!runtime.breaker.allowRequest()) {
    return {
      status: "circuit_open" as const,
      candidates: []
    };
  }

  if (!runtime.bucket.tryConsume()) {
    return {
      status: "rate_limited" as const,
      candidates: []
    };
  }

  const release = await runtime.semaphore.acquire();

  try {
    const candidates = await withTimeout(
      signal =>
        adapter.resolve(media, {
          ...ctx,
          signal
        }),
      ctx.timeoutMs,
      ctx.signal
    );

    runtime.breaker.success();

    return {
      status: "success" as const,
      candidates
    };
  } catch (error) {
    runtime.breaker.failure();

    return {
      status: classifyFailure(error),
      candidates: []
    };
  } finally {
    release();
  }
}
```

Now the source cannot bypass runtime governance.

## 98. Cache architecture

Caching should happen at two levels.

```text
                   Resolver
                       │
              ┌────────┴────────┐
              ▼                 ▼
        Identity cache     Source cache
              │                 │
           metadata        candidates
```

A third cache is operational:

```text
health cache
```

## 99. Cache key

Never use just:

```text
"movie:tt123"
```

for source results.

Include relevant configuration:

```ts
interface SourceCacheKey {
  readonly adapterId: string;
  readonly mediaId: string;
  readonly season?: number;
  readonly episode?: number;
  readonly language: string;
}
```

Serialize deterministically:

```ts
function cacheKey(key: SourceCacheKey): string {
  return [
    key.adapterId,
    key.mediaId,
    key.season ?? "",
    key.episode ?? "",
    key.language
  ].join(":");
}
```

## 100. Cache state

Don't make cache semantics binary.

```ts
type CacheState = "miss" | "fresh" | "stale";
```

A record:

```ts
interface CacheEntry<T> {
  readonly value: T;

  readonly createdAt: number;

  readonly expiresAt: number;

  readonly staleUntil: number;
}
```

Then:

```text
created
    │
    ├──────── fresh ────────┐
    │                       │
    ▼                       ▼
expires                 stale
                            │
                            ▼
                        staleUntil
                            │
                            ▼
                          dead
```

## 101. Stale-while-revalidate

For a source query:

```text
cache fresh
    │
    └── return immediately

cache stale
    │
    ├── return stale
    │
    └── refresh asynchronously

cache dead
    │
    └── synchronous source query
```

This can significantly reduce perceived latency.

But expose freshness internally:

```ts
interface CachedResolution<T> {
  readonly value: T;
  readonly state: "fresh" | "stale";
}
```

Never pretend stale evidence is fresh.

## 102. Cache stampede protection

Without protection:

```text
100 users
    │
    ▼
same uncached movie
    │
    ▼
100 requests to provider
```

Instead maintain an in-flight map:

```ts
const inflight = new Map<string, Promise<unknown>>();
```

Conceptually:

```text
Request A ──┐
Request B ──┤
Request C ──┼──→ same promise
Request D ──┤
Request E ──┘
```

Only one provider request occurs.

## 103. HTTP client boundary

Don't allow adapters to use arbitrary `fetch()` everywhere.

Provide:

```ts
interface SafeHttpClient {
  getJson<T>(url: string, options?: RequestOptions): Promise<T>;

  head(url: string, options?: RequestOptions): Promise<ResponseMetadata>;
}
```

Then centralize:

```text
timeouts
redirect rules
maximum response size
headers
logging
SSRF protection
abort handling
```

This is a major security boundary.

## 104. SSRF protection

If your addon ever accepts user-configured endpoints, distinguish:

```text
trusted configured origin
```

from:

```text
arbitrary URL returned by provider
```

Never assume:

```text
"the provider gave me this URL"
```

means it is safe for your server to fetch.

A server-side fetcher must consider:

```text
127.0.0.1
localhost
RFC1918 ranges
link-local
IPv6 loopback
IPv6 private ranges
metadata endpoints
DNS rebinding
redirects
```

A strong architecture is:

```text
Provider API
     │
     ▼
metadata only
     │
     ▼
Stremio
     │
     ▼
client-side playback
```

whenever direct playback makes server-side proxying unnecessary.

That substantially reduces your attack surface.

## 105. Don't build a media proxy into v0.1

A common temptation is:

```text
Stremio
   ↓
Addon
   ↓
your server
   ↓
source
```

But if Stremio can play:

```text
Stremio
   ↓
source
```

prefer the latter.

The addon becomes:

```text
control plane
```

rather than:

```text
media data plane
```

This reduces:

- bandwidth cost
- server CPU
- privacy exposure
- legal complexity
- failure modes
- SSRF surface

## 106. Observability

Define structured events.

```ts
interface ResolutionEvent {
  readonly requestId: string;

  readonly mediaId: string;

  readonly mediaType: string;

  readonly adapterId?: string;

  readonly status: string;

  readonly durationMs: number;

  readonly candidateCount?: number;
}
```

Log JSON rather than prose.

Example:

```json
{
  "event": "adapter.resolve",
  "requestId": "01K...",
  "adapterId": "user-library",
  "status": "success",
  "durationMs": 184,
  "candidateCount": 2
}
```

## 107. Metrics

Minimum metrics:

```text
resolver_requests_total
resolver_success_total
resolver_empty_total
resolver_failure_total

adapter_requests_total
adapter_success_total
adapter_timeout_total
adapter_rate_limit_total
adapter_error_total

adapter_latency_ms

cache_hit_total
cache_miss_total
cache_stale_total

candidate_seen_total
candidate_rejected_total
candidate_emitted_total
```

Dimensions should be bounded.

Good:

```text
adapter=user-library
```

Bad:

```text
url=https://random-user-generated-url...
```

Never allow unbounded user data to become metric labels.

## 108. Health versus readiness

Use two concepts.

### Liveness

Is the process alive?

```text
GET /health/live
```

Response:

```json
{
  "status": "ok"
}
```

### Readiness

Can this instance serve requests?

```text
GET /health/ready
```

Example:

```json
{
  "status": "ready",
  "version": "0.1.0"
}
```

A temporary source failure should generally **not** make the entire
addon unready.

That's an important distinction.

## 109. Source health

Expose operational state:

```json
{
  "sources": {
    "user-library": {
      "state": "healthy"
    },
    "public-domain": {
      "state": "degraded"
    }
  }
}
```

But don't leak:

```text
API credentials
private endpoint URLs
user account IDs
authorization headers
```

## 110. Request IDs

Every inbound request gets:

```text
request_id
```

Then:

```text
Stremio request
    │
    ├── adapter A
    ├── adapter B
    └── adapter C
          │
          └── same request_id
```

This makes a production failure traceable:

```text
request 01K...
  adapter A: 180ms success
  adapter B: 3500ms timeout
  adapter C: 240ms success
```

## 111. Metrics do not become evidence of correctness

This distinction matters:

```text
"source succeeded 99.2%"
```

is operational evidence.

It does **not** prove:

```text
"source is authorized."
```

Likewise:

```text
HTTP 200
```

doesn't prove:

```text
media exists
```

and:

```text
stream URL returned
```

doesn't prove:

```text
playback succeeds
```

Keep those semantics separate.

## 112. Playback verification

Do not attempt full playback verification for every request.

It is expensive.

Instead distinguish:

```text
DISCOVERED
    ↓
STRUCTURALLY_VALID
    ↓
AUTHORIZED
    ↓
DIRECT_PLAYBACK_CAPABLE
    ↓
OPTIONALLY_PROBED
    ↓
OBSERVED_PLAYBACK_SUCCESS
```

Only the first four are normally needed to emit a stream.

If you later add probing:

```text
HEAD / range request
```

record it as evidence rather than changing the candidate's fundamental
identity.

## 113. Source health versus candidate health

Another important separation:

```text
Source health
    = provider operational condition

Candidate validity
    = this particular stream's properties
```

A healthy provider can return a broken candidate.

A degraded provider can still return a valid candidate.

Do not conflate them.

## 114. Configuration model

Use validated environment configuration.

```ts
import { z } from "zod";

const ConfigSchema = z.object({
  PORT: z.coerce.number().int().min(1).max(65535).default(7000),

  TOTAL_TIMEOUT_MS: z.coerce.number().int().positive().default(4000),

  SOURCE_TIMEOUT_MS: z.coerce.number().int().positive().default(2500),

  MAX_CONCURRENCY: z.coerce.number().int().positive().default(6)
});
```

Then:

```ts
export const config = ConfigSchema.parse(process.env);
```

Configuration errors should fail at startup.

Not halfway through a user request.

## 115. Runtime composition

Now `index.ts` becomes dependency composition rather than business
logic.

```text
index.ts

config
   ↓
logger
   ↓
HTTP client
   ↓
registry
   ↓
runtime managers
   ↓
resolver
   ↓
Stremio adapter
   ↓
server
```

The business logic is elsewhere.

This makes testing much easier.

## 116. Final runtime tree

```text
src/
├── addon/
│   ├── manifest.ts
│   ├── parser.ts
│   └── stream-handler.ts
│
├── domain/
│   ├── media.ts
│   ├── candidate.ts
│   ├── failure.ts
│   └── result.ts
│
├── adapters/
│   ├── interface.ts
│   ├── registry.ts
│   └── ...
│
├── resolver/
│   ├── resolver.ts
│   ├── execute.ts
│   ├── normalize.ts
│   ├── validate.ts
│   ├── policy.ts
│   ├── dedupe.ts
│   └── rank.ts
│
├── runtime/
│   ├── semaphore.ts
│   ├── limiter.ts
│   ├── breaker.ts
│   ├── timeout.ts
│   ├── cache.ts
│   └── http.ts
│
├── observability/
│   ├── logger.ts
│   ├── metrics.ts
│   └── health.ts
│
└── config/
    └── config.ts
```

At this point the architecture has a very clean separation:

```text
DOMAIN
   ↓
What is a media source?

ADAPTERS
   ↓
How does a particular provider expose it?

RUNTIME
   ↓
How do we safely execute providers?

RESOLVER
   ↓
How do we combine results?

POLICY
   ↓
What is eligible?

RANKER
   ↓
What order?

STREMIO
   ↓
How do we present the result?
```

## 117. Release gate R1

The first meaningful implementation milestone is now:

```text
R1 — Aggregation Kernel
────────────────────────────────

[✓] MediaRef
[✓] SourceCandidate
[✓] SourceAdapter
[✓] Registry
[✓] Validation
[✓] Policy
[✓] Dedup
[✓] Deterministic ranking
[✓] Failure isolation

[✓] AbortSignal propagation
[✓] Timeout
[✓] Bounded concurrency
[✓] Rate limiting
[✓] Circuit breaker

[ ] Persistent cache
[ ] Safe HTTP client
[ ] SSRF tests
[ ] Metrics
[ ] Health endpoints
[ ] Stremio integration test
[ ] Container smoke test
```

The next gate should therefore be **the safe HTTP/cache subsystem plus
the complete Stremio protocol test harness**.

That is where we can test the full chain:

```text
Stremio request
      ↓
parse
      ↓
resolver
      ↓
adapter
      ↓
safe HTTP
      ↓
candidate
      ↓
policy
      ↓
dedup
      ↓
rank
      ↓
Stremio Stream[]
```

and establish the first genuine **end-to-end conformance baseline**.
