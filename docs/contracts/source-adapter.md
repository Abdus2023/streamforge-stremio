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
> **RESOLVED by `ADR-001` (2026-09-29).** This contract previously froze a
> minimal, `MediaRef`-based `SourceAdapter` shape as a placeholder pending
> resolution of `OPEN-8`. Repository evidence (`03-resolution.md`'s
> pipeline diagrams, `13-roadmap.md`'s explicit V0.1 scope) showed adapter
> selection happens *after* identity resolution in V0.1, not before. The
> shape below reflects that decision — see
> [`ADR-001`](../decisions/ADR-001-source-adapter-identity-boundary.md)
> for the full evidence and rationale.

## `SourceAdapter`

Adapters are selected **after** identity resolution: the resolver first
produces a `CanonicalMedia` (see `docs/contracts/identity.md`), then
filters adapters, then calls `resolve()` with that resolved identity —
never with a raw, identity-unresolved `MediaRef`.

```ts
export interface SourceAdapter {
  readonly id: string;
  readonly name: string;
  readonly capabilities: SourceCapabilities;

  /** Cheap, pre-identity filter — no I/O (e.g. "I only handle movies"). */
  supportsMedia(media: MediaRef): boolean;

  /** Post-identity-resolution filter (e.g. "I require a TMDB id"). */
  supportsIdentity(identities: readonly ExternalIdentity[]): boolean;

  /** Only ever called once identity has been resolved. */
  resolve(
    media: CanonicalMedia,
    context: ResolveContext
  ): Promise<readonly SourceCandidate[]>;

  /** Optional liveness/capability probe, independent of any single request. */
  health?(): Promise<HealthResult>;
}
```

`SourceCapabilities` is a per-adapter declaration used for routing (see
`docs/architecture/04-providers.md`, "Capability Routing"); its exact
field list is PROPOSED, not yet frozen — treat it as an extension point,
not a closed contract.

### Known variants (audit findings, historical)

The monolith contains five other `SourceAdapter` shapes that do **not**
match the frozen contract above. All are HISTORICAL / SUPERSEDED per
`ADR-001` — none is a live open question anymore:

| Variant (source location) | Difference from frozen shape | Classification |
|---|---|---|
| `04-providers.md` — first "Adapter contract" occurrence (`Model A`) | Raw `MediaRef`, single `supports()`, no `capabilities` | HISTORICAL — superseded by `ADR-001` |
| `04-providers.md` — second occurrence | Same as Model A, no `health()` | HISTORICAL — superseded |
| `04-providers.md` — third occurrence | `id` only (no `name`); `supports(media: CanonicalMedia)`; `resolve(query: SourceQuery, ctx)` (query-object style) | HISTORICAL — a structurally different, abandoned draft, superseded |
| `04-providers.md` — fifth occurrence | Adds `readonly capabilities: SourceCapabilities` but keeps single `supports(MediaRef)` and `resolve(MediaRef, ...)` | HISTORICAL — an intermediate step toward the frozen shape, superseded |
| `04-providers.md` — sixth/last occurrence | Matches the frozen shape exactly except omitting `health()` | **This is the frozen shape's primary source** — `health()` was added back in per `ADR-001`'s synthesis rationale |

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
- `health()` reports *liveness*, not permission — a healthy adapter is not
  automatically an authorized one (see `docs/architecture/05-policy.md`,
  "Trusted vs untrusted providers").

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

> **RESOLVED by `ADR-003` (2026-09-29).** `SourceRegistry` (sources only)
> is the V0.1-frozen registry. The generalized `ProviderRegistry<T>` below
> is explicitly **PROPOSED / DEFERRED to V0.2+**, for when metadata,
> subtitle, or catalog providers are introduced (none exist in V0.1 scope
> — see `docs/architecture/13-roadmap.md`). See
> [`ADR-003`](../decisions/ADR-003-provider-registry-ownership.md).

Two shapes appear across the design's evolution:

> **OPEN-11 — follow-up from `ADR-001`, non-blocking for freeze, blocking
> for implementation.** The `SourceRegistry.applicable()` method below
> still calls `adapter.supports(media)`, a method that no longer exists on
> the frozen `SourceAdapter` (replaced by `supportsMedia`/
> `supportsIdentity` per `ADR-001`). This code sample was not rewritten to
> avoid inventing an unreviewed two-stage filtering method signature. An
> implementer MUST NOT copy this method verbatim — a corresponding
> `ADR-006` (or a straightforward two-method split, e.g.
> `applicableByMedia(media: MediaRef)` and
> `applicableByIdentity(identities: readonly ExternalIdentity[])`) is
> needed before `SourceRegistry` can be implemented. See
> `docs/decisions/README.md`.

```ts
// Early, single-purpose shape (sources only) — see OPEN-11 above
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

> **OPEN-13 — newly discovered, BLOCKING, not resolved this pass.**
> `docs/architecture/04-providers.md`'s "Registry redesign" section
> defines a materially different, admission-lifecycle-integrated
> `SourceRegistry` that stores `RegisteredSource { declaration:
> SourceDeclaration; admission: AdmissionDecision; adapter?: SourceAdapter
> }` and exposes `executable(): SourceAdapter[]`, driven by
> `docs/architecture/05-policy.md`'s `evaluateAdmission()`. This was not
> reconciled with the simpler `register(adapter)/all()/applicable(media)`
> shape frozen above. Do not assume the two are the same registry, and do
> not assume one supersedes the other — an implementer must not guess
> whether admission-lifecycle state belongs inside `SourceRegistry` or one
> layer upstream of it. See `OPEN-13` in `docs/decisions/README.md`.

## Related contracts

- Candidate/stream shapes produced by `resolve()`: `docs/contracts/stream.md`
- Identity types passed in via `MediaRef`: `docs/contracts/identity.md`
- Runtime primitives that construct `ResolveContext`: `docs/contracts/runtime.md`
- Evidence semantics for anything an adapter reports: `docs/contracts/evidence.md`
