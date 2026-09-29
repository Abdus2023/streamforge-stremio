# ADR-001: `SourceAdapter` resolves against identity-resolved media, not a raw `MediaRef`

[⇧ Back to the decision ledger](./README.md)

- **Status:** ACCEPTED
- **Date:** 2026-09-29
- **Resolves:** `OPEN-8` in `docs/decisions/README.md`
- **Affects:** `docs/contracts/source-adapter.md`, `docs/architecture/04-providers.md`, `docs/architecture/03-resolution.md`

## Context

The monolith stated at least 6 non-identical `SourceAdapter` shapes across
its evolution. The two poles are:

**Model A (minimal, `MediaRef`-based — previously frozen):**

```ts
export interface SourceAdapter {
  readonly id: string;
  readonly name: string;
  supports(media: MediaRef): boolean;
  resolve(media: MediaRef, ctx: ResolveContext): Promise<readonly SourceCandidate[]>;
  health?(): Promise<HealthResult>;
}
```

**Model C (identity/capability-aware, last and most evolved shape in the monolith):**

```ts
export interface SourceAdapter {
  readonly id: string;
  readonly name: string;
  readonly capabilities: SourceCapabilities;
  supportsMedia(media: MediaRef): boolean;
  supportsIdentity(identities: readonly ExternalIdentity[]): boolean;
  resolve(media: CanonicalMedia, context: ResolveContext): Promise<readonly SourceCandidate[]>;
}
```

Model A lets a resolver call an adapter before identity is resolved
(the adapter only ever sees a raw `MediaRef`). Model C requires identity
resolution to happen first, producing a `CanonicalMedia`, before any
adapter is invoked.

These are not stylistically different — they imply a different pipeline
stage ordering, which affects how `03-resolution.md`'s pipeline is
implemented and what an adapter author can assume about its inputs.

## Problem

**Does V0.1 adapter selection happen before or after identity resolution?**
The frozen contract (Model A) implied "before." The rest of the
documented pipeline consistently implies "after." This is exactly the
kind of ambiguity that would let two competent implementers build
materially different systems while both believing they followed the
documentation.

## Observed evidence (repository-grounded, not preference)

1. `docs/architecture/03-resolution.md`, "Identity Layer in the Complete
   Pipeline" — the pipeline diagram shows `IDENTITY RESOLVER → RECONCILE →
   CanonicalMedia → SOURCE ROUTING → EXECUTION → CANDIDATES`. Source
   routing/execution happens strictly after `CanonicalMedia` exists.
2. `docs/architecture/03-resolution.md`, "Resulting Source-Selection
   Algorithm" — shows `Resolve identity → RESOLVED → CanonicalMedia →
   capability filter → identity filter → admission filter → health filter
   → circuit filter → bounded execution`. An explicit "identity filter"
   step operates on already-resolved identity, before execution.
3. `docs/architecture/03-resolution.md`, "Parallel vs sequential
   orchestration" — states directly: "For `/stream`, identity resolution
   usually precedes source resolution: `identity → CanonicalMedia →
   sources`."
4. `docs/architecture/13-roadmap.md`, "V0.1 implementation freeze" — the
   explicit V0.1 `CORE` scope list is `MediaRef, CanonicalMedia, Identity,
   SourceCandidate, ResolutionResult`. `CanonicalMedia` and `Identity` are
   **in scope for V0.1**, not deferred — so V0.1 does have identity
   resolution available before adapter execution.
5. `docs/architecture/04-providers.md`, the Model C section itself
   concludes: "Now source execution is based on resolved identity" — this
   is the document's own stated destination, not an aside.
6. No section anywhere states "keep adapters identity-agnostic for V0.1
   deliberately" or gives a scoping rationale for Model A being
   preferred. Model A is simply the earliest, chronologically first
   draft, predating the entire identity layer in the monolith's own
   narrative order.

No credible counter-evidence was found for keeping adapter selection
identity-agnostic in V0.1.

## Options considered

1. **Freeze Model A** (raw `MediaRef`, adapter selection before identity
   resolution). Rejected — contradicted by 3 independent passages in
   `03-resolution.md` and by `13-roadmap.md`'s explicit V0.1 scope.
2. **Freeze Model C** (identity/capability-aware, `resolve(CanonicalMedia,
   ...)`). Supported by all available evidence.
3. **Support both** (adapter chooses which it wants). Rejected — this
   reintroduces exactly the ambiguity this ADR exists to remove; a
   resolver cannot treat "some adapters take `MediaRef`, others take
   `CanonicalMedia`" uniformly without a second dispatch mechanism that
   is undocumented anywhere.

## Decision

**Adopt Model C, with one small, explicitly-flagged synthesis:** keep the
optional `health()` probe from Model A, since nothing in the evidence
suggests it was deliberately removed (Model C's absence of `health()` is
incidental — the passage introducing it was focused on demonstrating the
`supportsMedia`/`supportsIdentity` split, not on health). The frozen
`SourceAdapter` contract is now:

```ts
export interface SourceAdapter {
  readonly id: string;
  readonly name: string;
  readonly capabilities: SourceCapabilities;

  /** Cheap, synchronous, pre-identity filter (e.g. "I only handle movies"). */
  supportsMedia(media: MediaRef): boolean;

  /** Post-identity-resolution filter (e.g. "I require a TMDB id"). */
  supportsIdentity(identities: readonly ExternalIdentity[]): boolean;

  /** Only called once identity has been resolved. */
  resolve(
    media: CanonicalMedia,
    context: ResolveContext
  ): Promise<readonly SourceCandidate[]>;

  /** Optional liveness/capability probe, independent of any single request. */
  health?(): Promise<HealthResult>;
}
```

Adapter selection therefore happens **after** identity resolution in the
V0.1 pipeline: `identity resolution → CanonicalMedia → capability/identity
filter (adapter selection) → parallel resolve() → validate → dedupe →
policy filter → rank → protocol mapping`.

## Rejected alternatives

- Model A (see above) — superseded, not merged. It remains in
  `docs/architecture/04-providers.md`, annotated as historical, because it
  has real explanatory value (it's the simplest possible statement of
  "what is an adapter" before capabilities/identity are introduced) but
  must not be read as normative.
- The query-object-style draft (`SourceQuery { media: CanonicalMedia }`,
  `resolve(query, ctx)`) — superseded; it's a structural alternative to
  Model C that was abandoned in the monolith's own narrative before Model
  C was reached.

## Migration implications

- `SourceRegistry.applicable(media)` (see `ADR-003`) must be re-specified
  to filter in two stages: `applicable(media: MediaRef)` (pre-identity,
  using `supportsMedia`) and a second identity-aware filter (using
  `supportsIdentity`) applied once `CanonicalMedia` is available. This is
  **not yet a separate frozen method signature** — flagged as a follow-up
  needed before implementation (see `docs/decisions/README.md`, new item
  after this ADR).
- Any code that assumed `resolve(media: MediaRef, ...)` must be updated to
  `resolve(media: CanonicalMedia, ...)`. Since no implementation exists in
  this repository, there is no code to migrate — this is a pure
  documentation correction at this stage.
- `docs/architecture/03-resolution.md`'s pipeline description already
  matches this decision and required no change.

## Affected contracts

- `docs/contracts/source-adapter.md` — `SourceAdapter` interface updated.

## Status

ACCEPTED. `OPEN-8` is now `RESOLVED` (see `docs/decisions/README.md`).
