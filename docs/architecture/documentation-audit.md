# Documentation Audit — Contract-Freeze Verification (2026-09-29)

[⇧ Architecture index](../architecture.md) · [⇆ Document map](./README.md)

> **What this file is.** A point-in-time audit artifact produced by a deep
> repository-level verification pass over the already-split documentation
> set. It is not itself architecture — it is evidence for the claims made
> in `docs/architecture.md` and `docs/decisions/README.md`. It may go
> stale; re-run the checks described here (see "How this was produced")
> before trusting it after further edits.
>
> **Scope limitation, stated up front.** This repository declares ~150
> distinct named interfaces/types across `docs/architecture/*.md`. This
> audit performed a **full field-level diff** on the concepts explicitly
> named as contract-owned in the task that requested this audit
> (`MediaRef`, `ExternalIdentity`, `CanonicalMedia`, `SourceAdapter`,
> `ResolveContext`, `HealthResult`, `SourceRegistry`/`ProviderRegistry`,
> `SourceCandidate`, `Stream`, `RuntimeSnapshot`, `ConfigurationTransaction`,
> `RuntimePolicy`, the evidence levels) plus everything named in the four
> previously-recorded `OPEN` items. For the remaining ~130 interfaces, this
> audit did a **structural inventory pass** (name, location, occurrence
> count) but not a field-level diff of every occurrence — see the "Other
> concepts" table below for what was and wasn't deep-checked.

---

## 1. Repository baseline (re-verified 2026-09-29)

| Fact | Value | Evidence |
|---|---|---|
| Branch | `arena/01a0e9bd-streamforge-stremio` | `git branch --show-current` |
| HEAD | `9081018` at start of this pass | `git rev-parse HEAD` |
| Base branch | `main` | `git fetch origin main` |
| Ahead/behind `main` | 26 ahead / 0 behind | `git rev-list --left-right --count origin/main...HEAD` |
| `src/`, `test/`, `tests/` | absent | `find` |
| `.github/workflows/` | absent | `find` |
| `tsconfig.json`, `Dockerfile`, `compose.*` | absent | `find` |
| `package.json` scripts | none defined | `cat package.json` |
| `package.json` dependencies | none defined | `cat package.json` |

**Conclusion:** every implementation-shaped claim anywhere in this
repository's documentation must be `DESIGNED` or `PROPOSED`, never
`IMPLEMENTED`, `EXECUTED`, or `VERIFIED`.

---

## 2. Contract status matrix

| Contract file | Owned concepts | Internally consistent? | Blocking `OPEN` items | Contract status |
|---|---|---|---|---|
| `contracts/source-adapter.md` | `SourceAdapter`, `ResolveContext`, `HealthResult`, `SourceRegistry`/`ProviderRegistry<T>` | `ResolveContext` corrected to the converged shape (see `RESOLVED-1`); `SourceAdapter` has an unresolved shape question | `OPEN-1`, `OPEN-4`, `OPEN-8`, `OPEN-9` | **NOT_FROZEN** |
| `contracts/identity.md` | `MediaRef`, `ExternalIdentity`, `CanonicalMedia` | Yes, after superseding 3 `MediaRef` and 3 `CanonicalMedia` drafts (`RESOLVED`) | `OPEN-2` (confidence placement) | **NOT_FROZEN** |
| `contracts/stream.md` | `SourceCandidate`, `Stream`, subtitle candidates | `SourceCandidate`/`Stream` consistent after superseding 1 draft; subtitle candidate never frozen | `OPEN-3`, `OPEN-7` (resolved, informational) | **NOT_FROZEN** (subtitle portion is the blocker; `SourceCandidate`/`Stream` are freeze-ready pending `OPEN-8` upstream) |
| `contracts/runtime.md` | `RuntimeSnapshot`, `ConfigurationTransaction`, `RuntimePolicy` | Yes — the only occurrence of each in `09-control-plane.md` matches this file exactly, no competing drafts found | none directly; indirectly depends on `SourceAdapter` shape via `AdmittedSource` | **NOT_FROZEN** (indirect dependency on `OPEN-8`) |
| `contracts/evidence.md` | 4 evidence levels, receipt/evidence-graph shape | The 4 levels are consistent everywhere they're named; `ReceiptEnvelope`/`EvidenceRecord<T>`/receipts were inventoried but not field-level diffed against each other this pass | not diffed — see scope limitation | **NOT_FROZEN** (evidence levels alone would qualify; receipts are unverified) |

