# Evidence & Provenance

[⇧ Architecture index](../architecture.md) · [⇆ Document map](./README.md)

> **Scope.** The evidence model: `OBSERVED` ≠ `DERIVED` ≠ `VERIFIED` ≠ `ANNOTATED`, and the larger chain of distinctions — representation ≠ semantics ≠ evidence ≠ truth ≠ authority ≠ authorization ≠ admission ≠ execution ≠ success ≠ canonicality ≠ durability. Covers observations, receipts, provenance, replay, determinism, and lineage. An observation must never be silently promoted into a verification claim.

> **Primary dependencies:** `../contracts/evidence.md`

> **Status.** Unless a section explicitly states otherwise with a concrete repository reference (file path, commit, or CI run), everything below is **DESIGNED** or **PROPOSED** architecture, not implemented code. This document was migrated from the original `docs/architecture.md` monolith; section order is preserved from that document, numbering has been dropped in favor of descriptive headings, and some very long single sections in the monolith may appear here still bearing internal editorial framing (e.g. first-person design narration) that predates the doc-split.

## Sections in this document

- [Adapter execution should produce evidence](#adapter-execution-should-produce-evidence)
- [Release evidence](#release-evidence)
- [Identity is evidence, not a string](#identity-is-evidence-not-a-string)
- [Identity evidence](#identity-evidence)
- [Stream and subtitle provenance](#stream-and-subtitle-provenance)
- [Candidate evidence](#candidate-evidence)
- [Evidence event](#evidence-event)
- [Persist facts, derive views](#persist-facts-derive-views)
- [Evidence Event](#evidence-event)
- [Provider Disagreement](#provider-disagreement)
- [Canonicality Is Not Truth](#canonicality-is-not-truth)
- [Identity Evidence Receipt](#identity-evidence-receipt)
- [Identity evidence becomes a routing input](#identity-evidence-becomes-a-routing-input)
- [The critical distinction: evidence verification](#the-critical-distinction-evidence-verification)
- [Source-level receipt](#source-level-receipt)
- [Observation, not truth](#observation-not-truth)
- [Why field-level provenance matters](#why-field-level-provenance-matters)
- [Metadata receipts](#metadata-receipts)
- [Subtitle observation](#subtitle-observation)
- [Subtitles and metadata can share identity evidence](#subtitles-and-metadata-can-share-identity-evidence)
- [But do not share mutable conclusions blindly](#but-do-not-share-mutable-conclusions-blindly)
- [Evidence graph](#evidence-graph)
- [Catalog observation](#catalog-observation)
- ["Persist facts; derive views"](#"persist-facts;-derive-views")
- [Rebuildability invariant](#rebuildability-invariant)
- [Receipt architecture](#receipt-architecture)
- [Receipt ≠ truth](#receipt-≠-truth)
- [Evidence IDs](#evidence-ids)
- [Canonical evidence representation](#canonical-evidence-representation)
- [Evidence envelope](#evidence-envelope)
- [Evidence levels](#evidence-levels)
- [Example](#example)
- [Evidence graph](#evidence-graph)
- [Deterministic replay](#deterministic-replay)
- [Replay ≠ re-fetch](#replay-≠-re-fetch)
- [Candidate rejection evidence](#candidate-rejection-evidence)
- [Observation identity vs entity identity](#observation-identity-vs-entity-identity)
- [Reproducibility chain](#reproducibility-chain)

---

## Adapter execution should produce evidence

> **Historical (distinct, non-converged variant), per `ADR-007`
> (2026-09-29, second session).** This `AdapterExecution` draft uses
> `startedAt`/`completedAt` and a typed `failure?: SourceFailure` instead
> of `durationMs`/`error?: string`, and its own 6-value `status` union.
> The canonical `AdapterExecution` (fields converged independently across
> `docs/architecture/04-providers.md` and `docs/architecture/06-runtime.md`)
> is defined in [`docs/contracts/result.md`](../contracts/result.md). This
> draft's timestamp/typed-failure approach is preserved as a plausible
> future direction for a dedicated execution-receipt contract, not
> discarded.

Instead of:

```ts
Promise<SourceCandidate[]>
```

I recommend:

```ts
// HISTORICAL variant — see note above and docs/contracts/result.md
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

## Release evidence

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

## Identity is evidence, not a string

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

> **SUPERSEDED by `ADR-002` (2026-09-29).** `MediaIdentity`/
> `IdentityEvidence` below are retained as historical rationale for *why*
> confidence-bearing identity evidence matters — they are **not** part of
> the frozen contract. Their `matchedBy`/`confidence` fields were merged
> into `IdentityObservation` (`04-providers.md`) instead, so evidence
> stays on the type identity-provider adapters already produce, rather
> than living in a second, disconnected model. Do not implement against
> `MediaIdentity`/`IdentityEvidence` directly — use `IdentityObservation`
> and `IdentityReceipt` (below). See
> [`ADR-002`](../decisions/ADR-002-identity-confidence-ownership.md).

```ts
// SUPERSEDED — see ADR-002. Kept for historical rationale only.
export interface MediaIdentity {
  readonly canonical?: ExternalIdentity;

  readonly aliases: readonly ExternalIdentity[];

  readonly evidence: readonly IdentityEvidence[];
}
```

## Identity evidence (SUPERSEDED, see ADR-002)

```ts
// SUPERSEDED — merged into IdentityObservation.matchedBy/confidence
// (docs/architecture/04-providers.md). See ADR-002.
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

## Stream and subtitle provenance

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

## Candidate evidence

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

## Evidence event

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

## Persist facts, derive views

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

## Evidence Event

Every source execution should eventually emit:

```ts
interface ResolutionEvent {
  requestId: string;
  timestamp: string;

  media: MediaRef;

  adapterId: string;

  stage: "selected" | "started" | "completed" | "failed" | "rejected";

  outcome: "success" | "empty" | "partial" | "failure" | "unauthorized";

  durationMs?: number;

  candidateCount?: number;

  failureCode?: FailureCode;
}
```

Example:

```json
{
  "requestId": "req_01J...",
  "adapterId": "fixture-authorized",
  "stage": "completed",
  "outcome": "success",
  "candidateCount": 1,
  "durationMs": 14
}
```

This is a fact.

A dashboard such as:

```text
Source A availability = 99.2%
```

is a derived view.

That preserves:

```text
facts
  ↓
events
  ↓
derived metrics
```

rather than storing conclusions as if they were observations.

## Provider Disagreement

Suppose:

```text
Provider A: tt1234567 → tmdb 550

Provider B: tt1234567 → tmdb 999999
```

The system must not silently choose one.

Instead:

```text
identity conflict
      │
      ▼
CONFLICT / AMBIGUOUS
```

Then:

```text
source requiring TMDB
        ↓
cannot safely route
```

unless an explicit resolution rule establishes which relationship is
authoritative.

This follows the general principle:

**Conflicting evidence must remain conflicting until resolved.**

## Canonicality Is Not Truth

This distinction is subtle.

Suppose:

```text
canonicalId = media:abc123
```

That means:

Our system currently treats these identity observations as belonging
to one canonical entity.

It does **not** mean:

The system has discovered metaphysical truth about the media.

So:

```text
canonicality ≠ truth
```

This is exactly the kind of semantic collapse the architecture is
designed to prevent.

## Identity Evidence Receipt

Every identity resolution can produce:

```ts
export interface IdentityReceipt {
  readonly receiptId: string;

  readonly requestIdentity: ExternalIdentity;

  readonly observations: readonly IdentityObservation[];

  readonly outcome: "resolved" | "not_found" | "ambiguous" | "not_resolved";

  readonly canonicalId?: string;

  readonly observedAt: string;
}
```

This is particularly valuable when debugging:

```text
"Why didn't source X run?"
```

We can answer:

```text
Source X requires TMDB identity.

TMDB identity was not established.

Therefore source X was not routed.
```

Rather than:

```text
"the source didn't work."
```

## Identity evidence becomes a routing input

The complete routing decision now becomes:

```text
External Identity
       │
       ▼
Identity Resolver
       │
       ▼
Identity State
       │
       ├── NOT_FOUND
       ├── NOT_RESOLVED
       ├── AMBIGUOUS
       └── RESOLVED
                │
                ▼
          CanonicalMedia
                │
                ▼
        Source Declaration
                │
        ┌───────┴────────┐
        ▼                ▼
 identity sufficient   insufficient
        │                │
        ▼                ▼
   admission         explanation
```

This is much safer than:

```text
title → scrape everything → hope
```

## The critical distinction: evidence verification

The previous algorithm should **not** automatically equate:

```text
evidence exists
```

with:

```text
evidence verified
```

That distinction becomes important as the system grows.

A stronger model is:

```ts
interface AuthorizationEvidence {
  readonly evidenceId: string;
  readonly kind: AuthorizationEvidenceKind;

  readonly subject: string;
  readonly observedAt: string;

  readonly verification: "unverified" | "verified" | "expired";
}
```

Then admission requires:

```text
at least one acceptable
AND currently verified
AND not expired
```

This gives:

```text
DECLARED
    ↓
OBSERVED
    ↓
VERIFIED
    ↓
ADMITTED
```

rather than:

```text
string says authorized → trust it
```

## Source-level receipt

The runtime should eventually generate a receipt like:

```ts
interface SourceExecutionReceipt {
  readonly receiptId: string;
  readonly requestId: string;

  readonly sourceId: string;

  readonly canonicalId: string;

  readonly startedAt: string;
  readonly completedAt: string;

  readonly outcome: "success" | "empty" | "failed" | "rejected";

  readonly candidateCount: number;

  readonly failureCode?: FailureCode;

  readonly evidenceIds: readonly string[];
}
```

Again:

```text
receipt = record of execution
```

not:

```text
receipt = proof that the media is true
```

## Observation, not truth

The provider result should be called an **observation**.

```ts
interface MetadataObservation {
  readonly providerId: string;

  readonly observedAt: string;

  readonly status: "success" | "not_found" | "not_resolved" | "ambiguous";

  readonly fields: readonly MetadataFieldObservation[];
}
```

Each field retains provenance:

```ts
interface MetadataFieldObservation<T = unknown> {
  readonly field: MetadataField;

  readonly value: T;

  readonly source: string;

  readonly observedAt: string;

  readonly evidenceId?: string;
}
```

Therefore:

```text
title = "Example Movie"
source = provider-A
observedAt = ...
```

is an observation.

It is not transformed into:

```text
TITLE_TRUTH = "Example Movie"
```

## Why field-level provenance matters

Suppose two providers report:

```text
Provider A: title = "The Example"

Provider B: title = "Example: The Movie"
```

But both agree:

```text
year = 2024
```

We should not throw away the disagreement.

Represent:

```text
title
├── A → "The Example"
└── B → "Example: The Movie"

year
├── A → 2024
└── B → 2024
```

Now a later reconciliation policy can derive a display value.

The observations remain intact.

## Metadata receipts

A metadata resolution can produce:

```ts
interface MetadataReceipt {
  readonly receiptId: string;
  readonly requestId: string;

  readonly canonicalId: string;

  readonly providerObservations: readonly string[];

  readonly outcome: "resolved" | "partial" | "empty" | "ambiguous" | "not_resolved";

  readonly observedAt: string;
}
```

This makes later debugging possible:

```text
Why did the UI show this title?

→ Provider A observed it.
→ Provider B disagreed.
→ reconciliation selected A.
```

That is substantially better than:

```text
"the metadata service returned it."
```

## Subtitle observation

Provider output:

```ts
interface SubtitleObservation {
  readonly providerId: string;

  readonly observedAt: string;

  readonly status: "success" | "not_found" | "not_resolved" | "ambiguous";

  readonly subtitles: readonly SubtitleObservationItem[];
}
```

And:

```ts
interface SubtitleObservationItem {
  readonly id: string;

  readonly url: string;

  readonly language: string;

  readonly format?: SubtitleFormat;

  readonly hearingImpaired?: boolean;

  readonly forced?: boolean;

  readonly evidenceIds: readonly string[];
}
```

Again:

```text
provider output
     ↓
observation
     ↓
central validation
```

## Subtitles and metadata can share identity evidence

Once:

```text
CanonicalMedia
```

exists, both systems can reuse it.

```text
                    CanonicalMedia
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
          Metadata                Subtitles
               │                     │
               ▼                     ▼
        observations             observations
```

This avoids repeatedly solving identity resolution for every
subsystem.

Identity becomes a shared foundation.

## But do not share mutable conclusions blindly

A cached identity resolution should not automatically be treated as
eternal.

Therefore:

```text
Identity Cache
       │
       ▼
CanonicalMedia
       │
       ├── metadata request
       ├── stream request
       └── subtitle request
```

but each subsystem records:

```text
which identity evidence it relied upon
```

This is essential for reproducibility.

## Evidence graph

The architecture is now approaching:

```text
Request
  │
  ├──────── Identity Evidence
  │              │
  │              ▼
  │        CanonicalMedia
  │              │
  │        ┌─────┼─────┐
  │        ▼     ▼     ▼
  │      Meta  Source  Subs
  │        │     │      │
  │        ▼     ▼      ▼
  │    Observ. Candidates Tracks
  │        │     │      │
  └────────┴─────┴──────┘
             │
             ▼
          Derived
           Views
```

This is much closer to an auditable aggregation engine than a
conventional "addon scraper."

## Catalog observation

As with the other subsystems, preserve state:

```ts
interface CatalogObservation {
  readonly providerId: string;

  readonly observedAt: string;

  readonly status: "success" | "not_found" | "not_resolved" | "ambiguous";

  readonly entries: readonly CatalogObservationEntry[];
}
```

Entry:

```ts
interface CatalogObservationEntry {
  readonly media: MediaRef;

  readonly canonicalId?: string;

  readonly title?: string;

  readonly year?: number;

  readonly poster?: string;

  readonly background?: string;

  readonly evidenceIds: readonly string[];
}
```

The important detail is:

```text
canonicalId?
```

not:

```text
canonicalId: string
```

A catalog provider may know that a title exists without having
established canonical identity.

## "Persist facts; derive views"

The architecture now has a recurring pattern:

```text
                FACTS
                  │
       ┌──────────┼──────────┐
       ▼          ▼          ▼
    Identity   Metadata   Catalog
    Evidence   Evidence    Evidence
       │          │          │
       └──────────┼──────────┘
                  ▼
             DERIVATION
                  │
       ┌──────────┼──────────┐
       ▼          ▼          ▼
  Canonical     Metadata    Catalog
   Media         View        Index
```

Never make the catalog projection the authority merely because it is
convenient to query.

## Rebuildability invariant

A strong architectural invariant:

```text
Canonical facts + deterministic derivation rules = rebuildable views
```

Therefore:

```text
catalog index
metadata cache
search index
ranking cache
```

should ideally be reconstructible.

If deleting a derived index destroys authoritative facts, the
boundary has failed.

## Receipt architecture

> **Receipt family audit note (2026-09-29, second session).** This is not
> one duplicated concept but at least three legitimate layers, confirmed
> by re-reading every field across the receipt/evidence family:
>
> ```text
> EvidenceRecord<T>            (generic envelope: core fact + hash + provenance)
>      ↓
> domain-specific receipts     (fact-recording, each with its own `outcome`)
>      ├── IdentityReceipt
>      ├── MetadataReceipt
>      └── SourceExecutionReceipt
>      ↓
> ReceiptEnvelope               (transport/storage metadata: receiptId,
>                                generation, createdAt, kind, schemaVersion)
> ```
>
> Two field-naming patterns were checked and found to be **intentional,
> not contradictory**: (1) `observedAt` (a single point when evidence was
> gathered — `IdentityReceipt`, `MetadataReceipt`, `EvidenceRecord`) is
> deliberately distinct from `startedAt`/`completedAt` (a duration for
> work actually performed — `SourceExecutionReceipt`, mirroring
> `AdapterExecution`'s `durationMs`) and from `createdAt` (when the
> envelope/record object itself was created, potentially later than the
> observation — `ReceiptEnvelope`). (2) `outcome` (used consistently by
> all three fact-recording receipts) is deliberately distinct from
> `status` (used by `AdapterExecution` and `AdmissionDecision`, which
> describe execution/decision state, not a recorded fact). Neither
> distinction should be collapsed.
>
> One naming inconsistency **was** found and is not yet resolved:
> `SourceExecutionReceipt.sourceId` and `AdapterExecution.adapterId`
> (`docs/contracts/result.md`) both identify the same underlying
> `SourceAdapter.id`, under two different field names. This is low
> severity (neither type references the other's field, so no confusion
> at the type level) but is recorded as `OPEN-14` for a future pass to
> pick one name.
>
> A second, more substantive gap was also found: `ReceiptEnvelope` is
> introduced as a common wrapper ("subsystem-specific payloads remain
> strongly typed") but no example ever shows the actual composition (e.g.
> a generic `ReceiptEnvelope<T> extends ... { payload: T }`, or each
> receipt independently including its own copy of the envelope fields).
> This is **not resolved** in this pass — it does not affect any V0.1
> CORE-scope contract, but it does affect `docs/contracts/evidence.md`'s
> receipt portion, which remains `NOT_FROZEN` for this reason among
> others. See `OPEN-14` and the evidence-contract status in
> `docs/architecture/documentation-audit.md`.

We now have several receipts:

```text
IdentityReceipt
SourceExecutionReceipt
MetadataReceipt
SubtitleReceipt
CatalogIngestionReceipt
```

Introduce a common envelope:

```ts
interface ReceiptEnvelope {
  readonly receiptId: string;

  readonly requestId?: string;

  readonly generation: string;

  readonly createdAt: string;

  readonly kind: string;

  readonly schemaVersion: string;
}
```

Then subsystem-specific payloads remain strongly typed.

## Receipt ≠ truth

This distinction should remain explicit:

```text
Receipt
  = record that an operation/observation occurred

Receipt
  ≠ proof that the underlying claim is true
```

For example:

```text
"provider returned URL X"
```

is an observable fact.

It does not prove:

```text
"URL X is legally authorized"
```

unless authorization evidence independently establishes that.

## Evidence IDs

Evidence should have stable identifiers.

```ts
interface EvidenceRef {
  readonly evidenceId: string;

  readonly kind: string;

  readonly digest: string;
}
```

The digest should be calculated over a canonical representation.

This is where the earlier evidence architecture becomes useful.

## Canonical evidence representation

Conceptually:

```text
Observation
   ↓
Normalize
   ↓
Canonical serialization
   ↓
Digest
   ↓
EvidenceRecord
```

Avoid:

```text
JSON.stringify(object)
```

as a long-term canonicalization specification.

Property ordering and representation details need an explicit
canonicalization contract.

## Evidence envelope

Separate:

```text
core fact
```

from:

```text
execution environment
```

For example:

```ts
interface EvidenceRecord<T> {
  readonly core: T;

  readonly evidenceId: string;

  readonly algorithm: "sha256";

  readonly observedAt: string;

  readonly source: string;

  readonly envelope?: {
    readonly requestId?: string;
    readonly generation?: string;
    readonly runtimeVersion?: string;
  };
}
```

The core should remain deterministic.

The envelope may vary between executions.

## Evidence levels

> **See the normative contract:** [`docs/contracts/evidence.md`](../contracts/evidence.md) defines the four evidence levels once, authoritatively.

We can now formalize statuses:

```text
OBSERVED
DERIVED
VERIFIED
ANNOTATED
```

### OBSERVED

Provider directly returned it.

### DERIVED

The system computed it.

### VERIFIED

An explicit verification procedure succeeded.

### ANNOTATED

A human/operator supplied additional context.

These should never be silently collapsed.

## Example

Provider returns:

```text
title = "Example Movie"
```

The system computes:

```text
normalizedTitle = "example movie"
```

An identity resolver establishes:

```text
IMDb tt1234567 ↔ TMDB 999
```

An operator supplies:

```text
source is operator-owned
```

The resulting evidence graph is:

```text
title
  OBSERVED

normalizedTitle
  DERIVED

identity mapping
  VERIFIED

ownership declaration
  ANNOTATED / VERIFIED
  depending on actual verification
```

The system must preserve these distinctions.

## Evidence graph

The graph becomes:

```text
                         REQUEST
                            │
                            ▼
                       OBSERVATION
                            │
                  ┌─────────┼─────────┐
                  ▼         ▼         ▼
              Identity   Metadata   Source
              Evidence   Evidence   Evidence
                  │         │         │
                  └─────────┼─────────┘
                            ▼
                        DERIVATION
                            │
                 ┌──────────┼──────────┐
                 ▼          ▼          ▼
              Canonical   Catalog   Candidates
                Media      View
```

This is the basis for reproducibility.

## Deterministic replay

Now introduce replay.

```ts
interface ReplayInput {
  readonly request: unknown;

  readonly generation: string;

  readonly evidence: readonly EvidenceRef[];
}
```

Replay should answer:

Given the same input evidence and the same algorithm version, does the
derived result remain identical?

This is different from rerunning external providers.

## Replay ≠ re-fetch

Very important:

```text
REPLAY
    uses recorded evidence

LIVE EXECUTION
    queries providers
```

A replay must not silently contact the Internet.

Otherwise it ceases to be deterministic replay.

## Candidate rejection evidence

Instead of simply:

```ts
return [];
```

preserve rejection reasons internally:

```ts
interface CandidateRejection {
  readonly candidateId: string;

  readonly reason:
    | "invalid_url"
    | "unauthorized"
    | "not_direct_playback"
    | "unsupported_media"
    | "network_policy"
    | "duplicate";
}
```

This allows diagnostics without exposing sensitive details to
Stremio.

## Observation identity vs entity identity

This distinction is now central:

```text
Observation ID
    ↓
identifies an observation

Candidate ID
    ↓
identifies a derived candidate

Canonical Media ID
    ↓
identifies an application-level media entity
```

Three namespaces.

Never reuse one as another.

## Reproducibility chain

The complete chain becomes:

```text
SOURCE CONFIG
      │
      ▼
CONFIG DIGEST
      │
      ▼
RUNTIME GENERATION
      │
      ▼
REQUEST
      │
      ▼
OBSERVATIONS
      │
      ▼
PURE DERIVATION
      │
      ▼
RESULT
```

This is considerably stronger than ordinary application logging.
