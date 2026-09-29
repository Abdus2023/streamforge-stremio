# StreamForge

**StreamForge — Authorized Stream Aggregation Engine for Stremio**

StreamForge is a modular, deterministic source-aggregation engine that connects Stremio to multiple independently implemented media sources through a common execution and policy pipeline.

It separates:

- media identity
- source discovery
- source execution
- candidate validation
- authorization
- deduplication
- ranking
- playback presentation
- observability
- failure evidence

The result is a small protocol adapter over a reusable aggregation kernel rather than a collection of provider-specific shortcuts.

## Design principle

```
External Sources
       │
       ▼
Source Adapters
       │
       ▼
 Normalization
       │
       ▼
  Validation
       │
       ▼
Authorization Policy
       │
       ▼
Deduplication
       │
       ▼
   Ranking
       │
       ▼
Stremio Mapping
       │
       ▼
   Stremio
```

The central rule is:

**A source candidate is not automatically an eligible playback stream.**

A returned URL is evidence that a source returned a URL.

It is not, by itself, evidence of authorization, validity, availability, or successful playback.

## Why StreamForge?

Multi-source media integrations tend to accumulate provider-specific logic inside the protocol handler.

That produces systems where:

```
Stremio request
     ↓
provider lookup
     ↓
provider parsing
     ↓
authorization assumption
     ↓
URL manipulation
     ↓
ranking
     ↓
response
```

becomes one large, difficult-to-test function.

StreamForge instead establishes explicit boundaries:

```
Protocol ≠ Identity ≠ Discovery ≠ Resolution ≠ Authorization ≠ Ranking ≠ Playback
```

Each boundary has a contract and can be tested independently.

## Core properties

### Deterministic

Given the same normalized candidates and policy configuration, StreamForge produces the same ordering.

Ranking uses deterministic tie-breakers rather than opaque or probabilistic behavior.

### Policy-aware

Candidates whose authorization state is:

```
authorized
unknown
denied
```

are represented separately.

`unknown` is never silently converted into `authorized`.

### Failure-preserving

A failed source does not erase successful results from other sources.

The resolver distinguishes:

```
success
empty
partial
failed
```

rather than reducing every condition to:

```
streams: []
```

### Provider-isolated

A source adapter cannot redefine the core domain model.

Provider-specific fields remain at the adapter boundary.

### Protocol-independent core

The aggregation engine does not depend on Stremio semantics.

Stremio is an output adapter.

The resolver can therefore be reused by another presentation layer later.

### Resilient

The runtime architecture supports:

- request timeouts
- cancellation
- bounded concurrency
- rate limiting
- circuit breakers
- caching
- in-flight request deduplication

### Observable

Execution preserves source-level status and failure information.

Operational evidence is not confused with playback success.

## Architecture

```
┌──────────────────────────────────────────────┐
│                  Stremio                      │
└───────────────────────┬──────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────┐
│              Protocol Adapter                 │
│        parse → delegate → map response        │
└───────────────────────┬──────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────┐
│                 Resolver                      │
│                                                │
│  identity → execute → validate → policy       │
│           → dedupe → rank                     │
└──────────────┬───────────────────┬────────────┘
               │                   │
               ▼                   ▼
      ┌────────────────┐   ┌────────────────┐
      │ Source Registry │   │ Runtime Guard  │
      └───────┬─────────┘   └────────────────┘
              │
       ┌──────┼────────┬────────┐
       ▼      ▼         ▼        ▼
    Adapter Adapter  Adapter  Adapter
       │      │         │        │
       └──────┴────────┴────────┘
                  │
                  ▼
          SourceCandidate[]
```

## Source lifecycle

Every source follows the same conceptual lifecycle:

```
Source Adapter
      │
      ▼
Source Response
      │
      ▼
Normalization
      │
      ▼
Structural Validation
      │
      ▼
Authorization Policy
      │
      ├── rejected
      │
      ▼
Eligible Candidate
      │
      ▼
Deduplication
      │
      ▼
Ranking
      │
      ▼
Stremio Stream
```

The Stremio mapper does not perform resolution, authorization, deduplication, or ranking.

