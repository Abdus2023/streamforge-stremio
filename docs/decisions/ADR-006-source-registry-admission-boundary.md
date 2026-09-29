# ADR-006: `SourceRegistry` is an executable-adapter collection; admission is a separate, upstream control-plane concern

[⇧ Back to the decision ledger](./README.md)

- **Status:** ACCEPTED
- **Date:** 2026-09-29 (second session)
- **Resolves:** `OPEN-11`, `OPEN-13` in `docs/decisions/README.md`
- **Affects:** `docs/contracts/source-adapter.md`, `docs/architecture/04-providers.md`, `docs/architecture/05-policy.md`

## Context

Two materially different things were both called `SourceRegistry`:

1. **The simple, frozen registry** (`docs/contracts/source-adapter.md`):
   `register(adapter: SourceAdapter): void`, `all()`,
   `applicable(media: MediaRef)` — a thin wrapper around a
   `Map<string, SourceAdapter>`, holding only already-constructed
   `SourceAdapter` instances.
2. **An admission-lifecycle-integrated registry**
   (`docs/architecture/04-providers.md`, "Registry redesign" section):
   registers `RegisteredSource { declaration: SourceDeclaration; admission:
   AdmissionDecision; adapter?: SourceAdapter }` objects, and exposes
   `all(): RegisteredSource[]` plus `executable(): SourceAdapter[]`
   (filtered by `admission.status === "admitted"`), driven by a documented
   `DECLARED → VALIDATED → ADMISSION_EVALUATED → ADMITTED → REGISTERED →
   HEALTH_MONITORED → EXECUTABLE` lifecycle and a real, cross-referenced
   `evaluateAdmission(declaration: SourceDeclaration): AdmissionDecision`
   function in `docs/architecture/05-policy.md`.

This was recorded as `OPEN-13` (a genuine, unreconciled contradiction) in
the previous pass, plus a smaller mechanical gap, `OPEN-11` (the frozen
registry's own sample code called a method, `supports()`, that no longer
exists on `SourceAdapter` after `ADR-001`).

## Problem

Is `SourceRegistry` responsible for admission (deciding whether a source
is allowed to run), or only for holding and querying sources that have
already been admitted by something else?

## Observed evidence

- `docs/architecture/05-policy.md` independently defines
  `SourceDeclaration`, `AdmissionDecision`, and `evaluateAdmission()` — a
  complete, self-contained admission model that does not itself reference
  or require a specific registry shape.
- `docs/contracts/source-adapter.md`'s existing invariant text (unchanged
  since the original split) already states: "registration is explicit and
  static at composition time... there is no dynamic/arbitrary adapter
  registration via HTTP or any other externally reachable interface." This
  describes composition-time wiring, which is naturally where an admission
  decision would already have been made — by the time something is handed
  to `register()`, it is assumed trustworthy.
- The admission lifecycle diagram's own terminal states are `EXECUTABLE`
  (success path) and `disabled`/`expired`/`revoked` (exit paths) — i.e.,
  the lifecycle's output is exactly "is this adapter allowed to run," which
  is a yes/no gate a caller can evaluate once and then hand a plain
  `SourceAdapter` onward.

## Decision

**`SourceRegistry` is the V0.1-frozen registry of already-admitted,
executable adapters. It is not the admission authority.**

```
DECLARATION
     ↓
ADMISSION       (docs/architecture/05-policy.md: SourceDeclaration → evaluateAdmission() → AdmissionDecision)
     ↓
COMPOSITION     (only admitted adapters are ever constructed/registered)
     ↓
EXECUTION       (SourceRegistry: register/all/applicableByMedia/applicableByIdentity)
```

Canonical V0.1 `SourceRegistry`:

```ts
export interface SourceRegistry {
  register(adapter: SourceAdapter): void;

  all(): readonly SourceAdapter[];

  /** Pre-identity-resolution filter, using SourceAdapter.supportsMedia(). */
  applicableByMedia(media: MediaRef): readonly SourceAdapter[];

  /** Post-identity-resolution filter, using SourceAdapter.supportsIdentity(). */
  applicableByIdentity(
    identities: readonly ExternalIdentity[]
  ): readonly SourceAdapter[];
}
```

This resolves `OPEN-11` (the old `applicable(media)` calling the removed
`supports()` method is replaced by two explicitly-named, `ADR-001`-aligned
methods) and `OPEN-13` (interpretation 3 from the `OPEN-13` ledger entry is
adopted: admission and registration are different points in the same
pipeline, not competing designs of the same registry).

**Explicit non-responsibilities**, stated so no implementer assumes
otherwise:

```
SourceRegistry ≠ Admission Authority   (that's 05-policy.md's evaluateAdmission())
SourceRegistry ≠ Policy Engine         (authorization/admission policy lives in 05-policy.md)
SourceRegistry ≠ Health Authority      (health lives in SourceHealthCounters/SourceHealthSnapshot, ADR-004)
SourceRegistry ≠ Provider Discovery System (no dynamic registration; composition-time only)
```

**If an adapter is not admitted, it must never reach `register()`.** The
admission-lifecycle machinery in `04-providers.md`'s "Registry redesign"
section describes *how* the composition root decides which adapters to
construct and register — it is not itself the `SourceRegistry` contract,
and is re-labeled accordingly (see "Affected documents" below). The
`RegisteredSource`/`executable()` shape is retained as HISTORICAL/
explanatory material illustrating the admission process, not as a
competing frozen registry contract.

## Rejected alternatives

- **Making `SourceRegistry` itself admission-aware** (storing
  `RegisteredSource` records with lifecycle state) — rejected: this would
  conflate registry (a lookup/query structure) with admission (a policy
  decision) and health (a runtime-state concept), directly violating the
  semantic-boundary principle (`admission ≠ execution ≠ registry`) that
  this whole audit is built around.
- **Deleting the admission-lifecycle material as wrong** — rejected: it is
  not wrong, it was simply never connected to the registry contract. It
  remains valuable as the control-plane admission design and is
  re-labeled, not discarded.

## Migration implications

- `docs/contracts/source-adapter.md`'s `SourceRegistry` code sample is
  updated to the two-method-filter shape above.
- `docs/architecture/04-providers.md`'s "Registry redesign" section gets
  an explicit note: this section describes the **admission process**, not
  the `SourceRegistry` contract; the canonical `SourceRegistry` is in
  `docs/contracts/source-adapter.md`.
- No implementation exists to migrate.

## Affected contracts

- `docs/contracts/source-adapter.md` — `SourceRegistry` interface replaced
  with the two-stage-filter shape; explicit non-responsibilities added.

## Affected documents

- `docs/architecture/04-providers.md` — "Registry redesign" section
  annotated as historical/admission-process material, not a competing
  registry contract.
- `docs/architecture/05-policy.md` — cross-referenced as the true home of
  `SourceDeclaration`/`AdmissionDecision`/`evaluateAdmission()`.

## Status

ACCEPTED. `OPEN-11` and `OPEN-13` are now `RESOLVED` (see
`docs/decisions/README.md`).
