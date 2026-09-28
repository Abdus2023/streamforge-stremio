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

## 118. Safe HTTP + cache + Stremio conformance

The next layer closes the gap between the abstract resolver and an
actually deployable addon.

The important boundary is:

```text
                 ┌─────────────────────┐
                 │    Stremio request   │
                 └──────────┬──────────┘
                             │
                             ▼
                     MediaRef parser
                             │
                             ▼
                        Resolver
                             │
                 ┌───────────┴───────────┐
                 │                       │
                 ▼                       ▼
              Cache                 Source runtime
                                         │
                                ┌────────┼────────┐
                                ▼        ▼        ▼
                              limit   breaker   timeout
                                         │
                                         ▼
                                   Safe HTTP
                                         │
                                         ▼
                                   Source API
```

The critical principle remains:

**The HTTP client is a trust boundary, not merely a convenience wrapper
around `fetch()`.**

## 119. Safe HTTP contract

Create:

```text
src/runtime/http.ts
```

The adapter should not receive raw `fetch`.

```ts
export interface SafeHttpClient {
  getJson<T>(url: string, options?: HttpOptions): Promise<T>;

  getText(url: string, options?: HttpOptions): Promise<string>;
}

export interface HttpOptions {
  readonly signal?: AbortSignal;
  readonly headers?: Record<string, string>;
  readonly maxBytes?: number;
  readonly maxRedirects?: number;
}
```

This gives us one place to enforce:

```text
URL validation
redirect validation
timeouts
response-size limits
content-type checks
header policy
abort propagation
logging
```

## 120. URL validation

Start conservatively.

```ts
const ALLOWED_PROTOCOLS = new Set(["http:", "https:"]);

export function validateHttpUrl(input: string): URL {
  const url = new URL(input);

  if (!ALLOWED_PROTOCOLS.has(url.protocol)) {
    throw new Error("unsupported_url_protocol");
  }

  if (url.username || url.password) {
    throw new Error("url_credentials_forbidden");
  }

  return url;
}
```

Reject:

```text
file:
ftp:
data:
javascript:
blob:
ssh:
```

and URLs containing embedded credentials.

## 121. SSRF policy

The first version should explicitly classify addresses.

```ts
type AddressClass =
  | "public"
  | "loopback"
  | "private"
  | "link_local"
  | "reserved"
  | "unknown";
```

Do not blindly implement:

```ts
if (hostname === "localhost")
```

because:

```text
localhost
127.0.0.1
127.0.0.2
::1
0.0.0.0
10.x.x.x
172.16.x.x
192.168.x.x
169.254.x.x
```

are not the complete problem.

## 122. DNS rebinding

The difficult case is:

```text
evil.example
     │
     ├── DNS lookup #1 → public IP
     │
     └── DNS lookup #2 → 127.0.0.1
```

Therefore:

validating the hostname string alone is not SSRF protection.

And:

resolving the hostname once and then using a separate HTTP stack can
still leave a race.

For production, the HTTP implementation should control DNS resolution
and connection establishment.

That is a **deployment-security requirement**, not something the
domain layer should pretend to solve.

## 123. Safer baseline

For the first public release, adopt this policy:

```text
Server-side fetching:
    only explicitly configured/trusted origins

Provider-returned URLs:
    emitted to Stremio
    NOT automatically proxied by addon
```

This is substantially safer than allowing arbitrary remote URLs to
become server-side fetch targets.

## 124. Redirects

A safe client must not validate only the initial URL.

Bad:

```text
GET https://trusted.example
        ↓
302 http://127.0.0.1
```

Therefore either:

```text
automatic redirects = disabled
```

or manually validate every redirect.

For v0.1:

```text
redirect: "manual"
```

is preferable.

Then:

```text
response.status = 3xx
        │
        ▼
Location header
        │
        ▼
validateHttpUrl()
        │
        ▼
SSRF policy
        │
        ▼
next request
```

## 125. Response-size limit

Never assume an API response is small.

```ts
const MAX_JSON_BYTES = 2 * 1024 * 1024;
```

A malicious or broken source returning:

```text
500 MB JSON
```

should not consume the addon process.

The HTTP layer should enforce a byte ceiling while reading.

Conceptually:

```ts
async function readLimited(
  response: Response,
  maxBytes: number
): Promise<Uint8Array> {
  if (!response.body) {
    return new Uint8Array();
  }

  const reader = response.body.getReader();

  const chunks: Uint8Array[] = [];

  let total = 0;

  while (true) {
    const { value, done } = await reader.read();

    if (done) break;

    total += value.byteLength;

    if (total > maxBytes) {
      await reader.cancel();

      throw new Error("response_too_large");
    }

    chunks.push(value);
  }

  const result = new Uint8Array(total);

  let offset = 0;

  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.byteLength;
  }

  return result;
}
```

## 126. Content-type validation

If `getJson()` is requested:

```text
expected: application/json
          application/*+json
```

A source returning:

```text
text/html
```

should not silently become a JSON parse attempt.

That distinction belongs in failure classification.

```text
HTTP 200 + HTML       ≠ valid JSON response
```

## 127. HTTP failure taxonomy

Expand the previous status model:

```ts
export type AdapterStatus =
  | "success"
  | "empty"
  | "timeout"
  | "aborted"
  | "rate_limited"
  | "circuit_open"
  | "invalid_response"
  | "http_error"
  | "network_error"
  | "error";
```

This gives the observability layer useful semantics.

## 128. Never collapse HTTP status into success

This:

```ts
if (response.ok) {
  return response.json();
}
```

is insufficient.

You need:

```text
HTTP status
+ content type
+ body validity
+ schema validity
```

before producing source candidates.

The pipeline becomes:

```text
HTTP response
    │
    ▼
transport validation
    │
    ▼
content validation
    │
    ▼
schema validation
    │
    ▼
adapter normalization
    │
    ▼
SourceCandidate[]
```

## 129. Zod belongs at the adapter boundary

External data is untrusted.

Example:

```ts
const ExternalRecord = z.object({
  id: z.string(),
  url: z.string(),
  title: z.string().optional(),
  size: z.number().optional()
});
```

Then:

```ts
const parsed = ExternalRecord.safeParse(record);

if (!parsed.success) {
  throw new Error("invalid_source_record");
}
```

Only after this should you construct:

```text
SourceCandidate
```

The domain model should not be polluted with provider-specific
optional garbage.

## 130. Cache interface

Now define:

```text
src/runtime/cache.ts
```

```ts
export interface CacheStore<T> {
  get(key: string): Promise<CacheEntry<T> | null>;

  set(key: string, entry: CacheEntry<T>): Promise<void>;

  delete(key: string): Promise<void>;
}
```

Start with memory.

```ts
export class MemoryCache<T> implements CacheStore<T> {
  private readonly map = new Map<string, CacheEntry<T>>();

  async get(key: string) {
    return this.map.get(key) ?? null;
  }

  async set(key: string, entry: CacheEntry<T>) {
    this.map.set(key, entry);
  }

  async delete(key: string) {
    this.map.delete(key);
  }
}
```

## 131. Don't cache authorization assumptions

This is important.

Avoid:

```text
cache: "URL X is authorized"
```

unless the authorization evidence itself has a defined validity
period.

Instead cache the source observation:

```text
source record
observedAt
provider evidence
```

and derive current policy separately.

Why?

Because:

```text
observation
```

and:

```text
authorization decision
```

have different lifetimes.

## 132. Cache candidates, not final Stremio streams

Prefer:

```text
cache
    ↓
SourceCandidate[]
    ↓
current policy
    ↓
current deduplication
    ↓
current ranking
    ↓
Stremio
```

instead of caching:

```text
Stremio Stream[]
```

This allows policy/ranking changes without invalidating the entire
cache.

## 133. Cache key versioning

Add a namespace:

```ts
const CACHE_VERSION = "candidate-v1";
```

Then:

```ts
function makeCacheKey(key: SourceCacheKey): string {
  return [
    CACHE_VERSION,
    key.adapterId,
    key.mediaId,
    key.season ?? "",
    key.episode ?? "",
    key.language
  ].join("|");
}
```

When the candidate schema changes:

```text
candidate-v1
    ↓
candidate-v2
```

instead of silently interpreting old data under the new schema.

## 134. Stale cache policy

Use:

```ts
export interface CachePolicy {
  readonly freshMs: number;
  readonly staleMs: number;
}
```

Example:

```text
fresh = 5 minutes
stale = 30 minutes
```

Then:

```text
0 ───────── 5m ───────────── 30m
│            │                 │
│  FRESH     │     STALE       │ DEAD
│            │                 │
└────────────┴─────────────────┘
```

## 135. Stale data must remain marked stale

Never:

```ts
return candidates;
```

without indicating their age internally.

Instead:

```ts
interface ResolutionSource {
  readonly candidates: readonly SourceCandidate[];

  readonly freshness: "live" | "fresh_cache" | "stale_cache";
}
```

This preserves evidence provenance.

## 136. In-flight request deduplication

Add:

```ts
class InflightRegistry<T> {
  private readonly map = new Map<string, Promise<T>>();

  async run(key: string, factory: () => Promise<T>): Promise<T> {
    const existing = this.map.get(key);

    if (existing) {
      return existing;
    }

    const promise = factory();

    this.map.set(key, promise);

    try {
      return await promise;
    } finally {
      this.map.delete(key);
    }
  }
}
```

Now ten simultaneous requests can share one source call.

## 137. Important cancellation caveat

Do not let request A cancel the shared operation needed by requests
B–J.

This is a subtle bug.

Bad:

```text
A ─┐
B ─┤
C ─┼── shared operation
D ─┤
E ─┘

A disconnects
     ↓
ABORT
     ↓
everyone loses
```

The shared operation needs its **own lifecycle**.

Then each caller decides whether it still wants the result.

This is another reason not to blindly pass one HTTP request's
`AbortSignal` into a globally shared cache operation.

## 138. Stremio protocol boundary

Now freeze the protocol boundary.

The resolver returns:

```text
readonly SourceCandidate[]
```

The Stremio adapter converts only:

```text
SourceCandidate
        ↓
StremioStream
```

Example:

```ts
interface StremioStream {
  readonly name?: string;
  readonly title?: string;
  readonly url: string;
  readonly behaviorHints?: {
    readonly notWebReady?: boolean;
  };
}
```

The mapper should not perform:

```text
HTTP
policy
deduplication
ranking
authorization
metadata lookup
```

It should be boring.

That's intentional.

## 139. Stream mapper

```ts
export function toStremioStream(candidate: SourceCandidate): StremioStream {
  const resolution =
    candidate.mediaInfo.width && candidate.mediaInfo.height
      ? `${candidate.mediaInfo.width}x${candidate.mediaInfo.height}`
      : undefined;

  return {
    name: candidate.sourceId,

    title: [
      resolution,
      candidate.mediaInfo.videoCodec,
      candidate.mediaInfo.audioCodec
    ]
      .filter(Boolean)
      .join(" • "),

    url: candidate.location.url
  };
}
```

No hidden source lookup.

No proxy.

No ranking.

No mutation.

## 140. Series parsing

Freeze the ID grammar explicitly.

For example:

```text
movie: tt1234567

series: tt1234567:1:4
```

Parser:

```ts
export interface ParsedStremioId {
  readonly imdbId: string;
  readonly season?: number;
  readonly episode?: number;
}

export function parseId(type: MediaType, id: string): ParsedStremioId {
  if (type === "movie") {
    if (!/^tt\d+$/.test(id)) {
      throw new Error("invalid_movie_id");
    }

    return {
      imdbId: id
    };
  }

  const match = /^(tt\d+):(\d+):(\d+)$/.exec(id);

  if (!match) {
    throw new Error("invalid_series_id");
  }

  return {
    imdbId: match[1],
    season: Number(match[2]),
    episode: Number(match[3])
  };
}
```

The grammar should have tests before adding more accepted formats.

## 141. Unknown versus invalid

Don't do:

```ts
parseInt("abc");
```

and let it become:

```text
NaN
```

`NaN` is neither a meaningful season nor a useful UNKNOWN state.

Instead:

```text
malformed input
    = INVALID

missing optional information
    = UNKNOWN / ABSENT
```

This follows the same semantic discipline as the evidence
architecture.

## 142. Stremio handler

Conceptually:

```ts
export async function handleStream(type: MediaType, id: string) {
  const media = parseStremioMedia(type, id);

  const result = await resolver.resolve(media);

  return {
    streams: result.candidates.map(toStremioStream)
  };
}
```

That's nearly all it should contain.

## 143. Empty results

Empty result must not hide the reason.

Internally:

```text
streams = []
```

but diagnostics retain:

```json
{
  "status": "empty",
  "adapters": [
    {
      "id": "source-a",
      "status": "empty"
    },
    {
      "id": "source-b",
      "status": "timeout"
    },
    {
      "id": "source-c",
      "status": "circuit_open"
    }
  ]
}
```

Stremio gets:

```json
{
  "streams": []
}
```

Operational telemetry gets the richer evidence.

## 144. Do not leak internal diagnostics through Stremio

This distinction matters.

Internal:

```text
adapter errors
URLs
request IDs
authorization evidence
timings
```

should not automatically become public Stremio metadata.

The addon protocol is a presentation boundary.

## 145. End-to-end test

Now construct the first real conformance test.

```ts
it("resolves an eligible candidate into a Stremio stream", async () => {
  const adapter = new FakeAdapter([
    makeCandidate({
      sourceId: "fixture",
      authorization: {
        status: "authorized"
      },
      capabilities: {
        directPlayback: true
      }
    })
  ]);

  registry.register(adapter);

  const result = await resolver.resolve({
    type: "movie",
    id: "tt1234567"
  });

  expect(result.candidates).toHaveLength(1);

  const stream = toStremioStream(result.candidates[0]);

  expect(stream.url).toBe("https://example.test/video.mp4");
});
```

This test proves the **kernel contract**, not real-world source
availability.

## 146. Failure isolation test

```ts
it("does not fail the entire resolution when one adapter times out", async () => {
  registry.register(new TimeoutAdapter());

  registry.register(new SuccessfulAdapter());

  const result = await resolver.resolve(media);

  expect(result.candidates.length).toBeGreaterThan(0);

  expect(result.executions.some(x => x.status === "timeout")).toBe(true);
});
```

This is a critical invariant.

## 147. Policy invariant

```ts
it("never emits unknown-authorization candidates", async () => {
  const candidate = makeCandidate({
    authorization: {
      status: "unknown"
    }
  });

  const result = await resolveWith(candidate);

  expect(result.candidates).toHaveLength(0);
});
```

