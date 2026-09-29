# ADR-007: `ResolutionResult` is the final request-level outcome; `AdapterExecution` is per-adapter execution evidence

[⇧ Back to the decision ledger](./README.md)

- **Status:** ACCEPTED
- **Date:** 2026-09-29 (second session)
- **Resolves:** `OPEN-12` in `docs/decisions/README.md`
- **Affects:** `docs/contracts/result.md` (new), `docs/architecture/02-domain.md`, `docs/architecture/03-resolution.md`, `docs/architecture/04-providers.md`, `docs/architecture/06-runtime.md`, `docs/architecture/07-evidence.md`

## Context

`docs/architecture/13-roadmap.md`'s V0.1 CORE scope names `ResolutionResult`
but it was never given a home in `docs/contracts/`. Two non-identical
drafts existed:

1. `docs/architecture/02-domain.md`: `{ media: MediaRef, status:
   ResolutionStatus, candidates: readonly SourceCandidate[], failures:
   readonly Failure[], sourceCount: number, durationMs: number }`, with
   `ResolutionStatus = "success" | "empty" | "partial" | "failed"`.
2. `docs/architecture/03-resolution.md`: `{ media, executions: readonly
   Awaited<ReturnType<typeof executeAdapter>>[], candidates }` — i.e., the
   full per-adapter execution ledger embedded directly in the result.

Separately, `AdapterExecution` (per-adapter execution evidence) was
defined **three** times with diverging fields:

- `docs/architecture/04-providers.md`: `{ adapterId, status: AdapterStatus
  (4 values), durationMs, candidates, error?: string }`.
