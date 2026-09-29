# Documentation Audit — Contract-Freeze Verification (2026-09-29, updated)

[⇧ Architecture index](../architecture.md) · [⇆ Document map](./README.md)

> **What this file is.** A point-in-time audit artifact produced by a deep
> repository-level verification pass over the already-split documentation
> set. It is not itself architecture — it is evidence for the claims made
> in `docs/architecture.md` and `docs/decisions/README.md`. It may go
> stale; re-run the checks described here (see "How this was produced")
> before trusting it after further edits.
>
> **Updated 2026-09-29 (second pass, same day): 5 of the 9 `OPEN` items**
> this file originally recorded (`OPEN-1`, `OPEN-2`, `OPEN-3`, `OPEN-4`,
> `OPEN-8`) were resolved via explicit ADRs
> (`docs/decisions/ADR-001..005-*.md`) and the corresponding contract/
> architecture files were updated to match. This file was updated in
> place — not rewritten — to reflect that. Three new items were also
> discovered during that pass: `OPEN-10` and `OPEN-11` (both low-severity/
> non-blocking or narrowly-scoped) and `OPEN-12` (`ResolutionResult` has
> no canonical contract-file home — **this is now the single blocking
> item preventing full `CONTRACT_FREEZE`**). See
> `docs/decisions/README.md` for the full, current ledger — it is the
> source of truth; this file summarizes it.
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

## 1. Repository baseline (re-verified 2026-09-29, second pass)

| Fact | Value | Evidence |
|---|---|---|
| Branch | `arena/01a0e9bd-streamforge-stremio` | `git branch --show-current` |
| HEAD | `514bdc2` after the ADR-normalization commit | `git rev-parse HEAD` |
| Base branch | `main` | `git fetch origin main` |
| Ahead/behind `main` | 30 ahead / 0 behind | `git rev-list --left-right --count origin/main...HEAD` |
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
| `contracts/source-adapter.md` | `SourceAdapter`, `ResolveContext`, `HealthResult`, `SourceHealthCounters`/`SourceHealthSnapshot`, `SourceRegistry`/`ProviderRegistry<T>` | `ResolveContext` converged (`RESOLVED-1`); `SourceAdapter` boundary resolved (`ADR-001`); health layering resolved (`ADR-004`); registry-vs-generic-registry ownership resolved (`ADR-003`); **but** an admission-lifecycle-integrated 6th `SourceRegistry` shape was found this pass and is unreconciled | `OPEN-9` (low severity, additive); `OPEN-11` (registry `applicable()` needs re-specification); `OPEN-13` (**newly discovered, BLOCKING** — admission-lifecycle registry vs. simple registry) | **FREEZE-READY** for `SourceAdapter`/`HealthResult`/`SourceHealthCounters`/`SourceHealthSnapshot` themselves; **`SourceRegistry` is NOT_FROZEN** — `OPEN-11` and `OPEN-13` are both open and `OPEN-13` was missed by the first two ADR-writing passes, found only on independent re-scan |
| `contracts/identity.md` | `MediaRef`, `ExternalIdentity`, `CanonicalMedia` | Yes, after superseding 3 `MediaRef` and 3 `CanonicalMedia` drafts (`RESOLVED`); confidence ownership resolved (`ADR-002`) | `OPEN-10` (low severity, non-blocking — `IdentityResolution` vs. `IdentityReceipt.outcome` state-count mismatch) | **FROZEN** |
| `contracts/stream.md` | `SourceCandidate`, `Stream`, `ResolutionResult`, subtitle candidates (deferred) | `SourceCandidate`/`Stream` consistent after superseding 1 draft; subtitles formally deferred, not a blocker (`ADR-005`); `ResolutionResult` has no canonical shape | `OPEN-7` (resolved, informational); `OPEN-12` (**blocking** — `ResolutionResult` has two non-identical drafts and no contract-file home) | **NOT_FROZEN** — `SourceCandidate`/`Stream` are freeze-ready; `ResolutionResult` (listed in V0.1 CORE scope) is the blocker |
| `contracts/runtime.md` | `RuntimeSnapshot`, `ConfigurationTransaction`, `RuntimePolicy` | Yes — the only occurrence of each in `09-control-plane.md` matches this file exactly, no competing drafts found | none — its `SourceAdapter`-shaped dependency (`AdmittedSource`) is now resolved via `ADR-001` | **FROZEN** |
| `contracts/evidence.md` | 4 evidence levels, receipt/evidence-graph shape, `IdentityObservation` (extended, `ADR-002`) | The 4 levels are consistent everywhere they're named; `ReceiptEnvelope`/`EvidenceRecord<T>`/receipts were inventoried but not field-level diffed against each other this pass | not diffed — see scope limitation | **NOT_FROZEN** (evidence levels alone would qualify; receipts are unverified) |

