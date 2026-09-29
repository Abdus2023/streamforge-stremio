# Documentation Audit — Implementation Pass Verification (2026-09-29)

[⇧ Architecture index](../architecture.md) · [⇆ Document map](./README.md)

> **What this file is.** A point-in-time audit artifact produced by a deep
> repository-level verification pass over the documentation set. It is not
> itself architecture — it is evidence for the claims made in
> `docs/architecture.md` and `docs/decisions/README.md`. It may go stale;
> re-run the checks described here (see "How this was produced") before
> trusting it after further edits.
>
> **This revision (implementation pass, 2026-09-29):**
> wrote `ADR-006` and `ADR-007`, amended `ADR-001`, and created
> `docs/contracts/result.md`, resolving the three items that blocked
> freeze at the end of the second pass — `OPEN-11`, `OPEN-12`, and
> `OPEN-13`. Also performed a dedicated receipt-family field audit
> (previously an explicitly out-of-scope gap) and recorded one new,
> **non-blocking** item, `OPEN-14`. The contract freeze remains intact. A first executable V0.1 core slice now exists under `src/`, with conformance tests under `test/`. Remaining open items (`OPEN-9`, `OPEN-10`, `OPEN-14`) are unchanged and non-blocking for the implemented core slice. See
> `docs/decisions/README.md` for the full, current ledger — it is the source of truth; this file summarizes it.
>
> **Current implementation evidence:** HEAD `7b48b29cc601ff6d1b08dd62db6d671d2d7b0de0` contains `src/`, `test/`, `tsconfig.json`, and TypeScript tooling in `package.json`. Tests and typecheck have not been executed by CI; therefore implementation is present but runtime/build verification remains unverified.
>
> **Scope limitation, stated up front, carried over unchanged from prior
> passes.** This repository declares ~150 distinct named interfaces/types
> across `docs/architecture/*.md`. This audit performed a **full
> field-level diff** on the concepts explicitly named as contract-owned in
> the task that requested it (`SourceAdapter`, `SourceRegistry`,
> `ProviderRegistry`, `ResolutionResult`, `AdapterExecution`,
> `ResolveContext`, `CanonicalMedia`, `ExternalIdentity`,
> `IdentityEvidence`, `IdentityResolution`, `IdentityReceipt`,
> `ReceiptEnvelope`, `EvidenceRecord`, `MetadataReceipt`,
> `SourceExecutionReceipt`, `SubtitleCandidate`, `HealthResult`,
> `SourceHealth`, `CircuitBreaker`) plus everything named in the prior
> `OPEN` items. For the remaining interfaces, this audit relies on the
> structural inventory from the second pass (§4 below, carried forward) —
> it was not re-verified field-by-field this pass unless the item is
> explicitly listed as newly checked.

---

## 1. Repository baseline (re-verified 2026-09-29, third pass)