- `docs/architecture/06-runtime.md` (second occurrence, "Source execution
  status", line ~2139): identical fields, paired with a richer, 9-value
  `AdapterStatus` (adds `aborted`/`rate_limited`/`circuit_open`/
  `invalid_response`/`network_error` to the earlier 4-value set).
  `06-runtime.md` also has a **third**, standalone `AdapterStatus`
  definition earlier in the same file ("HTTP failure taxonomy", line
  ~1582) with **10** values — the same 9 plus an additional `http_error`
  — that is not paired with its own `AdapterExecution` interface.
  **Correction (re-checked during this pass): these two `06-runtime.md`
  occurrences are not identical**, as an earlier draft of this ADR stated;
  they differ by exactly the `http_error` value.
- `docs/architecture/07-evidence.md`: adds `startedAt`/`completedAt`
  (instead of just `durationMs`), and replaces `error?: string` with a
  typed `failure?: SourceFailure`; a fourth, 6-value `AdapterStatus`
  variant (`success`/`empty`/`timeout`/`rate_limited`/`invalid`/`error` —
  uses `invalid` instead of `invalid_response`, and omits
  `aborted`/`circuit_open`/`network_error`/`http_error`).

## Problem

1. What is `ResolutionResult`'s canonical shape?
2. Does it embed the full per-adapter execution ledger, or reference a
   separate, dedicated execution-evidence type?
3. What is `AdapterExecution`'s canonical shape and `AdapterStatus`'s
   canonical value set?

## Observed evidence

- `docs/architecture/02-domain.md`'s `ResolutionResult` is part of the same
  already-frozen domain module sequence as `MediaRef`/`SourceCandidate`/
  `Failure` (`Failure` — `{ code: FailureCode, sourceId?, message? }` —
  already exists there, unresolved by any prior ADR, and is exactly what a
  `failures: readonly Failure[]` field needs).
- `docs/architecture/03-resolution.md`'s draft embeds
  `Awaited<ReturnType<typeof executeAdapter>>[]` (i.e., `AdapterExecution[]`)
  directly. This conflates "what happened at the end of this request" with
  "what happened on every individual adapter call" — exactly the
  boundary this audit's operating principles require separating
  (`observed ≠ derived`, `execution ≠ result`).
- `AdapterExecution`'s `{adapterId, status, durationMs, candidates, error?:
  string}` shape (the fields, independent of the exact `AdapterStatus`
  value set) appears **twice**, independently, in `04-providers.md` and
  `06-runtime.md` — convergent, majority evidence (the same kind of
  evidence pattern already used to resolve `RESOLVED-1`). The
  `07-evidence.md` variant (timestamps instead of duration, typed
  `failure`) is the outlier field-wise.
- For `AdapterStatus`'s exact value set: three non-identical drafts exist
  (4 values in `04-providers.md`; 9 values in `06-runtime.md`'s "Source
  execution status", paired directly with the converged `AdapterExecution`
  fields; 10 values — the same 9 plus `http_error` — in `06-runtime.md`'s
  separate, standalone "HTTP failure taxonomy" section; 6 values, using
  different naming, in `07-evidence.md`). The 9-value set is chosen as
  canonical because it is the one actually co-located with the converged
  `AdapterExecution` shape in two of the three richer drafts' narrative
  position (it's the direct successor to `04-providers.md`'s 4-value set
  attached to the same interface). The 10-value "HTTP failure taxonomy"
  draft's extra `http_error` value is preserved as a **noted, historical
  candidate addition**, not silently dropped — see "Rejected alternatives."

## Decision

1. **`ResolutionResult` is the final, request-level outcome — not an
   execution ledger.** Canonical shape, taken verbatim from
   `docs/architecture/02-domain.md` (already the CORE-scope-consistent,
   majority-evidenced draft):

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

   `docs/architecture/03-resolution.md`'s draft (embedding the full
   `executions` ledger) is now HISTORICAL/SUPERSEDED — annotated in place,
   not deleted.

2. **`AdapterExecution` is separate, per-adapter execution evidence**, not
   part of `ResolutionResult`:

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

   `docs/architecture/04-providers.md`'s narrower 4-value `AdapterStatus`
   is HISTORICAL (an earlier, incomplete draft of the same converged
   field set). `docs/architecture/07-evidence.md`'s variant (timestamps,
   typed `failure`) is also HISTORICAL — recorded as a distinct,
   non-canonical alternative, not silently merged in, since it was not the
   majority/converged shape.

3. **Relationship:** `AdapterExecution[]` is the input the resolver
   consumes to compute `ResolutionResult.candidates`,
   `ResolutionResult.failures`, and `ResolutionResult.status` — it is
   process-level evidence, not part of the durable/returned outcome. A
   future evidence/receipt contract (see `docs/contracts/evidence.md`) may
   choose to persist `AdapterExecution[]` as part of a resolution receipt;
   that is a distinct concern from what `ResolutionResult` itself carries
   back to the caller.

## Rejected alternatives

- Embedding `executions: readonly AdapterExecution[]` inside
  `ResolutionResult` (the `03-resolution.md` draft) — rejected: this makes
  every caller of the resolver responsible for per-adapter execution
  detail it usually doesn't need, and blurs the `execution ≠ success`
  boundary (a `ResolutionResult.status` of `"success"` should be
  computable without inspecting individual adapter executions).
- Picking `07-evidence.md`'s `AdapterExecution` variant (timestamps +
  typed `failure`) — rejected: it is the least-repeated of the drafts; the
  two independently-converged occurrences in `04-providers.md` and
  `06-runtime.md` are stronger evidence of intended design.
- Including `http_error` in the canonical `AdapterStatus` — not adopted,
  but not discarded either: the 10-value "HTTP failure taxonomy" draft is
  a standalone list not paired with its own `AdapterExecution` interface,
  so it reads as an exploratory expansion rather than the converged shape.
  It is recorded here, not silently dropped, as a plausible V0.2+
  refinement (`http_error` could distinguish a 4xx/5xx HTTP-layer failure
  from the more generic `invalid_response`/`network_error`).

## Migration implications

- New file `docs/contracts/result.md` created, owning `ResolutionResult`,
  `ResolutionStatus`, `Failure`, `AdapterExecution`, `AdapterStatus`.
- `docs/architecture/02-domain.md`'s `ResolutionResult`/`Failure` section
  annotated as the canonical source, now mirrored in the contract file.
- `docs/architecture/03-resolution.md`'s embedded-ledger `ResolutionResult`
  draft annotated HISTORICAL/SUPERSEDED.
- `docs/architecture/04-providers.md`, `06-runtime.md`, `07-evidence.md`'s
  `AdapterExecution`/`AdapterStatus` occurrences annotated per the
  canonical/historical split above.
- No implementation exists to migrate.

## Affected contracts

- `docs/contracts/result.md` (new).

## Status

ACCEPTED. `OPEN-12` is now `RESOLVED` (see `docs/decisions/README.md`).