Two contracts (`identity.md`, `runtime.md`) now qualify for
`CONTRACT_FREEZE` per the 14-point checklist in `docs/architecture.md`.
`source-adapter.md`'s `SourceAdapter`/health types are freeze-ready, but
its `SourceRegistry` portion is blocked by `OPEN-11` and, more
significantly, the newly-discovered `OPEN-13` (an unreconciled
admission-lifecycle registry variant). `stream.md` and `evidence.md`
remain `NOT_FROZEN`. See §7 for the precise remaining unblocking
conditions.

---

## 3. Concept ownership matrix — contract-owned concepts (fully diffed)

| Concept | Canonical owner | Other occurrences | Conflict? | Action taken | Status |
|---|---|---|---|---|---|
| `MediaRef` | `contracts/identity.md` | `02-domain.md` ×4 (3 non-canonical) | Yes — 3 drafts embed `imdbId`/`tmdbId` | Annotated in place as HISTORICAL/SUPERSEDED, recorded as `OPEN-5` | `RESOLVED` |
| `ExternalIdentity` | `contracts/identity.md` | `02-domain.md` (canonical match, inside already-annotated section), `07-evidence.md` (minimal restatement) | Minor — minimal restatement drops provenance fields | Annotated in `contracts/identity.md` | `RESOLVED` (informational) |
| `CanonicalMedia` | `contracts/identity.md` | `02-domain.md` ×4 (3 non-canonical) | Yes — 3 drafts (presentation-conflated, Map-based) | Annotated in place, recorded as `OPEN-6` | `RESOLVED` |
| `SourceAdapter` | `contracts/source-adapter.md` | `04-providers.md` ×6 (5 now HISTORICAL) | Resolved — adapter selection happens after identity resolution | `ADR-001` adopted the identity/capability-aware shape (`supportsMedia`/`supportsIdentity`/`resolve(CanonicalMedia, ...)`/`health?()`); all 5 other drafts marked HISTORICAL/SUPERSEDED | `RESOLVED` by `ADR-001` |
| `ResolveContext` | `contracts/source-adapter.md` | `04-providers.md` ×3, `06-runtime.md` ×2 | Contract previously froze the minority (1×) shape instead of the converged (4×) shape | **Corrected** the contract to the converged shape; annotated the outlier; recorded as `RESOLVED-1` / `OPEN-9` | `RESOLVED` |
| `HealthResult` / `SourceHealthCounters` / `SourceHealthSnapshot` | `contracts/source-adapter.md` (`HealthResult`); `04-providers.md` (`SourceHealthCounters`); `10-observability.md` (`SourceHealthSnapshot`) | Previously both non-`HealthResult` types were named `SourceHealth` | Resolved — three distinct layers, not duplicates | `ADR-004` renamed the two colliding `SourceHealth` types; all three now have distinct names and a stated relationship | `RESOLVED` by `ADR-004` |
| `SourceRegistry` / `ProviderRegistry<T>` | `contracts/source-adapter.md` | `04-providers.md` ×5 (corrected count — an independent re-scan found a 5th, admission-lifecycle-integrated occurrence missed by the first count of 4) | `SourceRegistry` vs. `ProviderRegistry<T>` resolved (chronological evolution); the 5th, admission-lifecycle occurrence is a **new, unreconciled contradiction** | `ADR-003`: `SourceRegistry` is the V0.1-frozen registry; `ProviderRegistry<T>` deferred to V0.2+. **Not yet resolved:** whether the admission-lifecycle `RegisteredSource`-based registry is a V0.2+ evolution, the true V0.1 shape, or a distinct upstream layer | `PARTIALLY RESOLVED` — registry genericity resolved by `ADR-003`; `OPEN-11` and `OPEN-13` remain open and block `SourceRegistry`'s own freeze |
| `SourceCandidate` | `contracts/stream.md` | `02-domain.md` ×4 (2 non-canonical), `03-resolution.md` (canonical match) | Yes — 1 draft uses `authorized: boolean`, violating the tri-state invariant | Annotated in place; superseded; recorded as `OPEN-7` | `RESOLVED` |
| `Stream` | `contracts/stream.md` | none found duplicated | No | none needed | `RESOLVED` |
| `SubtitleCandidate` | *(none — deferred, not frozen)* | `02-domain.md` ×4 (corrected count; was previously miscounted as 3) | Not diffed field-by-field — moot, since none is being frozen | `ADR-005`: subtitles deferred to V0.2+; all 4 drafts kept as PROPOSED/EXPLORATORY, none promoted | `RESOLVED` (deferred, not frozen) by `ADR-005` |
| `ResolutionResult` | *(none — no canonical home)* | `02-domain.md` (richer draft), `03-resolution.md` (simpler draft) | Yes — two non-identical drafts, both using `MediaRef` not `CanonicalMedia` despite `ADR-001` | Discovered this pass; recorded as `OPEN-12`, not resolved (insufficient evidence to prefer one draft) | `OPEN` — **blocking**, since `13-roadmap.md` lists this in V0.1 CORE scope |
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
| ~~`SourceHealth`~~ → `SourceHealthCounters` / `SourceHealthSnapshot` | `04-providers.md`, `10-observability.md` | Resolved by `ADR-004` — renamed to distinct names, no longer a naming collision | None — see `ADR-004` |
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

