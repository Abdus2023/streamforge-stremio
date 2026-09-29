# Resolution Pipeline

[⇧ Architecture index](../architecture.md) · [⇆ Document map](./README.md)

> **Scope.** The end-to-end resolution pipeline: request → identity resolution → adapter selection → parallel resolution → validation → deduplication → policy filtering → ranking → protocol mapping. Covers concurrency, timeouts, cancellation, partial success, deterministic deduplication and ranking, catalog/search/metadata reconciliation processes, and identity resolution algorithms. Policy *definitions* (authorization, eligibility, admission) live in `05-policy.md`; this document only shows where policy filtering sits in the pipeline.

> **Primary dependencies:** `02-domain.md`, `04-providers.md`, `05-policy.md`, `../contracts/stream.md`

> **Status.** Unless a section explicitly states otherwise with a concrete repository reference (file path, commit, or CI run), everything below is **DESIGNED** or **PROPOSED** architecture, not implemented code. This document was migrated from the original `docs/architecture.md` monolith; section order is preserved from that document, numbering has been dropped in favor of descriptive headings, and some very long single sections in the monolith may appear here still bearing internal editorial framing (e.g. first-person design narration) that predates the doc-split.

## Sections in this document

- [Parallel aggregation](#parallel-aggregation)
- [Deduplication](#deduplication)
- [Ranking engine](#ranking-engine)
- [Resolver pipeline](#resolver-pipeline)
- [Failure semantics](#failure-semantics)
- [Don't let ranking become business logic](#don't-let-ranking-become-business-logic)
- [Deterministic ranking](#deterministic-ranking)
- [Resolution normalization](#resolution-normalization)
- [Multi-source aggregation becomes compositional](#multi-source-aggregation-becomes-compositional)
- [Failure matrix](#failure-matrix)
- [Candidate model](#candidate-model)
- [Validation](#validation)
- [Deduplication](#deduplication)
- [Ranking](#ranking)
- [Resolver](#resolver)
- [Playback verification](#playback-verification)
- [Content-type validation](#content-type-validation)
- [Stream mapper](#stream-mapper)
- [Empty results](#empty-results)
- [Deterministic ranking invariant](#deterministic-ranking-invariant)
- [Identity resolution: the missing layer](#identity-resolution-the-missing-layer)
- [Subtitle pipeline](#subtitle-pipeline)
- [Subtitle ranking](#subtitle-ranking)
- [Subtitle deduplication](#subtitle-deduplication)
- [Quality semantics](#quality-semantics)
- [Stream probing](#stream-probing)
- [The crucial abstraction: Resolver ≠ Provider](#the-crucial-abstraction-resolver-≠-provider)
- [The complete request lifecycle](#the-complete-request-lifecycle)
- [End-to-end state machine](#end-to-end-state-machine)
- [Validation](#validation)
- [Deduplication](#deduplication)
- [Deterministic ranking](#deterministic-ranking)
- [Failure classification](#failure-classification)
- [Resolver implementation](#resolver-implementation)
- [Ranking invariant](#ranking-invariant)
- [Capability-aware source routing](#capability-aware-source-routing)
- [Identity resolution](#identity-resolution)
- [Source routing pipeline](#source-routing-pipeline)
- [Candidate ranking is downstream](#candidate-ranking-is-downstream)
- [Stream URLs are special](#stream-urls-are-special)
- [Request identity](#request-identity)
- [Complete aggregation state](#complete-aggregation-state)
- [Metadata should be merged, not blindly overwritten](#metadata-should-be-merged-not-blindly-overwritten)
- [Subtitle ranking](#subtitle-ranking)
- [`src/application/resolver.ts`](#srcapplicationresolverts)
- [Partial success is first-class](#partial-success-is-first-class)
- [Empty result semantics](#empty-result-semantics)
- [Candidate Pipeline](#candidate-pipeline)
- [Candidate Normalization](#candidate-normalization)
- [Ranking Must Remain Deterministic](#ranking-must-remain-deterministic)
- [Failure Normalization](#failure-normalization)
- [Candidate Validation](#candidate-validation)
- [Empty Is Not Failure](#empty-is-not-failure)
- [Request Lifecycle](#request-lifecycle)
- [Identity Resolution Algorithm](#identity-resolution-algorithm)
- [Reconciliation](#reconciliation)
- [Routing Matrix](#routing-matrix)
- [Routing Explanation](#routing-explanation)
- [Identity Resolver](#identity-resolver)
- [Reconciliation Must Be Pure](#reconciliation-must-be-pure)
- [Identity Layer in the Complete Pipeline](#identity-layer-in-the-complete-pipeline)
- [Resulting Source-Selection Algorithm](#resulting-source-selection-algorithm)
- [Determinism requirement](#determinism-requirement)
- [Duplicate asset identity](#duplicate-asset-identity)
- [Canonical ID validation](#canonical-id-validation)
- [Metadata reconciliation](#metadata-reconciliation)
- [Different fields need different reconciliation rules](#different-fields-need-different-reconciliation-rules)
- [Preserve disagreements](#preserve-disagreements)
- [Metadata routing decision](#metadata-routing-decision)
- [Metadata and playback remain independent](#metadata-and-playback-remain-independent)
- [Language normalization](#language-normalization)
- [Subtitle deduplication](#subtitle-deduplication)
- [Subtitle ranking](#subtitle-ranking)
- [Empty subtitles](#empty-subtitles)
- [Subtitle failure matrix](#subtitle-failure-matrix)
- [The anti-pattern](#the-anti-pattern)
- [Search query normalization](#search-query-normalization)
- [Search ranking](#search-ranking)
- [Catalog ranking model](#catalog-ranking-model)
- [Dedupe catalog results](#dedupe-catalog-results)
- [Unresolved catalog entries](#unresolved-catalog-entries)
- [Catalog ingestion](#catalog-ingestion)
- [Ingestion is asynchronous](#ingestion-is-asynchronous)
- [Freshness](#freshness)
- [Full-text search](#full-text-search)
- [Three independent states](#three-independent-states)
- [Resource resolver](#resource-resolver)
- [Why not `resolveEverything()`?](#why-not-resolveeverything())
- [Failure-domain isolation](#failure-domain-isolation)
- [Resource-specific budgets](#resource-specific-budgets)
- [Parallel vs sequential orchestration](#parallel-vs-sequential-orchestration)
- [Admission graph vs execution graph](#admission-graph-vs-execution-graph)
- [The central invariant](#the-central-invariant)
- [Pure resolver core](#pure-resolver-core)
- [Functional core / imperative shell](#functional-core--imperative-shell)
- [Resolver kernel](#resolver-kernel)

---

## Parallel aggregation

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

## Deduplication

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

## Ranking engine

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

## Resolver pipeline

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

## Failure semantics

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

## Don't let ranking become business logic

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

## Deterministic ranking

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

## Resolution normalization

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

## Multi-source aggregation becomes compositional

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

## Failure matrix

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

## Candidate model

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

## Validation

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

## Deduplication

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

## Ranking

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

## Resolver

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

## Playback verification

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

## Content-type validation

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

## Stream mapper

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

## Empty results

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

## Deterministic ranking invariant

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

## Identity resolution: the missing layer

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

## Subtitle pipeline

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

## Subtitle ranking

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

## Subtitle deduplication

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

## Quality semantics

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

## Stream probing

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

## The crucial abstraction: Resolver ≠ Provider

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

## The complete request lifecycle

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

## End-to-end state machine

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

## Validation

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

## Deduplication

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

## Deterministic ranking

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

## Failure classification

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

## Resolver implementation

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

## Ranking invariant

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

## Capability-aware source routing

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

## Identity resolution

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

## Source routing pipeline

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

## Candidate ranking is downstream

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

## Stream URLs are special

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

## Request identity

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

## Complete aggregation state

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

## Metadata should be merged, not blindly overwritten

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

## Subtitle ranking

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

## `src/application/resolver.ts`

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

## Partial success is first-class

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

## Empty result semantics

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

## Candidate Pipeline

The actual pipeline is now:

```text
adapter output
     │
     ▼
STRUCTURAL VALIDATION
     │
     ├── invalid → failure
     │
     ▼
AUTHORIZATION
     │
     ├── not authorized → failure
     │
     ▼
NORMALIZATION
     │
     ▼
DEDUPLICATION
     │
     ▼
RANKING
     │
     ▼
Stremio mapping
```

Never:

```text
adapter
  ↓
URL
  ↓
Stremio
```

because that bypasses the evidence and policy layers.

## Candidate Normalization

A useful intermediate type:

```ts
export interface NormalizedCandidate extends SourceCandidate {
  canonicalUrl: string;
}
```

Normalization:

```ts
export function normalizeCandidate(
  candidate: SourceCandidate
): NormalizedCandidate {
  const parsed = new URL(candidate.url);

  parsed.hash = "";

  return {
    ...candidate,
    canonicalUrl: parsed.toString()
  };
}
```

Then deduplication uses:

```text
canonicalUrl
```

rather than raw URL strings.

Example:

```text
https://example.test/movie.mp4#player
https://example.test/movie.mp4
```

becomes one canonical candidate.

## Ranking Must Remain Deterministic

For two otherwise identical candidates:

```text
A → source-z
B → source-a
```

the result cannot depend on:

```text
Promise completion order
network latency
Map insertion order from concurrent execution
```

Use an explicit comparator:

```ts
export function compareCandidates(
  a: SourceCandidate,
  b: SourceCandidate
): number {
  const direct =
    Number(b.capabilities.directPlayback) -
    Number(a.capabilities.directPlayback);

  if (direct !== 0) {
    return direct;
  }

  const resolution =
    resolutionValue(b.mediaInfo?.resolution) -
    resolutionValue(a.mediaInfo?.resolution);

  if (resolution !== 0) {
    return resolution;
  }

  const bitrate = (b.mediaInfo?.bitrate ?? 0) - (a.mediaInfo?.bitrate ?? 0);

  if (bitrate !== 0) {
    return bitrate;
  }

  return a.sourceId.localeCompare(b.sourceId);
}
```

Then:

```ts
export function rankCandidates(
  candidates: readonly SourceCandidate[]
): SourceCandidate[] {
  return [...candidates].sort(compareCandidates);
}
```

## Failure Normalization

Every infrastructure failure should eventually become a domain failure.

```text
AbortError
   ↓
source_aborted

timeout
   ↓
source_timeout

HTTP 429
   ↓
source_rate_limited

HTTP 500
   ↓
source_invalid_response / source_network_error
   depending on semantics

breaker open
   ↓
source_circuit_open
```

This is where operational reality becomes domain evidence.

## Candidate Validation

`test/resolver/validation.test.ts`

```ts
import { describe, expect, it } from "vitest";

import { validateCandidate } from "../../src/resolver/validate.js";

const baseCandidate = {
  sourceId: "fixture-authorized",

  media: {
    type: "movie" as const,
    id: "tt1234567"
  },

  url: "https://media.example.test/movie.mp4",

  provenance: {
    adapterId: "fixture-authorized",
    observedAt: "2026-09-28T00:00:00.000Z"
  },

  capabilities: {
    directPlayback: true
  },

  authorization: {
    status: "authorized" as const,
    basis: "fixture"
  }
};

describe("validateCandidate", () => {
  it("accepts a structurally valid candidate", () => {
    const result = validateCandidate(baseCandidate);

    expect(result.valid).toBe(true);
  });

  it("rejects unsupported URL schemes", () => {
    const result = validateCandidate({
      ...baseCandidate,
      url: "file:///etc/passwd"
    });

    expect(result.valid).toBe(false);
  });

  it("rejects missing source identity", () => {
    const result = validateCandidate({
      ...baseCandidate,
      sourceId: ""
    });

    expect(result.valid).toBe(false);
  });
});
```

The test deliberately does not decide authorization.

It asks only:

Is this candidate structurally well-formed?

That keeps:

```text
structure ≠ authorization
```

## Empty Is Not Failure

Add the inverse test:

```ts
it("distinguishes empty from failed", async () => {
  const registry = new SourceRegistry();

  registry.register(new EmptyAdapter());

  const resolver = makeResolver(registry);

  const result = await resolver.resolve(movie(), new AbortController().signal);

  expect(result.status).toBe("empty");

  expect(result.candidates).toEqual([]);

  expect(result.failures).toEqual([]);
});
```

This distinction should survive all the way to observability.

## Request Lifecycle

The full lifecycle now becomes:

```text
┌─────────────────────────────────────────────┐
│               STREMIO REQUEST               │
└──────────────────────┬──────────────────────┘
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
                     ROUTE
                       │
                       ▼
                SOURCE SELECTION
                       │
                       ▼
                   CONCURRENCY
                       │
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
                   DEDUPLICATE
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

And the evidence stream runs alongside it:

```text
                       ┌───────────────┐
                        │ Evidence/Event│
                        │    Ledger     │
                        └───────▲───────┘
                                │
                      every meaningful transition
                                │
                  ──────────────┘
```

## Identity Resolution Algorithm

Initial algorithm:

```text
INPUT
  ExternalIdentity
         │
         ▼
   normalize
         │
         ▼
lookup local identity cache
         │
    ┌────┴────┐
    │         │
  FOUND     MISS
    │         │
    │         ▼
    │    select capable
    │    identity adapters
    │         │
    │         ▼
    │      execute
    │         │
    │         ▼
    │    collect observations
    │         │
    └────┬────┘
         ▼
     reconcile
         │
    ┌────┼─────────────┐
    ▼    ▼             ▼
FOUND AMBIGUOUS   NOT_RESOLVED
    │
    ▼
CanonicalMedia
```

## Reconciliation

Suppose three observations arrive:

```text
A → TMDB 550
B → TMDB 550
C → TVDB 12345
```

Then:

```text
A ──┐
    ├── tmdb:550
B ──┘

C → tvdb:12345
```

If evidence establishes that:

```text
tmdb:550 ↔ tvdb:12345
```

then:

```text
CanonicalMedia
├── imdb:tt...
├── tmdb:550
└── tvdb:12345
```

But if:

```text
tmdb:550 ↔ tvdb:12345
```

cannot be established:

```text
AMBIGUOUS
```

rather than guessing.

## Routing Matrix

| Request identity | Adapter requires | Mapping | Route |
| --- | --- | --- | --- |
| IMDb | IMDb | exact | YES |
| IMDb | TMDB | verified mapping | YES |
| IMDb | TVDB | verified mapping | YES |
| IMDb | TMDB | fuzzy title match | NO |
| IMDb | TMDB | ambiguous mapping | NO |
| IMDb | unknown | none | NO |
| TMDB | TMDB | exact | YES |
| TMDB | IMDb | verified mapping | YES |

The critical property:

```text
insufficient identity evidence
        ↓
NO ROUTE
```

rather than:

```text
insufficient evidence
        ↓
best guess
```

## Routing Explanation

The router should eventually produce an explainable decision:

```ts
export interface RoutingDecision {
  readonly adapterId: string;

  readonly decision:
    | "eligible"
    | "identity_missing"
    | "identity_ambiguous"
    | "media_unsupported"
    | "circuit_open"
    | "not_admitted";

  readonly requiredIdentities: readonly IdentityKind[];

  readonly availableIdentities: readonly IdentityKind[];

  readonly evidenceIds: readonly string[];
}
```

Example:

```json
{
  "adapterId": "tmdb-authorized-source",
  "decision": "identity_missing",
  "requiredIdentities": ["tmdb"],
  "availableIdentities": ["imdb"],
  "evidenceIds": []
}
```

This is vastly more useful than:

```text
adapter skipped
```

## Identity Resolver

The core resolver can look like:

```ts
export class IdentityResolver {
  constructor(
    private readonly registry: IdentityRegistry,
    private readonly cache: IdentityCache
  ) {}

  async resolve(
    input: ExternalIdentity,
    context: IdentityResolveContext
  ): Promise<IdentityResolution> {
    const normalized = normalizeIdentity(input);

    const cached = await this.cache.get(normalized);

    if (cached) {
      return cached;
    }

    const adapters = this.registry
      .all()
      .filter(adapter =>
        adapter.capabilities.inputKinds.includes(normalized.kind)
      );

    const observations = await Promise.allSettled(
      adapters.map(adapter =>
        adapter.resolve(
          {
            kind: normalized.kind,
            value: normalized.value,
            mediaType: input.mediaType
          },
          context
        )
      )
    );

    const result = reconcileIdentityObservations(normalized, observations);

    await this.cache.set(normalized, result);

    return result;
  }
}
```

The important thing is what happens inside:

```text
reconcileIdentityObservations()
```

That function becomes a major correctness boundary.

## Reconciliation Must Be Pure

Make reconciliation a pure function:

```ts
function reconcileIdentityObservations(
  input: ExternalIdentity,
  observations: readonly IdentityObservation[]
): IdentityResolution {
  // no HTTP
  // no cache
  // no logging
  // no mutable global state
}
```

This makes it:

```text
deterministic
testable
replayable
auditable
```

Given identical evidence:

```text
same observations
       ↓
same resolution
```

That is exactly what we want from an evidence-driven system.

## Identity Layer in the Complete Pipeline

We can now refine the architecture:

```text
                         STREMIO
                             │
                             ▼
                          PARSE
                             │
                             ▼
                     ExternalIdentity
                             │
                             ▼
                     IDENTITY RESOLVER
                             │
               ┌─────────────┼──────────────┐
               ▼             ▼              ▼
           cache          adapters       evidence
               │             │
               └──────┬──────┘
                      ▼
                  RECONCILE
                      │
           ┌──────────┼───────────┐
           ▼          ▼           ▼
       resolved    ambiguous   not-resolved
           │
           ▼
     CanonicalMedia
           │
           ▼
       SOURCE ROUTING
           │
           ▼
        EXECUTION
           │
           ▼
      CANDIDATES
           │
           ▼
  VALIDATE → AUTHORIZE → DEDUPE → RANK
           │
           ▼
         STREMIO
```

## Resulting Source-Selection Algorithm

The complete source selection algorithm is now:

```text
REQUEST
  │
  ▼
Parse
  │
  ▼
Normalize identity
  │
  ▼
Resolve identity
  │
  ├── NOT_FOUND ──────────────► no identity route
  │
  ├── NOT_RESOLVED ───────────► retry/fallback policy
  │
  ├── AMBIGUOUS ──────────────► block dependent routes
  │
  └── RESOLVED
          │
          ▼
    CanonicalMedia
          │
          ▼
    capability filter
          │
          ▼
    identity filter
          │
          ▼
    admission filter
          │
          ▼
    health filter
          │
          ▼
    circuit filter
          │
          ▼
    bounded execution
```

This is substantially stronger than:

```text
for each source:
    search(title)
```

because every decision is explainable.

## Determinism requirement

Given the same canonical media and equivalent source state:

```text
resolve(M, C)
```

should produce semantically equivalent output independent of:

- candidate input order,
- asynchronous completion order,
- map iteration order,
- logging order.

Formally:

```text
Resolve(M, C) = Resolve(M, C)
```

under equivalent observations.

And:

```text
Rank(A ∪ B) = Rank(B ∪ A)
```

This becomes especially important once multiple legitimate libraries
are configured.

## Duplicate asset identity

Two records should not silently represent the same asset.

Define:

```ts
function assetKey(asset: LibraryAsset): string {
  return asset.assetId;
}
```

The library loader should reject:

```text
asset-001
asset-001
```

unless the semantics explicitly permit versioning.

This is preferable to silently selecting one.

## Canonical ID validation

The library should not accept arbitrary canonical identifiers if the
system has defined a canonical namespace.

For v0.1:

```ts
type CanonicalMediaId = `media:${string}`;
```

Then:

```ts
function isCanonicalMediaId(value: string): value is CanonicalMediaId {
  return /^media:[A-Za-z0-9._:-]+$/.test(value);
}
```

This does **not** mean the identifier is universally canonical.

It means:

The application recognizes it as belonging to its canonical-ID
namespace.

That distinction should remain explicit.

## Metadata reconciliation

We need a pure function:

```ts
reconcileMetadata(observations: readonly MetadataObservation[]): MetadataRecord;
```

No:

- HTTP
- database
- cache
- logging
- global state

inside it.

Given the same observations:

```text
reconcile(O) = reconcile(O)
```

This makes the result testable.

## Different fields need different reconciliation rules

Do not use one universal rule.

For example:

### Year

```text
2024
2024
2024
```

strong agreement.

### Title

```text
"The Example"
"Example"
"Example: The Movie"
```

requires a display policy.

### Genres

Should normally be treated as a set:

```text
Provider A: ["Drama", "Mystery"]

Provider B: ["Mystery", "Thriller"]
```

Possible derived set:

```text
["Drama", "Mystery", "Thriller"]
```

But that is a **policy choice**, not a fact.

### Runtime

```text
Provider A → 118 min
Provider B → 120 min
```

Do not silently average:

```text
119 min
```

That would manufacture information.

## Preserve disagreements

A useful structure is:

```ts
interface MetadataConflict {
  readonly field: MetadataField;

  readonly observations: readonly MetadataFieldObservation[];

  readonly resolution: "selected" | "merged" | "unresolved";
}
```

Then:

```ts
interface MetadataReconciliationResult {
  readonly record: MetadataRecord;

  readonly conflicts: readonly MetadataConflict[];
}
```

This prevents:

```text
conflict
   ↓
silently overwrite
```

## Metadata routing decision

```ts
interface MetadataRoutingDecision {
  readonly providerId: string;

  readonly decision:
    | "eligible"
    | "identity_missing"
    | "media_unsupported"
    | "disabled"
    | "rate_limited"
    | "circuit_open";

  readonly requiredIdentities: readonly IdentityKind[];

  readonly availableIdentities: readonly IdentityKind[];
}
```

Again:

```text
routing decision ≠ metadata result
```

A provider being eligible doesn't mean it successfully returned
metadata.

## Metadata and playback remain independent

This is a major design invariant.

A movie can have:

```text
metadata = available
streams = empty
```

or:

```text
metadata = unavailable
streams = available
```

or:

```text
metadata = partial
streams = partial
```

Therefore:

```text
metadata failure
    ≠ stream failure
```

The resolver should not block playback merely because optional
metadata is unavailable.

## Language normalization

Language strings are notoriously inconsistent.

A provider might return:

```text
en
eng
EN
en-US
English
```

These should not be compared as arbitrary strings.

Introduce a normalized representation:

```ts
interface LanguageTag {
  readonly normalized: string;
  readonly original: string;
}
```

For example:

```text
"EN-US"
   ↓
"en-US"
```

and:

```text
"eng"
   ↓
"en"
```

where the normalization mapping is explicitly defined.

Do not silently claim:

```text
English = American English
```

unless the normalization policy supports that equivalence.

## Subtitle deduplication

Two providers may return the same subtitle.

Raw URLs can differ:

```text
https://a.example/sub.srt
https://a.example/sub.srt#download
```

Normalize before deduplication.

But URL equality isn't always enough.

A stronger key can include:

```text
media + language + forced + hearing-impaired + canonicalized URL
```

Do not deduplicate two genuinely different subtitle tracks merely
because they share a language.

## Subtitle ranking

Ranking should be explicit.

Possible preference dimensions:

```text
1. preferred language
2. exact language/region match
3. forced/non-forced requirement
4. hearing-impaired preference
5. format
6. provider/source
```

But the resolver should distinguish:

```text
user preference
```

from:

```text
authorization
```

A preferred subtitle cannot override authorization.

## Empty subtitles

A valid request with no subtitles should produce:

```json
{
  "subtitles": []
}
```

assuming that is the protocol's expected response shape for the
deployed SDK/API contract.

Do not turn:

```text
no subtitles found
```

into:

```text
HTTP 500
```

unless the protocol contract explicitly requires an error.

## Subtitle failure matrix

| Provider condition | Domain outcome |
| --- | --- |
| subtitles found | success |
| no subtitles | not_found / empty |
| timeout | not_resolved |
| rate limit | not_resolved |
| ambiguous episode mapping | ambiguous |
| malformed response | failure |
| unauthorized candidate | candidate rejected |

Again:

```text
not_found ≠ not_resolved
```

## The anti-pattern

Avoid:

```text
/catalog
   ↓
for every source
   ↓
source.resolve(...)
   ↓
discover everything
```

That creates several problems:

```text
catalog request
    ↓
N sources
    ↓
N network requests
    ↓
N different provider semantics
    ↓
unbounded discovery
```

It also encourages providers to expose arbitrary content simply
because they happen to return it.

The correct architecture is:

```text
Catalog
   │
   ▼
CatalogIndex
   │
   ▼
CatalogEntries
   │
   ▼
Stremio Catalog DTO
```

## Search query normalization

Normalize:

```ts
interface NormalizedSearchQuery {
  readonly original: string;

  readonly normalized: string;
}
```

Potential normalization:

```text
trim
Unicode normalization
collapse whitespace
case normalization
```

But don't aggressively remove punctuation or transliterate languages
unless that behavior is explicitly part of the search contract.

For example:

```text
"Spider-Man"
```

should not silently become a different semantic query.

## Search ranking

Search ranking is different from stream ranking.

Stream ranking asks:

Which playable candidate should appear first?

Search ranking asks:

Which catalog entity best matches the query?

Therefore keep:

```text
StreamRanker
```

and:

```text
CatalogRanker
```

separate.

## Catalog ranking model

A deterministic first implementation could consider:

```text
exact title match
prefix match
token match
year match
provider confidence
canonical identity availability
stable canonical ID
```

But every score must be explainable.

For example:

```ts
interface CatalogRankingExplanation {
  readonly exactTitle: boolean;
  readonly prefixMatch: boolean;
  readonly tokenMatchCount: number;
  readonly yearMatch: boolean;
  readonly identityResolved: boolean;
}
```

Then:

```text
score = derived view
```

rather than an unexplained magic number.

## Dedupe catalog results

Two providers may return:

```text
Provider A: tt1234567

Provider B: tmdb:550
```

Identity reconciliation can establish that they represent the same
media.

Then:

```text
Provider A ─┐
            ├──> CanonicalMedia
Provider B ─┘
```

and the catalog projection becomes one entry.

This is one of the strongest reasons identity must remain
independent.

## Unresolved catalog entries

Suppose:

```text
Provider A: title = "Example" year = 2024

Identity: AMBIGUOUS
```

The system has two choices:

### Strict canonical catalog

Only include resolved identities.

### Evidence-preserving staging catalog

Retain unresolved observations separately until identity is resolved.

For the main Stremio catalog, the strict approach is safer:

```text
AMBIGUOUS
   ↓
not promoted to canonical catalog entry
```

The observation is not destroyed.

## Catalog ingestion

Instead of querying providers during every user request:

```text
Provider
   ↓
ingestion job
   ↓
observation
   ↓
reconciliation
   ↓
catalog index
```

This changes the runtime behavior dramatically.

A user request becomes:

```text
/catalog
   ↓
CatalogIndex
   ↓
fast deterministic response
```

rather than:

```text
/catalog
   ↓
multiple external providers
   ↓
latency + failures
```

## Ingestion is asynchronous

Introduce:

```ts
interface CatalogIngestionJob {
  readonly jobId: string;

  readonly providerId: string;

  readonly catalogId: string;

  readonly startedAt: string;

  readonly completedAt?: string;

  readonly status: "running" | "completed" | "partial" | "failed";
}
```

This allows:

```text
runtime request path
```

to remain separate from:

```text
background synchronization path
```

## Freshness

Catalog data becomes time-dependent.

Add:

```ts
interface CatalogFreshness {
  readonly observedAt: string;

  readonly generatedAt: string;

  readonly expiresAt?: string;
}
```

But:

```text
expired
```

does not mean:

```text
false
```

This follows the same rule as identity and metadata.

```text
expired catalog
    ≠ media does not exist
```

## Full-text search

If search grows beyond simple matching:

```text
CatalogEntry
    ↓
tokenizer
    ↓
FTS index
```

But the FTS index remains a derived structure.

Therefore:

```text
FTS index corruption
    ≠ loss of canonical evidence
```

It can be rebuilt.

That is an important durability property.

## Three independent states

This produces an important distinction:

```text
CATALOG
  "media exists in browse index"

METADATA
  "descriptive information exists"

PLAYBACK
  "authorized playback candidate exists now"
```

All combinations are possible.

| Catalog | Metadata | Playback | Meaning |
| --- | --- | --- | --- |
| ✓ | ✓ | ✓ | browse + information + playback |
| ✓ | ✓ | ✗ | known media, no playable candidate |
| ✓ | ✗ | ✓ | playable but metadata unavailable |
| ✗ | ✓ | ✓ | possible direct resolution without catalog listing |
| ✗ | ✗ | ✓ | direct playback path only |
| ✓ | ✗ | ✗ | browse-only entry |

This is preferable to one global:

```text
available = true/false
```

## Resource resolver

An even stronger abstraction is a typed resource model:

```text
                MediaApplication
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
      Streams        Metadata       Subtitles
                        │
                  ┌─────┴─────┐
                  ▼           ▼
               Catalog       Search
```

Each operation remains independent.

There is no giant:

```text
resolveEverything()
```

method.

That would recreate the coupling we spent the previous sections
removing.

## Why not `resolveEverything()`?

Because a Stremio client may request:

```text
/meta
```

without:

```text
/stream
```

or:

```text
/catalog
```

without either.

If one mega-resolver executes all subsystems:

```text
/catalog
  ↓
identity
  ↓
metadata
  ↓
streams
  ↓
subtitles
```

then an outage in a subtitle provider could accidentally affect
catalog browsing.

Independent resource resolution gives:

```text
failure isolation
```

as an architectural property.

## Failure-domain isolation

The resulting system can be represented as:

```text
                 STREMIO
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
      Catalog     Metadata     Stream
         │           │           │
         ▼           ▼           ▼
       pool-A      pool-B      pool-C
         │           │           │
         ▼           ▼           ▼
     providers    providers   providers
                     │
                  pool-D
                     │
                 subtitles
```

More accurately, subtitles would have their own pool as well.

The principle is:

one subsystem's external latency must not consume the entire
process's execution budget.

## Resource-specific budgets

Define:

```ts
interface ResourceBudget {
  readonly timeoutMs: number;

  readonly maxConcurrency: number;

  readonly maxCandidates: number;
}
```

Then:

```text
stream:
    5000ms / 20

metadata:
    3000ms / 10

subtitle:
    3000ms / 10

catalog:
    mostly local / 4
```

Those numbers are examples, not validated production defaults.

The important part is that budgets are **declared per resource**.

## Parallel vs sequential orchestration

For `/stream`, identity resolution usually precedes source
resolution:

```text
identity
   ↓
CanonicalMedia
   ↓
sources
```

But metadata and subtitles may sometimes execute independently once
canonical identity exists.

For example:

```text
CanonicalMedia
     │
┌───┼────┐
▼   ▼    ▼
meta stream subtitles
```

These can run concurrently when requested together by an internal
workflow.

The default Stremio handlers, however, should only perform the work
needed for their individual resource.

## Admission graph vs execution graph

We now have two different graphs.

### Admission graph

```text
Declaration
   ↓
Validation
   ↓
Authorization evidence
   ↓
Admission
```

### Execution graph

```text
Request
   ↓
Identity
   ↓
Provider selection
   ↓
Runtime controls
   ↓
Observation
   ↓
Validation
   ↓
Authorization
   ↓
Projection
```

Do not merge them.

An admitted provider can fail during execution.

An unhealthy provider does not become unauthorized.

## The central invariant

The whole architecture can now be reduced to one rule:

```text
OBSERVE
   ↓
PRESERVE
   ↓
VALIDATE
   ↓
AUTHORIZE
   ↓
DERIVE
   ↓
PRESENT
```

Not:

```text
FETCH
 ↓
TRUST
 ↓
RETURN
```

That distinction is what makes the addon an aggregation platform
rather than a collection of network scrapers.

## Pure resolver core

This suggests splitting resolution into:

```text
LIVE ADAPTERS
     │
     ▼
OBSERVATIONS
     │
     ▼
PURE CORE
     │
     ▼
DERIVED RESULT
```

The pure core performs:

```text
validation
authorization
dedupe
ranking
reconciliation
```

This dramatically improves testing.

## Functional core / imperative shell

The architecture is now:

```text
             IMPERATIVE SHELL
       HTTP / network / clocks / storage
                      │
                      ▼
               OBSERVATIONS
                      │
                      ▼
               FUNCTIONAL CORE
         validation / policy / ranking
                      │
                      ▼
                 DERIVED VIEW
```

This is particularly compatible with the user's evidence-first model.

## Resolver kernel

Extract a pure kernel:

```ts
interface ResolverKernel {
  resolve(input: ResolverKernelInput): ResolverKernelOutput;
}
```

Input:

```ts
interface ResolverKernelInput {
  readonly media: CanonicalMedia;

  readonly candidates: readonly SourceCandidate[];

  readonly policy: RuntimePolicy;

  readonly preferences: ResolutionPreferences;
}
```

Output:

```ts
interface ResolverKernelOutput {
  readonly accepted: readonly SourceCandidate[];

  readonly rejected: readonly CandidateRejection[];

  readonly ranking: readonly RankingDecision[];
}
```

No:

```text
fetch
clock
randomness
database
logger
environment
```

inside the kernel.
