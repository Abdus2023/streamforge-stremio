# Domain Model

[⇧ Architecture index](../architecture.md) · [⇆ Document map](./README.md)

> **Scope.** The canonical, protocol-neutral domain model: `MediaRef`, `CanonicalMedia`, `ExternalIdentity`, `SourceCandidate`, `Stream`, `Subtitle`, `ResolutionResult`, `CatalogEntry`, and related identity/metadata/catalog value types. Defines identity semantics (what a canonical identity is, how ambiguity and conflicts are represented) as pure data/type contracts. Does not leak provider-specific schemas or describe how candidates are produced or ranked (see `03-resolution.md`, `04-providers.md`).

> **Primary dependencies:** `../contracts/identity.md`, `../contracts/stream.md`

> **Status.** Unless a section explicitly states otherwise with a concrete repository reference (file path, commit, or CI run), everything below is **DESIGNED** or **PROPOSED** architecture, not implemented code. This document was migrated from the original `docs/architecture.md` monolith; section order is preserved from that document, numbering has been dropped in favor of descriptive headings, and some very long single sections in the monolith may appear here still bearing internal editorial framing (e.g. first-person design narration) that predates the doc-split.

## Sections in this document

- [Core domain model](#core-domain-model)
- [Metadata architecture](#metadata-architecture)
- [Subtitles](#subtitles)
- [Freeze the domain contract first](#freeze-the-domain-contract-first)
- [Candidate is not yet a stream](#candidate-is-not-yet-a-stream)
- [Media identity](#media-identity)
- [Unknown versus invalid](#unknown-versus-invalid)
- [Never silently resolve ambiguity](#never-silently-resolve-ambiguity)
- [Canonical media identity](#canonical-media-identity)
- [Movie and episode identity](#movie-and-episode-identity)
- [Identity normalization](#identity-normalization)
- [Identity aliases](#identity-aliases)
- [Identity conflicts](#identity-conflicts)
- [Metadata is a separate capability](#metadata-is-a-separate-capability)
- [Catalog strategy](#catalog-strategy)
- [Catalog identity should be deterministic](#catalog-identity-should-be-deterministic)
- [Namespace IDs](#namespace-ids)
- [Subtitle architecture](#subtitle-architecture)
- [Presentation metadata](#presentation-metadata)
- [Complete domain topology](#complete-domain-topology)
- [Domain: `media.ts`](#domain-mediats)
- [Domain: candidate](#domain-candidate)
- [Domain: failures](#domain-failures)
- [Domain: result](#domain-result)
- [Make invalid states harder to represent](#make-invalid-states-harder-to-represent)
- [Identity compatibility](#identity-compatibility)
- [Identity failure must be explicit](#identity-failure-must-be-explicit)
- [Identity graph](#identity-graph)
- [Subtitle model](#subtitle-model)
- [Why IMDb IDs Are Useful Here](#why-imdb-ids-are-useful-here)
- [Subtitles Follow the Same Candidate Model](#subtitles-follow-the-same-candidate-model)
- [Identity Layer — From String IDs to Canonical Media](#identity-layer-—-from-string-ids-to-canonical-media)
- [Identity State Machine](#identity-state-machine)
- [Identity Domain Model](#identity-domain-model)
- [Identity Is a Graph](#identity-is-a-graph)
- [Identity vs Source](#identity-vs-source)
- [Identity Normalization](#identity-normalization)
- [Identity Key](#identity-key)
- [Canonical ID](#canonical-id)
- [Identity Confidence](#identity-confidence)
- [Identity Graph Storage](#identity-graph-storage)
- [Avoid Premature Graph Infrastructure](#avoid-premature-graph-infrastructure)
- [Identity Failure Matrix](#identity-failure-matrix)
- [Identity Authority](#identity-authority)
- [The resulting state machine](#the-resulting-state-machine)
- [Series assets](#series-assets)
- [Metadata must become its own subsystem](#metadata-must-become-its-own-subsystem)
- [`MetadataRecord`](#metadatarecord)
- [Metadata state machine](#metadata-state-machine)
- [Identity-linked metadata](#identity-linked-metadata)
- [Artwork is special](#artwork-is-special)
- [Series metadata](#series-metadata)
- [Subtitles: the first auxiliary playback capability](#subtitles-the-first-auxiliary-playback-capability)
- [Subtitle domain model](#subtitle-domain-model)
- [Episode matching](#episode-matching)
- [Catalog as an explicit capability](#catalog-as-an-explicit-capability)
- [Catalog identity is not automatically canonical](#catalog-identity-is-not-automatically-canonical)
- [Catalog index](#catalog-index)
- [Catalog entry](#catalog-entry)
- [Search result identity](#search-result-identity)
- [Candidate identity](#candidate-identity)

---

## Core domain model

Don't let external source formats leak into the addon.

> **HISTORICAL / SUPERSEDED.** The `MediaRef` below is an early draft that
> embeds `imdbId`/`tmdbId` directly on the type. It is superseded by the
> frozen `MediaRef` in [`../contracts/identity.md`](../contracts/identity.md),
> which keeps external identifiers in `ExternalIdentity` instead. See
> `docs/decisions/README.md` (`OPEN-5`, `RESOLVED`). The `SourceCandidate`
> below is also an early draft — see the note further down for details.

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
```

> **HISTORICAL / SUPERSEDED.** `capabilities.authorized: boolean` below
> cannot represent the required `authorized | unknown | denied` tri-state
> and conflicts with the authorization invariant (see `05-policy.md`).
> Superseded by the frozen shape in
> [`../contracts/stream.md`](../contracts/stream.md). See
> `docs/decisions/README.md` (`OPEN-7`, `RESOLVED`).

```ts
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

## Metadata architecture

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

> **HISTORICAL / SUPERSEDED.** Earliest `CanonicalMedia` draft — conflates
> identity with presentation fields (`title`, `year`, `imdbId`, `tmdbId`).
> Superseded by the frozen shape in
> [`../contracts/identity.md`](../contracts/identity.md). See
> `docs/decisions/README.md` (`OPEN-6`, `RESOLVED`).

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

## Subtitles

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

## Freeze the domain contract first

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

> **HISTORICAL / SUPERSEDED.** Same issue as the other early `MediaRef`
> drafts — embeds `imdbId`/`tmdbId` directly. See
> [`../contracts/identity.md`](../contracts/identity.md) and
> `docs/decisions/README.md` (`OPEN-5`, `RESOLVED`).

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

## Candidate is not yet a stream

This distinction is fundamental.

> **HISTORICAL.** This intermediate `SourceCandidate` draft matches the
> frozen field structure but omits the `authorization` block entirely.
> See [`../contracts/stream.md`](../contracts/stream.md) and
> `docs/decisions/README.md` (`OPEN-7`).

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

## Media identity

> **HISTORICAL / SUPERSEDED.** Same issue as the earlier `MediaRef` draft
> above — embeds `imdbId`/`tmdbId` directly. See
> [`../contracts/identity.md`](../contracts/identity.md) and
> `docs/decisions/README.md` (`OPEN-5`, `RESOLVED`).

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

## Unknown versus invalid

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

## Never silently resolve ambiguity

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

## Canonical media identity

> **HISTORICAL / SUPERSEDED.** Embeds `imdbId`/`tmdbId`/`title`/`year`
> directly rather than a provenance-bearing `identities` array. Superseded
> by the frozen shape in
> [`../contracts/identity.md`](../contracts/identity.md). See
> `docs/decisions/README.md` (`OPEN-6`, `RESOLVED`).

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

## Movie and episode identity

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

## Identity normalization

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

## Identity aliases

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

## Identity conflicts

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

## Metadata is a separate capability

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

## Catalog strategy

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

## Catalog identity should be deterministic

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

## Namespace IDs

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

## Subtitle architecture

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

## Presentation metadata

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

## Complete domain topology

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

## Domain: `media.ts`

> **See the normative contract:** [`../contracts/identity.md`](../contracts/identity.md)
> defines `MediaRef` once, authoritatively. This occurrence matches it
> exactly and was used as the canonical source when the contract was
> extracted.

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

## Domain: candidate

> **See the normative contract:** [`docs/contracts/stream.md`](../contracts/stream.md) defines `SourceCandidate` and the `Stream` mapping once, authoritatively.

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

## Domain: failures

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

## Domain: result

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

## Make invalid states harder to represent

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

## Identity compatibility

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

> **HISTORICAL / SUPERSEDED.** This intermediate draft represents
> `identities` as a `ReadonlyMap<IdentityKind, string>`, losing
> per-identity provenance (`source`, `observedAt`). Superseded by the
> frozen shape in [`../contracts/identity.md`](../contracts/identity.md).
> See `docs/decisions/README.md` (`OPEN-6`, `RESOLVED`).

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

## Identity failure must be explicit

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

## Identity graph

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

## Subtitle model

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

## Why IMDb IDs Are Useful Here

For a stream-only addon:

```text
Stremio/Cinemeta
       │
       │ canonical IMDb ID
       ▼
tt1234567
       │
       ▼
our addon
       │
       ├── source A
       ├── source B
       └── source C
```

We don't need to duplicate metadata merely to attach streams to an
existing Cinemeta item.

The SDK documentation explicitly describes this model: an addon
declaring `tt` stream IDs can provide streams for Cinemeta items
without implementing its own metadata resource.

That means:

```text
META AUTHORITY
     │
     ▼
Cinemeta / Stremio ecosystem

STREAM AUTHORITY
     │
     ▼
our addon
```

This is a cleaner separation.

## Subtitles Follow the Same Candidate Model

Instead of special-casing subtitles:

```ts
interface SubtitleCandidate {
  id: string;
  media: MediaRef;

  url: string;

  language: string;

  format: "srt" | "vtt" | "ass" | "ssa" | "unknown";

  hearingImpaired: boolean;

  provenance: Provenance;

  authorization: Authorization;
}
```

Pipeline:

```text
subtitle adapter
      ↓
validate
      ↓
authorize
      ↓
dedupe
      ↓
rank
      ↓
Stremio subtitle object
```

The protocol documentation confirms subtitles are a first-class addon
resource.

## Identity Layer — From String IDs to Canonical Media

The next boundary is identity.

The fundamental rule is:

**A provider identifier is evidence about an entity, not the entity
itself.**

So:

```text
"tt1234567"
```

must not become the internal canonical identity merely because
Stremio supplied it.

Instead:

```text
Stremio ID
    ↓
identity observation
    ↓
identity resolution
    ↓
CanonicalMedia
    ↓
source routing
```

This prevents provider-specific IDs from leaking through the whole
system.

## Identity State Machine

Identity resolution needs more states than success/failure.

```text
                  ┌───────────────┐
                   │ NOT_REQUESTED │
                   └───────┬───────┘
                           │
                           ▼
                   ┌───────────────┐
                   │    RESOLVING  │
                   └───────┬───────┘
                           │
              ┌────────────┼─────────────┐
              ▼            ▼             ▼
          NOT_FOUND    RESOLVED      AMBIGUOUS
              │            │             │
              │            ▼             │
              │       CANONICAL         │
              │        MEDIA             │
              │            │             │
              └────────────┴─────────────┘
```

The distinction is essential:

| State | Meaning |
| --- | --- |
| `NOT_FOUND` | Provider explicitly reports no matching identity |
| `NOT_RESOLVED` | We cannot currently establish identity |
| `AMBIGUOUS` | Multiple plausible identities remain |
| `RESOLVED` | Sufficient evidence establishes one canonical entity |

These must not collapse into:

```text
null
```

because `null` destroys semantics.

## Identity Domain Model

> **See the normative contract:** [`docs/contracts/identity.md`](../contracts/identity.md) defines `MediaRef`, `ExternalIdentity`, and `CanonicalMedia` once, authoritatively.

Create:

```text
src/identity/
├── types.ts
├── resolver.ts
├── registry.ts
├── normalize.ts
├── graph.ts
├── confidence.ts
└── cache.ts
```

The fundamental types:

```ts
export type IdentityKind = "imdb" | "tmdb" | "tvdb" | "internal";

export interface ExternalIdentity {
  readonly kind: IdentityKind;
  readonly value: string;
  readonly source: string;
  readonly observedAt: string;
}
```

Then:

```ts
export interface CanonicalMedia {
  readonly canonicalId: string;

  readonly media: MediaRef;

  readonly identities: readonly ExternalIdentity[];

  readonly resolvedAt: string;
}
```

Example:

```json
{
  "canonicalId": "media:01J...",
  "media": {
    "type": "movie",
    "id": "tt1234567"
  },
  "identities": [
    {
      "kind": "imdb",
      "value": "tt1234567",
      "source": "cinemeta",
      "observedAt": "2026-09-28T20:00:00Z"
    },
    {
      "kind": "tmdb",
      "value": "550",
      "source": "tmdb",
      "observedAt": "2026-09-28T20:00:01Z"
    }
  ],
  "resolvedAt": "2026-09-28T20:00:01Z"
}
```

The canonical ID is ours.

The external identifiers remain provenance-bearing observations.

## Identity Is a Graph

A better mental model is:

```text
                    ┌─────────────┐
                     │ Canonical   │
                     │   Media     │
                     └──────┬──────┘
                            │
              ┌─────────────┼──────────────┐
              │             │              │
              ▼             ▼              ▼
         IMDb ID        TMDB ID        TVDB ID
        tt1234567         550           550
              │             │              │
              ▼             ▼              ▼
           Source A      Source B       Source C
```

The edges have provenance.

We should not merely store:

```text
IMDb = tt1234567
TMDB = 550
```

but:

```text
IMDb → tt1234567
    observed by → provider X
    observed at → timestamp
    evidence → receipt
```

This becomes valuable when providers disagree.

## Identity vs Source

This distinction should be explicit:

```text
                    REQUEST
                        │
                        ▼
                   IDENTITY
                        │
              "What media is this?"
                        │
                        ▼
                 CANONICAL MEDIA
                        │
                        ▼
                    ROUTING
                        │
              "Who can handle it?"
                        │
                        ▼
                   SOURCES
                        │
              "What can play it?"
                        │
                        ▼
                 CANDIDATES
```

Without this separation, adapters eventually start doing their own
incompatible identity matching.

That produces:

```text
Source A → title matching
Source B → IMDb matching
Source C → filename matching
Source D → fuzzy matching
```

and the resolver no longer knows why two sources supposedly refer to
the same thing.

## Identity Normalization

External IDs need strict normalization.

IMDb:

```ts
export function normalizeImdbId(value: string): string {
  const normalized = value.trim().toLowerCase();

  if (!/^tt\d+$/.test(normalized)) {
    throw new Error("Invalid IMDb identifier");
  }

  return normalized;
}
```

TMDB:

```ts
export function normalizeTmdbId(value: string): string {
  const normalized = value.trim();

  if (!/^\d+$/.test(normalized)) {
    throw new Error("Invalid TMDB identifier");
  }

  return normalized;
}
```

The normalized value becomes:

```text
identity key = kind + ":" + normalizedValue
```

Examples:

```text
imdb:tt1234567
tmdb:550
tvdb:12345
```

## Identity Key

```ts
export function identityKey(identity: ExternalIdentity): string {
  return `${identity.kind}:${identity.value}`;
}
```

Never use:

```text
identity.value
```

alone.

Otherwise:

```text
tmdb:550
```

and:

```text
tvdb:550
```

would collide.

## Canonical ID

A canonical ID should not be derived from the first provider ID
encountered.

Bad:

```text
canonicalId = "imdb:tt1234567"
```

because the system then implicitly declares IMDb authoritative.

Better:

```text
canonicalId = "media:<stable-id>"
```

For a first implementation, UUID/ULID-style identifiers are
sufficient.

For deterministic reconstruction from evidence, another possibility
is:

```text
canonicalId = hash(
  normalized identity evidence
)
```

But this requires much stronger identity semantics.

Therefore for v0.1:

```text
canonicalId = opaque internal identity
```

and canonicality is established by the resolver/evidence layer.

## Identity Confidence

Avoid a single arbitrary number such as:

```text
confidence = 0.87
```

unless the calibration methodology exists.

Instead use evidence classes:

```ts
export type IdentityEvidence =
  | {
      type: "exact_provider_mapping";
      source: string;
    }
  | {
      type: "explicit_cross_reference";
      source: string;
    }
  | {
      type: "exact_external_id";
      source: string;
    }
  | {
      type: "title_year_match";
      source: string;
    }
  | {
      type: "fuzzy_match";
      source: string;
    };
```

Then policy can say:

```text
exact cross-reference
    → routable

title/year match
    → not sufficient for high-risk source

fuzzy match
    → never silently canonical
```

This is more auditable than an unexplained confidence score.

## Identity Graph Storage

For v0.1:

```text
in-memory
```

is sufficient.

For later persistence:

```text
identity_edges
────────────────────────────────────
from_kind
from_value
to_kind
to_value
source
observed_at
evidence_id
status
```

Example:

```text
imdb:tt1234567
       │
       │ observed by provider-x
       ▼
tmdb:550
```

A graph database is **not** required.

A relational/document representation is sufficient initially.

## Avoid Premature Graph Infrastructure

Do not introduce:

```text
Neo4j
graph database
distributed identity service
```

for v0.1.

The semantic model is a graph.

The implementation does not have to be.

This is another important distinction:

```text
conceptual model ≠ required storage technology
```

A simple:

```text
Map<IdentityKey, IdentityRecord>
```

can implement the initial model.

## Identity Failure Matrix

| Observation set | Resolution |
| --- | --- |
| exact mapping | `resolved` |
| agreeing mappings | `resolved` |
| conflicting mappings | `ambiguous` |
| all explicit not-found | `not_found` |
| timeout only | `not_resolved` |
| rate limit only | `not_resolved` |
| not-found + timeout | `not_resolved` |
| ambiguous + timeout | `ambiguous` |

This preserves information rather than flattening it.

## Identity Authority

There should also be an explicit distinction between:

```text
identity source
```

and:

```text
identity authority
```

An API returning:

```text
IMDb tt1234567 → TMDB 550
```

provides an observation.

The application may decide:

```text
this observation is sufficient for routing
```

But that decision is application policy.

Therefore:

```text
provider observation ≠ application authority
```

This mirrors the earlier rule:

```text
source health ≠ source authorization
```

and:

```text
canonicality ≠ truth
```

## The resulting state machine

We can now describe the complete resolution lifecycle:

```text
                   REQUEST
                       │
                       ▼
                    PARSE
                       │
                       ▼
                  IDENTITY
                       │
         ┌─────────────┼──────────────┐
         ▼             ▼              ▼
     NOT_FOUND    NOT_RESOLVED    AMBIGUOUS
         │             │              │
         └─────────────┴──────────────┘
                       │
                   RESOLVED
                       │
                       ▼
               CAPABILITY FILTER
                       │
                       ▼
               IDENTITY FILTER
                       │
                       ▼
                ADMISSION
                       │
                  ┌────┴────┐
                  ▼         ▼
               REJECT      ADMIT
                            │
                            ▼
                       CIRCUIT
                            │
                            ▼
                      RATE LIMIT
                            │
                            ▼
                      CONCURRENCY
                            │
                            ▼
                        TIMEOUT
                            │
                            ▼
                      NETWORK POLICY
                            │
                            ▼
                        EXECUTE
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
                        PRESENT
```

This is now approaching a real execution architecture rather than
merely a Stremio wrapper.

## Series assets

Series need a stronger asset key.

A movie:

```text
media:movie-001
```

is enough.

An episode requires:

```text
media:series-001
season=2
episode=7
```

Therefore the library record needs:

```ts
interface LibraryAsset {
  readonly assetId: string;
  readonly canonicalId: string;

  readonly episode?: {
    readonly season: number;
    readonly episode: number;
  };

  // ...
}
```

Then lookup should be:

```text
findAssets(
  canonicalId,
  media,
  signal
)
```

rather than relying only on the series canonical ID.

Better:

```ts
interface MediaLibrary {
  findAssets(
    media: MediaRef,
    canonicalId: string,
    signal: AbortSignal
  ): Promise<readonly LibraryAsset[]>;
}
```

Now:

```text
movie  → canonicalId
series  → canonicalId + season + episode
```

cannot accidentally collapse into the same lookup.

## Metadata must become its own subsystem

We now have:

```text
Stremio ID
    ↓
Identity
    ↓
CanonicalMedia
    ↓
Authorized sources
    ↓
Playable candidates
```

But Stremio eventually needs more than playback.

It needs to know things such as:

- title
- year
- poster
- background
- description
- genres
- runtime
- cast
- directors
- season information
- episode title
- episode description

The dangerous shortcut is:

```text
metadata provider
      ↓
"therefore this is the identity"
```

That would allow metadata to silently become identity authority.

Instead:

```text
IDENTITY
    │
    ├───────────────┐
    ▼               ▼
CanonicalMedia    Metadata
                    │
                    ├── title
                    ├── year
                    ├── artwork
                    ├── genres
                    └── description
```

Metadata enriches an entity.

It does not define the entity by itself.

## `MetadataRecord`

The derived application view can be:

```ts
interface MetadataRecord {
  readonly canonicalId: string;

  readonly fields: Readonly<Partial<Record<MetadataField, MetadataValue>>>;

  readonly generatedAt: string;
}
```

And:

```ts
interface MetadataValue<T = unknown> {
  readonly value: T;

  readonly sources: readonly string[];

  readonly evidenceIds: readonly string[];

  readonly confidence: "high" | "medium" | "low";
}
```

Important:

`MetadataRecord` is a **derived view**.

The observations remain the underlying facts.

```text
OBSERVATIONS
     │
     ▼
RECONCILIATION
     │
     ▼
MetadataRecord
     │
     ▼
Stremio Meta DTO
```

## Metadata state machine

Metadata should preserve the same epistemic distinction already used
for identity.

```text
REQUEST
   │
   ▼
PROVIDER QUERY
   │
   ├── SUCCESS
   │
   ├── NOT_FOUND
   │
   ├── NOT_RESOLVED
   │
   └── AMBIGUOUS
```

Then:

```text
multiple observations
        │
        ▼
reconciliation
        │
        ├── agreed
        ├── merged
        └── conflict
```

No provider failure becomes:

```text
"there is no metadata"
```

For example:

```text
timeout ≠ not_found
```

## Identity-linked metadata

Metadata requests should normally use already-resolved identity
evidence.

For example:

```ts
interface MetadataRequest {
  readonly media: CanonicalMedia;

  readonly preferredLanguages: readonly string[];
}
```

A metadata provider may support:

```text
internal ID
IMDb ID
TMDB ID
```

Routing chooses the appropriate identity representation from the
already established `CanonicalMedia`.

It should not perform silent fuzzy matching as a side effect.

## Artwork is special

Artwork URLs require their own validation.

A metadata provider may return:

```text
poster = "https://..."
```

That does not automatically make the URL safe to proxy.

The addon should preferably return the URL directly when the client
can retrieve it, subject to the source's authorization and network
model.

If the addon ever proxies artwork, it needs the same:

```text
SSRF
redirect
size
content-type
timeout
```

controls as any other remote resource.

## Series metadata

Series introduce another hierarchy:

```text
Series
├── metadata
│
├── Season 1
│    ├── Episode 1
│    ├── Episode 2
│    └── ...
│
└── Season 2
     ├── Episode 1
     └── ...
```

The domain should distinguish:

```ts
interface SeriesMetadata {
  readonly media: CanonicalMedia;

  readonly title?: MetadataValue<string>;

  readonly seasons: readonly SeasonMetadata[];
}
```

and:

```ts
interface EpisodeMetadata {
  readonly season: number;
  readonly episode: number;

  readonly title?: MetadataValue<string>;
  readonly overview?: MetadataValue<string>;
  readonly runtime?: MetadataValue<number>;
}
```

This avoids stuffing episode data into arbitrary key-value objects.

## Subtitles: the first auxiliary playback capability

Subtitles should reuse the same architecture rather than creating a
parallel, ad-hoc subsystem.

The conceptual pipeline is:

```text
CanonicalMedia
      │
      ▼
Subtitle Routing
      │
      ▼
Provider Admission
      │
      ▼
Provider Execution
      │
      ▼
SubtitleObservation
      │
      ▼
Validate
      │
      ▼
Authorize
      │
      ▼
Dedupe
      │
      ▼
Rank
      │
      ▼
Stremio Subtitle DTO
```

The key distinction is:

```text
subtitle observation
    ≠ subtitle truth
    ≠ subtitle authorization
    ≠ subtitle quality
```

## Subtitle domain model

Start with a domain object independent of Stremio:

```ts
export type SubtitleFormat = "srt" | "vtt" | "ass" | "ssa" | "unknown";

export interface SubtitleCandidate {
  readonly id: string;

  readonly media: MediaRef;

  readonly url: string;

  readonly language: string;

  readonly format: SubtitleFormat;

  readonly hearingImpaired: boolean;

  readonly forced: boolean;

  readonly provenance: {
    readonly providerId: string;
  };

  readonly authorization: {
    readonly status: "authorized" | "unauthorized" | "unknown";

    readonly evidenceIds: readonly string[];
  };
}
```

The `forced` field is important.

A forced subtitle track can have different semantics from a normal
subtitle track.

## Episode matching

Subtitles for a series must be matched to the exact episode.

This is a critical invariant.

Given:

```text
series = media:series-001
season = 2
episode = 7
```

a subtitle provider must not return a track belonging to:

```text
season 2 episode 6
```

merely because the series ID matches.

The subtitle identity therefore includes:

```ts
interface SubtitleMediaKey {
  readonly canonicalId: string;

  readonly season?: number;
  readonly episode?: number;
}
```

For movies:

```text
canonicalId
```

For episodes:

```text
canonicalId + season + episode
```

## Catalog as an explicit capability

Introduce:

```ts
interface CatalogProvider {
  readonly id: string;

  readonly capabilities: CatalogCapabilities;

  list(
    request: CatalogRequest,
    context: CatalogContext
  ): Promise<CatalogObservation>;
}
```

Capabilities:

```ts
interface CatalogCapabilities {
  readonly mediaTypes: readonly MediaType[];

  readonly catalogs: readonly string[];

  readonly supportsPagination: boolean;

  readonly supportsSearch: boolean;
}
```

This is intentionally different from:

```text
SourceCapabilities
```

because:

```text
canPlay(media)
```

does not imply:

```text
canEnumerate(catalog)
```

## Catalog identity is not automatically canonical

Suppose a provider returns:

```text
title = "Example"
year = 2024
providerId = "catalog-A"
providerItemId = "12345"
```

That is an observation.

It does **not** automatically establish:

```text
canonicalId = media:example-2024
```

Instead:

```text
Catalog observation
       │
       ▼
Identity resolution
       │
       ├── RESOLVED
       ├── AMBIGUOUS
       ├── NOT_FOUND
       └── NOT_RESOLVED
```

This preserves the same identity boundary already established.

## Catalog index

For production-scale browsing, use an explicit index:

```ts
interface CatalogIndex {
  list(request: CatalogRequest): Promise<readonly CatalogEntry[]>;

  search(request: SearchRequest): Promise<readonly CatalogEntry[]>;
}
```

The index is a **derived view**.

Canonical facts remain elsewhere.

```text
observations
    ↓
reconciliation
    ↓
catalog index
```

Therefore:

```text
CatalogIndex ≠ source of truth
```

## Catalog entry

```ts
interface CatalogEntry {
  readonly canonicalId: string;

  readonly media: MediaRef;

  readonly title: string;

  readonly year?: number;

  readonly poster?: string;

  readonly background?: string;

  readonly genres: readonly string[];

  readonly sourceEvidenceIds: readonly string[];

  readonly generatedAt: string;
}
```

This is a projection optimized for browsing.

It should not contain the complete evidence graph.

## Search result identity

A search result should carry:

```ts
interface SearchResult {
  readonly canonicalId: string;

  readonly media: MediaRef;

  readonly title: string;

  readonly year?: number;

  readonly poster?: string;

  readonly score: number;

  readonly explanation: CatalogRankingExplanation;
}
```

The score is a **derived ranking value**, not evidence.

## Candidate identity

Define:

```ts
function candidateKey(candidate: SourceCandidate): string {
  return hashCanonical({
    sourceId: candidate.sourceId,
    media: candidate.media,
    url: canonicalizeUrl(candidate.url)
  });
}
```

Then:

```text
candidateKey(A) === candidateKey(B)
```

means they represent the same candidate under the declared
canonicalization rules.

It does **not** mean the two provider observations were identical in
every respect.