## 7. Precise CONTRACT_FREEZE blocking conditions (updated, second pass)

Five of the original nine blocking `OPEN` items (`OPEN-1`, `OPEN-2`,
`OPEN-3`, `OPEN-4`, `OPEN-8`) were resolved this pass via `ADR-001`
through `ADR-005`. Remaining conditions for full `CONTRACT_FREEZE`:

1. **`source-adapter.md`**: `SourceAdapter`/`HealthResult`/
   `SourceHealthCounters`/`SourceHealthSnapshot` are now freeze-ready
   (`ADR-001`, `ADR-004`). `SourceRegistry` is **not** freeze-ready:
   `OPEN-11` (method signature needs re-specifying into the two-stage
   `supportsMedia`/`supportsIdentity` filter implied by `ADR-001`) and
   `OPEN-13` (an admission-lifecycle-integrated 6th registry shape, found
   only on independent re-scan, not reconciled with the simple frozen
   registry) both need a resolution — `OPEN-13` likely needs a dedicated
   ADR, not just an edit. `OPEN-9` remains open but is explicitly
   non-blocking (additive, does not change the frozen shape).
2. **`identity.md`**: **FROZEN.** `OPEN-2` resolved by `ADR-002`.
   `OPEN-10` (a 3-state vs. 4-state mismatch between `IdentityResolution`
   and `IdentityReceipt.outcome`) remains open but does not block any
   currently-frozen V0.1 contract.
3. **`stream.md`**: subtitle deferral (`ADR-005`) removed that blocker.
   The remaining, **newly-discovered** blocker is `OPEN-12`:
   `ResolutionResult` is named in `13-roadmap.md`'s V0.1 CORE scope but
   has two non-identical drafts and no canonical home in
   `docs/contracts/`. This must be resolved (either by an ADR picking one
   draft, or by explicitly re-scoping V0.1 CORE to exclude it) before
   `stream.md`/the CORE scope can be called fully frozen.
4. **`runtime.md`**: **FROZEN.** Its only dependency (`AdmittedSource`
   being adapter-shaped) is resolved transitively by `ADR-001`.
5. **`evidence.md`**: unchanged from the previous pass — a follow-up
   audit diffing `ReceiptEnvelope`, `EvidenceRecord<T>`, `IdentityReceipt`,
   `MetadataReceipt`, and `SourceExecutionReceipt` against each other was
   out of scope for both passes (see scope limitation at the top of this
   file). This is a stated, not silently dropped, limitation.

---

## 8. Changes made in this audit pass

**First pass (2026-09-29, commits `e2de799`, `481d359`, `a065298`):** the
contradiction/status inventory recorded in this file's first version.

**Second pass (2026-09-29, commit `514bdc2`):** wrote 5 ADRs
(`docs/decisions/ADR-001` through `ADR-005`), resolving `OPEN-1`,
`OPEN-2`, `OPEN-3`, `OPEN-4`, and `OPEN-8`; applied matching edits to
`docs/contracts/source-adapter.md`, `docs/contracts/identity.md`,
`docs/contracts/stream.md`, and `docs/architecture/{02-domain,
04-providers,07-evidence,10-observability,13-roadmap}.md`; fixed a
`README.md` vs. `13-roadmap.md` V0.1-scope contradiction (`RESOLVED-2`);
discovered and recorded three new items (`OPEN-10`, `OPEN-11`, `OPEN-12`);
updated `docs/decisions/README.md` and this file in place. See the final
report in the task response for the itemized file list and per-change
rationale (git history is also authoritative: all commits are named
`docs: ...` and touch only `docs/`, `README.md`).

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
