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

## `SourceAdapter`

The adapter interface is intentionally the smallest possible surface that
lets a new source be added without modifying the resolver core.

```ts
export interface SourceAdapter {
  readonly id: string;
  readonly name: string;

  /** Cheap, synchronous applicability check — no I/O. */
  supports(media: MediaRef): boolean;

  /** Produce zero or more candidates for a media reference. */
  resolve(
    media: MediaRef,
    ctx: ResolveContext
  ): Promise<readonly SourceCandidate[]>;

  /** Optional liveness/capability probe, independent of any single request. */
  health?(): Promise<HealthResult>;
}
```

Invariants that bind every implementation of this interface (see
`docs/architecture/04-providers.md` and `docs/architecture/05-policy.md`
for the rationale behind each):

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

  readonly locale?: string;
  readonly preferredLanguages?: readonly string[];
  readonly userConfig?: Record<string, unknown>;
}
```

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

> **OPEN — architectural contradiction candidate.** Later sections of the
> original monolith (control-plane era) introduce a richer, per-provider
> health/circuit-breaker state (see `docs/architecture/06-runtime.md`,
> "Health state machine") that is not reconciled field-by-field with this
> minimal `HealthResult`. Both describe "is this provider currently good to
> call" but were written at different points in the design's evolution.
> They have not been merged into one type. Do not treat them as
> interchangeable until an ADR resolves the shape.

## Provider / adapter registry

Two shapes appear across the design's evolution:

```ts
// Early, single-purpose shape (sources only)
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

## Related contracts

- Candidate/stream shapes produced by `resolve()`: `docs/contracts/stream.md`
- Identity types passed in via `MediaRef`: `docs/contracts/identity.md`
- Runtime primitives that construct `ResolveContext`: `docs/contracts/runtime.md`
- Evidence semantics for anything an adapter reports: `docs/contracts/evidence.md`
