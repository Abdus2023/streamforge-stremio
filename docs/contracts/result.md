# Contract: `ResolutionResult` / `AdapterExecution`

[⇧ Architecture index](../architecture.md) · [⇆ Document map](../architecture/README.md)

> **Normative.** The single authoritative definition of the final
> request-level resolution outcome (`ResolutionResult`, `ResolutionStatus`,
> `Failure`) and of per-adapter execution evidence (`AdapterExecution`,
> `AdapterStatus`). `docs/architecture/02-domain.md`,
> `docs/architecture/03-resolution.md`, `docs/architecture/04-providers.md`,
> and `docs/architecture/06-runtime.md` explain *why* these shapes exist
> and the algorithm that produces them; they link here instead of
> redefining the types. If any other document appears to define these
> types differently, that is a documentation defect — this file wins.
>
> **Status:** DESIGNED. No implementation exists in the repository as of
> this revision (no `src/` directory exists yet).
>
> **New file, created by `ADR-007` (2026-09-29, second session).**
> `ResolutionResult` was named in `docs/architecture/13-roadmap.md`'s V0.1
> CORE scope but had no canonical contract-file home; two non-identical
> drafts existed. See
> [`ADR-007`](../decisions/ADR-007-resolution-result-outcome-boundary.md)
> for the full evidence and rationale.

## Semantic boundary

```
ResolutionResult   =  final, request-level outcome returned to the caller
AdapterExecution[] =  per-adapter execution-level evidence, consumed by
                       the resolver to compute ResolutionResult, not
                       returned to the caller as part of it
```

`ResolutionResult` is not an execution ledger. A caller reading
`ResolutionResult.status` should never need to inspect individual adapter
executions to understand "did this request succeed."

## `ResolutionResult`

```ts
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

- `status` is derived, not independently settable: `"success"` when
  `candidates.length > 0` and no failures affected the outcome;
  `"partial"` when some candidates were produced but at least one adapter
  failed; `"empty"` when no candidates were produced and no adapter
  failed (e.g. all adapters legitimately returned nothing); `"failed"`
  when no candidates were produced and at least one adapter failed. This
  mirrors the tri/quad-state discipline used elsewhere in this
  documentation set (see `docs/architecture/03-resolution.md`, "Empty
  result semantics").
- `sourceCount` is the number of adapters that were selected (post
  `supportsMedia`/`supportsIdentity` filtering, see
  `docs/contracts/source-adapter.md`) for this request, regardless of
  outcome — it is not the number of adapters that returned candidates.

## `Failure`

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

`code` MUST be treated as the stable, machine-readable identity of a
failure; `message` is diagnostic only and MUST NOT be pattern-matched on
by any consumer.

## `AdapterExecution`

Per-adapter execution evidence — the input the resolver consumes to
compute `ResolutionResult`, not part of the result itself.

```ts
export type AdapterStatus =
  | "success"
  | "empty"
  | "timeout"
  | "aborted"
  | "rate_limited"
  | "circuit_open"
  | "invalid_response"
  | "network_error"
  | "error";

export interface AdapterExecution {
  readonly adapterId: string;

  readonly status: AdapterStatus;

  readonly durationMs: number;

  readonly candidates: readonly SourceCandidate[];

  readonly error?: string;
}
```

### Known variants (audit findings, historical)

| Variant (source location) | Difference from frozen shape | Classification |
|---|---|---|
| `docs/architecture/02-domain.md` `ResolutionResult` | Matches the frozen shape exactly | **Canonical source** — mirrored here verbatim |
| `docs/architecture/03-resolution.md` `ResolutionResult` | Embeds `executions: readonly AdapterExecution[]` directly instead of `status`/`failures`/`sourceCount`/`durationMs` | HISTORICAL — superseded, see `ADR-007` (conflated execution ledger with final outcome) |
| `docs/architecture/04-providers.md` `AdapterExecution`/`AdapterStatus` | Matches frozen `AdapterExecution` fields; `AdapterStatus` has only 4 values (`success`\|`empty`\|`timeout`\|`error`) | HISTORICAL — an earlier, narrower draft of the converged shape |
| `docs/architecture/06-runtime.md` `AdapterExecution`/`AdapterStatus` ("Source execution status") | Matches the frozen shape exactly, including the 9-value `AdapterStatus` | **Canonical source** — mirrored here verbatim |
| `docs/architecture/06-runtime.md` `AdapterStatus` ("HTTP failure taxonomy", standalone, not paired with its own `AdapterExecution`) | Same 9 values plus an additional `http_error` (10 values total) | HISTORICAL — a plausible V0.2+ refinement, not adopted since it is not paired with the converged `AdapterExecution` shape; recorded, not discarded (see `ADR-007`) |
| `docs/architecture/07-evidence.md` `AdapterExecution` | Uses `startedAt`/`completedAt` instead of `durationMs`; `failure?: SourceFailure` (typed) instead of `error?: string`; a 6-value `AdapterStatus` using `invalid` instead of `invalid_response` | HISTORICAL — a distinct, non-converged alternative; not merged in since it wasn't the majority/repeated shape. May be revisited if a future receipt contract needs typed failures and timestamps instead of a duration and a string. |

## Binding invariants

- `ResolutionResult.candidates` and `AdapterExecution.candidates` (across
  all executions for a request) share the same deduplication/ranking
  invariants as `docs/contracts/stream.md`'s `SourceCandidate[]` — this
  file does not restate them.
- `AdapterExecution.error` is diagnostic only, mirroring `Failure.message`
  — never pattern-matched on for control flow; `AdapterExecution.status`
  is the machine-readable field.
- A `ResolutionResult` with `status: "failed"` or `"partial"` MUST still
  carry every legitimately authorized candidate that was produced —
  partial failure never discards valid, already-produced results (see
  `docs/architecture/03-resolution.md`, "Failure-preserving" and
  `README.md`, "Failure-preserving").

## Related contracts

- Candidates referenced by both types: `docs/contracts/stream.md`
- The adapter whose `resolve()` call produces the candidates an
  `AdapterExecution` records: `docs/contracts/source-adapter.md`
- Identity resolved before any adapter execution begins:
  `docs/contracts/identity.md`