This should be treated as a security invariant, not merely a unit
test.

## 148. Deterministic ranking invariant

Given:

```text
A = 1080p
B = 720p
C = 1080p
```

and otherwise equal:

```text
A sourceId = alpha
C sourceId = zeta
```

the order must always be:

```text
A
C
B
```

independent of:

```text
adapter execution completion order
network timing
Map insertion order
Promise scheduling
```

This is exactly the kind of property worth property-based testing
later.

## 149. Runtime test matrix

Freeze this matrix:

| Condition | Expected status |
| --- | --- |
| Valid response | `success` |
| Valid response, zero candidates | `empty` |
| Timeout | `timeout` |
| Parent cancellation | `aborted` |
| Rate limit exhausted | `rate_limited` |
| Breaker open | `circuit_open` |
| Invalid JSON | `invalid_response` |
| HTTP 500 | `http_error` |
| Connection failure | `network_error` |
| Unexpected exception | `error` |

This is far better than:

```text
success / error
```

because the latter destroys operational evidence.

## 150. Conformance properties

The resolver should now satisfy these invariants:

```text
P1  Unauthorized candidates are never emitted.

P2  Unknown authorization is never treated as authorized.

P3  Adapter failure does not erase successful results
    from other adapters.

P4  Timeout cancels the underlying operation.

P5  Global cancellation propagates to active adapters.

P6  Concurrency never exceeds configured capacity.

P7  Circuit-open sources are not executed.

P8  Ranking is deterministic.

P9  Deduplication is deterministic.

P10 Stremio mapping performs no source resolution.

P11 Cached candidates pass through current policy.

P12 Stale cache is distinguishable from live data.

P13 Arbitrary provider URLs are not automatically proxied
    through the addon server.
```

These are more valuable than a large collection of superficial tests.

## 151. First architecture freeze

At this point the system has four explicit authority layers:

```text
                    AUTHORITY
                           │
                          ▼
               ┌──────────────────────┐
              │ Policy / Eligibility  │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Resolver              │
              │ aggregation authority │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Runtime               │
              │ execution authority   │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Stremio adapter       │
              │ presentation only     │
              └──────────────────────┘
```

And three things remain deliberately outside that authority chain:

```text
Provider claims
    ≠ Authorization truth

HTTP success
    ≠ Playback success

Stremio rendering
    ≠ Source validity
```

## 152. R2 release gate

```text
R2 — Safe Resolution Runtime
────────────────────────────────────

DOMAIN
[✓] MediaRef
[✓] SourceCandidate
[✓] Failure model

ADAPTER
[✓] SourceAdapter
[✓] Registry
[✓] External schema validation

RESOLUTION
[✓] Parallel execution
[✓] Failure isolation
[✓] Policy
[✓] Dedup
[✓] Deterministic ranking

RUNTIME
[✓] Abort propagation
[✓] Per-source timeout
[✓] Global timeout
[✓] Concurrency limiter
[✓] Rate limiter
[✓] Circuit breaker
[✓] In-flight deduplication

HTTP
[✓] URL protocol validation
[✓] Credential rejection
[✓] Response-size boundary
[✓] Content-type validation
[✓] Redirect policy
[ ] Production-grade DNS/IP binding

CACHE
[✓] Candidate cache abstraction
[✓] Fresh/stale/dead semantics
[✓] Versioned cache keys
[✓] Current-policy revalidation

STREMIO
[✓] ID parser
[✓] Candidate mapper
[✓] Empty-result behavior
[✓] Protocol boundary

OBSERVABILITY
[✓] Request IDs
[✓] Structured events
[✓] Basic metrics
[✓] Liveness
[✓] Readiness

TESTING
[✓] Failure isolation
[✓] Policy invariant
[✓] Ranking determinism
[✓] Runtime status matrix
[ ] Full integration suite
[ ] Container smoke test
[ ] CI release evidence
```

### Status

**R2 = PARTIALLY VERIFIED / implementation blueprint**

It is not yet a release claim because the actual repository, tests, CI
execution, and container behavior have not been executed here.

The next major layer is **metadata + subtitles + catalog identity
resolution**, because source aggregation is only useful when the addon
can reliably connect:

```text
Stremio catalog item
        ↓
IMDb/TMDB/etc. identity
        ↓
movie / series / season / episode
        ↓
source query
        ↓
eligible streams
        ↓
subtitle tracks
```

That layer introduces a second major problem: **identity resolution is
not the same thing as source discovery**, and conflating them will
eventually produce incorrect matches.

## 153. Identity resolution: the missing layer

We now have a working conceptual stream pipeline, but there is a
deeper problem:

```text
"Which movie is this?"
```

is not the same question as:

```text
"Where can I play it?"
```

The system should therefore become:

```text
                    Stremio
                        │
                        ▼
                  Request Parser
                        │
                        ▼
                 Identity Resolver
                        │
                        ▼
                  Canonical MediaRef
                        │
                        ▼
                 Source Aggregator
                        │
               ┌────────┴────────┐
               ▼                 ▼
            Streams           Subtitles
```

This is important because a source can be perfectly reachable while
referring to the **wrong work**.

## 154. Identity is evidence, not a string

Do not treat:

```text
tt1234567
```

as magically proving identity.

Instead model identity evidence.

```ts
export type IdentityKind = "imdb" | "tmdb" | "tvdb" | "internal";

export interface ExternalIdentity {
  readonly kind: IdentityKind;
  readonly value: string;
}
```

Then:

```ts
export interface MediaIdentity {
  readonly canonical?: ExternalIdentity;

  readonly aliases: readonly ExternalIdentity[];

  readonly evidence: readonly IdentityEvidence[];
}
```

## 155. Identity evidence

```ts
export interface IdentityEvidence {
  readonly provider: string;

  readonly matchedBy:
    | "exact_id"
    | "external_id"
    | "title_year"
    | "title_episode"
    | "manual";

  readonly confidence: "verified" | "probable" | "ambiguous";

  readonly observedAt: string;
}
```

The word `confidence` here is **not** a probabilistic claim.

It describes the evidence classification.

## 156. Never silently resolve ambiguity

Suppose the user requests:

```text
The Office
```

There can be multiple works.

Bad:

```text
"The Office" → arbitrary result
```

Better:

```text
title match
    ↓
multiple candidates
    ↓
AMBIGUOUS
```

For Stremio, the catalog/metadata layer should ideally provide a
stable external identifier before stream resolution.

## 157. Canonical media identity

Create:

```ts
export interface CanonicalMedia {
  readonly type: "movie" | "series";

  readonly canonicalId: string;

  readonly imdbId?: string;

  readonly tmdbId?: string;

  readonly title: string;

  readonly year?: number;

  readonly season?: number;

  readonly episode?: number;
}
```

This becomes the input to source aggregation.

## 158. Movie and episode identity

Do not model:

```text
series: tt123
```

as sufficient for an episode.

Instead:

```text
Series:
  canonical series identity

Episode:
  series identity
  season
  episode
```

Therefore:

```ts
export interface EpisodeRef {
  readonly series: CanonicalMedia;
  readonly season: number;
  readonly episode: number;
}
```

This prevents a source adapter from accidentally resolving the entire
series when the user requested S02E04.

## 159. Identity normalization

Create:

```text
src/identity/
├── resolver.ts
├── normalize.ts
├── evidence.ts
├── parser.ts
└── types.ts
```

The identity resolver's job:

```text
external ID
    ↓
validate
    ↓
normalize
    ↓
lookup aliases
    ↓
canonical identity
```

It should not retrieve streams.

## 160. Source adapter contract changes

Earlier:

```ts
resolve(media: MediaRef);
```

Now we can make the contract more explicit:

```ts
export interface SourceQuery {
  readonly media: CanonicalMedia;
}

export interface SourceAdapter {
  readonly id: string;

  supports(media: CanonicalMedia): boolean;

  resolve(query: SourceQuery, ctx: ResolveContext): Promise<SourceCandidate[]>;
}
```

The adapter receives a normalized identity.

This prevents every adapter from implementing its own IMDb/TMDB
parsing.

## 161. Identity aliases

A movie might have:

```text
IMDb: tt1234567

TMDB: 12345

internal: movie:12345
```

These are not three movies.

They are:

```text
              canonical work
              /      |       \
          IMDb     TMDB    internal
```

The identity resolver owns that relationship.

## 162. Identity conflicts

Suppose:

```text
IMDb → Movie A
TMDB → Movie B
```

Do not arbitrarily choose.

Return:

```ts
export type IdentityResolution =
  | {
      readonly status: "resolved";
      readonly media: CanonicalMedia;
    }
  | {
      readonly status: "ambiguous";
      readonly candidates: readonly CanonicalMedia[];
    }
  | {
      readonly status: "not_found";
    };
```

This is exactly where preserving UNKNOWN/AMBIGUOUS prevents silent
corruption.

## 163. Metadata is a separate capability

The addon may eventually expose:

```text
catalog
meta
stream
subtitle
```

These should remain separate handlers.

```text
Catalog
    ↓
"What exists?"

Meta
    ↓
"What is this?"

Stream
    ↓
"Where can I play it?"

Subtitle
    ↓
"What subtitle tracks exist?"
```

Don't make `stream` responsible for metadata.

## 164. Catalog strategy

There are two possible architectures.

### A. Curated catalog

```text
your catalog
    ↓
stable IDs
```

Useful for:

- public-domain media
- user-owned libraries
- explicitly authorized collections

### B. Metadata catalog

```text
metadata provider
    ↓
canonical catalog
```

The addon doesn't host the media.

It only exposes metadata and resolves authorized playback sources.

## 165. Catalog identity should be deterministic

A catalog item should have:

```ts
interface CatalogItem {
  readonly id: string;
  readonly type: "movie" | "series";
  readonly name: string;
  readonly poster?: string;
  readonly year?: number;
}
```

The ID must remain stable.

Bad:

```text
id = title.toLowerCase()
```

because titles can collide.

Better:

```text
imdb:tt1234567
```

or another explicitly defined canonical namespace.

## 166. Namespace IDs

Use prefixes internally:

```text
imdb:tt1234567
tmdb:123456
internal:movie:abc123
```

This avoids ambiguity between numeric identifiers.

```ts
export interface NamespacedId {
  readonly namespace: "imdb" | "tmdb" | "internal";

  readonly value: string;
}
```

## 167. Subtitle architecture

Subtitles should not be bolted onto `SourceCandidate`.

They are a separate resource.

```ts
export interface SubtitleCandidate {
  readonly id: string;

  readonly media: MediaRef;

  readonly url: string;

  readonly language: string;

  readonly format: "srt" | "vtt" | "ass" | "ssa" | "unknown";

  readonly hearingImpaired?: boolean;

  readonly forced?: boolean;

  readonly provenance: {
    readonly adapter: string;
    readonly observedAt: string;
  };

  readonly authorization: {
    readonly status: "authorized" | "unknown" | "denied";
  };
}
```

Again:

```text
stream authorization
```

and:

```text
subtitle authorization
```

are separate facts.

## 168. Subtitle pipeline

Use the same architecture:

```text
Subtitle sources
      ↓
Adapters
      ↓
Normalize
      ↓
Validate
      ↓
Policy
      ↓
Dedup
      ↓
Rank
      ↓
Stremio subtitle mapper
```

Do not create a second completely different architecture.

## 169. Subtitle ranking

Possible deterministic ordering:

```text
1. requested language
2. exact language/region match
3. forced preference
4. hearing-impaired preference
5. format
6. source ID
```

But configuration matters.

For example:

```ts
export interface SubtitlePreferences {
  readonly languages: readonly string[];

  readonly preferForced: boolean;

  readonly preferHearingImpaired: boolean;
}
```

## 170. Language matching

Do not compare:

```text
"en" === "en-US"
```

as a simple string equality rule.

Normalize language tags.

Conceptually:

```text
en
│
├── en-US
├── en-GB
├── en-AU
└── en-CA
```

The preference algorithm can distinguish:

```text
exact match
regional match
language-only match
```

## 171. Subtitle deduplication

Two subtitle providers can produce the same track.

Canonicalize:

```text
media + language + forced + hearing-impaired + normalized URL
```

But URL equality alone is insufficient.

Two URLs can represent identical subtitles.

For stronger deduplication:

```text
download authorized subtitle
      ↓
content hash
      ↓
deduplicate
```

Only do this when the source policy explicitly permits retrieving the
subtitle data.

## 172. Don't download arbitrary subtitle URLs through the addon

The same security rule applies:

```text
provider
    ↓
subtitle URL
```

does not automatically mean:

```text
addon server
    ↓
download URL
```

unless that origin is permitted by the HTTP policy.

Prefer returning a direct URL to the client when possible.

## 173. Stream and subtitle provenance

Eventually the UI should be able to communicate:

```text
Source A
1080p
H.264
English audio
```

and:

```text
Subtitle B
English
SRT
```

without leaking internal implementation details.

This suggests a presentation model.

## 174. Presentation metadata

Add optional fields:

```ts
export interface CandidatePresentation {
  readonly label?: string;

  readonly languageLabel?: string;

  readonly qualityLabel?: string;
}
```

But keep these derived:

```text
SourceCandidate
     │
     ▼
presentation derivation
```

not manually duplicated across adapters.

## 175. Quality semantics

Don't treat:

```text
1080p
```

as proof of actual video resolution.

It is a metadata claim unless verified.

Therefore:

```text
mediaInfo.width
mediaInfo.height
```

may have evidence status later:

```ts
readonly evidence:
  "source_declared"
  | "observed"
  | "verified";
```

This is more rigorous.

## 176. Candidate evidence

Extend:

```ts
export interface FieldEvidence {
  readonly origin: "source_declared" | "observed" | "derived";

  readonly observedAt?: string;
}
```

Then:

```ts
export interface MediaInfo {
  readonly width?: number;
  readonly height?: number;

  readonly evidence?: {
    readonly resolution?: FieldEvidence;
  };
}
```

This prevents the UI from confusing:

```text
provider says 1080p
```

with:

```text
we measured 1080p
```

## 177. Stream probing

If later desired:

```text
Candidate
    ↓
optional probe
    ↓
observed metadata
```

But probing should never silently replace the source declaration.

Store:

```text
declared: 1080p
observed: 1920×1080
```

rather than mutating history.

## 178. Metadata cache

Metadata has a different TTL from stream candidates.

For example conceptually:

```text
catalog: long TTL

metadata: long TTL

source candidates: short TTL

health: very short TTL
```

Therefore don't use one universal cache.

```ts
interface CacheNamespace {
  readonly name: string;
  readonly freshMs: number;
  readonly staleMs: number;
}
```