| Fact | Value | Evidence |
|---|---|---|
| Branch | `arena/01a0e9bd-streamforge-stremio` | `git branch --show-current` |
| HEAD (at start of this pass's roadmap/audit commit) | `a777eb9` | `git rev-parse HEAD` |
| Base branch | `main` | `git fetch origin main` |
| Ahead/behind `main` | 35 ahead / 0 behind (before this commit lands) | `git rev-list --left-right --count origin/main...HEAD` |
| `src/`, `test/`, `tests/` | absent | `find` |
| `.github/workflows/` | absent | `find` |
| `tsconfig.json`, `Dockerfile`, `compose.*` | absent | `find` |
| `package.json` scripts | none defined | `cat package.json` |
| `package.json` dependencies | none defined | `cat package.json` |

**Conclusion (unchanged):** every implementation-shaped claim anywhere in
this repository's documentation must be `DESIGNED` or `PROPOSED`, never
`IMPLEMENTED`, `EXECUTED`, or `VERIFIED`. Nothing in this pass changed
that conclusion — no `src/`, tests, or CI were added.

---

## 2. Contract status matrix

| Contract file | Owned concepts | Internally consistent? | Blocking `OPEN` items | Contract status |
|---|---|---|---|---|
| `contracts/source-adapter.md` | `SourceAdapter` (minimal V0.1 core: `id`, `supportsMedia`, `supportsIdentity`, `resolve`), optional `Named`/`HealthCheckable`/`CapabilityDeclaring` extensions, `ResolveContext`, `HealthResult`, `SourceHealthCounters`/`SourceHealthSnapshot`, `SourceRegistry` | Yes. `SourceAdapter` narrowed and frozen (`ADR-001`, amended this pass); `ResolveContext` converged; health layering resolved (`ADR-004`); registry shape and admission boundary resolved (`ADR-006`) | none blocking; `OPEN-9` (low severity, additive, non-blocking) | **FROZEN** |
| `contracts/identity.md` | `MediaRef`, `ExternalIdentity`, `CanonicalMedia` | Yes, after superseding 3 `MediaRef` and 3 `CanonicalMedia` drafts; confidence ownership resolved (`ADR-002`) | `OPEN-10` (low severity, non-blocking — `IdentityResolution` vs. `IdentityReceipt.outcome` state-count mismatch) | **FROZEN** |
| `contracts/result.md` | `ResolutionResult`, `ResolutionStatus`, `Failure`, `AdapterExecution`, `AdapterStatus` | Yes. New this pass — resolves the `ResolutionResult`/`AdapterExecution` conflation and the non-identical-drafts problem (`ADR-007`) | none blocking | **FROZEN** |
| `contracts/stream.md` | `SourceCandidate`, `Stream`, subtitle candidates (deferred) | `SourceCandidate`/`Stream` consistent after superseding 1 draft; subtitles formally deferred (`ADR-005`); `ResolutionResult` moved out to `contracts/result.md` (no longer owned here) | none blocking for the concepts still owned here | **FROZEN** for `SourceCandidate`/`Stream`; subtitle scope intentionally deferred, not frozen |
| `contracts/runtime.md` | `RuntimeSnapshot`, `ConfigurationTransaction`, `RuntimePolicy` | Yes — the only occurrence of each in `09-control-plane.md` matches this file exactly | none | **FROZEN** |
| `contracts/evidence.md` | 4 evidence levels, receipt/evidence-graph shape, `IdentityObservation` (extended, `ADR-002`) | The 4 levels are consistent everywhere named; receipt family layering confirmed this pass (`EvidenceRecord<T>` → domain receipts → `ReceiptEnvelope`, three legitimate layers, not duplicates) | `OPEN-14` (receipt field-naming + `ReceiptEnvelope` composition gap — low severity, does not affect any V0.1 CORE contract) | **FROZEN** for the 4 evidence levels; receipt portion explicitly **NOT_FROZEN**, documented as such in the contract file itself |

**Five of six contract files now qualify for `CONTRACT_FREEZE`** per the
14-point checklist below. `contracts/evidence.md`'s receipt portion
remains the sole `NOT_FROZEN` area, and it is explicitly out of V0.1
CORE/RUNTIME/PROVIDER scope (`13-roadmap.md` lists "receipts" under
`EVIDENCE` scope, not `CORE`) — see the Freeze Gate discipline in
`docs/architecture.md` for how a partial, explicitly-scoped gap is
handled without silently broadening or narrowing V0.1.

---

## 3. Concept ownership matrix — contract-owned concepts (fully diffed)

| Concept | Canonical owner | Other occurrences | Conflict? | Action taken this pass | Status |
|---|---|---|---|---|---|
| `SourceAdapter` | `contracts/source-adapter.md` | `04-providers.md` (historical drafts, already annotated) | Resolved | `ADR-001` amended: narrowed the required surface to `{id, supportsMedia, supportsIdentity, resolve}`; `name`/`capabilities`/`health()` demoted to optional extension interfaces (`Named`, `CapabilityDeclaring`, `HealthCheckable`) | `RESOLVED` by `ADR-001` (amended) |
| `SourceRegistry` / `ProviderRegistry<T>` | `contracts/source-adapter.md` | `04-providers.md` ("Registry redesign" section, now annotated as admission-process material, not a competing registry) | Resolved | New `ADR-006`: registry is `{register, all, applicableByMedia, applicableByIdentity}`; admission (`SourceDeclaration`/`AdmissionDecision`) confirmed as a separate, upstream, control-plane concern the registry never performs | `RESOLVED` by `ADR-006` |
| `ResolutionResult` | `contracts/result.md` (new) | `02-domain.md` (canonical source, cross-referenced), `03-resolution.md` (historical draft, annotated) | Resolved | New `ADR-007`: adopted `02-domain.md`'s richer shape (`{media, status, candidates, failures, sourceCount, durationMs}`) as canonical; `03-resolution.md`'s embedded-execution-ledger draft marked historical | `RESOLVED` by `ADR-007` |
| `AdapterExecution` / `AdapterStatus` | `contracts/result.md` (new) | `04-providers.md`, `06-runtime.md` ×2, `07-evidence.md` — all now annotated | Resolved, with a correction | New `ADR-007` adopts the converged 9-value `AdapterStatus` (paired with `AdapterExecution`, `06-runtime.md` "Source execution status") as canonical. **Correction made this pass:** the two `06-runtime.md` occurrences were previously assumed identical; a field-by-field re-check found they differ (a separate, standalone 10-value "HTTP failure taxonomy" draft exists with an extra `http_error` value) — this is recorded accurately in `ADR-007` and `contracts/result.md`'s "Known variants" table, and the 10-value draft is preserved as a noted future-refinement candidate, not silently dropped | `RESOLVED` by `ADR-007` |
| `ResolveContext` | `contracts/source-adapter.md` | `04-providers.md`, `06-runtime.md` | No | Unchanged this pass — remains the converged, minimal shape (`preferredLanguages` only) | `RESOLVED` (prior pass) |
| `CanonicalMedia` | `contracts/identity.md` | `02-domain.md` (historical drafts, annotated) | No | Unchanged this pass | `RESOLVED` (prior pass) |
| `ExternalIdentity` | `contracts/identity.md` | `02-domain.md`, `07-evidence.md` (minimal restatement) | Minor, informational only | Unchanged this pass | `RESOLVED` (prior pass, informational) |
| `IdentityEvidence` / `IdentityObservation` | `contracts/identity.md` | — | No | Unchanged this pass | `RESOLVED` (prior pass, `ADR-002`) |
| `ReceiptEnvelope` | `07-evidence.md` (architecture-level only — no frozen contract) | — (single occurrence) | Gap, not conflict | New this pass: confirmed as the outer transport/storage envelope layer; its composition with domain receipt payloads is unspecified — recorded as `OPEN-14`, not silently resolved | `OPEN` (non-blocking, `OPEN-14`) |
| `EvidenceRecord<T>` | `07-evidence.md` (architecture-level only — no frozen contract) | — (single occurrence) | No | New this pass: confirmed as the generic core-fact + hash + provenance envelope, one layer below `ReceiptEnvelope` | `RESOLVED` (informational — layering confirmed, no conflict) |
| `IdentityReceipt` | `07-evidence.md` (architecture-level only) | — | No | New this pass: confirmed `outcome`/`observedAt` naming is intentional, not a collision with `AdapterExecution.status`/`durationMs` | `RESOLVED` (informational) |
| `MetadataReceipt` | `07-evidence.md` (architecture-level only) | — | No | Same as above | `RESOLVED` (informational) |
| `SourceExecutionReceipt` | `07-evidence.md` (architecture-level only) | `contracts/result.md` (`AdapterExecution`, a related but distinct concept) | Minor naming inconsistency | New this pass: `SourceExecutionReceipt.sourceId` vs. `AdapterExecution.adapterId` name the same underlying `SourceAdapter.id` differently — recorded as part of `OPEN-14`, not silently renamed without an implementer present to confirm which name wins | `OPEN` (non-blocking, `OPEN-14`) |
| `SubtitleCandidate` | *(none — deferred, not frozen)* | `02-domain.md` ×4 | Not diffed field-by-field — moot | Unchanged this pass (`ADR-005`, prior pass) | `RESOLVED` (deferred, not frozen) |
| `HealthResult` / `SourceHealth` (`SourceHealthCounters`/`SourceHealthSnapshot`) | `contracts/source-adapter.md` (`HealthResult`); `04-providers.md`/`10-observability.md` (the other two) | — | No | Unchanged this pass (`ADR-004`, prior pass) | `RESOLVED` (prior pass) |
| `CircuitBreaker` (class) | *(architecture-level only, not a frozen contract)* | `06-runtime.md` ×2 | Not diffed this pass | Unchanged — out of V0.1 CORE scope (deferred: "advanced health orchestration") | `NOT VERIFIED` (non-blocking — not named in V0.1 CORE/RUNTIME scope) |

---

## 4. Other concepts inventoried but not fully diffed this pass (carried forward from the second pass, unchanged unless noted)

| Concept | Occurrences | Preliminary read | Recommended action |
|---|---|---|---|
| `PolicyDecision` | `05-policy.md` ×3 | Likely legitimate evolution; not diffed field-by-field | Future audit pass; low risk |
| ~~`AdapterExecution`~~ | *(resolved this pass — see §3)* | — | — |
| ~~`AdapterStatus`~~ | *(resolved this pass — see §3)* | — | — |
| ~~`SourceHealth`~~ → `SourceHealthCounters` / `SourceHealthSnapshot` | `04-providers.md`, `10-observability.md` | Resolved by `ADR-004` | None |
| `Semaphore` (class) | `06-runtime.md` ×2 | Likely the same evolving class shown twice | Low priority |
| `CatalogProvider` | `02-domain.md`, `08-protocols.md` | Plausibly legitimate — domain-level vs. protocol-facing | No action, not verified |
| `MetadataProvider` | `04-providers.md` ×2 | Not diffed | Future audit pass |
| `MetadataRecord` | `02-domain.md`, `08-protocols.md` | Plausibly legitimate — domain record vs. protocol DTO | No action, not verified |
| `LibraryAsset` | `02-domain.md`, `04-providers.md`, `05-policy.md` | Not diffed | Future audit pass |
| `IdentityAdapter` | `04-providers.md` ×2 | Not diffed | Future audit pass |
| `IdentityKind` | `02-domain.md`, `04-providers.md`, `07-evidence.md`, contract | All identical by grep | None needed |
| `MediaType` | `02-domain.md` ×4, contract | All identical | None needed |
| `RequestContext` / `CallerContext` / `ResolveContext` | `08-protocols.md`, `08-protocols.md`, `contracts/source-adapter.md` | Three legitimately different layers | No action — explicitly not collapsing these |
| `ProtocolAdapter` | `08-protocols.md` (one occurrence) | No duplication found | None needed |

---

## 5. Protocol-leakage audit

Unchanged from the second pass — no edits touched Stremio-boundary
material this pass. See the second-pass results (still valid):
`02-domain.md`, `04-providers.md`, `05-policy.md`, `06-runtime.md`,
`07-evidence.md` all **PASS**; `03-resolution.md` **PASS with a minor
note** (an inline `toStremioStream()` function body that would fit
`08-protocols.md` slightly better, not treated as a blocking leak).

---

## 6. Status-semantics audit

Unchanged from the second pass — no new violations found or introduced
this pass. `11-testing.md`'s conditional-future-state pattern remains the
correct model; no document asserts `IMPLEMENTED`/`VERIFIED`/`EXECUTED`
without a concrete repository reference.

---

## 7. Freeze-gate status (updated, third pass)

All three items that blocked freeze at the end of the second pass are
now resolved:

1. **`OPEN-11`** (registry method signature) — **RESOLVED** by `ADR-006`:
   `applicableByMedia`/`applicableByIdentity` replace the ambiguous
   `applicable()`.
2. **`OPEN-12`** (`ResolutionResult` has no canonical home) —
   **RESOLVED** by `ADR-007` and the new `docs/contracts/result.md`.
3. **`OPEN-13`** (admission-lifecycle registry variant unreconciled) —
   **RESOLVED** by `ADR-006`: the admission-lifecycle material in
   `04-providers.md`'s "Registry redesign" section is confirmed to
   describe the admission control-plane layer (`05-policy.md`), not a
   competing `SourceRegistry` contract.

Remaining open items, all explicitly non-blocking:

- **`OPEN-9`** — low severity, additive, does not change any frozen
  shape.
- **`OPEN-10`** — low severity, a state-count mismatch between
  `IdentityResolution` and `IdentityReceipt.outcome` that does not affect
  any currently-frozen V0.1 contract.
- **`OPEN-14`** (new this pass) — receipt family `sourceId`/`adapterId`
  naming inconsistency and `ReceiptEnvelope`'s unspecified payload
  composition. Non-blocking for V0.1 CORE (receipts are `EVIDENCE` scope,
  not `CORE`), but keeps `contracts/evidence.md`'s receipt portion
  `NOT_FROZEN` — this is stated explicitly in that file, not silently
  dropped.

**No item currently blocks `CONTRACT_FREEZE` for the V0.1 CORE / RUNTIME
/ PROVIDER scope named in `13-roadmap.md`.** See the final report's §6
Freeze Gate section for the full 14-item checklist verdict.

---

## 8. Changes made across all three passes

**First pass (2026-09-29, commits `e2de799`, `481d359`, `a065298`):** the
initial contradiction/status inventory.

**Second pass (2026-09-29, commit `514bdc2`):** wrote `ADR-001` through
`ADR-005`, resolving `OPEN-1`–`OPEN-4` and `OPEN-8`; applied matching
contract/architecture edits; fixed a `README.md` vs. `13-roadmap.md`
scope contradiction; discovered `OPEN-9`–`OPEN-13`.

**Third pass (2026-09-29, this revision — commits `a68f229`, `5c830e7`,
`a777eb9`, and this commit):**

- `a68f229` — **docs: normalize source registry contract.** `ADR-001`
  amended (narrowed `SourceAdapter`); new `ADR-006` (registry/admission
  boundary, resolves `OPEN-11`/`OPEN-13`); `contracts/source-adapter.md`
  rewritten; `04-providers.md`/`05-policy.md` annotated.
- `5c830e7` — **docs: define resolution result boundary.** New
  `ADR-007` and `contracts/result.md` (resolves `OPEN-12`);
  `02-domain.md`/`03-resolution.md`/`06-runtime.md` annotated, including
  a correction to a false "identical duplication" claim about
  `06-runtime.md`'s two `AdapterStatus` drafts.
- `a777eb9` — **docs: normalize evidence and receipt contracts.**
  `07-evidence.md` receipt-family layering confirmed and documented;
  `contracts/evidence.md` receipt scope stated explicitly; new `OPEN-14`
  (non-blocking).
- *(this commit)* — **docs: refresh roadmap and audit.** `13-roadmap.md`'s
  "Decisions applied to this scope" section rewritten to remove the now-
  stale `OPEN-12`-is-blocking bullet and to state the resolved
  `SourceRegistry`/`SourceAdapter` boundaries, plus an explicit
  scope-lock list of what stays deferred past V0.1; this file
  regenerated from current `HEAD`.

Note on commit-order discipline: a separate "reconcile architecture
examples with canonical contracts" commit was planned but its content
was, in practice, inseparable from the three normalization commits above
(each contract change was accompanied in the same commit by the
architecture-doc annotation marking its historical/superseded drafts) —
splitting it out would have required interactive hunk-level staging of
single files touching one concern each, which was judged lower-value than
keeping each commit's contract-and-annotation change together and fully
reviewable. This is recorded here rather than silently omitted.

A final ledger-freeze commit follows this one (see git history / the
final report), updating `docs/decisions/README.md`'s summary line to
state the freeze-gate verdict.

---

## How this was produced

1. Extracted every `export interface`, `interface`, `export type`,
   `export class`, and `class` declaration across `docs/` and `README.md`
   via `grep`.
2. For each contract-owned concept named in the task's symbol list,
   extracted the full brace-matched body of every occurrence and diffed
   them by eye — including a character-by-character re-check of the two
   `AdapterStatus` value lists in `06-runtime.md` that a prior draft of
   `ADR-007` had incorrectly called identical.
3. Re-ran `git fetch`/`git rev-parse`/`git rev-list`/`find` to re-verify
   the repository baseline independently of prior-session memory.
4. Verified Markdown fence balance (`grep -c '^```'`, must be even) on
   every file touched this pass.
5. Verified internal (non-`http`) Markdown links resolve to an existing
   file, via a small Python script walking every `docs/**/*.md` and
   `README.md` link target.

This file does not claim CI ran, tests ran, or any code executed, because
none of those exist in this repository.