No contract in this repository currently qualifies for `CONTRACT_FREEZE` per the gate in `docs/architecture.md`. See §7 for the precise unblocking conditions.

---

## 3. Concept ownership matrix — contract-owned concepts (fully diffed)

| Concept | Canonical owner | Other occurrences | Conflict? | Action taken | Status |
|---|---|---|---|---|---|
| `MediaRef` | `contracts/identity.md` | `02-domain.md` ×4 (3 non-canonical) | Yes — 3 drafts embed `imdbId`/`tmdbId` | Annotated in place as HISTORICAL/SUPERSEDED, recorded as `OPEN-5` | `RESOLVED` |
| `ExternalIdentity` | `contracts/identity.md` | `02-domain.md` (canonical match, inside already-annotated section), `07-evidence.md` (minimal restatement) | Minor — minimal restatement drops provenance fields | Annotated in `contracts/identity.md` | `RESOLVED` (informational) |
| `CanonicalMedia` | `contracts/identity.md` | `02-domain.md` ×4 (3 non-canonical) | Yes — 3 drafts (presentation-conflated, Map-based) | Annotated in place, recorded as `OPEN-6` | `RESOLVED` |
| `SourceAdapter` | `contracts/source-adapter.md` | `04-providers.md` ×6 (5 non-canonical) | Yes — capability field and identity-aware resolve() unresolved | Annotated in place; contract file documents all variants; recorded as `OPEN-8` | `OPEN` (highest priority) |
| `ResolveContext` | `contracts/source-adapter.md` | `04-providers.md` ×3, `06-runtime.md` ×2 | Contract previously froze the minority (1×) shape instead of the converged (4×) shape | **Corrected** the contract to the converged shape; annotated the outlier; recorded as `RESOLVED-1` / `OPEN-9` | `RESOLVED` |
| `HealthResult` | `contracts/source-adapter.md` | (unique) | Overlaps semantically with two `SourceHealth` shapes | Cross-referenced in contract file; recorded as `OPEN-1` | `OPEN` |
| `SourceRegistry` / `ProviderRegistry<T>` | `contracts/source-adapter.md` | `04-providers.md` ×4 | Evolution vs. duplication unresolved | Both shapes recorded in contract file; recorded as `OPEN-4` | `OPEN`, low severity |
| `SourceCandidate` | `contracts/stream.md` | `02-domain.md` ×4 (2 non-canonical), `03-resolution.md` (canonical match) | Yes — 1 draft uses `authorized: boolean`, violating the tri-state invariant | Annotated in place; superseded; recorded as `OPEN-7` | `RESOLVED` |
| `Stream` | `contracts/stream.md` | none found duplicated | No | none needed | `RESOLVED` |
| `SubtitleCandidate` | *(none — never frozen)* | `02-domain.md` ×3 | Not diffed field-by-field this pass | Recorded as `OPEN-3` | `OPEN` |
| `RuntimeSnapshot` | `contracts/runtime.md` | `09-control-plane.md` (identical, canonical source) | No | Pointer already present | `RESOLVED` |
| `ConfigurationTransaction` | `contracts/runtime.md` | `09-control-plane.md` (identical) | No | Pointer already present | `RESOLVED` |
| `RuntimePolicy` | `contracts/runtime.md` | `09-control-plane.md` (identical, canonical source) | No | Pointer already present | `RESOLVED` |
| Evidence levels (`OBSERVED`/`DERIVED`/`VERIFIED`/`ANNOTATED`) | `contracts/evidence.md` | Referenced (not redefined) throughout | No | Pointer present | `RESOLVED` |

---

## 4. Other concepts inventoried but not fully diffed this pass