## 179. Identity cache

Identity resolution is especially suitable for caching.

```text
"tt1234567"
    ↓
canonical identity
```

The result changes much less frequently than:

```text
available stream URLs
```

Therefore identity results can use a long-lived cache namespace,
separate from and much longer than the source-candidate cache.

## 180. Identity failure cache

Be careful caching:

```text
NOT_FOUND
```

forever.

A temporary provider outage could masquerade as:

```text
media doesn't exist
```

Instead classify:

```text
NOT_FOUND
PROVIDER_UNAVAILABLE
INVALID_INPUT
AMBIGUOUS
```

and use different cache policies.

## 181. Complete domain topology

The project now becomes:

```text
                         ┌───────────────┐
                          │    Stremio    │
                          └───────┬───────┘
                                  │
                ┌─────────────────┼─────────────────┐
                │                 │                 │
                ▼                 ▼                 ▼
             Catalog             Meta             Stream
                │                                   │
                └──────────────┬────────────────────┘
                               ▼
                      Identity Resolver
                               │
                               ▼
                      Canonical Media
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
        Stream Resolver                  Subtitle Resolver
              │                                 │
              ▼                                 ▼
         Source adapters                    Sub adapters
              │                                 │
              └──────────────┬──────────────────┘
                             ▼
                     Runtime substrate
```

## 182. Repository evolution

```text
src/
├── addon/
│   ├── catalog-handler.ts
│   ├── meta-handler.ts
│   ├── stream-handler.ts
│   ├── subtitle-handler.ts
│   ├── manifest.ts
│   └── parser.ts
│
├── domain/
│   ├── media.ts
│   ├── identity.ts
│   ├── candidate.ts
│   ├── subtitle.ts
│   ├── failure.ts
│   └── result.ts
│
├── identity/
│   ├── resolver.ts
│   ├── normalize.ts
│   ├── evidence.ts
│   └── cache.ts
│
├── adapters/
│   ├── streams/
│   │   ├── interface.ts
│   │   ├── registry.ts
│   │   └── ...
│   │
│   ├── subtitles/
│   │   ├── interface.ts
│   │   ├── registry.ts
│   │   └── ...
│   │
│   └── metadata/
│       ├── interface.ts
│       └── ...
│
├── resolver/
│   ├── stream-resolver.ts
│   ├── subtitle-resolver.ts
│   ├── normalize.ts
│   ├── validate.ts
│   ├── policy.ts
│   ├── dedupe.ts
│   └── rank.ts
│
├── runtime/
│   ├── timeout.ts
│   ├── semaphore.ts
│   ├── limiter.ts
│   ├── breaker.ts
│   ├── cache.ts
│   ├── http.ts
│   └── inflight.ts
│
└── observability/
    ├── logger.ts
    ├── metrics.ts
    └── health.ts
```

## 183. The crucial abstraction: Resolver ≠ Provider

We can now state the architecture more formally.

```text
Resolver = policy-governed composition of observations

Provider adapter = translator from external representation to
                    internal candidate
```

Therefore:

```text
Provider adapter MUST NOT decide:
    global ranking
    global authorization policy
    global deduplication
    Stremio representation
```

And:

```text
Resolver MUST NOT know:
    provider JSON schema
    provider-specific pagination
    provider-specific field names
```

That is the interface contract.

## 184. Authorization boundary

The complete chain should now be:

```text
External source
      │
      ▼
Observation
      │
      ▼
Candidate
      │
      ▼
Authorization evidence
      │
      ▼
Policy decision
      │
      ▼
Eligible candidate
      │
      ▼
Ranking
      │
      ▼
Stremio
```

Never:

```text
URL found
    ↓
therefore authorized
```

## 185. What this means for the Popcorn-Time-style experience

The UX can still be:

```text
Movie
    ↓
play
    ↓
multiple sources
    ↓
quality/language choices
```

But the backend semantics are cleaner:

```text
Popcorn-Time-style UX
        ≠
Popcorn-Time-style acquisition mechanism
```

The aggregator can support authorized/public-domain/user-owned sources
without embedding unauthorized scraping or bypass mechanisms.

## 186. R3 release gate

```text
R3 — Identity + Resource Model
────────────────────────────────────

IDENTITY
[✓] Namespaced IDs
[✓] Canonical media
[✓] Movie identity
[✓] Episode identity
[✓] Identity evidence
[✓] Ambiguity preservation
[✓] Identity cache semantics

METADATA
[✓] Catalog model
[✓] Meta model
[ ] Metadata adapter implementation

STREAMS
[✓] Candidate model
[✓] Policy
[✓] Ranking
[✓] Stremio mapper

SUBTITLES
[✓] Independent candidate model
[✓] Language semantics
[✓] Policy boundary
[✓] Ranking design
[ ] Adapter implementation
[ ] Stremio subtitle integration

SECURITY
[✓] Server-side proxy avoided by default
[✓] URL credentials rejected
[✓] Redirect boundary defined
[✓] Response-size boundary
[ ] DNS/IP binding implementation

TESTING
[✓] Identity invariants defined
[✓] Stream invariants defined
[ ] Subtitle conformance tests
[ ] Metadata conformance tests
[ ] Full Stremio integration
```

**Status: PROVISIONAL architecture; not execution-verified.**

The next step is to build the **actual Stremio addon surface**:
manifest generation, `/manifest.json`, catalog/meta/stream/subtitle
handlers, deterministic request parsing, and an integration test that
treats Stremio itself as the external protocol contract.

## 187. Stremio protocol surface

Now we cross the final architectural boundary: the internal
aggregation kernel must become a real Stremio addon without allowing
the protocol layer to contaminate the domain.

The target is:

```text
                    HTTP
                     │
                     ▼
               /manifest.json
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
      /catalog     /meta       /stream
                                   │
                                   ▼
                               Resolver
                                   │
                                   ▼
                           SourceCandidate[]
                                   │
                                   ▼
                            Stremio streams
```

And later:

```text
/stream
/subtitles
```

## 188. Manifest is a contract

The manifest should describe only capabilities actually implemented.

Do not advertise:

```text
catalog
meta
stream
subtitle
```

because they are planned.

Advertise only what is currently executable.

Conceptually:

```ts
export const manifest = {
  id: "com.example.authorized-aggregator",
  version: "0.1.0",
  name: "Authorized Source Aggregator",
  description: "Aggregates eligible playback sources.",
  resources: ["stream"],
  types: ["movie", "series"],
  idPrefixes: ["tt"]
};
```

The exact SDK typing should be validated against the installed
`stremio-addon-sdk` version during implementation rather than assuming
a remembered SDK type definition is current.

That distinction matters because:

```text
architecture contract
    ≠
third-party SDK API contract
```

## 189. Manifest generation should be pure

Don't construct it dynamically from runtime state.

Bad:

```text
source A unavailable
    ↓
remove stream capability
```

The manifest describes **what the addon implements**, not today's
source health.

Therefore:

```text
manifest
    = static capability declaration
```

while:

```text
health
    = current runtime state
```

## 190. Version semantics

Use:

```text
addon version
```

for the addon contract.

Use separate versions for:

```text
candidate schema
identity schema
cache schema
```

For example:

```text
addon:       0.3.0
candidate:   v2
identity:    v1
cache:       candidate-v2
```

Do not use one version number to imply all schemas are identical.

## 191. Request parsing boundary

The HTTP layer gives you strings.

The domain requires typed values.

Therefore:

```text
HTTP string
    ↓
Stremio parser
    ↓
validated protocol request
    ↓
domain MediaRef
```

Define:

```ts
export interface StreamRequest {
  readonly type: "movie" | "series";
  readonly id: string;
}
```

Then:

```ts
export function parseStreamRequest(type: string, id: string): StreamRequest {
  if (type !== "movie" && type !== "series") {
    throw new Error("unsupported_media_type");
  }

  if (!id) {
    throw new Error("missing_media_id");
  }

  return {
    type,
    id
  };
}
```

The parser should reject malformed input before invoking identity
resolution.

## 192. Separate protocol ID from domain ID

This is subtle but important.

Stremio might provide:

```text
tt1234567:1:4
```

The domain should receive:

```json
{
  "type": "series",
  "id": "tt1234567",
  "season": 1,
  "episode": 4
}
```

Don't pass the raw string through the entire system.

That would make every internal layer understand Stremio syntax.

## 193. Domain parser

```ts
export function toMediaRef(request: StreamRequest): MediaRef {
  if (request.type === "movie") {
    return {
      type: "movie",
      id: request.id
    };
  }

  const parts = request.id.split(":");

  if (parts.length !== 3) {
    throw new Error("invalid_series_id");
  }

  const [seriesId, seasonRaw, episodeRaw] = parts;

  const season = Number(seasonRaw);

  const episode = Number(episodeRaw);

  if (
    !Number.isInteger(season) ||
    season < 1 ||
    !Number.isInteger(episode) ||
    episode < 1
  ) {
    throw new Error("invalid_episode_coordinates");
  }

  return {
    type: "series",
    id: seriesId,
    season,
    episode
  };
}
```

Now the rest of the application doesn't care that the original request
came from Stremio.

## 194. Error taxonomy at the protocol edge

Don't turn everything into HTTP 500.

Distinguish:

```text
400
invalid request

404
unsupported resource / not found

200 + empty streams
valid request, no eligible sources

500
internal failure
```

The exact behavior should follow the SDK's expected resource-handler
semantics.

The important principle is:

**A valid media request with zero eligible streams is not necessarily
an application failure.**

## 195. Stream handler

The stream handler should be tiny.

```ts
export async function handleStream(request: StreamRequest) {
  const media = toMediaRef(request);

  const result = await resolver.resolve(media);

  return {
    streams: result.candidates.map(toStremioStream)
  };
}
```

Notice what isn't here:

```text
HTTP
ranking
dedup
authorization
source selection
retry
cache
```

All of those already belong elsewhere.

## 196. Why the handler must stay boring

A protocol handler that grows into:

```text
500-line stream handler
```

is an architectural warning.

It usually means:

```text
domain logic + runtime logic + protocol logic
```

have become coupled.

The desired shape is:

```text
handler
    = parse
    + delegate
    + map
```

## 197. Catalog handler

Catalog is different.

It should not ask every source:

```text
"What movies do you have?"
```

on every request.

That creates:

```text
Stremio
    ↓
catalog
    ↓
all providers
    ↓
expensive discovery
```

Instead use a defined catalog authority.

For example:

```text
CatalogProvider
```

```ts
export interface CatalogProvider {
  list(request: CatalogRequest): Promise<readonly CatalogItem[]>;
}
```

This provider could represent:

- a curated public-domain catalog
- a user's authorized library
- a metadata-backed catalog

but the contract remains the same.

## 198. Catalog is not source discovery

This distinction is critical.

```text
Catalog: "What titles should Stremio display?"

Source discovery: "What eligible playback resources exist for this title?"
```

They may use related providers but they are not the same operation.

A title can appear in a catalog while currently having:

```text
0 eligible sources
```

and a source can exist for a title that is not part of your catalog.

## 199. Meta handler

Meta should return descriptive information.

```ts
export interface MetaProvider {
  get(media: CanonicalMedia): Promise<Meta>;
}
```

For example:

```ts
export interface Meta {
  readonly id: string;
  readonly type: "movie" | "series";
  readonly name: string;
  readonly poster?: string;
  readonly description?: string;
  readonly year?: number;
}
```

Again:

```text
metadata ≠ playback authorization
```

## 200. Metadata provider policy

Metadata sources can be treated differently from stream sources.

For example:

```text
Metadata: possibly public metadata API

Streams: only explicitly eligible/authorized sources
```

This is a useful architectural separation.

## 201. The complete request lifecycle

A movie request:

```text
GET /stream/movie/tt1234567.json
             │
             ▼
      protocol parser
             │
             ▼
       MediaRef(movie)
             │
             ▼
      identity resolver
             │
             ▼
       CanonicalMedia
             │
             ▼
       source registry
             │
      ┌──────┼──────┐
      ▼      ▼      ▼
      A      B      C
      │      │      │
      ▼      ▼      ▼
   runtime runtime runtime
      │      │      │
      └──────┼──────┘
             ▼
      SourceCandidate[]
             │
             ▼
        validation
             │
             ▼
          policy
             │
             ▼
          dedupe
             │
             ▼
          ranking
             │
             ▼
       Stremio streams
```

That is the complete control flow.

## 202. Series request

For:

```text
tt1234567:2:7
```

the pipeline becomes:

```text
series request
     │
     ▼
series identity
     │
     ▼
episode coordinate
     │
     ▼
SourceQuery {
    series,
    season: 2,
    episode: 7
}
     │
     ▼
source adapters
```

An adapter must not accidentally query:

```text
tt1234567
```

without preserving:

```text
season = 2
episode = 7
```

That deserves an explicit test.

## 203. Test: episode isolation

```ts
it("preserves season and episode", async () => {
  const adapter = new RecordingAdapter();

  registry.register(adapter);

  await resolver.resolve({
    type: "series",
    id: "tt1234567",
    season: 2,
    episode: 7
  });

  expect(adapter.lastQuery).toMatchObject({
    media: {
      season: 2,
      episode: 7
    }
  });
});
```

This catches a surprisingly damaging class of bugs.

## 204. Stremio integration test

Now don't test only internal functions.

Test the actual HTTP boundary.

Conceptually:

```text
test
    ↓
start addon server
    ↓
GET /manifest.json
    ↓
GET /stream/movie/...
    ↓
parse JSON
    ↓
assert protocol shape
```

This is the first test that actually validates:

```text
our code + SDK + HTTP server + manifest + handler
```

## 205. Manifest contract test

```ts
it("serves a valid manifest", async () => {
  const response = await fetch(`${baseUrl}/manifest.json`);

  expect(response.status).toBe(200);

  const manifest = await response.json();

  expect(manifest.id).toBeTruthy();

  expect(manifest.version).toBeTruthy();

  expect(manifest.resources).toContain("stream");

  expect(manifest.types).toContain("movie");
});
```

This should become a release gate.

## 206. Stream contract test

```ts
it("returns Stremio-compatible streams", async () => {
  const response = await fetch(`${baseUrl}/stream/movie/tt1234567.json`);

  expect(response.status).toBe(200);

  const body = await response.json();

  expect(Array.isArray(body.streams)).toBe(true);

  for (const stream of body.streams) {
    expect(typeof stream.url).toBe("string");
  }
});
```

The test deliberately avoids requiring a particular real source.

It tests the protocol contract.

## 207. Contract fixtures

