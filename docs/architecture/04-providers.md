# Providers & Adapters

[⇧ Architecture index](../architecture.md) · [⇆ Document map](./README.md)

> **Scope.** The `SourceAdapter` contract, `ResolveContext`, `HealthResult`, and `ProviderRegistry`: how adapters declare capabilities, how they are isolated from each other and from the runtime, how adapter health/failure is reported, and how adapters are registered and configured. The normative adapter interface itself lives in `../contracts/source-adapter.md`; this document explains the *why* of the contract, adapter lifecycle, and the reference/fixture adapters used during design.

> **Primary dependencies:** `../contracts/source-adapter.md`, `05-policy.md`, `06-runtime.md`

> **Status.** Unless a section explicitly states otherwise with a concrete repository reference (file path, commit, or CI run), everything below is **DESIGNED** or **PROPOSED** architecture, not implemented code. This document was migrated from the original `docs/architecture.md` monolith; section order is preserved from that document, numbering has been dropped in favor of descriptive headings, and some very long single sections in the monolith may appear here still bearing internal editorial framing (e.g. first-person design narration) that predates the doc-split.

## Sections in this document

- [Adapter contract](#adapter-contract)
- [Source reliability](#source-reliability)
- [Local media source](#local-media-source)
- [Adapter registry](#adapter-registry)
- [Resolver v2](#resolver-v2)
- [Source-specific normalization](#source-specific-normalization)
- [Source adapters become tiny](#source-adapters-become-tiny)
- [Example adapter skeleton](#example-adapter-skeleton)
- [Adapter contract](#adapter-contract)
- [Registry](#registry)
- [Adapter execution](#adapter-execution)
- [First legitimate adapter](#first-legitimate-adapter)
- [Zod belongs at the adapter boundary](#zod-belongs-at-the-adapter-boundary)
- [Source adapter contract changes](#source-adapter-contract-changes)
- [Language matching](#language-matching)
- [Adapter ≠ permission](#adapter-≠-permission)
- [Source configuration](#source-configuration)
- [Source registry admission](#source-registry-admission)
- [No dynamic arbitrary adapters](#no-dynamic-arbitrary-adapters)
- [Adapter contract](#adapter-contract)
- [Adapter registry](#adapter-registry)
- [Fixture adapter](#fixture-adapter)
- [Fixture candidate](#fixture-candidate)
- [Capability contract](#capability-contract)
- [Why capabilities belong to the adapter](#why-capabilities-belong-to-the-adapter)
- [Capability validation](#capability-validation)
- [Registry becomes an authority boundary](#registry-becomes-an-authority-boundary)
- [Capability routing](#capability-routing)
- [The first adapter](#the-first-adapter)
- [Registry construction](#registry-construction)
- [Source Execution](#source-execution)
- [What the First Real Adapter Should Look Like](#what-the-first-real-adapter-should-look-like)
- [Identity Provider Contract](#identity-provider-contract)
- [Source Adapter Capability Expansion](#source-adapter-capability-expansion)
- [Capability Routing](#capability-routing)
- [Adapter Declaration vs Adapter Implementation](#adapter-declaration-vs-adapter-implementation)
- [Capability consistency](#capability-consistency)
- [Source lifecycle](#source-lifecycle)
- [Registry redesign](#registry-redesign)
- [Make impossible states unrepresentable](#make-impossible-states-unrepresentable)
- [Source execution contract](#source-execution-contract)
- [First legitimate real-source category](#first-legitimate-real-source-category)
- [Example: operator-owned HTTP library](#example-operator-owned-http-library)
- [Mapping canonical media into owned-library paths](#mapping-canonical-media-into-owned-library-paths)
- [Why the index matters](#why-the-index-matters)
- [Multi-source execution](#multi-source-execution)
- [Semantic translation belongs in the adapter](#semantic-translation-belongs-in-the-adapter)
- [Source-owned playback URLs](#source-owned-playback-urls)
- [Source-specific identity requirement](#source-specific-identity-requirement)
- [Concrete Source: `OwnedMediaAdapter`](#concrete-source-ownedmediaadapter)
- [Library index contract](#library-index-contract)
- [Repository implementations](#repository-implementations)
- [JSON library for v0.1](#json-library-for-v01)
- [JSON repository](#json-repository)
- [`OwnedMediaAdapter`](#ownedmediaadapter)
- [Why `CanonicalMedia` enters the adapter](#why-canonicalmedia-enters-the-adapter)
- [Asset matching invariant](#asset-matching-invariant)
- [Source-local filtering](#source-local-filtering)
- [Library ingestion pipeline](#library-ingestion-pipeline)
- [Metadata contract](#metadata-contract)
- [Metadata provider ≠ identity provider](#metadata-provider-≠-identity-provider)
- [Provider capability routing](#provider-capability-routing)
- [BCP 47 boundary](#bcp-47-boundary)
- [Subtitle provider contract](#subtitle-provider-contract)
- [User language preferences](#user-language-preferences)
- [Hearing-impaired preference](#hearing-impaired-preference)
- [Subtitle format conversion](#subtitle-format-conversion)
- [Shared provider runtime](#shared-provider-runtime)
- [Generic provider runtime contract](#generic-provider-runtime-contract)
- [Provider registry](#provider-registry)
- [Capability matrix](#capability-matrix)
- [Capability staging](#capability-staging)
- [Provider package boundary](#provider-package-boundary)

---

## Adapter contract

> **See the normative contract:** [`docs/contracts/source-adapter.md`](../contracts/source-adapter.md) defines `SourceAdapter`, `ResolveContext`, and `HealthResult` once, authoritatively. Earlier/later drafts of this interface that appear in this document are kept for historical/explanatory context but do not supersede the contract file.

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

> **HISTORICAL / see `docs/decisions/README.md` (`OPEN-9`, `RESOLVED-1`).**
> This is the only occurrence of `ResolveContext` with `locale`/
> `userConfig` and non-`readonly` fields. Four later, independent
> occurrences converged on a smaller, fully-`readonly` shape, which is
> what [`../contracts/source-adapter.md`](../contracts/source-adapter.md)
> now freezes. `locale`/`userConfig` are tracked as a possible future
> extension (`OPEN-9`), not silently dropped.

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

## Source reliability

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

## Local media source

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

## Adapter registry

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

## Resolver v2

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

## Source-specific normalization

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

## Source adapters become tiny

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

## Example adapter skeleton

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

## Adapter contract

> **See the normative contract:** [`docs/contracts/source-adapter.md`](../contracts/source-adapter.md) defines `SourceAdapter`, `ResolveContext`, and `HealthResult` once, authoritatively. Earlier/later drafts of this interface that appear in this document are kept for historical/explanatory context but do not supersede the contract file.

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

## Registry

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

## Adapter execution

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

## First legitimate adapter

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

## Zod belongs at the adapter boundary

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

## Source adapter contract changes

> **HISTORICAL.** This section explores a query-object-style
> `SourceAdapter` (`resolve(query: SourceQuery, ctx)`, `supports(media:
> CanonicalMedia)`) that differs structurally from the frozen contract in
> [`../contracts/source-adapter.md`](../contracts/source-adapter.md). Kept
> for the design rationale; does not supersede the frozen contract. See
> `docs/decisions/README.md` (`OPEN-8`).

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

## Language matching

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

## Adapter ≠ permission

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

## Source configuration

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

## Source registry admission

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

## No dynamic arbitrary adapters

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

## Adapter contract

> **See the normative contract:** [`docs/contracts/source-adapter.md`](../contracts/source-adapter.md) defines `SourceAdapter`, `ResolveContext`, and `HealthResult` once, authoritatively. Earlier/later drafts of this interface that appear in this document are kept for historical/explanatory context but do not supersede the contract file.

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

## Adapter registry

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

## Fixture adapter

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

## Fixture candidate

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

## Capability contract

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

> **OPEN — see `docs/decisions/README.md` (`OPEN-8`).** This draft adds
> `readonly capabilities: SourceCapabilities` to `SourceAdapter`, which the
> frozen contract in
> [`../contracts/source-adapter.md`](../contracts/source-adapter.md) does
> not have. Whether capability declaration belongs on the frozen adapter
> contract is an open decision, not yet resolved.

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

## Why capabilities belong to the adapter

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

## Capability validation

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

## Registry becomes an authority boundary

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

## Capability routing

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

## The first adapter

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

## Registry construction

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

## Source Execution

The resolver should eventually evolve toward:

```ts
const eligible = routeAdapters(media);

const executions = eligible.map(adapter =>
  limiter.run(() =>
    breaker.execute(adapter.id, () =>
      withTimeout(
        signal =>
          adapter.resolve(media, {
            signal,
            timeoutMs,
            preferredLanguages
          }),
        timeoutMs,
        parentSignal
      )
    )
  )
);

const results = await Promise.allSettled(executions);
```

`Promise.allSettled()` is particularly important.

We want:

```text
A fulfilled
B rejected
C fulfilled
D rejected
```

to become:

```text
candidates from A + C
failures from B + D
```

rather than losing all results because one promise rejected.

## What the First Real Adapter Should Look Like

After the fixture adapter passes, the next adapter should be chosen
according to this contract:

```text
SOURCE ADMISSION

1. Identity authority documented
2. API/source terms permit intended use
3. Authentication mechanism documented
4. Playback URL acquisition documented
5. URL ownership/authorization documented
6. Rate limits known
7. Failure semantics known
8. No credential bypass
9. No DRM circumvention
10. Adapter conformance tests pass
```

Only then:

```text
RawAdapter
    ↓
Capability validation
    ↓
Authorization validation
    ↓
Admission
    ↓
Runtime registry
```

## Identity Provider Contract

```ts
export interface IdentityAdapter {
  readonly id: string;

  readonly capabilities: {
    readonly inputKinds: readonly IdentityKind[];
    readonly outputKinds: readonly IdentityKind[];
    readonly mediaTypes: readonly MediaType[];
  };

  resolve(
    identity: ExternalIdentityRequest,
    context: IdentityResolveContext
  ): Promise<IdentityObservation>;
}
```

Request:

```ts
export interface ExternalIdentityRequest {
  readonly kind: IdentityKind;
  readonly value: string;
  readonly mediaType: MediaType;
}
```

Context:

```ts
export interface IdentityResolveContext {
  readonly signal: AbortSignal;
  readonly timeoutMs: number;
}
```

Observation:

```ts
export interface IdentityObservation {
  readonly status: "resolved" | "not_found" | "ambiguous" | "not_resolved";

  readonly identities: readonly ExternalIdentity[];

  readonly source: string;

  readonly observedAt: string;
}
```

Again:

```text
identity adapter ≠ source adapter
```

An identity provider tells us **what something is**.

A stream source tells us **whether it can provide an eligible
playback candidate**.

## Source Adapter Capability Expansion

The previous adapter contract should therefore evolve from:

```text
supports(media)
```

toward:

```ts
supports(media: CanonicalMedia): boolean;
```

But we should not remove the lower-level media check.

A useful contract is:

> **OPEN — see `docs/decisions/README.md` (`OPEN-8`), highest-priority
> open contract question.** This is the most-evolved `SourceAdapter` shape
> in the document set: it splits `supportsMedia`/`supportsIdentity` and
> resolves against an already identity-resolved `CanonicalMedia` rather
> than a raw `MediaRef`. It was never reconciled with the frozen,
> `MediaRef`-based contract in
> [`../contracts/source-adapter.md`](../contracts/source-adapter.md).
> Do not assume either shape is "the" contract without resolving `OPEN-8`
> first.

```ts
export interface SourceAdapter {
  readonly id: string;
  readonly name: string;
  readonly capabilities: SourceCapabilities;

  supportsMedia(media: MediaRef): boolean;

  supportsIdentity(identities: readonly ExternalIdentity[]): boolean;

  resolve(
    media: CanonicalMedia,
    context: ResolveContext
  ): Promise<readonly SourceCandidate[]>;
}
```

Now source execution is based on resolved identity.

## Capability Routing

Routing becomes:

```text
                 CanonicalMedia
                        │
                        ▼
               ┌─────────────────┐
               │ Capability check│
               └────────┬────────┘
                        │
           ┌────────────┼────────────┐
           ▼            ▼            ▼
        media type   identity      episode
           │            │            │
           └────────────┼────────────┘
                        ▼
                 eligible adapters
```

Then health/circuit state is evaluated:

```text
eligible
   ↓
healthy?
   ↓
circuit closed?
   ↓
execute
```

Authorization remains separate.

## Adapter Declaration vs Adapter Implementation

Do not let executable code define its own authority.

An adapter should have two conceptual parts:

```text
AdapterDeclaration
        │
        ├── capabilities
        ├── identity requirements
        ├── authorization declaration
        ├── network requirements
        └── operational limits
                 │
                 ▼
          Admission Engine
                 │
                 ▼
          AdmittedAdapter
                 │
                 ▼
        AdapterImplementation
```

The implementation is therefore **subject to a declaration**.

```ts
interface SourceDeclaration {
  readonly id: string;
  readonly name: string;

  readonly capabilities: SourceCapabilities;

  readonly requiredIdentityKinds: readonly IdentityKind[];

  readonly authorization: AuthorizationDeclaration;

  readonly network: NetworkDeclaration;

  readonly limits: SourceLimits;
}
```

## Capability consistency

The declaration itself must be validated.

Suppose an adapter declares:

```json
{
  "providesStreams": false
}
```

but its implementation returns playback URLs.

That is a contract violation.

Likewise:

```text
supportsEpisodes: false
```

must prevent execution against:

```json
{
  "type": "series",
  "season": 2,
  "episode": 7
}
```

Define:

```ts
interface SourceCapabilities {
  readonly mediaTypes: readonly MediaType[];

  readonly supportsMovies: boolean;
  readonly supportsSeries: boolean;
  readonly supportsEpisodes: boolean;

  readonly providesStreams: boolean;
  readonly providesSubtitles: boolean;
  readonly providesMetadata: boolean;

  readonly identityKinds: readonly IdentityKind[];

  readonly authorizationMode:
    | "configured_owned"
    | "public_domain"
    | "licensed"
    | "unknown";
}
```

Then enforce consistency:

```text
mediaTypes
     │
     ├── movie ──────► supportsMovies = true
     │
     └── series ─────► supportsSeries = true

series episodes
     │
     └───────────────► supportsEpisodes = true
```

No contradictory declarations.

## Source lifecycle

The adapter now gets a formal lifecycle:

```text
DECLARED
   │
   ▼
VALIDATED
   │
   ▼
ADMISSION_EVALUATED
   │
   ├── rejected ──────────────┐
   │                          │
   ▼                          │
ADMITTED                      │
   │                          │
   ▼                          │
REGISTERED                    │
   │                          │
   ▼                          │
HEALTH_MONITORED              │
   │                          │
   ▼                          │
EXECUTABLE                    │
   │                          │
   ├──── disabled ────────────┤
   │                          │
   ├──── expired ─────────────┤
   │                          │
   └──── revoked ─────────────┘
```

Important:

**Registered does not mean executable.**

## Registry redesign

The previous registry stored only executable adapters.

Now separate declarations from admitted implementations:

```ts
interface RegisteredSource {
  readonly declaration: SourceDeclaration;
  readonly admission: AdmissionDecision;
  readonly adapter?: SourceAdapter;
}
```

Registry:

```ts
class SourceRegistry {
  private readonly sources = new Map<string, RegisteredSource>();

  register(source: RegisteredSource): void {
    if (this.sources.has(source.declaration.id)) {
      throw new Error(`Duplicate source adapter: ${source.declaration.id}`);
    }

    this.sources.set(source.declaration.id, source);
  }

  all(): readonly RegisteredSource[] {
    return [...this.sources.values()];
  }

  executable(): readonly SourceAdapter[] {
    return [...this.sources.values()]
      .filter(
        source => source.admission.status === "admitted" && source.adapter !== undefined
      )
      .map(source => source.adapter!);
  }
}
```

The `!` here is structurally justified only because admission +
adapter presence form an invariant.

A stronger TypeScript design should eliminate even that assertion.

## Make impossible states unrepresentable

Instead of:

```ts
adapter?: SourceAdapter
```

use a discriminated union:

```ts
type RegisteredSource =
  | {
      readonly status: "rejected";
      readonly declaration: SourceDeclaration;
      readonly admission: AdmissionDecision;
    }
  | {
      readonly status: "admitted";
      readonly declaration: SourceDeclaration;
      readonly admission: AdmissionDecision;
      readonly adapter: SourceAdapter;
    };
```

Now:

```ts
if (source.status === "admitted") {
  source.adapter.resolve(...);
}
```

No nullable adapter.

This aligns with the project's larger rule:

**UNKNOWN must remain UNKNOWN; impossible states should not be encoded
as ordinary nullable fields.**

## Source execution contract

Once admitted, execution receives the **canonical media**, not the
original Stremio request.

Bad:

```ts
adapter.resolve({
  type: args.type,
  id: args.id
});
```

Better:

```ts
adapter.resolve(canonicalMedia, {
  signal,
  timeoutMs,
  preferredLanguages
});
```

Therefore:

```text
Stremio syntax
      ↓
MediaRef
      ↓
Identity resolution
      ↓
CanonicalMedia
      ↓
Source routing
      ↓
Adapter
```

The adapter doesn't need to understand Stremio.

## First legitimate real-source category

The first production-oriented adapter should **not** begin with an
arbitrary public streaming website.

Instead, use a source whose authorization boundary is naturally
explicit:

### User-owned media library

Examples include an operator-controlled HTTP media server or object
store containing media the operator is authorized to serve.

The adapter contract becomes:

```text
configured endpoint
        + configured credentials/token
        + operator-controlled media
        ↓
authorized source
```

The source is not discovered by scraping the Internet.

It is explicitly configured.

## Example: operator-owned HTTP library

Configuration:

```text
MEDIA_LIBRARY_BASE_URL=https://media.example.org
MEDIA_LIBRARY_TOKEN=...
MEDIA_LIBRARY_AUTHORIZATION=owned
```

The adapter declaration:

```ts
const ownedLibraryDeclaration: SourceDeclaration = {
  id: "owned-media-library",
  name: "Operator-Owned Media Library",

  capabilities: {
    mediaTypes: ["movie", "series"],
    supportsMovies: true,
    supportsSeries: true,
    supportsEpisodes: true,

    providesStreams: true,
    providesSubtitles: false,
    providesMetadata: false,

    identityKinds: ["internal"],

    authorizationMode: "configured_owned"
  },

  requiredIdentityKinds: ["internal"],

  authorization: {
    mode: "configured_owned",
    evidence: [
      {
        evidenceId: "config:owned-media-library",
        kind: "configuration",
        subject: "operator-owned-media-library",
        observedAt: "2026-09-29T00:00:00Z"
      }
    ]
  },

  network: {
    outboundHosts: ["media.example.org"],
    allowHttp: false,
    allowHttps: true,
    allowRedirects: true,
    maxRedirects: 3
  },

  limits: {
    timeoutMs: 5000,
    maxConcurrentRequests: 4,
    requestsPerMinute: 60,
    maxCandidates: 10
  }
};
```

The hostname is illustrative.

It is **not** a real source.

## Mapping canonical media into owned-library paths

Do not derive URLs directly from arbitrary user-controlled titles.

Instead:

```text
CanonicalMedia
      │
      ▼
OwnedLibraryIndex
      │
      ▼
LibraryAsset
      │
      ▼
Playback URL
```

For example:

```ts
interface LibraryAsset {
  readonly assetId: string;
  readonly canonicalId: string;

  readonly mediaType: MediaType;

  readonly url: string;

  readonly container?: string;
  readonly resolution?: number;
  readonly bitrate?: number;
}
```

The library index is authoritative for the operator's own media
inventory.

## Why the index matters

Without an index:

```text
IMDb ID
  ↓
guess filename
  ↓
guess path
  ↓
HTTP request
```

This creates brittle and potentially unsafe semantics.

With an index:

```text
IMDb
 ↓
identity resolver
 ↓
canonicalId
 ↓
library index
 ↓
asset
 ↓
authorized playback URL
```

Now the source adapter answers a deterministic question:

"Does this canonical media entity have a playable asset in my
authorized library?"

## Multi-source execution

The architecture can now support:

```text
                    CanonicalMedia
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
    Owned Library     Licensed API    Public Domain
           │              │              │
           ▼              ▼              ▼
       Candidate A    Candidate B    Candidate C
           │              │              │
           └──────────────┼──────────────┘
                          ▼
                     VALIDATE
                          ▼
                    AUTHORIZE
                          ▼
                      DEDUPE
                          ▼
                       RANK
                          ▼
                   Stremio streams
```

No source is special-cased in the resolver.

That is the key architectural payoff.

## Semantic translation belongs in the adapter

This is another important boundary:

```text
HTTP semantics
      ↓
adapter interpretation
      ↓
domain semantics
```

Not:

```text
HTTP 404
  = NOT_FOUND
```

globally.

For example:

```ts
if (response.status === 404) {
  return {
    status: "not_found",
    identities: [],
    source: this.id,
    observedAt: now()
  };
}
```

That interpretation belongs to the specific identity adapter.

The generic HTTP runtime knows only:

```text
status = 404
```

## Source-owned playback URLs

For the first real adapter, a clean architecture is:

```text
Owned Library
      │
      ├── identity index
      ├── asset index
      └── playback endpoint
              │
              ▼
       OwnedLibraryAdapter
              │
              ▼
       SourceCandidate
```

Example:

```ts
interface OwnedLibraryRecord {
  readonly canonicalId: string;
  readonly assetId: string;

  readonly playbackUrl: string;

  readonly mediaInfo?: {
    readonly container?: string;
    readonly resolution?: number;
    readonly bitrate?: number;
  };
}
```

The adapter converts this into:

```ts
{
  sourceId: "owned-media-library",
  media,
  url: record.playbackUrl,
  mediaInfo: record.mediaInfo,
  language: "und",
  provenance: {
    adapterId: "owned-media-library"
  },
  capabilities: {
    directPlayback: true
  },
  authorization: {
    status: "authorized",
    evidenceIds: ["asset:..."]
  }
}
```

No scraping is required.

No third-party site discovery is required.

## Source-specific identity requirement

The owned library should ideally not perform title matching at
playback time.

Instead:

```text
CanonicalMedia
       │
       ▼
canonicalId
       │
       ▼
library index
       │
       ├── asset found
       └── asset absent
```

If absent:

```text
source_empty
```

not:

```text
source_failed
```

provided the index was successfully queried and established absence.

## Concrete Source: `OwnedMediaAdapter`

We can now implement the first non-fixture source without weakening
any of the boundaries established above.

The source is deliberately narrow:

**A media library controlled by the operator, exposing an explicit
index of authorized assets and playback URLs.**

It is not a web scraper, torrent indexer, or generic Internet stream
finder.

The architecture becomes:

```text
                     Stremio
                         │
                         ▼
                  Stream Handler
                         │
                         ▼
                 Resolution Service
                         │
                         ▼
                  CanonicalMedia
                         │
                         ▼
                OwnedMediaAdapter
                         │
               ┌─────────┴─────────┐
               ▼                   ▼
        Library Identity       Library Assets
            Index                  Index
               │                   │
               └─────────┬─────────┘
                         ▼
                  SourceCandidate
                         │
                         ▼
                   Stremio URL
```

## Library index contract

The adapter should not know how the library stores its data.

Define an application-facing repository:

```ts
export interface MediaLibrary {
  findAssets(
    canonicalId: string,
    signal: AbortSignal
  ): Promise<readonly LibraryAsset[]>;
}
```

Asset:

```ts
export interface LibraryAsset {
  readonly assetId: string;
  readonly canonicalId: string;

  readonly playbackUrl: string;

  readonly mediaInfo?: {
    readonly container?: string;
    readonly codecs?: readonly string[];
    readonly resolution?: number;
    readonly bitrate?: number;
    readonly sizeBytes?: number;
    readonly durationMs?: number;
  };

  readonly language?: string;

  readonly authorization: {
    readonly status: "authorized" | "unauthorized" | "unknown";
    readonly evidenceIds: readonly string[];
  };
}
```

The important invariant:

```text
LibraryAsset
    │
    ├── identity
    ├── playback location
    ├── technical metadata
    └── authorization evidence
```

The asset itself remains a fact-bearing object.

## Repository implementations

We can support multiple storage backends without changing the
adapter.

```text
MediaLibrary
    │
    ├── JsonMediaLibrary
    ├── SqliteMediaLibrary
    ├── PostgresMediaLibrary
    ├── ObjectStoreMediaLibrary
    └── ApiMediaLibrary
```

The adapter sees only:

```text
findAssets(canonicalId, signal)
```

This means the first implementation can be extremely simple.

## JSON library for v0.1

A practical first implementation is a static JSON manifest.

Example:

```json
{
  "assets": [
    {
      "assetId": "asset-001",
      "canonicalId": "media:movie-001",
      "playbackUrl": "https://media.example.org/library/movie-001.mp4",
      "mediaInfo": {
        "container": "mp4",
        "resolution": 1080,
        "bitrate": 8000000
      },
      "language": "en",
      "authorization": {
        "status": "authorized",
        "evidenceIds": ["asset-authorization-001"]
      }
    }
  ]
}
```

This is not intended to be the final database design.

It is valuable because it provides:

```text
deterministic input
+ zero external discovery
+ easy testing
+ easy reproducibility
```

That makes it suitable for the first real end-to-end implementation.

## JSON repository

The repository can then be:

```ts
export class JsonMediaLibrary implements MediaLibrary {
  constructor(private readonly assets: readonly LibraryAsset[]) {}

  async findAssets(
    canonicalId: string,
    signal: AbortSignal
  ): Promise<readonly LibraryAsset[]> {
    if (signal.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }

    return this.assets.filter(asset => asset.canonicalId === canonicalId);
  }
}
```

Notice what this implementation does **not** do:

- no network access,
- no scraping,
- no guessing,
- no title search,
- no authorization inference.

## `OwnedMediaAdapter`

The adapter now becomes thin:

```ts
export class OwnedMediaAdapter implements SourceAdapter {
  readonly id = "owned-media-library";
  readonly name = "Operator-Owned Media Library";

  readonly capabilities = {
    mediaTypes: ["movie", "series"] as const,

    supportsMovies: true,
    supportsSeries: true,
    supportsEpisodes: true,

    providesStreams: true,
    providesSubtitles: false,
    providesMetadata: false,

    identityKinds: ["internal"] as const,

    authorizationMode: "configured_owned" as const
  };

  constructor(private readonly library: MediaLibrary) {}

  supportsMedia(media: MediaRef): boolean {
    return media.type === "movie" || media.type === "series";
  }

  async resolve(
    media: CanonicalMedia,
    context: ResolveContext
  ): Promise<readonly SourceCandidate[]> {
    const assets = await this.library.findAssets(
      media.canonicalId,
      context.signal
    );

    return assets.map(asset => this.toCandidate(media.media, asset));
  }

  private toCandidate(media: MediaRef, asset: LibraryAsset): SourceCandidate {
    return {
      sourceId: this.id,
      media,
      url: asset.playbackUrl,
      mediaInfo: asset.mediaInfo,
      language: asset.language ?? "und",

      provenance: {
        adapterId: this.id
      },

      capabilities: {
        directPlayback: true
      },

      authorization: {
        status: asset.authorization.status,
        evidenceIds: asset.authorization.evidenceIds
      }
    };
  }
}
```

The adapter is now primarily a **semantic translator**:

```text
LibraryAsset
     ↓
SourceCandidate
```

## Why `CanonicalMedia` enters the adapter

This is deliberate.

The adapter does not receive:

```text
MediaRef
```

as its primary identity.

It receives:

```text
CanonicalMedia
```

because source routing already established the identity.

Thus:

```text
IMDb tt1234567
       │
       ▼
Identity Resolver
       │
       ▼
media:abc123
       │
       ▼
OwnedMediaAdapter
       │
       ▼
library lookup
```

The source cannot reinterpret the identity.

## Asset matching invariant

For an episode candidate:

```text
candidate.media.type = "series"
candidate.media.id = request series ID
candidate.media.season = asset.season
candidate.media.episode = asset.episode
```

The adapter must not return:

```text
season 2 episode 6
```

for:

```text
season 2 episode 7
```

even if the same series contains both.

This deserves a dedicated conformance test.

## Source-local filtering

Some filtering does belong inside the adapter.

For example:

```text
asset authorization = unauthorized
```

can be omitted before creating a candidate.

But there is value in preserving rejection evidence.

A richer adapter result could eventually become:

```ts
interface SourceResolution {
  readonly candidates: readonly SourceCandidate[];
  readonly rejections: readonly SourceRejection[];
}
```

For v0.1, keep the public adapter contract simple and let the central
candidate authorization policy reject unauthorized candidates.

That creates one authoritative authorization gate.

## Library ingestion pipeline

The complete source now has two separate pipelines.

### Configuration pipeline

```text
JSON
 │
 ▼
schema validation
 │
 ▼
asset validation
 │
 ▼
authorization evidence
 │
 ▼
network validation
 │
 ▼
library index
```

### Runtime pipeline

```text
CanonicalMedia
 │
 ▼
library lookup
 │
 ▼
LibraryAsset
 │
 ▼
SourceCandidate
 │
 ▼
central validation
 │
 ▼
central authorization
 │
 ▼
dedupe
 │
 ▼
ranking
```

This avoids putting all policy into the adapter.

## Metadata contract

Introduce:

```ts
interface MetadataProvider {
  readonly id: string;

  readonly capabilities: MetadataCapabilities;

  getMetadata(
    media: CanonicalMedia,
    context: MetadataContext
  ): Promise<MetadataObservation>;
}
```

Capabilities:

```ts
interface MetadataCapabilities {
  readonly mediaTypes: readonly MediaType[];

  readonly fields: readonly MetadataField[];

  readonly identityKinds: readonly IdentityKind[];
}
```

Fields:

```ts
type MetadataField =
  | "title"
  | "original_title"
  | "year"
  | "runtime"
  | "genres"
  | "overview"
  | "poster"
  | "background"
  | "cast"
  | "directors"
  | "season"
  | "episode"
  | "episode_title"
  | "episode_overview";
```

This allows providers to declare exactly what they can supply.

## Metadata provider ≠ identity provider

This distinction deserves an explicit interface separation.

```ts
interface IdentityAdapter {
  resolve(...): Promise<IdentityObservation>;
}

interface MetadataProvider {
  getMetadata(...): Promise<MetadataObservation>;
}
```

A provider may implement both internally, but the interfaces remain
distinct.

Why?

Because:

```text
"Provider says title X"
```

doesn't automatically mean:

```text
"Provider proved this is entity X"
```

## Provider capability routing

Suppose:

```text
Provider A requires TMDB
Provider B requires IMDb
Provider C requires internal ID
```

and the canonical entity contains:

```text
IMDb
TMDB
internal
```

Then all three may be eligible.

But if it contains only:

```text
IMDb
```

then:

```text
A → identity_missing
B → eligible
C → identity_missing
```

This should produce a routing explanation exactly like source
routing.

## BCP 47 boundary

Internally, use a normalized language-tag model rather than making
every subsystem understand raw provider strings.

```ts
interface NormalizedLanguage {
  readonly language: string;
  readonly region?: string;
  readonly script?: string;
}
```

Example:

```text
en
en-US
fr
fr-FR
ar
ar-TN
```

The provider's original value remains provenance.

Therefore:

```text
original = "English"
normalized = "en"
```

is preferable to destroying the original value.

## Subtitle provider contract

```ts
interface SubtitleProvider {
  readonly id: string;

  readonly capabilities: {
    readonly mediaTypes: readonly MediaType[];
    readonly languages: readonly string[];
    readonly formats: readonly SubtitleFormat[];
    readonly supportsForced: boolean;
    readonly supportsHearingImpaired: boolean;
  };

  resolve(
    media: CanonicalMedia,
    context: SubtitleResolveContext
  ): Promise<SubtitleObservation>;
}
```

The provider does not know about:

```text
Stremio HTTP
Stremio JSON
Express
Fastify
SDK objects
```

## User language preferences

The request context already contains:

```ts
preferredLanguages: readonly string[];
```

For example:

```text
["fr", "en", "ar"]
```

Ranking can use this preference.

It should not modify provider observations.

```text
OBSERVED: language = en

DERIVED: preferred-language score = 2
```

This distinction matters for evidence.

## Hearing-impaired preference

Represent it explicitly:

```ts
interface SubtitlePreferences {
  readonly preferredLanguages: readonly string[];

  readonly preferHearingImpaired: boolean;

  readonly preferForced: boolean;
}
```

Then ranking becomes deterministic.

Example:

```text
Candidate A
language = fr
HI = false

Candidate B
language = fr
HI = true

preferHI = true

B ranks ahead of A
```

The ranking result is a derived preference, not a claim that B is
objectively better.

## Subtitle format conversion

Do **not** initially convert:

```text
ASS → VTT
SRT → VTT
SSA → SRT
```

inside the addon.

That introduces:

- parsing complexity,
- encoding issues,
- styling loss,
- timing transformations,
- new failure modes.

For v0.1:

```text
provider format
      ↓
Stremio-compatible representation
```

If conversion is later required:

```text
SubtitleConverter
```

should become a separate subsystem with its own conformance suite.

## Shared provider runtime

At this point it becomes useful to generalize the runtime.

Instead of:

```text
SourceRuntime
MetadataRuntime
SubtitleRuntime
```

with duplicated infrastructure, create:

```text
ProviderRuntime<T>
```

The runtime handles:

```text
admission
circuit
rate limit
concurrency
timeout
cancellation
network policy
observability
```

while the provider supplies domain semantics.

```text
                 ProviderRuntime
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
       Source        Metadata       Subtitle
      Provider       Provider        Provider
```

## Generic provider runtime contract

```ts
interface ProviderRuntime {
  execute<T>(
    providerId: string,
    operation: (context: ProviderExecutionContext) => Promise<T>,
    options: ProviderExecutionOptions
  ): Promise<ProviderExecutionResult<T>>;
}
```

Options:

```ts
interface ProviderExecutionOptions {
  readonly timeoutMs: number;
  readonly signal: AbortSignal;
}
```

Result:

```ts
type ProviderExecutionResult<T> =
  | {
      readonly status: "success";
      readonly value: T;
    }
  | {
      readonly status: "failed";
      readonly failure: SourceFailure;
    };
```

For a production implementation, this generic result should
eventually be made domain-neutral rather than reusing `SourceFailure`;
the important point is the abstraction, not the provisional type
name.

## Provider registry

The original `SourceRegistry` can eventually become:

```ts
interface ProviderRegistry {
  readonly sources: SourceRegistry;
  readonly metadata: MetadataProviderRegistry;
  readonly subtitles: SubtitleProviderRegistry;
}
```

Or a typed generic registry:

```text
ProviderRegistry<SourceProvider>
ProviderRegistry<MetadataProvider>
ProviderRegistry<SubtitleProvider>
```

Avoid one untyped registry containing arbitrary plugin objects.

That would weaken compile-time guarantees.

## Capability matrix

The system can now expose an internal capability matrix:

| Provider | Identity | Metadata | Streams | Subtitles |
| --- | --- | --- | --- | --- |
| Identity provider A | ✓ | — | — | — |
| Owned media | internal | — | ✓ | — |
| Metadata provider A | ✓ required | ✓ | — | — |
| Subtitle provider A | internal | — | — | ✓ |

This matrix is **derived from declarations**.

It should not be manually maintained.

## Capability staging

This suggests explicit capability profiles:

```ts
type AddonProfile =
  | "stream-only"
  | "stream-catalog"
  | "stream-catalog-meta"
  | "full";
```

But avoid using this as runtime magic.

A profile should generate/validate configuration.

## Provider package boundary

A provider package should ideally export only:

```text
declareProvider()
```

rather than arbitrary runtime hooks.

For example:

```ts
interface ProviderModule {
  readonly declaration: SourceDeclaration;

  create(dependencies: ProviderDependencies): SourceAdapter;
}
```

This makes the provider construction boundary explicit.
