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
> **Provenance of this shape (added during the 2026-09-29 audit pass).**
> The original monolith stated at least **6 non-identical** `SourceAdapter`
> shapes across its evolution (see "Known variants" below). The shape below
> is a **reconciled synthesis**, not a verbatim quote of any single
> section: it keeps `readonly id`/`readonly name` and
> `Promise<readonly SourceCandidate[]>` because those converged across the
> later majority of occurrences, and it keeps the optional `health()` probe
> because it is the only field that gives the runtime a way to implement
> the health/circuit-breaker model described in `06-runtime.md`. This
> reconciliation is itself a decision, not a neutral extraction — it is
> recorded as such rather than presented as if it were always frozen.

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

### Known variants (audit findings, not part of the frozen shape)

The monolith contains five other `SourceAdapter` shapes that do **not**
match the frozen contract above. None of them is silently discarded —
they are classified here so implementers know which ones are dead ends
and which one is a live open question:

| Variant (source location) | Difference from frozen shape | Classification |
|---|---|---|
| `04-providers.md` — first "Adapter contract" occurrence | No `health()` | HISTORICAL — superseded, informational only |
| `04-providers.md` — second occurrence | No `health()`, otherwise identical to frozen shape | HISTORICAL — superseded |
| `04-providers.md` — third occurrence | `id` only (no `name`); `supports(media: CanonicalMedia)` not `MediaRef`; `resolve(query: SourceQuery, ctx)` not `resolve(media, ctx)` | HISTORICAL — a structurally different draft (query-object style), superseded |
| `04-providers.md` — fifth occurrence | Adds `readonly capabilities: SourceCapabilities` | **OPEN — see decisions/README.md (OPEN-8)**: capability declaration may belong on the frozen contract |
| `04-providers.md` — sixth/last occurrence | Splits `supports` into `supportsMedia(media)` / `supportsIdentity(identities)`; `resolve(media: CanonicalMedia, context)` operates on a **resolved identity**, not a raw `MediaRef` | **OPEN — see decisions/README.md (OPEN-8)**: this is the most-evolved shape in the monolith and was never reconciled with the frozen one |

`OPEN-8` is the single most consequential open question in this contract:
whether v0.1 ships the minimal `MediaRef`-based adapter above, or the
later identity-aware/capability-aware shape. This must be resolved with
an ADR before implementation starts, not inferred from "whichever occurs
last in the document."

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

> **OPEN-1 — architectural contradiction, see `docs/decisions/README.md`.**
> Two other, materially different "is this provider healthy" shapes exist
> and are not reconciled with `HealthResult`:
> `interface SourceHealth { successes; failures; timeouts; latencyMs }`
> (`04-providers.md`, adapter-local counters) and a richer
> `interface SourceHealth { adapterId; requests; successes; empty;
> failures; timeoutCount; consecutiveFailures; latency: {p50,p95,p99} }`
> (`10-observability.md`, an operational metrics snapshot). All three
> could be the same concept at different layers (point-in-time probe vs.
> running counters vs. exported metrics), or two of them could be
> accidental duplicates. Do not treat them as interchangeable until an ADR
> resolves the shape and the relationship between them.

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