Create:

```text
test/
└── fixtures/
    ├── movie.json
    ├── series.json
    ├── candidate.json
    ├── subtitle.json
    └── manifest.json
```

Fixtures should represent:

```text
valid
invalid
ambiguous
empty
partial
```

not just happy paths.

## 208. Golden protocol fixtures

A powerful approach is:

```text
input fixture
      ↓
resolver
      ↓
normalized output
      ↓
canonical JSON
      ↓
compare
```

For deterministic outputs, this gives a simple regression mechanism.

But don't snapshot volatile values such as:

```text
timestamps
request IDs
latency
```

unless explicitly normalized.

## 209. Canonical JSON

For protocol fixtures, stable serialization helps.

The test should normalize:

```text
object key order
dynamic timestamps
IDs
```

before comparison.

For stronger artifact evidence, use canonical JSON rather than relying
on incidental JavaScript object ordering.

## 210. Adapter conformance suite

Every adapter should pass the same tests.

Define:

```ts
interface AdapterFactory {
  create(): SourceAdapter;
}
```

Then a shared suite:

```text
describeAdapterContract(createAdapter)
```

Tests:

```text
supports()
resolve()
timeout
abort
malformed response
empty result
authorization status
candidate normalization
```

Now adding a source means:

```text
implement adapter + pass conformance suite
```

rather than inventing bespoke tests.

## 211. Adapter ≠ permission

Even if an adapter passes every structural test:

```text
adapter conformance = PASS
```

that does not mean:

```text
source authorization = PASS
```

The latter must be established by the adapter's configured source
policy and evidence.

This distinction should remain visible in CI.

## 212. Source configuration

A source adapter should declare its authorization model.

```ts
export interface SourcePolicy {
  readonly authorizationMode:
    | "configured_owned"
    | "public_domain"
    | "licensed"
    | "unknown";
}
```

Then startup can reject:

```text
authorizationMode = "unknown"
```

for production deployments if desired.

This is stronger than hoping policy is respected at runtime.

## 213. Configuration admission

Use a startup gate:

```text
config
    ↓
validate
    ↓
policy admission
    ↓
construct adapter
```

not:

```text
construct adapter
    ↓
discover later that configuration is unsafe
```

So:

```text
INVALID CONFIGURATION
        ↓
startup failure
```

rather than:

```text
runtime surprises
```

## 214. Source registry admission

The registry can become:

```ts
export interface AdapterAdmission {
  readonly allowed: boolean;
  readonly reasons: readonly string[];
}
```

Then:

```text
register(adapter, admission)
```

or better:

```text
validate adapter configuration
        ↓
admitted adapter
        ↓
registry
```

The registry should contain only operationally admitted adapters.

## 215. No dynamic arbitrary adapters

Avoid an endpoint such as:

```text
POST /add-source
{
  "url": "..."
}
```

unless you have a very strong trust model.

Otherwise the addon becomes:

```text
remote SSRF executor
```

The source registry should normally be configured by deployment
configuration, not by arbitrary HTTP callers.

## 216. Security boundary map

At this point:

```text
                    UNTRUSTED
                        │
              ┌─────────┴─────────┐
              │                   │
       Stremio request       Provider response
              │                   │
              ▼                   ▼
        parser/validator     schema validation
              │                   │
              └─────────┬─────────┘
                        ▼
                   domain types
                        │
                        ▼
                     policy
                        │
                        ▼
                   eligible data
                        │
                        ▼
                   presentation
```

Every boundary transforms untrusted representation into a constrained
internal representation.

## 217. Failure taxonomy for the whole addon

We can now unify errors.

```ts
export type FailureCode =
  | "invalid_request"
  | "identity_not_found"
  | "identity_ambiguous"
  | "source_empty"
  | "source_timeout"
  | "source_aborted"
  | "source_rate_limited"
  | "source_circuit_open"
  | "source_invalid_response"
  | "source_network_error"
  | "candidate_invalid"
  | "candidate_not_authorized"
  | "internal_error";
```

Do not expose all of these directly to Stremio.

They are internal diagnostic semantics.

## 218. Result envelope

Instead of returning only arrays internally:

```ts
export interface ResolverResult<T> {
  readonly status: "success" | "empty" | "partial" | "failed";

  readonly value: readonly T[];

  readonly failures: readonly Failure[];

  readonly sourceCount: number;

  readonly durationMs: number;
}
```

This lets the system distinguish:

```text
zero sources because none exist
```

from:

```text
zero sources because every provider failed
```

That distinction is operationally crucial.

## 219. Example

Case A:

```text
source A → empty
source B → empty
source C → empty
```

Result:

```text
status = empty
```

Case B:

```text
source A → timeout
source B → network error
source C → circuit open
```

Result:

```text
status = failed
```

Case C:

```text
source A → success
source B → timeout
source C → empty
```

Result:

```text
status = partial
```

All three could produce:

```json
{
  "streams": []
}
```

at the Stremio boundary, but they are **not the same internal event**.

## 220. This is where observability becomes evidence architecture

We can now formalize:

```text
Protocol result
    ≠ Resolver result
    ≠ Adapter result
    ≠ HTTP result
```

For example:

```text
HTTP: 200
Adapter: success
Resolver: partial
Policy: 3 candidates rejected
Final: 2 streams
```

That's much more useful than a single boolean:

```text
success: true
```

## 221. End-to-end state machine

The addon is now approximately:

```text
REQUEST
   │
   ▼
PARSE
   │
   ├── invalid ───────────────→ REJECT
   │
   ▼
IDENTIFY
   │
   ├── ambiguous ────────────→ NO_RESOLUTION
   │
   ├── not found ────────────→ NO_RESOLUTION
   │
   ▼
DISCOVER
   │
   ▼
NORMALIZE
   │
   ▼
VALIDATE
   │
   ▼
AUTHORIZE
   │
   ├── rejected ─────────────→ DISCARD
   │
   ▼
DEDUP
   │
   ▼
RANK
   │
   ▼
MAP
   │
   ▼
STREMIO RESPONSE
```

This is now a complete semantic pipeline.

## 222. R4 — Protocol Conformance Gate

```text
R4
────────────────────────────────────────

MANIFEST
[✓] Static capability declaration
[✓] Versioned
[✓] Type declarations
[ ] SDK-version compile verification

PARSING
[✓] Movie IDs
[✓] Series IDs
[✓] Season/episode preservation
[✓] Invalid input rejection

STREAM
[✓] Handler boundary
[✓] Candidate → stream mapping
[✓] Empty result semantics
[ ] Live SDK integration test

CATALOG
[✓] Contract
[ ] Provider implementation

META
[✓] Contract
[ ] Provider implementation

SUBTITLE
[✓] Domain model
[✓] Resolver architecture
[ ] Protocol implementation

ERRORS
[✓] Internal failure taxonomy
[✓] Partial/empty/failed distinction

SECURITY
[✓] No arbitrary source registration
[✓] No automatic media proxy
[✓] Protocol/domain separation

TESTING
[✓] Unit contracts
[✓] End-to-end test design
[ ] Actual CI execution
[ ] Container smoke test
```

### Status

**R4 = ARCHITECTURALLY DEFINED / NOT EXECUTION-VERIFIED**

The next major step is no longer another abstraction layer. It is the
**actual executable reference implementation**:

```text
package.json
tsconfig.json
src/index.ts
manifest
domain
runtime
resolver
one explicitly authorized/public-domain adapter
tests
Dockerfile
compose.yaml
CI
```

Then we can freeze the first **`v0.1.0-conformance` baseline**, run the
entire suite, and only after evidence exists begin adding additional
source adapters.

## 223. Executable reference implementation

We have reached the point where continuing to add abstractions would
be counterproductive.

The next milestone is:

**Turn the architecture into a small, executable, testable addon
kernel before adding more providers.**

The first implementation should intentionally have **one safe fixture
adapter** representing an explicitly authorized/public-domain/user-owned
source. Everything else can plug into the same contract later.

## 224. Freeze the v0.1 boundary

Before writing implementation code, freeze this dependency direction:

```text
┌──────────────────────────────────────────────────┐
│                    addon/                          │
│              Stremio protocol only                 │
└───────────────────────┬──────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────┐
│                  application                       │
│       identity / resolver / orchestration          │
└───────────────┬──────────────────┬───────────────┘
                 │                  │
                 ▼                  ▼
┌──────────────────────┐   ┌──────────────────────┐
│       domain          │   │       runtime         │
│ media/candidates/      │   │ timeout/cache/http/   │
│ policy/results         │   │ limiter/breaker       │
└──────────────────────┘   └──────────────────────┘
                 ▲                  ▲
                 │                  │
                 └────────┬─────────┘
                          │
                          ▼
                   source adapters
```

Dependency rule:

```text
addon → application → domain
                 ↘ runtime

adapters → domain + runtime interfaces
```

Never:

```text
domain → Stremio SDK
domain → fetch
domain → Pino
domain → cache implementation
```

The domain remains portable.

## 225. Project tree

The concrete tree becomes:

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
│   │   └── stream-handler.ts
│   │
│   ├── application/
│   │   └── resolver.ts
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
│   │   └── fixture/
│   │       └── adapter.ts
│   │
│   ├── resolver/
│   │   ├── validate.ts
│   │   ├── policy.ts
│   │   ├── dedupe.ts
│   │   └── rank.ts
│   │
│   ├── runtime/
│   │   ├── timeout.ts
│   │   ├── semaphore.ts
│   │   ├── limiter.ts
│   │   ├── breaker.ts
│   │   ├── cache.ts
│   │   ├── inflight.ts
│   │   └── http.ts
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
    ├── domain/
    ├── runtime/
    ├── resolver/
    ├── addon/
    └── integration/
```

## 226. `package.json`

For the first implementation, keep dependencies deliberately small.

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
    "pino": "^9.0.0",
    "stremio-addon-sdk": "^1.6.0",
    "zod": "^4.0.0"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "tsx": "^4.0.0",
    "typescript": "^5.0.0",
    "vitest": "^3.0.0"
  }
}
```

These versions are **implementation placeholders**, not a claim that
they are the latest releases. Before freezing `package-lock.json`,
resolve the actual versions and record them as build evidence.

## 227. TypeScript configuration

```json
{
  "compilerOptions": {
    "target": "ES2023",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",

    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,

    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,

    "forceConsistentCasingInFileNames": true,

    "esModuleInterop": true,
    "skipLibCheck": true,

    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src/**/*.ts"]
}
```

The important settings are:

```text
strict
noUncheckedIndexedAccess
exactOptionalPropertyTypes
noImplicitOverride
```

They make the domain contracts considerably harder to accidentally
weaken.

## 228. Domain: `media.ts`

```ts
export type MediaType = "movie" | "series";

export interface MediaRef {
  readonly type: MediaType;
  readonly id: string;
  readonly season?: number;
  readonly episode?: number;
}
```

No Stremio dependency.

No provider dependency.

No HTTP dependency.

## 229. Domain: candidate

```ts
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

This is the central internal object.

## 230. Domain: failures

```ts
export type FailureCode =
  | "invalid_request"
  | "identity_not_found"
  | "identity_ambiguous"
  | "source_empty"
  | "source_timeout"
  | "source_aborted"
  | "source_rate_limited"
  | "source_circuit_open"
  | "source_invalid_response"
  | "source_network_error"
  | "candidate_invalid"
  | "candidate_not_authorized"
  | "internal_error";

export interface Failure {
  readonly code: FailureCode;
  readonly sourceId?: string;
  readonly message?: string;
}
```

Keep the machine-readable code stable.

Human-readable `message` remains diagnostic.

## 231. Domain: result

```ts
import type { SourceCandidate } from "./candidate.js";
import type { Failure } from "./failure.js";
import type { MediaRef } from "./media.js";

export type ResolutionStatus = "success" | "empty" | "partial" | "failed";

export interface ResolutionResult {
  readonly media: MediaRef;

  readonly status: ResolutionStatus;

  readonly candidates: readonly SourceCandidate[];

  readonly failures: readonly Failure[];

  readonly sourceCount: number;

  readonly durationMs: number;
}
```

Now the resolver has a meaningful semantic result rather than just:

```text
SourceCandidate[]
```

## 232. Adapter contract

```ts
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

  resolve(
    media: MediaRef,
    ctx: ResolveContext
  ): Promise<readonly SourceCandidate[]>;
}
```

The contract is intentionally small.

## 233. Adapter registry

```ts
import type { MediaRef } from "../domain/media.js";
import type { SourceAdapter } from "./interface.js";

export class SourceRegistry {
  private readonly adapters = new Map<string, SourceAdapter>();

  register(adapter: SourceAdapter): void {
    if (this.adapters.has(adapter.id)) {
      throw new Error(`duplicate_adapter:${adapter.id}`);
    }

    this.adapters.set(adapter.id, adapter);
  }

  all(): readonly SourceAdapter[] {
    return [...this.adapters.values()];
  }

  applicable(media: MediaRef): readonly SourceAdapter[] {
    return this.all().filter(adapter => adapter.supports(media));
  }
}
```

## 234. Validation

```ts
import type { SourceCandidate } from "../domain/candidate.js";

export function validateCandidate(candidate: SourceCandidate): boolean {
  try {
    const url = new URL(candidate.location.url);

    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return false;
    }

    if (!candidate.sourceId) {
      return false;
    }

    if (!candidate.provenance.adapter) {
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
  } catch {
    return false;
  }
}
```

This is structural validation.

It does **not** establish authorization.

## 235. Policy

```ts
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

This is intentionally strict.

`unknown` does not become `authorized`.

## 236. Deduplication

```ts
import type { SourceCandidate } from "../domain/candidate.js";

function canonicalUrl(raw: string): string {
  const url = new URL(raw);

  url.hash = "";

  return url.toString();
}

function key(candidate: SourceCandidate): string {
  const media = candidate.media;

  return [
    media.type,
    media.id,
    media.season ?? "",
    media.episode ?? "",
    canonicalUrl(candidate.location.url)
  ].join("|");
}

export function dedupeCandidates(
  candidates: readonly SourceCandidate[]
): readonly SourceCandidate[] {
  const seen = new Set<string>();

  const result: SourceCandidate[] = [];

  for (const candidate of candidates) {
    const k = key(candidate);

    if (seen.has(k)) {
      continue;
    }

    seen.add(k);
    result.push(candidate);
  }

  return result;
}
```

## 237. Deterministic ranking

