# Roadmap & Implementation Status

[⇧ Architecture index](../architecture.md) · [⇆ Document map](./README.md)

> **Scope.** The construction sequence only: ARCHITECTURE → FORMAL CONTRACTS → IMPLEMENTATION → CONFORMANCE TESTS → INTEGRATION → CI EXECUTION → RELEASE GATE → TAG. Separates what is implemented, partially implemented, planned next, future, and blocked. As of this revision, the repository contains no source code, tests, or CI — so the entire V0.1 slice remains explicitly **PROPOSED/DESIGNED**, not implemented, unless a later revision of this document states otherwise with repo evidence (commit/file reference).

> **Primary dependencies:** `*`

> **Status.** Unless a section explicitly states otherwise with a concrete repository reference (file path, commit, or CI run), everything below is **DESIGNED** or **PROPOSED** architecture, not implemented code. This document was migrated from the original `docs/architecture.md` monolith; section order is preserved from that document, numbering has been dropped in favor of descriptive headings, and some very long single sections in the monolith may appear here still bearing internal editorial framing (e.g. first-person design narration) that predates the doc-split.

## Sections in this document

- [Recommended repository](#recommended-repository)
- [The resulting system](#the-resulting-system)
- [Recommended implementation sequence](#recommended-implementation-sequence)
- [Turn the design into a real implementation](#turn-the-design-into-a-real-implementation)
- [Architecture after hardening](#architecture-after-hardening)
- [Build the runnable repository](#build-the-runnable-repository)
- [Repository v1](#repository-v1)
- [`package.json`](#packagejson)
- [TypeScript configuration](#typescript-configuration)
- [Next layer](#next-layer)
- [First architecture freeze](#first-architecture-freeze)
- [Repository evolution](#repository-evolution)
- [Executable reference implementation](#executable-reference-implementation)
- [Freeze the v0.1 boundary](#freeze-the-v01-boundary)
- [Project tree](#project-tree)
- [`package.json`](#packagejson)
- [TypeScript configuration](#typescript-configuration)
- [This gives us the first real vertical slice](#this-gives-us-the-first-real-vertical-slice)
- [The first frozen baseline](#the-first-frozen-baseline)
- [The architecture has reached an important point](#the-architecture-has-reached-an-important-point)
- [Next architectural layer](#next-architectural-layer)
- [Next milestone: metadata and subtitles](#next-milestone-metadata-and-subtitles)
- [Current release state](#current-release-state)
- [Implement the First Executable Vertical Slice](#implement-the-first-executable-vertical-slice)
- [Important architectural correction](#important-architectural-correction)
- [Current state](#current-state)
- [Concrete `src/index.ts`](#concrete-srcindexts)
- [Metadata Comes After Stream Stability](#metadata-comes-after-stream-stability)
- [The Actual Release Ladder](#the-actual-release-ladder)
- [Next Boundary](#next-boundary)
- [What We Still Must Not Claim](#what-we-still-must-not-claim)
- [The Next Major Expansion](#the-next-major-expansion)
- [Current Architecture After the Conformance Layer](#current-architecture-after-the-conformance-layer)
- [Current Status](#current-status)
- [The next architectural boundary](#the-next-architectural-boundary)
- [Updated system](#updated-system)
- [Architecture checkpoint](#architecture-checkpoint)
- [Next build target](#next-build-target)
- [What the addon still does not know](#what-the-addon-still-does-not-know)
- [Repository update](#repository-update)
- [Major milestone](#major-milestone)
- [The system now has three information graphs](#the-system-now-has-three-information-graphs)
- [The larger architecture](#the-larger-architecture)
- [Next boundary: subtitles](#next-boundary-subtitles)
- [Updated repository](#updated-repository)
- [The architecture has now reached a useful abstraction point](#the-architecture-has-now-reached-a-useful-abstraction-point)
- [Final information architecture](#final-information-architecture)
- [Next: turn the addon into a real platform](#next-turn-the-addon-into-a-real-platform)
- [The project has crossed another boundary](#the-project-has-crossed-another-boundary)
- [Next architectural milestone](#next-architectural-milestone)
- [The architecture now has a complete vertical slice](#the-architecture-now-has-a-complete-vertical-slice)
- [What comes next](#what-comes-next)

---

## Recommended repository

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

## The resulting system

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

## Turn the design into a real implementation

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

## Architecture after hardening

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

## Build the runnable repository

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

## Repository v1

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

## `package.json`

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

## TypeScript configuration

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

## First architecture freeze

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

## Repository evolution

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

## Executable reference implementation

We have reached the point where continuing to add abstractions would
be counterproductive.

The next milestone is:

**Turn the architecture into a small, executable, testable addon
kernel before adding more providers.**

The first implementation should intentionally have **one safe fixture
adapter** representing an explicitly authorized/public-domain/user-owned
source. Everything else can plug into the same contract later.

## Freeze the v0.1 boundary

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

## Project tree

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

## `package.json`

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

## TypeScript configuration

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

## This gives us the first real vertical slice

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

## The first frozen baseline

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

## The architecture has reached an important point

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

## Next architectural layer

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

## Next milestone: metadata and subtitles

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

## Current release state

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

## Implement the First Executable Vertical Slice

The architecture is now sufficiently specified to stop adding
abstractions and begin implementation.

The first slice should be deliberately narrow:

**Stremio request → parse → identity/capability routing → authorized
fixture adapter → validate → deduplicate → rank → Stremio stream
response**

No real third-party media-source scraping yet.

### Freeze the first executable contract

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

## Important architectural correction

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

## Current state

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

## Concrete `src/index.ts`

```ts
import { addonBuilder, serveHTTP } from "stremio-addon-sdk";

import { createManifest } from "./addon/manifest.js";
import { createStreamHandler } from "./addon/stream-handler.js";

import { Resolver } from "./application/resolver.js";
import { SourceRegistry } from "./adapters/registry.js";
import { FixtureAdapter } from "./adapters/fixture/adapter.js";

import { loadConfig } from "./config/config.js";

const config = loadConfig();

const registry = new SourceRegistry();

registry.register(new FixtureAdapter());

const resolver = new Resolver(registry, {
  timeoutMs: config.sourceTimeoutMs,
  preferredLanguages: config.preferredLanguages
});

const builder = new addonBuilder(createManifest());

builder.defineStreamHandler(createStreamHandler(resolver));

const addonInterface = builder.getInterface();

serveHTTP(addonInterface, {
  port: config.port
});
```

This gives us a real composition root:

```text
index.ts
                    │
       ┌────────────┼─────────────┐
       ▼            ▼             ▼
    config       registry       resolver
                    │             │
                    ▼             │
             FixtureAdapter ◄──────┘
                                  │
                                  ▼
                           Stremio handler
                                  │
                                  ▼
                           addonBuilder
                                  │
                                  ▼
                            serveHTTP()
```

The SDK remains confined to `addon/` plus the composition root.

## Metadata Comes After Stream Stability

Once stream resolution is executable, metadata can be added without
contaminating it.

The future architecture:

```text
CanonicalMedia
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
       Streams       Meta      Subtitles
          │           │           │
          └───────────┼───────────┘
                      ▼
                 Presentation
                      │
                      ▼
                   Stremio
```

Shared identity, separate capabilities.

That prevents:

```text
metadata provider unavailable
        ↓
stream provider considered unavailable
```

which would be an unnecessary coupling.

## The Actual Release Ladder

We now have a much cleaner release sequence:

```text
R0 — Architecture
     ↓
R1 — Compileable skeleton
     ↓
R2 — Fixture vertical slice
     ↓
R3 — CI conformance
     ↓
R4 — Local Stremio protocol test
     ↓
R5 — Containerized deployment
     ↓
R6 — First authorized real adapter
     ↓
R7 — Identity resolver
     ↓
R8 — Metadata
     ↓
R9 — Subtitles
     ↓
R10 — Catalog
     ↓
R11 — Persistent evidence/cache
     ↓
R12 — Multi-instance deployment
```

Each stage has its own evidence.

## Next Boundary

The next implementation block should be the actual conformance
harness, not another abstraction layer:

```text
test/
├── addon/
│   ├── manifest.test.ts
│   ├── stream-handler.test.ts
│   └── parser.test.ts
│
├── application/
│   └── resolver.test.ts
│
├── resolver/
│   ├── authorization.test.ts
│   ├── dedupe.test.ts
│   ├── ranking.test.ts
│   └── validation.test.ts
│
├── runtime/
│   ├── timeout.test.ts
│   ├── semaphore.test.ts
│   ├── breaker.test.ts
│   └── inflight.test.ts
│
├── adapters/
│   └── conformance.test.ts
│
└── integration/
    ├── protocol.test.ts
    └── http.test.ts
```

The decisive test is not merely:

```text
"the function returned the expected object"
```

but:

```text
Stremio-shaped request
        ↓
real SDK interface
        ↓
real addon handler
        ↓
real HTTP server
        ↓
/manifest.json
        ↓
/stream/movie/tt1234567.json
        ↓
expected protocol response
```

That is the first point at which we can legitimately say the addon
executes as a Stremio addon, rather than merely having code that
appears to implement one.

## What We Still Must Not Claim

At this stage, even with the complete test suite designed, we cannot
claim:

```text
"production ready"
"works with all Stremio clients"
"aggregates many providers"
"has reliable streaming"
"has real source coverage"
```

without corresponding evidence.

Current honest status:

```text
Architecture             DESIGNED
Contracts                DEFINED
Implementation plan      COMPLETE
SDK boundary             VERIFIED
Tests                    SPECIFIED
Execution                OPEN
CI                       OPEN
Container                OPEN
Real adapter             OPEN
Release artifact         OPEN
```

## The Next Major Expansion

Once `GATE-V0.1-S1` actually passes, the architecture should expand in
this order:

```text
                    V0.1
                      │
                      ▼
              Fixture vertical slice
                      │
                      ▼
             ┌─────────────────┐
             │ Identity Layer  │
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │ Source Admission│
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │ Real Authorized │
             │    Adapter      │
             └────────┬────────┘
                      │
           ┌──────────┼──────────┐
           ▼          ▼          ▼
        Metadata    Subtitles   Catalog
           │          │          │
           └──────────┼──────────┘
                      ▼
               Persistent Cache
                      │
                      ▼
               Evidence Ledger
                      │
                      ▼
              Multi-instance Runtime
```

The crucial change is that **real source integration comes before
source proliferation**.

One properly admitted adapter gives us a meaningful proof of the
adapter contract.

Twenty poorly characterized adapters merely multiply uncertainty.

## Current Architecture After the Conformance Layer

```text
                          STREMIO
                              │
                              ▼
                     ┌────────────────┐
                     │ Protocol Layer │
                     └───────┬────────┘
                             │
                             ▼
                     ┌────────────────┐
                     │   Application  │
                     │    Resolver    │
                     └───────┬────────┘
                             │
           ┌─────────────────┼──────────────────┐
           ▼                 ▼                  ▼
      Identity           Routing            Runtime
           │                 │                  │
           │          ┌──────┴──────┐           │
           │          ▼             ▼           │
           │       Admission      Health        │
           │          │             │           │
           └──────────┼─────────────┼───────────┘
                      ▼             ▼
                   ADAPTERS     CIRCUITS
                      │
                      ▼
               Source Candidates
                      │
                      ▼
               ┌──────────────┐
               │  Validate    │
               └──────┬───────┘
                      ▼
               ┌──────────────┐
               │ Authorize    │
               └──────┬───────┘
                      ▼
               ┌──────────────┐
               │ Deduplicate  │
               └──────┬───────┘
                      ▼
               ┌──────────────┐
               │    Rank      │
               └──────┬───────┘
                      ▼
               ┌──────────────┐
               │ Presentation │
               └──────┬───────┘
                      ▼
                    STREMIO
```

And underneath the entire graph:

```text
               ┌──────────────────────┐
                │ Evidence / Receipts  │
                └──────────────────────┘
```

This is the point where the project stops being merely a "Stremio
addon with multiple sources" and becomes a **governed
source-resolution system with a Stremio protocol adapter**.

The next block is the **identity layer**: canonical media,
IMDb/TMDB/TVDB mappings, `NOT_FOUND` vs `NOT_RESOLVED` vs `AMBIGUOUS`,
identity-provider adapters, cache semantics, and the routing algorithm
that prevents an adapter from being queried when the identity evidence
is insufficient.

## Current Status

| Component | Status |
| --- | --- |
| Stremio protocol boundary | **DEFINED** |
| SDK integration model | **VERIFIED** |
| Resolver | **DEFINED** |
| Candidate model | **DEFINED** |
| Authorization | **DEFINED** |
| Runtime controls | **DEFINED** |
| Conformance harness | **DEFINED** |
| Identity model | **DEFINED** |
| Identity state machine | **DEFINED** |
| Identity reconciliation | **DEFINED** |
| Identity cache semantics | **DEFINED** |
| Routing explanation | **DEFINED** |
| Actual test execution | **OPEN** |
| Real identity provider | **OPEN** |
| Real authorized source | **OPEN** |
| Metadata | **NEXT** |
| Subtitles | **NEXT** |
| Catalog | **NEXT** |
| Release artifact | **NOT ADMITTED** |

The next major boundary is **source admission + a real authorized
adapter**: how an adapter proves its capabilities, authorization
basis, identity requirements, network permissions, rate-limit
behavior, and provenance before it can enter the runtime registry.

## The next architectural boundary

We now have four separate admission questions:

```text
1. Identity
   "What media is this?"

2. Capability
   "Can this adapter handle it?"

3. Authorization
   "Is this adapter/source allowed to participate?"

4. Operational eligibility
   "Can we execute it right now?"
```

Together:

```text
REQUEST
  │
  ▼
IDENTITY
  │
  ▼
CAPABILITY
  │
  ▼
AUTHORIZATION
  │
  ▼
NETWORK POLICY
  │
  ▼
HEALTH
  │
  ▼
CIRCUIT
  │
  ▼
EXECUTION
```

That gives us a much stronger invariant:

**A source is executable only when identity, capability,
authorization, network policy, and operational state all
independently permit execution.**

## Updated system

The architecture is now:

```text
                         ┌─────────────────────┐
                          │      Stremio        │
                          └──────────┬──────────┘
                                     │
                               Protocol Layer
                                     │
                                     ▼
                               Media Request
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │ Identity Resolution │
                          └──────────┬──────────┘
                                     │
                          CanonicalMedia
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │   Source Routing    │
                          └──────────┬──────────┘
                                     │
                      ┌──────────────┼──────────────┐
                      ▼              ▼              ▼
                  Capability    Authorization    Identity
                      │              │              │
                      └──────────────┼──────────────┘
                                     ▼
                             Network Admission
                                     │
                                     ▼
                              Health / Circuit
                                     │
                                     ▼
                          Bounded Source Execution
                                     │
                                     ▼
                               Candidate Set
                                     │
                          ┌──────────┴──────────┐
                          ▼                     ▼
                     Validate              Authorize
                          │                     │
                          └──────────┬──────────┘
                                     ▼
                                   Dedupe
                                     │
                                     ▼
                                   Rank
                                     │
                                     ▼
                            Stremio Stream DTO
```

The important change is that **source adapters are no longer merely
functions that return URLs**.

They are governed capabilities with explicit:

```text
identity requirements
+ capability declaration
+ authorization evidence
+ network constraints
+ resource limits
+ health state
+ execution contract
```

That gives us the foundation for the next major subsystem: **the
actual authorized-source adapter runtime and its source-independent
HTTP client**, including retries, redirect validation, rate limiting,
cancellation, response-size limits, content validation, and how a
real owned/licensed media backend becomes a `SourceCandidate` without
contaminating the domain layer.

## Architecture checkpoint

The addon now has five distinct authorities:

| Authority | Question |
| --- | --- |
| **Protocol** | What did Stremio request? |
| **Identity** | What media does that request identify? |
| **Admission** | Which sources are permitted? |
| **Runtime** | Can an admitted source execute safely now? |
| **Resolver** | Which resulting candidates should be presented? |

And one important non-authority:

| Component | What it is *not* |
| --- | --- |
| Health | not authorization |
| Cache | not truth |
| Metadata | not identity authority |
| Ranking | not authorization |
| Logging | not canonical evidence |
| HTTP status | not automatically domain semantics |

That separation is what prevents the system from gradually turning:

```text
"we observed X"
```

into:

```text
"therefore X is true"
```

and then:

```text
"therefore we are authorized to act on X."
```

## Next build target

The natural next step is now **the concrete owned-media source
implementation**:

```text
OwnedMediaSource
├── manifest/declaration
├── configuration schema
├── identity index
├── asset index
├── credential boundary
├── HTTP implementation
├── candidate conversion
├── authorization evidence
├── source-specific error mapping
├── adapter conformance tests
└── end-to-end Stremio test
```

That is where the abstract contracts become an actual runnable
source, while keeping the source implementation replaceable by a
licensed API, public-domain repository, or another explicitly
authorized backend later.

## What the addon still does not know

Even after this succeeds, the addon has established only a limited
set of facts:

```text
PROVED within application
────────────────────────────

request parsed
identity resolved according to configured identity evidence
source admitted
library returned asset
asset passed structural validation
asset authorization status accepted
candidate ranked
```

It has **not** established:

```text
NOT PROVED
────────────────────────────

that every external metadata claim is true
that a third party owns the media
that the remote server will remain available
that the URL will work indefinitely
that every Stremio client supports the stream
that playback will succeed
that the media is legally usable outside the configured
authorization scope
```

This is exactly where:

**NO EVIDENCE → NO VERIFIED CLAIM**

becomes useful.

## Repository update

The proposed tree now becomes:

```text
src/
├── addon/
│   ├── manifest.ts
│   ├── parser.ts
│   └── stream-handler.ts
│
├── application/
│   └── resolver.ts
│
├── domain/
│   ├── media.ts
│   ├── candidate.ts
│   ├── failure.ts
│   └── result.ts
│
├── identity/
│   ├── types.ts
│   ├── resolver.ts
│   ├── registry.ts
│   ├── normalize.ts
│   ├── graph.ts
│   ├── confidence.ts
│   └── cache.ts
│
├── adapters/
│   ├── interface.ts
│   ├── registry.ts
│   ├── admission.ts
│   │
│   └── owned-media/
│       ├── adapter.ts
│       ├── declaration.ts
│       ├── library.ts
│       ├── json-library.ts
│       ├── schema.ts
│       └── url-policy.ts
│
├── resolver/
│   ├── validate.ts
│   ├── policy.ts
│   ├── dedupe.ts
│   └── rank.ts
│
├── runtime/
│   ├── executor.ts
│   ├── timeout.ts
│   ├── semaphore.ts
│   ├── limiter.ts
│   ├── breaker.ts
│   ├── cache.ts
│   ├── inflight.ts
│   └── http.ts
│
└── observability/
    ├── logger.ts
    ├── metrics.ts
    ├── receipts.ts
    └── health.ts
```

## Major milestone

The system has crossed an important architectural boundary:

```text
                  BEFORE
                      │
           abstract source adapters
                      │
                      ▼
                   AFTER
                      │
        governed executable source
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
     identity      admission      runtime
        │             │             │
        └─────────────┼─────────────┘
                      ▼
               authorized library
                      │
                      ▼
                SourceCandidate
                      │
                      ▼
                  Stremio
```

### Current evidence status

| Component | Status |
| --- | --- |
| Stremio protocol model | **DEFINED** |
| SDK integration shape | **VERIFIED from documentation** |
| Identity model | **DEFINED** |
| Identity reconciliation | **DEFINED** |
| Source admission | **DEFINED** |
| Source runtime | **DEFINED** |
| Owned-media source contract | **DEFINED** |
| JSON library design | **DEFINED** |
| Candidate authorization | **DEFINED** |
| Actual implementation | **OPEN** |
| Actual tests | **OPEN** |
| Actual CI run | **OPEN** |
| Real deployment | **OPEN** |

The next layer is **metadata as a separate evidence graph**, because
the current system can resolve a canonical media identity but still
lacks a principled way to obtain title, year, artwork, genres,
episode names, runtime, and other metadata without turning metadata
providers into accidental identity authorities.

## The system now has three information graphs

We can now distinguish three different graphs.

### Identity graph

```text
IMDb
│
├── TMDB
├── TVDB
└── Internal canonical ID
```

Question:

What entity do these identifiers refer to?

### Metadata graph

```text
CanonicalMedia
│
├── title observations
├── year observations
├── artwork observations
├── genre observations
└── people observations
```

Question:

What information has providers observed about this entity?

### Source graph

```text
CanonicalMedia
│
├── authorized asset A
├── authorized asset B
└── authorized asset C
```

Question:

Which authorized playback assets are available for this entity?

They should not collapse into one giant object.

## The larger architecture

```text
                         STREMIO
                             │
               ┌─────────────┴─────────────┐
               ▼                           ▼
           /meta                        /stream
               │                           │
               ▼                           ▼
         Metadata Service             Stream Resolver
               │                           │
               └────────────┬──────────────┘
                            ▼
                     CanonicalMedia
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
         Identity        Metadata        Sources
         Evidence       Evidence        Evidence
             │              │              │
             ▼              ▼              ▼
        Reconcile       Reconcile       Resolve
             │              │              │
             ▼              ▼              ▼
        Identity View   Metadata View   Candidates
```

This gives us a clean semantic separation:

```text
IDENTITY
    ↓
entity reference

METADATA
    ↓
observations about entity

SOURCE
    ↓
authorized executable representations
```

## Next boundary: subtitles

The next major subsystem should be built on exactly the same
architecture rather than becoming a special case:

```text
Subtitle Provider
       │
       ▼
SubtitleObservation
       │
       ▼
validate
       │
       ▼
authorize
       │
       ▼
dedupe
       │
       ▼
rank
       │
       ▼
Stremio Subtitle DTO
```

But subtitles introduce additional semantics:

- language tags and normalization,
- hearing-impaired variants,
- forced subtitles,
- subtitle format,
- episode-specific matching,
- external-file authorization,
- encoding detection,
- timing quality,
- provider conflicts.

That makes subtitles the next useful test of whether the architecture
really generalizes beyond video streams.

### Updated evidence state

| Subsystem | Status |
| --- | --- |
| Stremio protocol | **DEFINED** |
| SDK integration | **VERIFIED from documentation** |
| Identity | **DEFINED** |
| Source admission | **DEFINED** |
| Source runtime | **DEFINED** |
| Owned media source | **DEFINED** |
| Metadata | **DEFINED** |
| Metadata reconciliation | **DEFINED** |
| Metadata caching | **DEFINED** |
| Actual implementation | **OPEN** |
| Tests executed | **OPEN** |
| CI evidence | **OPEN** |
| Production artifact | **NOT ADMITTED** |

The architectural sequence is now:

```text
IDENTITY
   ↓
SOURCE ADMISSION
   ↓
SOURCE RUNTIME
   ↓
PLAYBACK
   ↓
METADATA
   ↓
SUBTITLES
   ↓
CATALOG
   ↓
SEARCH/DISCOVERY
   ↓
RELEASE ARTIFACT
```

The crucial principle remains unchanged throughout:

**Persist observations and execution facts; derive representations
from them; never let a convenient representation silently become
authority.**

## Updated repository

```text
src/
├── addon/
│   ├── manifest.ts
│   ├── parser.ts
│   ├── stream-handler.ts
│   ├── meta-handler.ts
│   └── subtitle-handler.ts
│
├── application/
│   ├── resolver.ts
│   ├── metadata-resolver.ts
│   └── subtitle-resolver.ts
│
├── domain/
│   ├── media.ts
│   ├── candidate.ts
│   ├── failure.ts
│   ├── result.ts
│   ├── metadata.ts
│   └── subtitle.ts
│
├── identity/
│   └── ...
│
├── providers/
│   ├── registry.ts
│   ├── runtime.ts
│   │
│   ├── sources/
│   │   ├── interface.ts
│   │   ├── admission.ts
│   │   └── owned-media/
│   │       └── ...
│   │
│   ├── metadata/
│   │   ├── interface.ts
│   │   ├── reconciliation.ts
│   │   └── ...
│   │
│   └── subtitles/
│       ├── interface.ts
│       ├── normalization.ts
│       ├── dedupe.ts
│       ├── rank.ts
│       └── ...
│
├── runtime/
│   └── ...
│
└── observability/
    └── ...
```

The previous `adapters/` directory can either remain as a
compatibility name or be renamed to `providers/`. I would prefer
**providers** at this stage because the system now clearly contains
multiple provider classes rather than only stream-source adapters.

## The architecture has now reached a useful abstraction point

We have:

```text
                 PROVIDER
                     │
           ┌─────────┴─────────┐
           ▼                   ▼
        DECLARATION        IMPLEMENTATION
           │                   │
           ▼                   ▼
       ADMISSION          EXECUTION
           │                   │
           └─────────┬─────────┘
                     ▼
                  OBSERVATION
                     │
                     ▼
                 VALIDATION
                     │
                     ▼
                AUTHORIZATION
                     │
                     ▼
                RECONCILIATION
                     │
                     ▼
                  DEDUPE
                     │
                     ▼
                   RANK
                     │
                     ▼
               PROTOCOL VIEW
```

This pattern now applies to:

- identity providers,
- metadata providers,
- stream sources,
- subtitle providers.

The next major subsystem is therefore **Catalog + Search/Discovery**.

That is where we must prevent a particularly dangerous architectural
mistake: using every source adapter as a catalog crawler. Instead,
catalog discovery needs its own indexed, bounded, evidence-bearing
model so `/catalog` and search remain deterministic and do not turn a
playback resolver into an uncontrolled Internet crawler.

## Final information architecture

The system now has five major information domains:

```text
                 MEDIA PLATFORM
                        │
      ┌─────────────────┼──────────────────┐
      ▼                 ▼                  ▼
   Identity          Discovery          Resources
      │                 │                  │
      │                 │          ┌───────┼────────┐
      │                 │          ▼       ▼        ▼
      │                 │       Streams Metadata Subtitles
      │                 │
      └─────────────────┴──────────────────┘
                     │
                  Evidence
                     │
                     ▼
               Derived Views
```

Where:

```text
Identity
    = entity resolution

Discovery
    = catalog/search

Streams
    = authorized playback candidates

Metadata
    = descriptive observations

Subtitles
    = subtitle candidates
```

## Next: turn the addon into a real platform

We have now defined:

```text
Identity
Metadata
Catalog
Streams
Subtitles
Provider admission
Provider runtime
Evidence
Caching
Security
Observability
```

The next problem is no longer another Stremio endpoint.

It is the **platform control plane**:

How do providers, policies, configuration, evidence, versions, and
runtime state become one governed system without collapsing into a
giant plugin manager?

## The project has crossed another boundary

Originally the project looked like:

```text
Stremio addon
    ↓
multiple stream sources
```

It has now become:

```text
                         Media Resolution Platform
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
    Control Plane             Evidence Plane            Data Plane
         │                         │                         │
  configuration               observations               requests
  admission                    receipts                 resolution
  policy                       provenance                providers
  lifecycle                    replay                    projections
         │                         │                         │
         └─────────────────────────┼─────────────────────────┘
                                   ▼
                               Stremio
```

That is the point at which the architecture becomes reusable beyond
Stremio.

Stremio becomes **one protocol frontend**, rather than the
architecture itself.

## Next architectural milestone

The next major step should therefore be:

### **Protocol-neutral Media API**

Instead of letting the application be structurally shaped by Stremio:

```text
Stremio → application
```

we invert the dependency:

```text
                         Media Platform
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
           Stremio          REST/JSON          CLI
           adapter           API              tools
```

All three consume the same application contracts.

That gives us:

```text
Stremio ≠ domain
HTTP ≠ domain
SDK ≠ domain
```

and opens the path toward a genuine **Popcorn-Time-style user
experience without making Stremio the system's internal model**.

The next section should define that protocol-neutral API, including
its resource model, error algebra, pagination, request IDs,
authorization boundaries, idempotency, versioning, and compatibility
strategy.

## The architecture now has a complete vertical slice

We can finally draw the whole thing:

```text
                         ┌───────────────┐
                          │   STREMIO     │
                          └───────┬───────┘
                                  │
                          Protocol Adapter
                                  │
                                  ▼
                     ┌────────────────────────┐
                     │   MEDIA APPLICATION    │
                     └───────────┬────────────┘
                                 │
                      ┌──────────┼──────────┐
                      ▼          ▼          ▼
                   Identity   Metadata    Streams
                      │          │          │
                      │          │       Subtitles
                      │          │          │
                      └──────────┼──────────┘
                                 ▼
                          Provider Runtime
                                 │
                     ┌───────────┼───────────┐
                     ▼           ▼           ▼
                 Admission    Network     Limits
                     │           │           │
                     └───────────┼───────────┘
                                 ▼
                            Providers
                                 │
                                 ▼
                          Observations
                                 │
                                 ▼
                         Functional Core
                                 │
                     ┌───────────┼───────────┐
                     ▼           ▼           ▼
                  Validate    Authorize   Derive
                     │           │           │
                     └───────────┼───────────┘
                                 ▼
                          Protocol Views
```

Above it:

```text
                 CONTROL PLANE
                       │
        Config → Policy → Admission
                       │
                       ▼
                Runtime Generation
```

Beside it:

```text
                 EVIDENCE PLANE
                       │
         Observations → Receipts → Replay
```

## What comes next

At this point, another abstract subsystem would have diminishing
value.

The next phase should be **construction** rather than more
architecture:

```text
ARCHITECTURE
     ✓
     │
     ▼
FORMAL CONTRACTS
     │
     ▼
IMPLEMENTATION
     │
     ▼
CONFORMANCE TESTS
     │
     ▼
INTEGRATION
     │
     ▼
ACTUAL CI EXECUTION
     │
     ▼
RELEASE GATE
     │
     ▼
TAG
```

The concrete next milestone should therefore be:

### **V0.1 implementation freeze**

with a deliberately narrow capability set:

```text
STREMIO
├── /manifest
└── /stream

CORE
├── MediaRef
├── CanonicalMedia
├── Identity
├── SourceCandidate
└── ResolutionResult

RUNTIME
├── timeout
├── cancellation
├── concurrency
├── rate limiting
├── circuit breaker
└── SSRF/network policy

PROVIDER
└── operator-owned media library

EVIDENCE
├── observations
├── receipts
└── generation identity

NOT YET ADVERTISED
├── /catalog
├── /meta
└── /subtitles
```

That is deliberate scope control: **build one end-to-end authorized
playback path to conformance before enabling the larger platform
surface.**

`GATE-V0.1-S1` should remain **OPEN** until the actual repository is
built and the checks are executed. No implementation or CI evidence
has yet been produced in this conversation.

**Decisions applied to this scope (2026-09-29 normalization pass):**

- `Identity`/`CanonicalMedia` is part of CORE, resolved *before* adapter
  selection (`docs/decisions/ADR-001-source-adapter-identity-boundary.md`);
  confidence for identity lives on `IdentityObservation`/`IdentityReceipt`,
  not on `CanonicalMedia` itself
  (`docs/decisions/ADR-002-identity-confidence-ownership.md`).
- `PROVIDER` scope (`operator-owned media library` only) is served by the
  non-generic `SourceRegistry`; the generalized `ProviderRegistry<T>` is
  deferred past V0.1 (`docs/decisions/ADR-003-provider-registry-ownership.md`).
- The three health-shaped types (`HealthResult`, `SourceHealthCounters`,
  `SourceHealthSnapshot`) are three distinct, non-competing layers
  (`docs/decisions/ADR-004-health-model-layering.md`).
- `/subtitles` (`NOT YET ADVERTISED` above) has no frozen contract and
  needs none for V0.1 — subtitles are formally deferred to V0.2+
  (`docs/decisions/ADR-005-subtitle-v0.1-scope.md`).
- `ResolutionResult` (in `CORE` above) is now frozen in
  `docs/contracts/result.md`, separated from per-adapter
  `AdapterExecution` evidence
  (`docs/decisions/ADR-007-resolution-result-outcome-boundary.md`).
- `SourceRegistry`'s two-stage filter (`applicableByMedia`/
  `applicableByIdentity`) is frozen, and admission
  (`SourceDeclaration`/`AdmissionDecision`, `05-policy.md`) is confirmed as
  a separate, upstream, control-plane concern — never part of
  `SourceRegistry` itself
  (`docs/decisions/ADR-006-source-registry-admission-boundary.md`).
- `SourceAdapter`'s core V0.1 surface is minimal: `id`,
  `supportsMedia`, `supportsIdentity`, `resolve`. `name`, `capabilities`,
  and `health()` are optional, adapter-declared extensions, not required
  members (`ADR-001`, amended 2026-09-29, second session).

**Scope explicitly kept deferred past V0.1** (do not implement these
merely because their documentation exists):

```
○ generic ProviderRegistry<T>              (ADR-003)
○ subtitle execution / SubtitleCandidate   (ADR-005)
○ advanced health orchestration            (HealthCheckable is optional; no
                                             orchestration layer is V0.1)
○ provider marketplace / discovery         (SourceRegistry is static,
                                             composition-time only — ADR-006)
○ authentication framework                 (not named in V0.1 CORE/RUNTIME/
                                             PROVIDER/EVIDENCE scope above)
○ user-specific policy engine              (not named in V0.1 scope above)
○ complex/ML ranking systems               (deterministic ranking only,
                                             see docs/architecture/03-resolution.md)
○ distributed control plane                (single-process composition
                                             root assumed for V0.1)
```