## Candidate model

The internal unit of aggregation is a `SourceCandidate`.

> The normative, frozen definition of `SourceCandidate` lives in
> [`docs/contracts/stream.md`](docs/contracts/stream.md). The shape below
> is a compatible illustration for README purposes (non-`readonly`, for
> readability) — if it ever drifts from the contract file, the contract
> file wins.

Conceptually:

```ts
interface SourceCandidate {
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
    audio?: readonly string[];
    subtitle?: readonly string[];
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

The candidate is an internal evidence-bearing object.

It is not yet a Stremio stream.

## Authorization

StreamForge deliberately treats authorization as an explicit domain property.

Supported states:

```
authorized
unknown
denied
```

The default policy is conservative:

```
authorized → eligible
unknown    → rejected
denied     → rejected
```

This architecture is designed for sources that are:

- public-domain
- licensed
- explicitly authorized
- user-owned
- locally controlled
- otherwise permitted by the deployment and source terms

StreamForge does not treat the existence of a publicly reachable URL as proof that its use is authorized.

## Source adapter contract

> The normative, frozen definition of `SourceAdapter` (including the
> optional `health()` probe and the still-open question of whether
> capability/identity-aware adapters belong in this contract) lives in
> [`docs/contracts/source-adapter.md`](docs/contracts/source-adapter.md).
> The shape below is a simplified illustration for README purposes.

Adapters implement a narrow interface:

```ts
interface SourceAdapter {
  readonly id: string;
  readonly name: string;

  supports(media: MediaRef): boolean;

  resolve(
    media: MediaRef,
    ctx: ResolveContext
  ): Promise<readonly SourceCandidate[]>;
}
```

This makes sources independently replaceable.

A resolver does not need to know how a source works internally.

## Runtime controls

Source execution is guarded by runtime controls:

```
       Adapter
          │
          ▼
   Circuit Breaker
          │
          ▼
    Rate Limiter
          │
          ▼
  Concurrency Gate
          │
          ▼
       Timeout
          │
          ▼
   Source Request
```

Important invariant:

A timeout must cancel the underlying operation, not merely stop waiting for its promise.

## Failure semantics

StreamForge distinguishes source outcomes.

```
success
empty
partial
failed
```

For individual adapters:

```
success
empty
timeout
aborted
rate_limited
circuit_open
invalid_response
network_error
error
```

Example:

```
Source A → success
Source B → timeout
Source C → empty
Source D → success

Resolver
   ↓
partial
```

The successful results from A and D remain usable.

## Deterministic ranking

Ranking is deliberately simple at the beginning.

The initial ordering considers:

1. direct playback capability
2. video resolution
3. bitrate
4. source identifier

For example:

```
1080p direct > 720p direct > 1080p indirect
```

The exact policy is configurable and must remain deterministic.

Machine-learning ranking is intentionally outside the initial conformance boundary.

## Deduplication

Candidates are deduplicated using a canonical identity composed from media identity and normalized location.

Conceptually:

```
media type + media ID + season + episode + canonical URL
```

URL fragments are ignored during canonicalization.

Deduplication occurs before ranking.

## Identity

Identity resolution is independent from source discovery.

StreamForge can represent namespaced identities such as:

```
imdb:tt1234567
tmdb:123456
internal:movie:abc123
```

Series episodes preserve:

```
series identity + season + episode
```

An ambiguous identity must not be silently replaced with an arbitrary match.

## Security boundaries

StreamForge treats external URLs as untrusted input.

The runtime HTTP layer is designed to enforce:

- `http:` / `https:` restrictions
- response-size limits
- content-type validation
- redirect validation
- request cancellation
- timeout limits
- SSRF protections for server-side requests

Server-side fetching of arbitrary provider-returned URLs is not assumed to be safe.

In particular:

Hostname validation alone is not sufficient for production-grade SSRF protection.

DNS resolution and IP-address binding must be handled correctly before claiming complete SSRF protection.

## Playback model

StreamForge does not automatically proxy every media URL.

The preferred model is:

```
StreamForge
     │
     ▼
eligible stream URL
     │
     ▼