```ts
import type { SourceCandidate } from "../domain/candidate.js";

function pixels(candidate: SourceCandidate): number {
  return (
    (candidate.mediaInfo.width ?? 0) * (candidate.mediaInfo.height ?? 0)
  );
}

export function rankCandidates(
  candidates: readonly SourceCandidate[]
): readonly SourceCandidate[] {
  return [...candidates].sort((a, b) => {
    if (a.capabilities.directPlayback !== b.capabilities.directPlayback) {
      return a.capabilities.directPlayback ? -1 : 1;
    }

    const resolution = pixels(b) - pixels(a);

    if (resolution !== 0) {
      return resolution;
    }

    const bitrate = (b.mediaInfo.bitrate ?? 0) - (a.mediaInfo.bitrate ?? 0);

    if (bitrate !== 0) {
      return bitrate;
    }

    return a.sourceId.localeCompare(b.sourceId);
  });
}
```

The final `sourceId` comparison is important.

Without it, equal candidates can depend on upstream ordering.

## 238. Timeout implementation

```ts
export async function withTimeout<T>(
  operation: (signal: AbortSignal) => Promise<T>,
  timeoutMs: number,
  parentSignal?: AbortSignal
): Promise<T> {
  const controller = new AbortController();

  const abortFromParent = () => {
    controller.abort(parentSignal?.reason);
  };

  if (parentSignal) {
    if (parentSignal.aborted) {
      abortFromParent();
    } else {
      parentSignal.addEventListener("abort", abortFromParent, {
        once: true
      });
    }
  }

  const timer = setTimeout(() => {
    controller.abort(new Error("timeout"));
  }, timeoutMs);

  try {
    return await operation(controller.signal);
  } finally {
    clearTimeout(timer);

    parentSignal?.removeEventListener("abort", abortFromParent);
  }
}
```

## 239. Semaphore

```ts
export class Semaphore {
  private active = 0;

  private readonly queue: Array<() => void> = [];

  constructor(private readonly capacity: number) {
    if (capacity < 1) {
      throw new Error("invalid_semaphore_capacity");
    }
  }

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

## 240. Circuit breaker

Use the previously defined state machine, but make `half-open` a
controlled probe.

```ts
export type BreakerState = "closed" | "open" | "half-open";

export class CircuitBreaker {
  private state: BreakerState = "closed";

  private failures = 0;

  private openedAt = 0;

  constructor(
    private readonly threshold = 5,
    private readonly cooldownMs = 30_000
  ) {}

  state(): BreakerState {
    this.refresh();

    return this.state;
  }

  allow(): boolean {
    this.refresh();

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

  private refresh(): void {
    if (
      this.state === "open" &&
      Date.now() - this.openedAt >= this.cooldownMs
    ) {
      this.state = "half-open";
    }
  }
}
```

## 241. Source execution status

```ts
export type AdapterStatus =
  | "success"
  | "empty"
  | "timeout"
  | "aborted"
  | "rate_limited"
  | "circuit_open"
  | "invalid_response"
  | "network_error"
  | "error";

export interface AdapterExecution {
  readonly adapterId: string;
  readonly status: AdapterStatus;
  readonly durationMs: number;
  readonly candidates: readonly SourceCandidate[];
  readonly error?: string;
}
```

Now the resolver can preserve partial failures.

## 242. Failure classification

```ts
export function classifyError(error: unknown): AdapterStatus {
  if (error instanceof Error && error.message === "timeout") {
    return "timeout";
  }

  if (error instanceof DOMException && error.name === "AbortError") {
    return "aborted";
  }

  if (error instanceof TypeError) {
    return "network_error";
  }

  return "error";
}
```

In production, make this more precise around the actual HTTP
implementation.

## 243. Resolver implementation

Now the pieces become one executable kernel.

```ts
import type { MediaRef } from "../domain/media.js";

import type { SourceCandidate } from "../domain/candidate.js";

import type { Failure } from "../domain/failure.js";

import type { ResolutionResult } from "../domain/result.js";

import type { SourceAdapter } from "../adapters/interface.js";

import { validateCandidate } from "./validate.js";

import { evaluatePolicy } from "./policy.js";

import { dedupeCandidates } from "./dedupe.js";

import { rankCandidates } from "./rank.js";

import { withTimeout } from "../runtime/timeout.js";

import { Semaphore } from "../runtime/semaphore.js";

export interface ResolverConfig {
  readonly totalTimeoutMs: number;
  readonly sourceTimeoutMs: number;
  readonly concurrency: number;
  readonly preferredLanguages: readonly string[];
}

export class Resolver {
  private readonly semaphore;

  constructor(
    private readonly adapters: readonly SourceAdapter[],
    private readonly config: ResolverConfig
  ) {
    this.semaphore = new Semaphore(config.concurrency);
  }

  async resolve(media: MediaRef): Promise<ResolutionResult> {
    const started = performance.now();

    const controller = new AbortController();

    const totalTimer = setTimeout(
      () => controller.abort(new Error("resolution_timeout")),
      this.config.totalTimeoutMs
    );

    try {
      const applicable = this.adapters.filter(adapter =>
        adapter.supports(media)
      );

      const executions = await Promise.all(
        applicable.map(adapter =>
          this.execute(adapter, media, controller.signal)
        )
      );

      const failures: Failure[] = [];

      const candidates: SourceCandidate[] = [];

      for (const execution of executions) {
        if (execution.status !== "success") {
          failures.push({
            code: this.failureCode(execution.status),
            sourceId: execution.adapterId,
            message: execution.error
          });

          continue;
        }

        for (const candidate of execution.candidates) {
          if (!validateCandidate(candidate)) {
            failures.push({
              code: "candidate_invalid",
              sourceId: execution.adapterId
            });

            continue;
          }

          const decision = evaluatePolicy(candidate);

          if (!decision.allowed) {
            failures.push({
              code: "candidate_not_authorized",
              sourceId: candidate.sourceId,
              message: decision.reasons.join(",")
            });

            continue;
          }

          candidates.push(candidate);
        }
      }

      const unique = dedupeCandidates(candidates);

      const ranked = rankCandidates(unique);

      return {
        media,
        status: this.status(applicable.length, executions.length, ranked.length),
        candidates: ranked,
        failures,
        sourceCount: applicable.length,
        durationMs: performance.now() - started
      };
    } finally {
      clearTimeout(totalTimer);
    }
  }

  private async execute(
    adapter: SourceAdapter,
    media: MediaRef,
    parentSignal: AbortSignal
  ): Promise<AdapterExecution> {
    const started = performance.now();

    const release = await this.semaphore.acquire();

    try {
      const candidates = await withTimeout(
        signal =>
          adapter.resolve(media, {
            signal,
            timeoutMs: this.config.sourceTimeoutMs,
            preferredLanguages: this.config.preferredLanguages
          }),
        this.config.sourceTimeoutMs,
        parentSignal
      );

      return {
        adapterId: adapter.id,

        status: candidates.length > 0 ? "success" : "empty",

        durationMs: performance.now() - started,

        candidates
      };
    } catch (error) {
      return {
        adapterId: adapter.id,
        status: this.classify(error),
        durationMs: performance.now() - started,
        candidates: [],
        error: error instanceof Error ? error.message : String(error)
      };
    } finally {
      release();
    }
  }

  private classify(error: unknown): AdapterStatus {
    if (error instanceof Error && error.message === "timeout") {
      return "timeout";
    }

    if (error instanceof DOMException && error.name === "AbortError") {
      return "aborted";
    }

    return "error";
  }

  private failureCode(status: AdapterStatus): Failure["code"] {
    switch (status) {
      case "timeout":
        return "source_timeout";
      case "aborted":
        return "source_aborted";
      case "rate_limited":
        return "source_rate_limited";
      case "circuit_open":
        return "source_circuit_open";
      case "invalid_response":
        return "source_invalid_response";
      case "network_error":
        return "source_network_error";
      default:
        return "internal_error";
    }
  }

  private status(
    sourceCount: number,
    executionCount: number,
    candidateCount: number
  ): ResolutionResult["status"] {
    if (candidateCount > 0) {
      return executionCount < sourceCount ? "partial" : "success";
    }

    return executionCount === sourceCount ? "empty" : "failed";
  }
}
```

There is one deliberate next refinement here: integrate the breaker and
limiter directly into `execute()` rather than leaving them as
conceptual infrastructure.

## 244. Fixture adapter

We need one adapter that doesn't depend on an external service.

```ts
import type { SourceAdapter, ResolveContext } from "../interface.js";

import type { MediaRef } from "../../domain/media.js";

import type { SourceCandidate } from "../../domain/candidate.js";

export class FixtureAdapter implements SourceAdapter {
  readonly id = "fixture-authorized";

  readonly name = "Authorized Fixture Source";

  constructor(private readonly candidates: readonly SourceCandidate[]) {}

  supports(media: MediaRef): boolean {
    return this.candidates.some(
      candidate =>
        candidate.media.type === media.type &&
        candidate.media.id === media.id &&
        candidate.media.season === media.season &&
        candidate.media.episode === media.episode
    );
  }

  async resolve(
    media: MediaRef,
    _ctx: ResolveContext
  ): Promise<readonly SourceCandidate[]> {
    return this.candidates.filter(
      candidate =>
        candidate.media.type === media.type &&
        candidate.media.id === media.id &&
        candidate.media.season === media.season &&
        candidate.media.episode === media.episode
    );
  }
}
```

This adapter is deliberately boring.

That's a feature.

## 245. Fixture candidate

```ts
export const fixtureCandidate = {
  sourceId: "fixture-authorized",

  media: {
    type: "movie",
    id: "tt1234567"
  },

  location: {
    url: "https://media.example.test/movie.mp4"
  },

  mediaInfo: {
    container: "mp4",
    videoCodec: "h264",
    audioCodec: "aac",
    width: 1920,
    height: 1080
  },

  language: {
    audio: ["en"]
  },

  provenance: {
    adapter: "fixture-authorized",
    sourceRecordId: "fixture-001",
    observedAt: "2026-01-01T00:00:00.000Z"
  },

  capabilities: {
    directPlayback: true,
    seekable: true
  },

  authorization: {
    status: "authorized",
    basis: "test_fixture"
  }
} satisfies SourceCandidate;
```

The URL is illustrative and is **not expected to be playable**. It
exists to test protocol semantics.

## 246. Stremio mapping

```ts
export interface StremioStream {
  readonly name?: string;
  readonly title?: string;
  readonly url: string;
}

export function toStremioStream(candidate: SourceCandidate): StremioStream {
  const quality =
    candidate.mediaInfo.width && candidate.mediaInfo.height
      ? `${candidate.mediaInfo.width}x${candidate.mediaInfo.height}`
      : undefined;

  return {
    name: candidate.sourceId,

    title: [quality, candidate.mediaInfo.videoCodec, candidate.mediaInfo.audioCodec]
      .filter(value => value !== undefined)
      .join(" • "),

    url: candidate.location.url
  };
}
```

The mapper remains pure.

## 247. Protocol parser

```ts
import type { MediaType, MediaRef } from "../domain/media.js";

export function parseMediaRef(type: string, id: string): MediaRef {
  if (type !== "movie" && type !== "series") {
    throw new Error("unsupported_media_type");
  }

  if (!id) {
    throw new Error("missing_media_id");
  }

  if (type === "movie") {
    return {
      type: "movie",
      id
    };
  }

  const parts = id.split(":");

  if (parts.length !== 3) {
    throw new Error("invalid_series_id");
  }

  const [seriesId, seasonRaw, episodeRaw] = parts;

  const season = Number(seasonRaw);

  const episode = Number(episodeRaw);

  if (
    !Number.isInteger(season) ||
    season < 1 ||
    !Number.isInteger(episode) ||
    episode < 1
  ) {
    throw new Error("invalid_episode_coordinates");
  }

  return {
    type: "series",
    id: seriesId,
    season,
    episode
  };
}
```

## 248. Manifest

Keep it isolated:

```ts
export const manifest = {
  id: "com.example.authorized-aggregator",

  version: "0.1.0",

  name: "Authorized Source Aggregator",

  description: "Aggregates eligible playback sources.",

  resources: ["stream"],

  types: ["movie", "series"],

  idPrefixes: ["tt"]
} as const;
```

The actual SDK's accepted manifest shape must be checked by the
compiler against the installed package before release.

## 249. Addon assembly

The application composition root should be explicit.

Conceptually:

```ts
const registry = new SourceRegistry();

registry.register(new FixtureAdapter([fixtureCandidate]));

const resolver = new Resolver(registry.all(), {
  totalTimeoutMs: 4000,
  sourceTimeoutMs: 2500,
  concurrency: 6,
  preferredLanguages: ["en"]
});
```

Then the Stremio layer gets only:

```text
manifest + resolver
```

## 250. This gives us the first real vertical slice

```text
                ┌─────────────┐
                 │   Stremio   │
                 └──────┬──────┘
                        │
                        ▼
                  HTTP handler
                        │
                        ▼
                   parseMediaRef
                        │
                        ▼
                     Resolver
                        │
                        ▼
                 Fixture Adapter
                        │
                        ▼
                  SourceCandidate
                        │
                        ▼
                     Policy
                        │
                        ▼
                     Dedup
                        │
                        ▼
                     Ranking
                        │
                        ▼
                 StremioStream
```

That is the first **vertical slice**.

## 251. Test the vertical slice before adding anything else

### Parser tests

```ts
it("parses a movie", () => {
  expect(parseMediaRef("movie", "tt1234567")).toEqual({
    type: "movie",
    id: "tt1234567"
  });
});
```

Series:

```ts
it("parses an episode", () => {
  expect(parseMediaRef("series", "tt1234567:2:7")).toEqual({
    type: "series",
    id: "tt1234567",
    season: 2,
    episode: 7
  });
});
```

Invalid:

```ts
it("rejects malformed episode IDs", () => {
  expect(() => parseMediaRef("series", "tt1234567:abc:7")).toThrow(
    "invalid_episode_coordinates"
  );
});
```

## 252. Policy invariant

```ts
it("rejects unknown authorization", async () => {
  const candidate = structuredClone(fixtureCandidate);

  candidate.authorization = {
    status: "unknown"
  };

  const adapter = new FixtureAdapter([candidate]);

  const resolver = new Resolver([adapter], config);

  const result = await resolver.resolve(candidate.media);

  expect(result.candidates).toHaveLength(0);

  expect(
    result.failures.some(failure => failure.code === "candidate_not_authorized")
  ).toBe(true);
});
```

This is one of the most important tests in the entire repository.

## 253. Ranking invariant

```ts
it("ranks higher resolution first", () => {
  const ranked = rankCandidates([
    makeCandidate({
      sourceId: "low",
      width: 1280,
      height: 720
    }),

    makeCandidate({
      sourceId: "high",
      width: 1920,
      height: 1080
    })
  ]);

  expect(ranked.map(x => x.sourceId)).toEqual(["high", "low"]);
});
```

## 254. Determinism test

Run the same input many times:

```ts
it("produces deterministic ranking", () => {
  const candidates = [
    makeCandidate({ sourceId: "z" }),

    makeCandidate({ sourceId: "a" }),

    makeCandidate({ sourceId: "m" })
  ];

  const first = rankCandidates(candidates);

  for (let i = 0; i < 100; i++) {
    expect(rankCandidates(candidates)).toEqual(first);
  }
});
```

The stronger future version should randomize input order as well.

## 255. Timeout test

```ts
it("aborts a slow adapter", async () => {
  const adapter: SourceAdapter = {
    id: "slow",
    name: "Slow",
    supports: () => true,
    resolve: async (_media, ctx) => {
      await new Promise<void>((_, reject) => {
        const timer = setTimeout(() => {}, 10_000);

        ctx.signal.addEventListener(
          "abort",
          () => {
            clearTimeout(timer);

            reject(new Error("aborted"));
          },
          { once: true }
        );
      });

      return [];
    }
  };

  // Resolver test...
});
```

The exact test implementation should avoid hanging the test runner,
but the invariant is:

```text
timeout
   →
AbortSignal
   →
underlying operation stops
```

## 256. Concurrency test

Create 20 fake adapters.

Each increments:

```ts
active++;
maxActive = Math.max(maxActive, active);
```

and sleeps briefly.

Configure:

```text
capacity = 4
```

Then assert:

```ts
expect(maxActive).toBeLessThanOrEqual(4);
```

This converts a runtime design assumption into executable evidence.

## 257. Integration test

The final test should be:

```text
npm run check
       │
       ├── typecheck
       ├── unit tests
       └── build
```

Then:

```text
start built server
       │
       ├── GET /manifest.json
       │
       └── GET /stream/movie/...
```

This is the first point where:

```text
"the code compiles"
```

and:

```text
"the addon actually speaks its protocol"
```

are independently demonstrated.

## 258. CI becomes execution authority

Given the evidence rule:

**NO EVIDENCE → NO VERIFIED CLAIM**

the repository should eventually have:

```text
CI
│
├── npm ci
├── npm run typecheck
├── npm test
├── npm run build
├── container build
└── integration smoke test
```

Only CI results should create:

```text
VERIFIED
```

status.

A local assistant-generated source tree is merely:

```text
PROVISIONAL
```

until execution evidence exists.

## 259. First CI workflow

```yaml
name: conformance

on:
  push:
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm

