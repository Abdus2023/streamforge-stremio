# Contract: `SourceAdapter`

[⇧ Architecture index](../architecture.md) · [⇆ Document map](../architecture/README.md)

> **Normative.** This is the single authoritative definition of the adapter
> boundary. `docs/architecture/04-providers.md` explains *why* the contract
> is shaped this way, how adapters are registered/isolated/health-checked,
> and links back here instead of redefining these types. If any other
> document appears to define `SourceAdapter`, `ResolveContext`,
> `HealthResult`, or a provider registry differently, that is a
> documentation defect — this file wins, and the discrepancy should be
> filed as an `OPEN — architectural contradiction` note (see
> `docs/decisions/README.md`).
>
> **Status:** DESIGNED. No implementation of this interface exists in the
> repository as of this revision (no `src/` directory exists yet).
>
> **RESOLVED by `ADR-001` (2026-09-29), narrowed by `ADR-001`'s amendment
> (2026-09-29, second session).** This contract previously froze a
> minimal, `MediaRef`-based `SourceAdapter` shape as a placeholder pending
> resolution of `OPEN-8`. Repository evidence (`03-resolution.md`'s
> pipeline diagrams, `13-roadmap.md`'s explicit V0.1 scope) showed adapter
> selection happens *after* identity resolution in V0.1, not before. A
> follow-up normalization pass then narrowed the interface further,
> removing `name`, `capabilities`, and `health()` from the *core* contract
> (no V0.1 consumer required them on every adapter) — they remain as
> separate, optional extension interfaces. See
> [`ADR-001`](../decisions/ADR-001-source-adapter-identity-boundary.md)
> for the full evidence and rationale, including its amendment section.

## `SourceAdapter`

Adapters are selected **after** identity resolution: the resolver first
produces a `CanonicalMedia` (see `docs/contracts/identity.md`), then
filters adapters, then calls `resolve()` with that resolved identity —
never with a raw, identity-unresolved `MediaRef`.

```ts
export interface SourceAdapter {
  readonly id: string;

  /** Cheap, pre-identity filter — no I/O (e.g. "I only handle movies"). */
  supportsMedia(media: MediaRef): boolean;

  /** Post-identity-resolution filter (e.g. "I require a TMDB id"). */
  supportsIdentity(identities: readonly ExternalIdentity[]): boolean;

  /** Only ever called once identity has been resolved. */
  resolve(
    media: CanonicalMedia,
    context: ResolveContext
  ): Promise<readonly SourceCandidate[]>;
}
```

This is the entire required V0.1 surface. Nothing else is mandatory on an
adapter.

### Optional extension interfaces

These are **not part of the core `SourceAdapter` contract**. An adapter
MAY implement any subset of them; the runtime and registry MUST feature-
detect them (e.g. `if (typeof adapter.health === "function")`) and MUST
NOT assume any adapter implements them.

```ts
/** Optional — a human-readable label, e.g. for logs/diagnostics. */
export interface Named {
  readonly name: string;
}

/** Optional — liveness/capability probe, independent of any single request. */
export interface HealthCheckable {
  health(): Promise<HealthResult>;
}

/** Optional, PROPOSED — capability declaration for future routing; its
 *  exact field list is not yet frozen (see docs/architecture/04-providers.md,
 *  "Capability Routing"). Not required for V0.1. */
export interface CapabilityDeclaring {
  readonly capabilities: SourceCapabilities;
}
```

### Known variants (audit findings, historical)

The monolith contains five other `SourceAdapter` shapes that do **not**
match the frozen contract above. All are HISTORICAL / SUPERSEDED per
`ADR-001` — none is a live open question anymore:

| Variant (source location) | Difference from frozen shape | Classification |
|---|---|---|
| `04-providers.md` — first "Adapter contract" occurrence (`Model A`) | Raw `MediaRef`, single `supports()`, no capability declaration | HISTORICAL — superseded by `ADR-001` |
| `04-providers.md` — second occurrence | Same as Model A, no `health()` | HISTORICAL — superseded |
| `04-providers.md` — third occurrence | `id` only (no `name`); `supports(media: CanonicalMedia)`; `resolve(query: SourceQuery, ctx)` (query-object style) | HISTORICAL — a structurally different, abandoned draft, superseded |
| `04-providers.md` — fifth occurrence | Adds `readonly capabilities: SourceCapabilities` but keeps single `supports(MediaRef)` and `resolve(MediaRef, ...)` | HISTORICAL — an intermediate step toward the frozen shape, superseded |
| `04-providers.md` — sixth/last occurrence | Matches the frozen shape exactly, plus `readonly name`/`readonly capabilities` (now split into the optional `Named`/`CapabilityDeclaring` interfaces above) | **This is the frozen shape's primary source** — `health()`/`name`/`capabilities` were moved to optional extension interfaces per `ADR-001`'s amendment |

Invariants that bind every implementation of this interface (see
`docs/architecture/04-providers.md` and `docs/architecture/05-policy.md`
for the rationale behind each):

- `supportsMedia()` MUST NOT perform I/O — it is a cheap, synchronous,
  pre-identity filter.
- `supportsIdentity()` is only ever called once identity resolution has
  produced at least a candidate set of `ExternalIdentity` values for the
  request (see `docs/architecture/03-resolution.md`, "identity filter").
- `resolve()` MUST honor `ctx.signal` (abort) and `ctx.timeoutMs` — an
  adapter that ignores cancellation can stall the whole aggregation fan-out.
- `resolve()` MUST NOT throw for "no results" — an empty array is a valid,
  non-error outcome (see `docs/architecture/03-resolution.md`, "Empty result
  semantics").
- `resolve()` MUST NOT set `authorization.status = "authorized"` on a
  candidate unless the adapter holds real evidence; the default for
  unknown status is `"unknown"`, never a silently-upgraded `"authorized"`
  (see `docs/architecture/05-policy.md`).
- If an adapter implements `HealthCheckable`, `health()` reports
  *liveness*, not permission — a healthy adapter is not automatically an
  authorized one (see `docs/architecture/05-policy.md`, "Trusted vs
  untrusted providers").

- An adapter MUST NOT read ambient globals (env vars, filesystem, network
  config) directly; everything it needs arrives through `ResolveContext`
  or its own constructor-injected configuration (see
  `docs/architecture/06-runtime.md`, "Dependency injection").

## `ResolveContext`

```ts
export interface ResolveContext {
  readonly signal: AbortSignal;
  readonly timeoutMs: number;
  readonly preferredLanguages: readonly string[];
}
```

**Correction made during the 2026-09-29 audit pass.** This file previously
froze a different, single-occurrence draft of `ResolveContext`
(`signal`/`timeoutMs` non-`readonly`, plus optional `locale?` and
`userConfig?: Record<string, unknown>`) that appeared exactly once, in the
very first "Adapter contract" section of the monolith. Re-auditing every
`ResolveContext` occurrence found that **four separate, later sections**
(two in `04-providers.md`, two in `06-runtime.md`) independently converged
on the shape above — fully `readonly`, and `preferredLanguages` **required**
rather than optional, with no `locale`/`userConfig`. Convergence across
four independent later occurrences is stronger evidence of the intended
frozen shape than a single early draft, so this file now reflects the
converged shape. This is a recorded, evidence-based correction (see
`docs/decisions/README.md`, entry `RESOLVED-1`), not a silent guess.

`locale` and `userConfig` are **not lost** — they are tracked as
`OPEN-9` (see `docs/decisions/README.md`): a plausible future extension of
`ResolveContext` for per-request locale/user preference plumbing, proposed
but not frozen.

`ResolveContext` is constructed once per resolution request by the runtime
(see `docs/architecture/06-runtime.md`) and passed identically to every
applicable adapter in the parallel fan-out (see
`docs/architecture/03-resolution.md`).

## `HealthResult`

The monolith did not converge on a single frozen shape for `HealthResult`
before the doc-split; the field below reflects the clearest statement found
during migration. This is marked **PROPOSED**, not final — treat the field
list as a starting point, not a frozen contract, until a corresponding
conformance test exists (see `docs/architecture/11-testing.md`).

```ts
export interface HealthResult {
  readonly healthy: boolean;
  readonly checkedAt: string;
  readonly detail?: string;
}
```

> **RESOLVED by `ADR-004` (2026-09-29).** Two other "is this provider
> healthy" shapes exist and are legitimately distinct layers, not
> duplicates or competitors of `HealthResult`:
> `SourceHealthCounters` (`04-providers.md`, renamed from the former
> `SourceHealth`; runtime-internal rolling counters that feed the circuit
> breaker) and `SourceHealthSnapshot` (`10-observability.md`, renamed from
> a second, differently-shaped `SourceHealth`; a derived, exported metrics
> view). `HealthResult` is the adapter's own on-demand, point-in-time
> self-report. See
> [`ADR-004`](../decisions/ADR-004-health-model-layering.md) for the full
> layering rationale — do not reintroduce the name `SourceHealth` for
> either of the other two shapes.

## Provider / adapter registry

> **RESOLVED by `ADR-003` (2026-09-29) and `ADR-006` (2026-09-29, second
> session).** `SourceRegistry` (sources only) is the V0.1-frozen registry.
> The generalized `ProviderRegistry<T>` below is explicitly **PROPOSED /
> DEFERRED to V0.2+**, for when metadata, subtitle, or catalog providers
> are introduced (none exist in V0.1 scope — see
> `docs/architecture/13-roadmap.md`). Separately, `ADR-006` fixed the
> registry's own method signatures (they previously referenced a removed
> method) and drew an explicit boundary between the registry and
> admission. See
> [`ADR-003`](../decisions/ADR-003-provider-registry-ownership.md) and
> [`ADR-006`](../decisions/ADR-006-source-registry-admission-boundary.md).

### Semantic model

```
DECLARATION
     ↓
ADMISSION       (docs/architecture/05-policy.md: SourceDeclaration → evaluateAdmission() → AdmissionDecision)
     ↓
COMPOSITION     (only admitted adapters are ever constructed/registered)
     ↓
EXECUTION       (SourceRegistry, below)
```

`SourceRegistry` holds only adapters that have already been admitted —
admission itself is decided upstream, in the control plane
(`docs/architecture/05-policy.md`), before an adapter is ever constructed
or passed to `register()`. Explicitly:

```text
SourceRegistry ≠ Admission Authority
SourceRegistry ≠ Policy Engine
SourceRegistry ≠ Health Authority
SourceRegistry ≠ Provider Discovery System
```

### `SourceRegistry` (V0.1-frozen)

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

This replaces an earlier code sample whose single `applicable(media)`
method called a `supports()` method that no longer exists on
`SourceAdapter` after `ADR-001` — see `ADR-006` for the full history
(`OPEN-11`).

### `ProviderRegistry<T>` (deferred, V0.2+)

```ts
// Later, generalized shape (any provider kind: source, metadata, subtitle)
interface ProviderRegistry<T> {
  register(provider: T): void;
  all(): readonly T[];
  get(id: string): T | undefined;
}

// e.g. ProviderRegistry<SourceAdapter>, ProviderRegistry<MetadataProvider>,
// ProviderRegistry<SubtitleProvider>
```

Both registries share the same invariant: registration is **explicit and
static at composition time** (see `docs/architecture/06-runtime.md`,
"No global provider singleton" and "Dependency injection"). There is no
dynamic/arbitrary adapter registration via HTTP or any other externally
reachable interface — this is a standing security invariant, not just an
implementation detail (see `docs/architecture/05-policy.md`).

### Admission (not part of this contract, cross-referenced)

`docs/architecture/04-providers.md`'s "Registry redesign" section and
`docs/architecture/05-policy.md`'s `SourceDeclaration`/`AdmissionDecision`/
`evaluateAdmission()` describe the **admission process** — how the
composition root decides which declared sources are allowed to become
registered adapters. This is a real, load-bearing part of the
architecture, but it is not the `SourceRegistry` contract itself; see
`ADR-006` for why these are different layers, not competing registry
designs.

## Related contracts

- Candidate/stream shapes produced by `resolve()`: `docs/contracts/stream.md`
- Identity types passed in via `MediaRef`/`CanonicalMedia`: `docs/contracts/identity.md`
- Runtime primitives that construct `ResolveContext`: `docs/contracts/runtime.md`
- Evidence semantics for anything an adapter reports: `docs/contracts/evidence.md`
- Per-adapter execution evidence (`AdapterExecution`) and the final
  request-level outcome (`ResolutionResult`) that consumes `resolve()`'s
  output: `docs/contracts/result.md`