Stremio
     │
     ▼
client playback
```

A server-side proxy is a separate capability with its own security, authorization, bandwidth, caching, and abuse considerations.

It is not implicit in source aggregation.

## Subtitles

Subtitles are modeled independently from media streams.

```
Subtitle Adapter
       │
       ▼
Subtitle Candidate
       │
       ▼
Validation
       │
       ▼
Authorization
       │
       ▼
Deduplication
       │
       ▼
Ranking
       │
       ▼
Stremio Subtitle
```

Stream authorization and subtitle authorization are separate concerns.

## Metadata and catalog

Metadata is deliberately not conflated with playback.

```
Catalog ≠ Metadata ≠ Identity ≠ Stream Discovery ≠ Subtitle Discovery
```

A source that can provide metadata does not automatically become a stream provider.

A source that can provide streams does not automatically become a metadata provider.

## Observability

The system should expose structured operational information such as:

```
resolver_requests_total
resolver_success_total
resolver_empty_total
resolver_partial_total
resolver_failure_total

adapter_requests_total
adapter_success_total
adapter_timeout_total
adapter_rate_limit_total
adapter_error_total

cache_hit_total
cache_miss_total
cache_stale_total

candidate_seen_total
candidate_rejected_total
candidate_emitted_total
```

Metrics must avoid unbounded labels.

Logs must not expose:

- credentials
- authorization tokens
- private user identifiers
- sensitive query data
- private media URLs when unnecessary

## Health

Two health concepts are intentionally separated:

```
/health/live
/health/ready
```

`live` means the process is alive.

`ready` means the required runtime is operational.

An optional source becoming unavailable should normally produce degraded functionality rather than make the entire addon unavailable.

## Repository structure

> **Status: DESIGNED, not present.** No implementation exists in this
> repository yet — there is no `src/`, `test/`, `Dockerfile`,
> `compose.yaml`, `tsconfig.json`, or `package-lock.json` on disk today
> (verified 2026-09-29). The tree below is the **target** layout the
> architecture is designed against, not a description of what currently
> exists. See [`docs/architecture/13-roadmap.md`](docs/architecture/13-roadmap.md)
> for the authoritative implemented/planned breakdown.

```
streamforge-stremio/
│
├── src/
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
├── test/
│   ├── domain/
│   ├── runtime/
│   ├── resolver/
│   ├── addon/
│   └── integration/
│
├── Dockerfile
├── compose.yaml
├── package.json
├── package-lock.json
├── tsconfig.json
└── README.md
```

## Development

> **Status: DESIGNED, not present.** `package.json` in this repository
> currently defines no `scripts` and no `dependencies` (verified
> 2026-09-29). The commands below are the **intended** developer workflow
> once implementation begins; running them today will fail with
> "missing script" errors. This is not a documentation error to silently
> fix by adding placeholder scripts — see
> [`docs/architecture/13-roadmap.md`](docs/architecture/13-roadmap.md) for
> the construction sequence that precedes real scripts existing.

Requirements:

- Node.js 22+
- npm

Install:

```
npm ci
```

Type-check:

```
npm run typecheck
```

Run tests:

```
npm test
```

Build:

```
npm run build
```

Run the complete local check:

```
npm run check
```

Development server:

```
npm run dev
```

## Testing philosophy

Tests are organized around invariants rather than implementation details.

Important invariants include:

```
1. Unauthorized candidates are never emitted.
2. Unknown authorization is never treated as authorized.
3. One failed source does not erase successful sources.
4. Timeout cancellation reaches the underlying operation.
5. Global cancellation reaches source operations.
6. Concurrency is bounded.
7. Circuit-open sources are not executed.
8. Ranking is deterministic.
9. Deduplication is deterministic.
10. Stremio mapping performs no source resolution.
11. Cached candidates pass through current policy.
12. Stale cache state remains distinguishable.
13. Arbitrary provider URLs are not automatically proxied.
14. Season and episode coordinates cannot silently change.
15. Ambiguous media identity is not silently resolved.
```

## Verification model

StreamForge follows an evidence-first development model.

```
PROVED
ARGUMENT
CONJECTURE
OPEN
```

and:

```
VERIFIED
PARTIALLY_VERIFIED
PROVISIONAL
BLOCKED
```

Source code inspection is not execution evidence.

The release pipeline is the execution authority.

Therefore:

```
NO EVIDENCE
     ↓