      - run: npm ci
      - run: npm run typecheck
      - run: npm test
      - run: npm run build
```

The exact action versions should also be frozen through the repository
lock/configuration process.

## 260. Container

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

## 261. Container health

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

## 262. Compose

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

## 263. Runtime health

Minimal native Node server:

```ts
import { createServer } from "node:http";

export function startHealthServer(port: number) {
  const server = createServer((req, res) => {
    if (req.url === "/health/live") {
      res.writeHead(200, {
        "content-type": "application/json"
      });

      res.end(JSON.stringify({ status: "ok" }));

      return;
    }

    if (req.url === "/health/ready") {
      res.writeHead(200, {
        "content-type": "application/json"
      });

      res.end(JSON.stringify({ status: "ready" }));

      return;
    }

    res.writeHead(404);
    res.end();
  });

  server.listen(port);

  return server;
}
```

## 264. Don't make readiness depend on all providers

This would be a mistake:

```text
provider B down
     ↓
addon NOT READY
```

if provider B is optional.

Instead:

```text
required runtime dependency down
       ↓
NOT READY

optional source unavailable
       ↓
DEGRADED
```

That distinction matters enormously once you have multiple sources.

## 265. First operational dashboard

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

## 266. The first genuine release gate

The project should now have:

```text
G0  Domain contracts                 ✓
G1  Adapter contracts                ✓
G2  Resolver                         ✓
G3  Candidate validation             ✓
G4  Authorization policy             ✓
G5  Deduplication                    ✓
G6  Deterministic ranking            ✓

G7  Abort propagation                ✓
G8  Timeout                          ✓
G9  Concurrency limit                ✓
G10 Rate limiting                    PARTIAL
G11 Circuit breaker                  PARTIAL
G12 Cache abstraction                ✓
G13 In-flight dedup                  ✓
G14 Safe HTTP boundary               PARTIAL
G15 Health endpoints                 ✓

G16 Stremio manifest                 ✓
G17 Movie request parsing            ✓
G18 Series request parsing           ✓
G19 Stream mapping                   ✓
G20 Protocol integration test        TODO

G21 Metadata                         TODO
G22 Catalog                          TODO
G23 Subtitles                        TODO

G24 Docker build                     TODO
G25 CI execution                     TODO
G26 Release evidence                 TODO
```

Notice the deliberate wording:

**implemented in blueprint/code ≠ verified by execution.**

## 267. The first frozen baseline

The first tag should eventually be something like:

```text
v0.1.0-conformance
```

But **do not create that tag merely because the code has been
written**.

The admission condition should be:

```text
npm ci
   ↓
typecheck PASS
   ↓
unit tests PASS
   ↓
integration tests PASS
   ↓
build PASS
   ↓
container build PASS
   ↓
container smoke test PASS
   ↓
CI PASS
   ↓
artifact digest recorded
   ↓
tag
```

That is much closer to the:

```text
freeze → formalize → implement → test → release gate → tag
```

workflow.

## 268. The architecture has reached an important point

We can now distinguish four separate truths:

```text
1. CODE TRUTH
   What the source tree says.

2. EXECUTION TRUTH
   What the test/build actually demonstrated.

3. SOURCE TRUTH
   What an external provider actually returned.

4. AUTHORIZATION TRUTH
   What the deployment is actually permitted to use.
```

None should be silently substituted for another.

For example:

```text
"adapter returns URL"
```

doesn't prove:

```text
"URL is authorized."
```

and:

```text
"tests pass"
```

doesn't prove:

```text
"the external source is currently available."
```

And:

```text
"HTTP 200"
```

doesn't prove:

```text
"the media plays."
```

## 269. Next architectural layer

After this executable baseline, the next expansion should be **not
another generic abstraction**.

It should be:

```text
                v0.1 kernel
                     │
           ┌─────────┼─────────┐
           ▼         ▼         ▼
       Metadata    Subtitle   Source
        adapter    adapter    adapters
           │         │         │
           └─────────┴─────────┘
                     │
                     ▼
              unified identity
```

with one particularly important feature:

### source capability negotiation

Instead of asking every adapter:

```text
"Can you resolve this?"
```

we eventually ask:

```ts
interface SourceCapabilities {
  readonly mediaTypes: readonly MediaType[];

  readonly supportsMovies: boolean;
  readonly supportsSeries: boolean;
  readonly supportsEpisodes: boolean;

  readonly providesMetadata: boolean;
  readonly providesStreams: boolean;
  readonly providesSubtitles: boolean;

  readonly requiresIdentity: readonly IdentityKind[];

  readonly authorizationMode:
    | "configured_owned"
    | "public_domain"
    | "licensed"
    | "unknown";
}
```

That gives the registry enough information to perform **admission and
routing before execution**, rather than discovering incompatibilities
only after a source has been called.

That becomes the foundation for the next stage:

```text
Capability
     ↓
Admission
     ↓
Identity matching
     ↓
Source selection
     ↓
Execution
     ↓
Evidence
     ↓
Policy
     ↓
Rank
     ↓
Stremio
```

**Current status: PROVISIONAL until actually built and executed.**

## 270. Capability-aware source routing

The next layer should make the registry **semantically aware** rather
than treating every adapter as interchangeable.

The key distinction is:

```text
Adapter exists
    ≠ Adapter admitted
    ≠ Adapter applicable
    ≠ Adapter capable
    ≠ Adapter currently healthy
    ≠ Adapter returned an eligible candidate
```

That gives us a much cleaner execution model.

## 271. Capability contract

Add:

```text
src/adapters/capabilities.ts
```

```ts
import type { MediaType } from "../domain/media.js";

export type IdentityKind = "imdb" | "tmdb" | "tvdb" | "internal";

export type AuthorizationMode =
  | "configured_owned"
  | "public_domain"
  | "licensed"
  | "unknown";

export interface SourceCapabilities {
  readonly mediaTypes: readonly MediaType[];

  readonly supportsMovies: boolean;
  readonly supportsSeries: boolean;
  readonly supportsEpisodes: boolean;

  readonly providesStreams: boolean;
  readonly providesSubtitles: boolean;
  readonly providesMetadata: boolean;

  readonly identityKinds: readonly IdentityKind[];

  readonly authorizationMode: AuthorizationMode;
}
```

The adapter becomes:

```ts
export interface SourceAdapter {
  readonly id: string;
  readonly name: string;

  readonly capabilities: SourceCapabilities;

  supports(media: MediaRef): boolean;

  resolve(
    media: MediaRef,
    ctx: ResolveContext
  ): Promise<readonly SourceCandidate[]>;
}
```

## 272. Why capabilities belong to the adapter

Do not infer capabilities from arbitrary runtime behavior.

Avoid:

```text
call adapter
    ↓
it happens to return subtitles
    ↓
therefore adapter supports subtitles
```

Instead:

```text
adapter declaration
        ↓
capability contract
        ↓
admission
```

This makes routing deterministic.

## 273. Capability validation

Create:

```ts
export function validateCapabilities(capabilities: SourceCapabilities): void {
  if (capabilities.mediaTypes.length === 0) {
    throw new Error("adapter_has_no_media_types");
  }

  if (
    capabilities.providesStreams === false &&
    capabilities.providesSubtitles === false &&
    capabilities.providesMetadata === false
  ) {
    throw new Error("adapter_has_no_capability");
  }

  if (capabilities.supportsEpisodes && !capabilities.supportsSeries) {
    throw new Error("episode_support_requires_series");
  }
}
```

This turns inconsistent declarations into startup failures.

## 274. Admission becomes explicit

Introduce:

```ts
export interface AdapterAdmission {
  readonly admitted: boolean;

  readonly reasons: readonly string[];

  readonly admittedAt: string;
}
```

Then:

```ts
export function admitAdapter(adapter: SourceAdapter): AdapterAdmission {
  const reasons: string[] = [];

  try {
    validateCapabilities(adapter.capabilities);
  } catch (error) {
    reasons.push(error instanceof Error ? error.message : String(error));
  }

  if (adapter.capabilities.authorizationMode === "unknown") {
    reasons.push("authorization_mode_unknown");
  }

  return {
    admitted: reasons.length === 0,

    reasons,

    admittedAt: new Date().toISOString()
  };
}
```

Notice that this is **configuration admission**, not runtime source
verification.

## 275. Registry becomes an authority boundary

Instead of:

```ts
registry.register(adapter);
```

use:

```ts
registry.register(adapter, admission);
```

or, preferably:

```ts
registry.registerAdmitted(admittedAdapter);
```

where an adapter cannot reach the runtime registry unless admission has
succeeded.

Conceptually:

```text
RawAdapter
    │
    ▼
validate
    │
    ▼
admission decision
    │
    ├── reject
    │
    ▼
AdmittedAdapter
    │
    ▼
RuntimeRegistry
```

This is much safer than a boolean flag floating around the
application.

## 276. Make invalid states harder to represent

We can encode the distinction:

```ts
export interface AdmittedAdapter {
  readonly adapter: SourceAdapter;
  readonly admission: AdapterAdmission & {
    readonly admitted: true;
  };
}
```

Then:

```ts
export function admit(adapter: SourceAdapter): AdmittedAdapter {
  const result = admitAdapter(adapter);

  if (!result.admitted) {
    throw new Error(`adapter_rejected:${adapter.id}`);
  }

  return {
    adapter,
    admission: result as AdapterAdmission & {
      admitted: true;
    }
  };
}
```

The type system now carries an important semantic fact.

## 277. Capability routing

Given:

```ts
const media: MediaRef = {
  type: "series",
  id: "tt1234567",
  season: 2,
  episode: 7
};
```

we don't want to execute every adapter.

Routing becomes:

```ts
export function isApplicable(
  adapter: AdmittedAdapter,
  media: MediaRef
): boolean {
  const { capabilities } = adapter.adapter;

  if (!capabilities.mediaTypes.includes(media.type)) {
    return false;
  }

  if (media.type === "movie" && !capabilities.supportsMovies) {
    return false;
  }

  if (media.type === "series" && !capabilities.supportsSeries) {
    return false;
  }

  if (
    media.type === "series" &&
    media.season !== undefined &&
    media.episode !== undefined &&
    !capabilities.supportsEpisodes
  ) {
    return false;
  }

  return true;
}
```

Now capability mismatch costs **zero provider requests**.

## 278. Identity compatibility

Capabilities also need identity compatibility.

Suppose a provider accepts:

```text
IMDb
```

while another requires:

```text
TMDB
```

The resolver shouldn't blindly call both.

Represent identity explicitly:

```ts
export interface CanonicalMedia {
  readonly canonicalId: string;

  readonly identities: ReadonlyMap<IdentityKind, string>;

  readonly media: MediaRef;
}
```

Example:

```text
canonical
    │
    ├── imdb → tt1234567
    ├── tmdb → 12345
    └── tvdb → 67890
```

## 279. Identity resolution

The identity layer becomes:

```text
Stremio ID
    │
    ▼
CanonicalMedia
    │
    ├── IMDb
    ├── TMDB
    └── TVDB
```

Then adapter routing asks:

```text
adapter.capabilities.identityKinds
```

rather than guessing.

## 280. Identity failure must be explicit

There are three fundamentally different cases:

```text
NOT_FOUND
```

means:

We searched the identity authority and found nothing.

```text
NOT_RESOLVED
```

means:

We don't have enough information to establish identity.

```text
AMBIGUOUS
```

means:

Multiple candidates remain possible.

Never collapse those into:

```text
id = undefined
```

because that destroys evidence.

## 281. Identity graph

The identity subsystem is naturally a graph:

```text
                 Canonical Media
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
       IMDb            TMDB           TVDB
         │              │              │
         └───────┬──────┴──────┬───────┘
                 │              │
                 ▼              ▼
              aliases
```

The canonical object is not necessarily any one provider's ID.

That's important.

```text
canonical identity
    ≠ IMDb identity
```

## 282. Source routing pipeline

We now get:

```text
                    MediaRef
                        │
                        ▼
                 IdentityResolver
                        │
                        ▼
                  CanonicalMedia
                        │
                        ▼
                CapabilityRouter
                        │
             ┌──────────┼──────────┐
             ▼          ▼          ▼
           A            C          F
        eligible     eligible    rejected
             │          │
             ▼          ▼
          breaker    breaker
             │          │
             ▼          ▼
          execute    execute
             │          │
             └────┬─────┘
                  ▼
             candidates
```

This is substantially more efficient than fan-out to everything.

## 283. Source selection policy

Routing should be deterministic.

A useful first policy:

```text
1. admitted
2. capability-compatible
3. identity-compatible
4. not circuit-open
5. within concurrency budget
6. execute
```

Don't rank sources by subjective quality yet.

First establish **eligibility**.

Then rank returned candidates.

This preserves:

```text
source selection ≠ candidate ranking
```

## 284. Candidate ranking is downstream

For example:

```text
Source A
    ↓
1080p candidate

Source B
    ↓
720p candidate

Source C
    ↓
1080p candidate
```

Source A isn't automatically "better" because its adapter was
preferred.

The ranking layer evaluates the actual candidate:

```text
resolution
codec
bitrate
language
direct playback
source reliability
```

This is a critical separation.

## 285. Reliability becomes measurable

We should eventually maintain:

```ts
export interface SourceHealth {
  readonly adapterId: string;