These appear 2+ times across the documentation set. Per Rule 26 ("not
every repeated name is a duplicate"), each is listed with a preliminary
read, not a final verdict. None were edited this pass beyond what's noted.

| Concept | Occurrences | Preliminary read | Recommended action |
|---|---|---|---|
| `PolicyDecision` | `05-policy.md` ×3 | Likely legitimate evolution (reasons list grows across drafts); not diffed field-by-field | Future audit pass; low risk — `05-policy.md` is a single self-contained document |
| `AdapterExecution` | `04-providers.md`, `06-runtime.md`, `07-evidence.md` | Plausibly three different layers (execution options / execution context / execution receipt) rather than one duplicated type — **names are ambiguous enough to warrant renaming**, not merging | Recommend an ADR that gives each a distinct name (e.g. `AdapterExecutionOptions`, `AdapterExecutionContext`, `AdapterExecutionReceipt`) |
| `AdapterStatus` | `06-runtime.md` ×2, `04-providers.md` (as a type alias) | Two enum-like shapes with different value sets — not diffed | Future audit pass |
| `SourceHealth` | `04-providers.md`, `10-observability.md` | Different field sets (see `OPEN-1`) | Covered by `OPEN-1` |
| `CircuitBreaker` (class) | `06-runtime.md` ×2 | Two implementations shown at different points in the runtime narrative; likely the same evolving class shown twice, not two designs | Low priority |
| `Semaphore` (class) | `06-runtime.md` ×2 | Same as above | Low priority |
| `CatalogProvider` | `02-domain.md`, `08-protocols.md` | Plausibly legitimate — domain-level provider abstraction vs. protocol-facing interface | No action; names should stay distinct if semantics differ, but this wasn't verified |
| `MetadataProvider` | `04-providers.md` ×2 | Not diffed | Future audit pass |
| `MetadataRecord` | `02-domain.md`, `08-protocols.md` | Plausibly legitimate — domain record vs. protocol DTO | No action, not verified |
| `LibraryAsset` | `02-domain.md`, `04-providers.md`, `05-policy.md` | Not diffed — appears in three different subsystem discussions (owned-media adapter, library repository, asset authorization) | Future audit pass |
| `IdentityAdapter` | `04-providers.md` ×2 | Not diffed | Future audit pass |
| `IdentityKind` | `02-domain.md`, `04-providers.md`, `07-evidence.md`, contract | All four textually identical (`"imdb" \| "tmdb" \| "tvdb" \| "internal"`) — verified identical by grep, not a conflict | None needed |
| `MediaType` | `02-domain.md` ×4, contract | All identical (`"movie" \| "series"`) except where embedded inside the superseded `MediaRef` drafts — no independent conflict | None needed |
| `RequestContext` / `CallerContext` / `ResolveContext` | `08-protocols.md`, `08-protocols.md`, `contracts/source-adapter.md` | Per Rule 26, these are almost certainly three legitimately different layers (protocol-level request context, caller identity, adapter execution context) | No action — explicitly not collapsing these |
| `ReceiptEnvelope` / `EvidenceRecord<T>` | `07-evidence.md` (one occurrence each) | Not cross-diffed against each other or against `IdentityReceipt`/`MetadataReceipt`/`SourceExecutionReceipt` (also in `07-evidence.md`) | Recommend a dedicated future audit of the receipt family — this is the least-verified part of the evidence model |
| `ProtocolAdapter` | `08-protocols.md` (one occurrence) | No duplication found | None needed |

---

## 5. Protocol-leakage audit (§13 of the audit request)

Grepped `02-domain.md`, `03-resolution.md`, `04-providers.md`,
`05-policy.md`, `06-runtime.md`, `07-evidence.md` for `stremio`
(case-insensitive). Every occurrence was inspected; classification:

| Document | Occurrences | Classification |
|---|---|---|
| `02-domain.md` | 17 | All boundary references ("No Stremio dependency", diagrams showing Stremio as an external actor, DTO names explicitly living in `08-protocols.md`) — **PASS** |
| `03-resolution.md` | 26 | Mostly boundary references and diagrams. One minor finding: `export function toStremioStream(candidate): StremioStream` is defined inline in `03-resolution.md` rather than in `08-protocols.md`. Low-severity — `03-resolution.md`'s own documented scope includes "protocol mapping" as the pipeline's last stage, so referencing the mapping step isn't inherently wrong, but the concrete function body would fit `08-protocols.md` better. **PASS with a minor note**, not treated as a blocking leak |
| `04-providers.md` | 13 | All boundary references ("the adapter never constructs a Stremio `Stream`", "the adapter doesn't need to understand Stremio") — **PASS** |
| `05-policy.md` | 5 | All boundary/error-taxonomy references — **PASS** |
| `06-runtime.md` | 15 | All boundary references, including an explicit section titled "Cache candidates, not final Stremio streams" which *is* the invariant this check is looking for — **PASS** |
| `07-evidence.md` | 1 | Boundary reference — **PASS** |

No Stremio-specific type definitions were found leaking into the core
domain/resolution/provider/policy/runtime/evidence documents. `StremioStream`,
`StremioMeta`, `StremioProtocolAdapter` are all defined exclusively in
`08-protocols.md`.

---

## 6. Status-semantics audit (§10)

- `docs/architecture/11-testing.md` already correctly distinguishes
  conditional future state from current state, e.g.: "Only then:
  `GATE-V0.1-S1 = PASSED`. But until those commands actually execute in
  CI: `GATE-V0.1-S1 = OPEN`." This is the correct pattern and required no
  fix.
- `README.md` previously violated this discipline in three places (fixed
  this pass, see §8 below): the "Current scope" `✓` list implied
  completed work; the "Development" section implied working npm scripts;
  the "Repository structure" section implied an existing file tree.
- No other document was found asserting `IMPLEMENTED`, `VERIFIED`, or
  `EXECUTED` without a concrete repository reference.

---

## 7. Precise CONTRACT_FREEZE blocking conditions

For each contract, this is exactly what would need to happen for it to
move to `CONTRACT_FREEZE`:

1. **`source-adapter.md`**: an ADR resolving `OPEN-8` (which `SourceAdapter`
   tier ships in v0.1: minimal `MediaRef`-based, or identity/capability-aware)
   and `OPEN-4` (registry generic vs. specialized); `OPEN-1` needs the
   `HealthResult`/`SourceHealth` relationship stated explicitly (three
   layers or a merge).
2. **`identity.md`**: an ADR resolving `OPEN-2` (where identity confidence
   lives: on `ExternalIdentity`, on `CanonicalMedia`, or via a separate
   `IdentityEvidence` linkage).
3. **`stream.md`**: freezing a `SubtitleCandidate` shape (`OPEN-3`) — the
   `SourceCandidate`/`Stream` portion has no remaining blocker.
4. **`runtime.md`**: blocked only transitively by `OPEN-8` (its
   `AdmittedSource` type is adapter-shaped); otherwise ready.
5. **`evidence.md`**: a follow-up audit diffing `ReceiptEnvelope`,
   `EvidenceRecord<T>`, `IdentityReceipt`, `MetadataReceipt`, and
   `SourceExecutionReceipt` against each other, which this pass did not
   perform (see scope limitation at the top of this file).

---

## 8. Changes made in this audit pass

See the final report in the task response for the itemized file list and
per-change rationale (git history is also authoritative: this audit's
commits are named `docs: ...` and touch only `docs/`, `README.md`).

---

## How this was produced

1. Extracted every `export interface`, `interface`, `export type`,
   `export class`, and `class` declaration across `docs/` and `README.md`
   via `grep`.
2. For each of the contract-owned concepts, extracted the full
   brace-matched body of every occurrence via a small Python script and
   diffed them by eye.
3. Grepped for `stremio` (case-insensitive) in the six boundary-sensitive
   documents and read every occurrence in context.
4. Re-ran `git fetch`/`git log`/`find` to re-verify the repository
   baseline independently of the prior session's memory.
5. Verified Markdown fence balance (`grep -c '^```'`, must be even) on
   every file touched.
6. Verified internal links resolve (see the final report for the exact
   check).

This file does not claim CI ran, tests ran, or any code executed, because
none of those exist in this repository.