NO VERIFIED CLAIM
```

## Release discipline

The intended release sequence is:

```
freeze
   ↓
formalize
   ↓
implement
   ↓
test
   ↓
release gate
   ↓
tag
```

A release candidate should demonstrate:

```
npm ci
   ↓
typecheck
   ↓
unit tests
   ↓
integration tests
   ↓
build
   ↓
container build
   ↓
container smoke test
   ↓
CI success
   ↓
artifact digest
   ↓
release tag
```

## Current scope

> **Status: all items below are DESIGNED, none are IMPLEMENTED.** The
> checkmarks describe what the *initial release is designed to cover*,
> not what exists in this repository today — there is no `src/` or
> `test/` directory yet (verified 2026-09-29). See
> [`docs/architecture/13-roadmap.md`](docs/architecture/13-roadmap.md) for
> the authoritative, evidence-based implementation-status ledger.

The initial release is designed to cover the aggregation kernel:

```
✓ domain model            (DESIGNED)
✓ source adapter contract (DESIGNED)
✓ registry                (DESIGNED)
✓ candidate validation    (DESIGNED)
✓ authorization policy    (DESIGNED)
✓ deduplication           (DESIGNED)
✓ deterministic ranking   (DESIGNED)
✓ timeout propagation     (DESIGNED)
✓ concurrency control     (DESIGNED)
✓ resolver result semantics (DESIGNED)
✓ Stremio stream mapping  (DESIGNED)
✓ health model            (DESIGNED)
✓ test architecture       (DESIGNED)
```

Here, "✓" means "the design for this is written down," not "this is
built." Nothing in this list has a corresponding file in `src/` or `test/`
yet.

The following remain separate expansion stages:

```
○ identity provider
○ metadata provider
○ catalog provider
○ subtitle protocol
○ production cache
○ production SSRF-safe HTTP client
○ source-specific adapters
○ observability backend
○ deployment configuration
```

## What StreamForge does not do

StreamForge is not designed to:

- bypass DRM
- defeat access controls
- steal credentials
- scrape private APIs
- circumvent authentication
- proxy arbitrary third-party URLs
- automatically download copyrighted media from unauthorized sources
- conceal source authorization status
- turn an unknown source into an authorized source merely because it is reachable

Source adapters are expected to operate only against sources the deployment is permitted to access and use.

## Roadmap

### Phase 1 — Conformance kernel

```
[ current ]
domain
resolver
policy
runtime
Stremio protocol
tests
CI
```

### Phase 2 — Identity

```
Stremio ID
     ↓
Canonical Media
     ↓
Identity Evidence
     ↓
Source Query
```

### Phase 3 — Source capability negotiation

```
Source
   ↓
Capabilities
   ↓
Admission
   ↓
Execution
```

### Phase 4 — Metadata

```
Catalog
   ↓
Identity
   ↓
Metadata
```

### Phase 5 — Subtitles

```
Subtitle discovery
     ↓
validation
     ↓
authorization
     ↓
ranking
     ↓
Stremio
```

### Phase 6 — Production runtime

```
cache
rate limits
circuit breakers
SSRF-safe HTTP
metrics
tracing
deployment
```

### Phase 7 — Source ecosystem

Each adapter remains independently testable and replaceable.

## Architectural rule

The most important rule in StreamForge is:

**Adapters discover. The kernel decides. The protocol presents.**

An adapter reports what it observed.

The kernel determines whether the candidate is structurally valid and policy-eligible.

The ranking layer determines deterministic ordering among eligible candidates.

The Stremio layer presents the result.

No layer silently assumes the authority of another.

## License

Choose the repository license explicitly before the first public release.

Do not inherit a license accidentally from a template or dependency.

Also review the terms of every external source adapter independently; the repository license does not grant permission to access or redistribute third-party media.