  readonly requests: number;
  readonly successes: number;
  readonly empty: number;
  readonly failures: number;

  readonly timeoutCount: number;

  readonly consecutiveFailures: number;

  readonly latency: Readonly<{
    p50?: number;
    p95?: number;
    p99?: number;
  }>;
}
```

But **health must never silently mutate semantic eligibility**.

For example:

```text
authorization = authorized
health = poor
```

means:

```text
authorized but currently unhealthy
```

not:

```text
unauthorized
```

## 286. Health state machine

```text
                 success
                     │
                     ▼
                ┌─────────┐
           ┌────│ CLOSED  │────┐
           │    └─────────┘    │
           │ failure            │
           │ threshold          │
           ▼                    │
       ┌─────────┐              │
       │  OPEN   │              │
       └────┬────┘              │
            │ cooldown          │
            ▼                   │
       ┌───────────┐            │
       │ HALF-OPEN │────────────┘
       └─────┬─────┘
             │ failure
             ▼
           OPEN
```

This state machine belongs to runtime health, not source policy.

## 287. In-flight deduplication

There is another important optimization.

Suppose ten Stremio requests arrive simultaneously:

```text
R1 ─┐
R2 ─┤
R3 ─┤
R4 ─┼──→ same media
R5 ─┤
R6 ─┤
R7 ─┘
```

Without coordination:

```text
7 × provider queries
```

With in-flight deduplication:

```text
             ┌── R1
             ├── R2
             ├── R3
media ───────┼── R4
             ├── R5
             ├── R6
             └── R7
                  │
                  ▼
             one resolution
```

## 288. In-flight cache

```ts
export class Inflight<T> {
  private readonly active = new Map<string, Promise<T>>();

  getOrCreate(key: string, operation: () => Promise<T>): Promise<T> {
    const existing = this.active.get(key);

    if (existing) {
      return existing;
    }

    const promise = operation();

    this.active.set(key, promise);

    void promise.finally(() => {
      if (this.active.get(key) === promise) {
        this.active.delete(key);
      }
    });

    return promise;
  }
}
```

One subtle point: callers can cancel their own request without
necessarily cancelling the shared underlying resolution.

That requires a later distinction between:

```text
caller cancellation
```

and:

```text
shared operation cancellation
```

## 289. Cache semantics

The cache must not be:

```text
"whatever was returned last time"
```

Instead define:

```text
CacheKey
CacheValue
Freshness
Stale policy
Invalidation
Provenance
```

For example:

```ts
export interface CacheEntry<T> {
  readonly value: T;

  readonly createdAt: number;
  readonly expiresAt: number;

  readonly sourceGeneration?: string;
}
```

## 290. Don't cache authorization blindly

This is another important boundary.

You can cache:

```text
metadata
```

for relatively long periods.

But an authorization-sensitive candidate may require:

```text
short TTL
```

or revalidation.

Otherwise:

```text
authorized yesterday
```

could become:

```text
implicitly authorized forever
```

through cache persistence.

## 291. Cache layers

A practical hierarchy:

```text
L1 in-flight
milliseconds → seconds

L2 memory cache
seconds → minutes

L3 persistent cache
minutes → hours/days

L4 external metadata
provider-dependent
```

Each layer has different semantics.

Don't call them all simply:

```text
cache
```

in diagnostics.

## 292. Stream URLs are special

A returned stream URL may be:

```text
stable
```

or:

```text
expiring
```

or:

```text
session-bound
```

Therefore the candidate model should eventually support:

```ts
readonly availability?: {
  readonly expiresAt?: string;
  readonly requiresRefresh?: boolean;
};
```

Then the cache can distinguish:

```text
candidate cache
```

from:

```text
URL cache
```

Those are not necessarily the same thing.

## 293. Do not proxy streams by default

A Popcorn-Time-like architecture can be tempted to do:

```text
Stremio
    ↓
addon
    ↓
download/relay
    ↓
user
```

That introduces:

```text
bandwidth
memory
connection lifecycle
range requests
TLS content handling
abuse surface
privacy
legal obligations
```

The first implementation should instead return eligible direct-playback
URLs:

```text
addon
    ↓
Stremio
    ↓
authorized source
```

A media proxy should be a separate subsystem requiring an independent
threat and resource model.

## 294. SSRF boundary

Any future URL-fetching component must assume:

```text
provider URL = untrusted
```

Do not permit arbitrary access to:

```text
127.0.0.1
localhost
RFC1918 ranges
link-local addresses
cloud metadata endpoints
Unix sockets
```

and equivalent IPv6 forms.

The safer architecture is:

```text
provider response
       │
       ▼
URL parser
       │
       ▼
network policy
       │
       ├── deny
       │
       ▼
HTTP client
```

not:

```ts
fetch(providerReturnedUrl);
```

## 295. Redirects are part of SSRF

Even if:

```text
https://approved.example/
```

is allowed,

the response could redirect to:

```text
http://127.0.0.1/
```

Therefore the policy must be applied **per redirect**.

Conceptually:

```text
URL₀
 ↓
policy
 ↓
HTTP
 ↓
Location
 ↓
policy again
 ↓
HTTP
```

Never treat the initial hostname as sufficient authorization.

## 296. DNS rebinding

Hostname validation alone is insufficient.

A hostile hostname could resolve differently later.

The production network client therefore needs:

```text
hostname policy
+ DNS resolution policy
+ IP range policy
+ redirect policy
```

This is another reason not to use the default fetch path blindly for
arbitrary provider URLs.

## 297. Request identity

Every resolution should have an internal request ID:

```text
req_01K...
```

Flow:

```text
request ID
   │
   ├── HTTP
   ├── resolver
   ├── adapter A
   ├── adapter B
   ├── policy
   └── response
```

Then logs can reconstruct the complete request.

## 298. Evidence event

Instead of only logs, define a structured event:

```ts
export interface ResolutionEvent {
  readonly requestId: string;

  readonly timestamp: string;

  readonly media: MediaRef;

  readonly adapterId?: string;

  readonly stage:
    | "request"
    | "identity"
    | "routing"
    | "source"
    | "validation"
    | "authorization"
    | "dedupe"
    | "ranking"
    | "response";

  readonly outcome: string;

  readonly durationMs?: number;
}
```

This is much closer to an evidence architecture.

## 299. Persist facts, derive views

The same principle applies here.

Persist:

```text
adapter called
adapter returned N candidates
candidate rejected
candidate admitted
candidate deduplicated
candidate ranked
```

Derive:

```text
success rate
provider health
average latency
source quality
```

Don't persist:

```text
"provider is bad"
```

as a primitive fact.

That's a derived interpretation.

## 300. Complete aggregation state

The system is now:

```text
                 REQUEST
                     │
                     ▼
                  PARSE
                     │
                     ▼
                CANONICALIZE
                     │
                     ▼
                 IDENTITY
                     │
                     ▼
                 ROUTING
                     │
              ┌──────┼──────┐
              ▼      ▼      ▼
              A      B      C
              │      │      │
          admission health  health
              │      │      │
              └──────┼──────┘
                     ▼
                  EXECUTE
                     │
                     ▼
               NORMALIZE
                     │
                     ▼
                VALIDATE
                     │
                     ▼
               AUTHORIZE
                     │
                     ▼
                  DEDUPE
                     │
                     ▼
                  RANK
                     │
                     ▼
                  CACHE
                     │
                     ▼
                 PRESENT
                     │
                     ▼
                  STREMIO
```

The architecture now has a clean separation between:

```text
identity
capability
admission
health
execution
evidence
policy
presentation
```

## 301. Next milestone: metadata and subtitles

Only after the stream path is stable should we expand the protocol
surface:

```text
/manifest.json
        │
        ├── /meta
        │
        ├── /catalog
        │
        ├── /stream
        │
        └── /subtitles
```

But these should share the same canonical identity layer.

The target is:

```text
                  CanonicalMedia
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
      Metadata        Streams       Subtitles
         │              │              │
         ▼              ▼              ▼
    MetaProvider   SourceAdapter   SubtitleAdapter
```

rather than three independent implementations of media identity.

## 302. Metadata should be merged, not blindly overwritten

Suppose:

```text
Provider A:
title = X
year = 1999
poster = A

Provider B:
title = X
year = 1999
poster = B

Provider C:
description = D
```

The merger should preserve provenance:

```ts
interface FieldValue<T> {
  readonly value: T;
  readonly source: string;
  readonly observedAt: string;
}
```

Then:

```text
title
  ├── A → X
  └── B → X

poster
  ├── A → ...
  └── B → ...

description
  └── C → ...
```

Only afterward do we derive:

```text
display title
display poster
display description
```

Again:

**Persist facts; derive views.**

## 303. Subtitle model

Keep subtitles separate from streams:

```ts
export interface SubtitleCandidate {
  readonly id: string;

  readonly media: MediaRef;

  readonly url: string;

  readonly language: string;

  readonly format: "srt" | "vtt" | "ass" | "ssa" | "unknown";

  readonly hearingImpaired?: boolean;

  readonly provenance: {
    readonly adapter: string;
    readonly observedAt: string;
  };

  readonly authorization: {
    readonly status: "authorized" | "unknown" | "denied";
  };
}
```

This avoids polluting `SourceCandidate` with subtitle-specific
semantics.

## 304. Subtitle ranking

Possible dimensions:

```text
language match
forced/full
hearing-impaired preference
format
provider reliability
authorization
```

Again:

```text
eligibility
    ↓
deduplication
    ↓
ranking
```

not one giant function.

## 305. Catalog is a different problem

A catalog is potentially huge.

Do not make:

```text
/catalog
```

execute:

```text
every source adapter
```

Catalog should have its own authority:

```text
CatalogIndex
    │
    ├── title
    ├── canonical ID
    ├── type
    ├── year
    └── metadata
```

Then source availability is queried only after the user selects an
item.

That produces:

```text
browse
    ↓
catalog
    ↓
select
    ↓
resolve streams
```

rather than:

```text
browse
    ↓
resolve thousands of streams
```

## 306. The resulting system is no longer "a scraper"

Its architecture is now closer to:

```text
             MEDIA RESOLUTION PLATFORM

┌──────────────────────────────────────────────┐
│                Stremio API                    │
└──────────────────────┬───────────────────────┘
                        │
┌──────────────────────▼───────────────────────┐
│             Application Layer                 │
│ identity / routing / orchestration            │
└───────────┬───────────────┬──────────────────┘
            │               │
      ┌─────▼─────┐   ┌────▼────────┐
      │   Domain  │   │   Runtime   │
      │ semantics │   │ reliability │
      └─────┬─────┘   └────┬────────┘
            │               │
            └───────┬───────┘
                     ▼
           ┌────────────────────┐
           │  Adapter Registry  │
           └─────────┬──────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    Metadata      Streams     Subtitles
    adapters      adapters     adapters
        │            │            │
        └────────────┼────────────┘
                     ▼
               External world
```

The external sources are deliberately kept at the edge.

## 307. Current release state

The architectural state is now:

| Layer | State |
| --- | --- |
| Domain model | Defined |
| Candidate model | Defined |
| Authorization semantics | Defined |
| Adapter contract | Defined |
| Capability contract | Defined |
| Admission | Defined |
| Identity architecture | Defined |
| Routing | Defined |
| Timeout | Defined |
| Concurrency | Defined |
| Circuit breaker | Defined |
| In-flight dedup | Defined |
| Candidate validation | Defined |
| Deduplication | Defined |
| Ranking | Defined |
| Stremio mapping | Defined |
| Manifest | Defined |
| Stream vertical slice | Defined |
| Metadata | Designed |
| Subtitles | Designed |
| Catalog | Designed |
| SSRF policy | Designed |
| Evidence events | Designed |
| CI gate | Designed |
| Actual execution evidence | **OPEN** |
| Real authorized source adapters | **OPEN** |
| `v0.1.0` release | **NOT ADMITTED** |

The critical boundary remains:

```text
DESIGNED
    ≠ IMPLEMENTED
    ≠ EXECUTED
    ≠ VERIFIED
```

The next step is therefore the **real repository implementation and
protocol integration test**, followed by the first admitted adapter
under the source-policy contract — not an uncontrolled collection of
media sources.

## 308. Implement the First Executable Vertical Slice

The architecture is now sufficiently specified to stop adding
abstractions and begin implementation.

The first slice should be deliberately narrow:

**Stremio request → parse → identity/capability routing → authorized
fixture adapter → validate → deduplicate → rank → Stremio stream
response**

No real third-party media-source scraping yet.

### 308.1 Freeze the first executable contract

```text
INPUT
GET /stream/movie/tt1234567.json
         ↓
 Stremio parser
        ↓
MediaRef {
  type: "movie",
  id: "tt1234567"
}
         ↓
 SourceRegistry
        ↓
eligible adapters
         ↓
 FixtureAdapter
        ↓
SourceCandidate[]
         ↓
structural validation
        ↓
authorization policy
        ↓
deduplication
        ↓
deterministic ranking
        ↓
 Stremio mapper
         ↓
{
  streams: [...]
}
```

The key release rule remains:

```text
NO EXECUTION EVIDENCE
        ↓
NO VERIFIED CLAIM
```

## 309. `src/addon/parser.ts`

The protocol parser should terminate at the domain boundary.

```ts
import type { MediaRef, MediaType } from "../domain/media.js";

export interface ParsedStreamRequest {
  media: MediaRef;
}

export class RequestParseError extends Error {
  readonly code = "invalid_request";

  constructor(message: string) {
    super(message);
    this.name = "RequestParseError";
  }
}

export function parseStreamRequest(
  type: string,
  rawId: string
): ParsedStreamRequest {
  if (type !== "movie" && type !== "series") {
    throw new RequestParseError(`Unsupported media type: ${type}`);
  }

  if (!rawId) {
    throw new RequestParseError("Missing media ID");
  }

  if (type === "movie") {
    return {
      media: {
        type: "movie",
        id: rawId
      }
    };
  }

  const parts = rawId.split(":");

  if (parts.length !== 3) {
    throw new RequestParseError(
      "Series ID must use <id>:<season>:<episode>"
    );
  }

  const [id, seasonRaw, episodeRaw] = parts;

  const season = Number(seasonRaw);
  const episode = Number(episodeRaw);

  if (
    !id ||
    !Number.isInteger(season) ||
    !Number.isInteger(episode) ||
    season < 1 ||
    episode < 1
  ) {
    throw new RequestParseError("Invalid series episode identifier");
  }

  return {
    media: {
      type: "series",
      id,
      season,
      episode
    }
  };
}
```

The important property is that the rest of the application never needs
to understand:

```text
tt1234567:2:7
```

It receives:

```json
{
  "type": "series",
  "id": "tt1234567",
  "season": 2,
  "episode": 7
}
```

That is the protocol/domain separation boundary.

## 310. `src/application/resolver.ts`

The application layer becomes the orchestration authority.

```ts
import type { MediaRef } from "../domain/media.js";
import type { SourceCandidate } from "../domain/candidate.js";
import type { Failure } from "../domain/failure.js";
import type { ResolutionResult } from "../domain/result.js";

import type { SourceRegistry } from "../adapters/registry.js";
import { validateCandidate } from "../resolver/validate.js";
import { authorizeCandidate } from "../resolver/policy.js";
import { deduplicateCandidates } from "../resolver/dedupe.js";
import { rankCandidates } from "../resolver/rank.js";

export interface ResolverOptions {
  timeoutMs: number;
  preferredLanguages: readonly string[];
}

export class Resolver {
  constructor(
    private readonly registry: SourceRegistry,
    private readonly options: ResolverOptions
  ) {}

  async resolve(
    media: MediaRef,
    signal: AbortSignal
  ): Promise<ResolutionResult> {
    const started = performance.now();

    const adapters = this.registry
      .all()
      .filter(adapter => adapter.supports(media));

    const candidates: SourceCandidate[] = [];
    const failures: Failure[] = [];

    for (const adapter of adapters) {
      try {
        const result = await adapter.resolve(media, {
          signal,
          timeoutMs: this.options.timeoutMs,
          preferredLanguages: this.options.preferredLanguages
        });

        for (const candidate of result) {
          const structural = validateCandidate(candidate);

          if (!structural.valid) {
            failures.push(structural.failure);
            continue;
          }

          const authorization = authorizeCandidate(candidate);

          if (!authorization.authorized) {
            failures.push(authorization.failure);
            continue;
          }

          candidates.push(candidate);
        }
      } catch (error) {
        failures.push({
          code: "source_network_error",
          sourceId: adapter.id,
          message: error instanceof Error ? error.message : String(error)
        });
      }
    }

    const unique = deduplicateCandidates(candidates);
    const ranked = rankCandidates(unique);

    const durationMs = performance.now() - started;

    let status: ResolutionResult["status"];

    if (ranked.length > 0 && failures.length === 0) {
      status = "success";
    } else if (ranked.length > 0) {
      status = "partial";
    } else if (failures.length > 0) {
      status = "failed";
    } else {
      status = "empty";
    }

    return {
      media,
      status,
      candidates: ranked,
      failures,
      sourceCount: adapters.length,
      durationMs
    };
  }
}
```

This establishes a critical distinction:

```text
adapter failure ≠ resolver failure
```

One source being unavailable should not automatically erase successful
results from other sources.

## 311. Partial success is first-class

Consider:

```text
Source A → 2 candidates
Source B → timeout
Source C → 1 candidate
Source D → unauthorized candidate
```

The resolver should produce:

```text
status = partial

candidates = 3

failures:
  B → timeout
  D → candidate_not_authorized
```

Not:

```text
status = failed
```

And certainly not:

```text
HTTP 500
```

The request itself was valid.

This distinction matters operationally:

| Condition | Result |
| --- | --- |
| Invalid Stremio request | protocol/application error |
| Valid request, no sources applicable | empty |
| Sources queried, none returned | empty |
| Some sources failed, candidates exist | partial |
| All sources failed | failed |
| Candidates returned and accepted | success |

## 312. Protocol handler

`src/addon/stream-handler.ts`:

```ts
import type { Resolver } from "../application/resolver.js";
import { parseStreamRequest } from "./parser.js";

export function createStreamHandler(resolver: Resolver) {
  return async (args: { type: string; id: string }) => {
    const { media } = parseStreamRequest(args.type, args.id);

    const controller = new AbortController();

    try {
      const result = await resolver.resolve(media, controller.signal);

      return {
        streams: result.candidates.map(candidate => ({
          name: candidate.sourceId,
          title: buildStreamTitle(candidate),
          url: candidate.url
        }))
      };
    } finally {
      controller.abort();
    }
  };
}

function buildStreamTitle(candidate: {
  mediaInfo?: {
    resolution?: string;
    container?: string;
  };
}): string {
  const parts = [];

  if (candidate.mediaInfo?.resolution) {
    parts.push(candidate.mediaInfo.resolution);
  }

  if (candidate.mediaInfo?.container) {
    parts.push(candidate.mediaInfo.container);
  }

  return parts.join(" · ");
}
```

Notice that `ResolutionResult` does **not** escape directly into the
Stremio API.

The mapper controls that boundary.

## 313. Empty result semantics

A perfectly valid request may result in:

```json
{
  "streams": []
}
```

That is not necessarily an error.

For example:

```text
GET /stream/movie/tt1234567.json
             ↓
valid IMDb identity
             ↓
authorized sources available
             ↓
none currently contain the requested media
             ↓
streams: []
```

This is substantially different from:

```text
malformed request
```

or:

```text
internal exception
```

The distinction should survive logging and metrics.

## 314. The first adapter

The first adapter should remain intentionally boring.

```ts
import type { SourceAdapter, ResolveContext } from "../interface.js";

import type { MediaRef } from "../../domain/media.js";
import type { SourceCandidate } from "../../domain/candidate.js";

export class FixtureAdapter implements SourceAdapter {
  readonly id = "fixture-authorized";

  readonly name = "Authorized Fixture Source";

  supports(media: MediaRef): boolean {
    return media.type === "movie";
  }

  async resolve(
    media: MediaRef,
    _ctx: ResolveContext
  ): Promise<SourceCandidate[]> {
    if (media.id !== "tt1234567") {
      return [];
    }

    return [
      {
        sourceId: this.id,

        media,

        url: "https://media.example.test/movie.mp4",

        mediaInfo: {
          container: "mp4",
          resolution: "1080p",
          bitrate: 5_000_000
        },

        language: "en",

        provenance: {
          adapterId: this.id,
          observedAt: new Date().toISOString()
        },

        capabilities: {
          directPlayback: true
        },

        authorization: {
          status: "authorized",
          basis: "fixture"
        }
      }
    ];
  }
}
```

This URL is deliberately a **test fixture**, not a real media source.

The purpose is to prove the pipeline.

## 315. Registry construction

```ts
import type { SourceAdapter } from "./interface.js";

export class SourceRegistry {
  private readonly adapters = new Map<string, SourceAdapter>();

  register(adapter: SourceAdapter): void {
    if (this.adapters.has(adapter.id)) {
      throw new Error(`Duplicate source adapter: ${adapter.id}`);
    }

    this.adapters.set(adapter.id, adapter);
  }

  get(id: string): SourceAdapter | undefined {
    return this.adapters.get(id);
  }

  all(): readonly SourceAdapter[] {
    return [...this.adapters.values()];
  }
}
```

The registry is deliberately deterministic.

No implicit:

```text
filesystem scanning
dynamic imports
magic discovery
```

yet.

Those mechanisms introduce another authority surface.

## 316. Application composition root

`src/index.ts` should be the place where dependencies become concrete.

Conceptually:

```ts
const config = loadConfig();

const registry = new SourceRegistry();

registry.register(new FixtureAdapter());

const resolver = new Resolver(registry, {
  timeoutMs: config.sourceTimeoutMs,
  preferredLanguages: config.preferredLanguages
});

const streamHandler = createStreamHandler(resolver);

const manifest = createManifest();

const addon = builder.defineAddon(manifest).defineStreamHandler(streamHandler);

serveHTTP(addon);
```

This is the **composition root**.

The domain does not instantiate infrastructure.

## 317. Dependency direction

The resulting dependency graph should be enforced:

```text
                    ┌──────────────┐
                     │   Stremio    │
                     │   Protocol   │
                     └──────┬───────┘
                            │
                            ▼
                     ┌──────────────┐
                     │     addon    │
                     └──────┬───────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ application  │
                     └───┬──────┬───┘
                         │      │
              ┌──────────┘      └──────────┐
              ▼                            ▼
        ┌──────────┐                ┌──────────┐
        │  domain  │                │ runtime  │
        └──────────┘                └──────────┘
              ▲                            ▲
              │                            │
        ┌─────┴────────────────────────────┴─────┐
        │                adapters                 │
        └────────────────────────────────────────┘
```

The forbidden direction is:

```text
domain → Stremio SDK
domain → HTTP
domain → filesystem
domain → database
domain → logger implementation
```

## 318. First protocol integration test

The first meaningful integration test should prove the entire chain.

```ts
it("resolves an authorized fixture through Stremio", async () => {
  const registry = new SourceRegistry();

  registry.register(new FixtureAdapter());

  const resolver = new Resolver(registry, {
    timeoutMs: 1_000,
    preferredLanguages: ["en"]
  });

  const handler = createStreamHandler(resolver);

  const response = await handler({
    type: "movie",
    id: "tt1234567"
  });

  expect(response.streams).toHaveLength(1);

  expect(response.streams[0]).toMatchObject({
    name: "fixture-authorized",
    url: "https://media.example.test/movie.mp4"
  });
});
```

This single test establishes:

```text
Stremio syntax
      ↓
parser
      ↓
domain MediaRef
      ↓
registry
      ↓
adapter
      ↓
candidate
      ↓
validation
      ↓
authorization
      ↓
deduplication
      ↓
ranking
      ↓
Stremio representation
```

That is the first **vertical proof obligation**.

## 319. Then test the rejection path

The positive test alone is insufficient.

Add:

```text
authorized candidate
        → accepted

unknown authorization
        → rejected

unauthorized candidate
        → rejected

malformed URL
        → rejected

duplicate candidate
        → one candidate

adapter timeout
        → failure recorded

one adapter fails
        → other adapters continue
```

The most important negative test:

```ts
expect(
  authorizeCandidate({
    // ...
    authorization: {
      status: "unknown"
    }
  }).authorized
).toBe(false);
```

This protects the architectural rule:

**Unknown authorization is not authorization.**

## 320. Source adapter conformance suite

Every future adapter should automatically receive the same contract
tests.

```ts
export function describeSourceAdapter(createAdapter: () => SourceAdapter) {
  describe("SourceAdapter contract", () => {
    it("has a stable ID", () => {
      const adapter = createAdapter();

      expect(adapter.id).toMatch(/^[a-z0-9][a-z0-9-]*$/);
    });

    it("has a name", () => {
      expect(createAdapter().name.length).toBeGreaterThan(0);
    });

    it("supports() is deterministic", () => {
      const adapter = createAdapter();

      const media = {
        type: "movie" as const,
        id: "tt1234567"
      };

      expect(adapter.supports(media)).toBe(adapter.supports(media));
    });
  });
}
```

Later this becomes:

```text
adapter implementation
       │
       ▼
conformance suite
       │
       ├── capability correctness
       ├── authorization semantics
       ├── cancellation
       ├── timeout
       ├── malformed response handling
       ├── deterministic identity
       └── evidence emission
```

## 321. Important architectural correction

At this point, **do not** add ten source adapters.

That would create:

```text
many adapters
       ↓
uncertain authorization
       ↓
uncertain provenance
       ↓
uncertain behavior
       ↓
large debugging surface
```

Instead:

```text
1 fixture adapter
        ↓
full pipeline
        ↓
CI
        ↓
protocol smoke test
        ↓
artifact
        ↓
digest
        ↓
release gate
        ↓
first real authorized adapter
```

This is much closer to the project's evidence model.

## 322. Next gate: executable evidence

The next milestone is no longer architectural.

It is:

```text
GATE V0.1-S1

[ ] repository compiles
[ ] typecheck passes
[ ] unit tests pass
[ ] integration test passes
[ ] Stremio manifest endpoint works
[ ] Stremio stream endpoint works
[ ] fixture authorization is enforced
[ ] unauthorized fixture is rejected
[ ] duplicate candidates collapse
[ ] ranking is deterministic
[ ] timeout is observable
[ ] container builds
[ ] container starts
[ ] health endpoint works
[ ] protocol smoke test passes
[ ] artifact digest recorded
```

Only after these are actually executed should the project state change
from:

```text
DESIGNED
```

to:

```text
IMPLEMENTATION_VERIFIED
```

and eventually:

```text
ARTIFACT_BOUND
```

## 323. Current state

| Layer | State |
| --- | --- |
| Stremio protocol model | **DESIGNED** |
| Domain model | **DESIGNED** |
| Source contract | **DESIGNED** |
| Capability model | **DESIGNED** |
| Authorization boundary | **DESIGNED** |
| Identity architecture | **DESIGNED** |
| Resolver pipeline | **IMPLEMENTATION BLUEPRINT** |
| Fixture adapter | **IMPLEMENTATION BLUEPRINT** |
| Protocol integration | **IMPLEMENTATION BLUEPRINT** |
| Real source adapters | **OPEN** |
| Metadata | **DESIGNED** |
| Catalog | **DESIGNED** |
| Subtitles | **DESIGNED** |
| SSRF policy | **DESIGNED** |
| Evidence ledger | **DESIGNED** |
| CI | **DESIGNED** |
| Actual CI execution | **OPEN** |
| Release artifact | **NOT ADMITTED** |

The next step is therefore **324: turn this blueprint into the actual
repository files and run the first conformance gate**, rather than
adding more architecture.
