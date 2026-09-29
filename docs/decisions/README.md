# Architecture Decisions

[⇧ Back to the architecture index](../architecture.md)

This is the contradiction/decision ledger for StreamForge. This file is
both the ADR index and the ledger of contradictions surfaced while
migrating and auditing the documentation.

**Rule:** an entry moves from `OPEN` to `RESOLVED` only when there is a
stated decision *and* a stated rationale grounded in repository evidence
(not a guess). If a reconciliation cannot be justified from existing
evidence, it stays `OPEN` — see `docs/architecture.md`, "Maintenance
rules."

Last updated: 2026-09-29 (contract-normalization / pre-freeze audit pass —
second pass; see "ADR index" below for the 5 ADRs written during this
pass).

## ADR index

| ADR | Title | Resolves | Status |
|---|---|---|---|
| [`ADR-001`](./ADR-001-source-adapter-identity-boundary.md) | `SourceAdapter` identity/capability boundary | `OPEN-8` | ACCEPTED |
| [`ADR-002`](./ADR-002-identity-confidence-ownership.md) | Identity confidence ownership | `OPEN-2` | ACCEPTED |
| [`ADR-003`](./ADR-003-provider-registry-ownership.md) | Provider registry ownership (`SourceRegistry` vs. `ProviderRegistry<T>`) | `OPEN-4` | ACCEPTED |
| [`ADR-004`](./ADR-004-health-model-layering.md) | Health model layering (`HealthResult`/`SourceHealthCounters`/`SourceHealthSnapshot`) | `OPEN-1` | ACCEPTED |
| [`ADR-005`](./ADR-005-subtitle-v0.1-scope.md) | Subtitle scope deferred past V0.1 | `OPEN-3` | ACCEPTED |

---

### OPEN-1 — `HealthResult` vs. `SourceHealth` (two shapes) vs. circuit-breaker state

- **Affected documents:** `docs/contracts/source-adapter.md`, `docs/architecture/04-providers.md` (`interface SourceHealth { successes; failures; timeouts; latencyMs }`), `docs/architecture/10-observability.md` (`interface SourceHealth { adapterId; requests; successes; empty; failures; timeoutCount; consecutiveFailures; latency: {p50,p95,p99} }`), `docs/architecture/06-runtime.md` ("Health state machine", `CircuitBreaker`/`BreakerState`)
- **Observed contradiction:** at least three different "is this provider okay" shapes exist and none reference each other: a point-in-time `HealthResult` (frozen contract), a simple provider-local counter struct `SourceHealth` in `04-providers.md`, and a richer metrics-oriented `SourceHealth` in `10-observability.md`.
- **Why it matters:** an implementer cannot tell whether these are (a) the same concept renamed across drafts, (b) three legitimately different layers (point-in-time probe / running counters / exported metrics snapshot), or (c) two accidental duplicates plus one real concept.
- **Possible interpretations:** (1) `HealthResult` = adapter-authored point-in-time probe; provider-local `SourceHealth` = internal counters the runtime keeps to *decide* health/circuit state; observability `SourceHealth` = a *derived, exported* snapshot for metrics — three legitimately distinct layers that only need distinct names to stop looking like duplicates. (2) The two `SourceHealth` structs are an accidental duplicate that should be merged.
- **Evidence available:** field-level diffs performed during this audit (2026-09-29); no code exists to check against.
- **Decision:** interpretation (1) — three legitimately distinct layers. `HealthResult` (unchanged) = adapter-authored point-in-time probe. `04-providers.md`'s `SourceHealth` is renamed `SourceHealthCounters` (runtime-internal rolling counters feeding circuit-breaker decisions). `10-observability.md`'s `SourceHealth` is renamed `SourceHealthSnapshot` (derived, exported metrics view). See [`ADR-004`](./ADR-004-health-model-layering.md).
- **Decision rationale:** each type has a distinct producer, consumer, and update cadence (on-demand probe / per-call internal counters / derived exported snapshot); merging them would couple runtime-internal bookkeeping to a public metrics contract. Renaming (not merging) removes the harmful naming collision without inventing an unneeded abstraction.
- **Status:** `RESOLVED` by `ADR-004` (2026-09-29).

### OPEN-2 — Identity confidence exists in the design but is not wired into the frozen identity contract

- **Affected documents:** `docs/contracts/identity.md` (`CanonicalMedia`, `ExternalIdentity`), `docs/architecture/07-evidence.md` (`MediaIdentity`, `IdentityEvidence { provider; matchedBy; confidence: "verified"|"probable"|"ambiguous" }`)
- **Observed contradiction:** `docs/architecture/02-domain.md` discusses "Identity Confidence" as an important concept, and `07-evidence.md` independently defines a full evidence-bearing identity model (`MediaIdentity`/`IdentityEvidence`) that already includes a `confidence` field — but the frozen `CanonicalMedia`/`ExternalIdentity` contract has no confidence field and does not reference `MediaIdentity`/`IdentityEvidence` at all.
- **Why it matters:** confidence is not an unmet requirement — it is a requirement that was already designed once, in a different type family, and never connected to the type family that got frozen. Implementing against the frozen contract alone would silently drop confidence tracking.
- **Possible interpretations:** (1) `ExternalIdentity` gains a `confidence` field directly. (2) `CanonicalMedia` gains an `readonly evidence: readonly IdentityEvidence[]` field alongside `identities`. (3) `MediaIdentity`/`CanonicalMedia` are the same concept under two names and should be merged into one type.
- **Evidence available:** exact type definitions of both families, located and diffed during this audit (2026-09-29).
- **Decision:** confidence stays off `CanonicalMedia`/`ExternalIdentity` (domain/truth layer); `IdentityObservation` (`04-providers.md`) gains optional `confidence`/`matchedBy` fields, absorbing what `IdentityEvidence` carried; `MediaIdentity`/`IdentityEvidence` (`07-evidence.md`) are marked SUPERSEDED, not deleted. See [`ADR-002`](./ADR-002-identity-confidence-ownership.md).
- **Decision rationale:** matches the `evidence ≠ truth` boundary stated throughout `07-evidence.md`; adds fields to a type adapters already produce (`IdentityObservation`) instead of inventing a new wrapper or coupling confidence to the resolved-state type.
- **Status:** `RESOLVED` by `ADR-002` (2026-09-29). Note: this surfaced one new, non-blocking follow-up — see `OPEN-10` below.

### OPEN-3 — Subtitle candidate shape never frozen

- **Affected documents:** `docs/contracts/stream.md`, `docs/architecture/04-providers.md`, `docs/architecture/08-protocols.md`, `docs/architecture/02-domain.md` (`SubtitleCandidate` appears **4** times with different fields — corrected count; the previous audit pass undercounted this as 3)
- **Observed contradiction:** the monolith discusses a subtitle candidate model, subtitle ranking, and subtitle deduplication extensively, and states subtitles "follow the same candidate model" as source candidates, but `SubtitleCandidate` is defined 4 different times in `02-domain.md` alone with different fields, and none is marked as canonical.
- **Why it matters:** without a frozen shape, subtitle provider adapters and the subtitle ranking/dedup pipeline cannot be implemented against a stable contract.
- **Possible interpretations:** one of the four existing drafts should be promoted to frozen (mirroring how `SourceCandidate` was resolved), or a new shape should be authored that reconciles all four, or subtitles are deferred out of V0.1 scope entirely.
- **Evidence available:** `docs/architecture/13-roadmap.md`'s V0.1 freeze scope explicitly places `/subtitles` under `NOT YET ADVERTISED`, and no V0.1-frozen contract (`SourceCandidate`, `Stream`) has a required dependency on `SubtitleCandidate` (`SourceCandidate.language.subtitle` is a plain string array of language codes, not a `SubtitleCandidate` reference).
- **Decision:** subtitles, and `SubtitleCandidate`, are deferred to V0.2+; no draft is promoted to frozen for V0.1. See [`ADR-005`](./ADR-005-subtitle-v0.1-scope.md).
- **Decision rationale:** the roadmap's own explicit scope statement removes the need to pick a winner among four competing, none-clearly-final drafts; deferring avoids freezing a contract with no V0.1 consumer.
- **Status:** `RESOLVED` (deferred, not frozen) by `ADR-005` (2026-09-29).

### OPEN-4 — Two provider registry shapes coexist

- **Affected documents:** `docs/contracts/source-adapter.md`, `docs/architecture/04-providers.md` (`SourceRegistry` appears 4 times)
- **Observed contradiction:** the monolith starts with a single-purpose `SourceRegistry` class and later generalizes to `ProviderRegistry<T>` for sources/metadata/subtitles/catalogs, but never explicitly retires the earlier shape; `SourceRegistry` itself also appears 4 times in `04-providers.md` with growing responsibility (register/all/applicable → admission-aware → capability-aware).
- **Why it matters:** an implementer needs to know whether to build one generic registry or several specialized ones, and whether `SourceRegistry` is a specialization of `ProviderRegistry<SourceAdapter>` or a wholly separate, superseded class.
- **Possible interpretations:** (1) `ProviderRegistry<T>` supersedes `SourceRegistry` entirely. (2) `SourceRegistry` remains as a thin, source-specific convenience wrapper over `ProviderRegistry<SourceAdapter>`.
- **Evidence available:** both shapes captured verbatim in `docs/contracts/source-adapter.md`; `04-providers.md`'s own text frames the generic shape as something `SourceRegistry` "can eventually become," not a present-tense replacement; `13-roadmap.md`'s V0.1 `PROVIDER` scope lists exactly one provider kind (`operator-owned media library`), with metadata/subtitle/catalog providers explicitly `NOT YET ADVERTISED`.
- **Decision:** `SourceRegistry` (sources only) is the V0.1-frozen registry. `ProviderRegistry<T>` is explicitly PROPOSED/DEFERRED to V0.2+, for when a second provider kind is actually introduced. See [`ADR-003`](./ADR-003-provider-registry-ownership.md).
- **Decision rationale:** V0.1 has nothing else for a generalized registry to register; freezing the generic form now would be guessing at an interface with no current consumer.
- **Status:** `RESOLVED` by `ADR-003` (2026-09-29).

### OPEN-5 — Early `MediaRef` drafts embed external identifiers directly

- **Affected documents:** `docs/contracts/identity.md`, `docs/architecture/02-domain.md` (3 non-frozen `MediaRef` occurrences)
- **Observed contradiction:** the frozen `MediaRef` (`type`, `id`, `season?`, `episode?`) keeps external identifiers out and delegates them to `ExternalIdentity`. Three earlier drafts in `02-domain.md` instead put `imdbId?: string` and `tmdbId?: string` directly on `MediaRef`.
- **Why it matters:** these are architecturally incompatible designs of "what a media reference is." Mixing them would let identity data leak into what is meant to be a protocol-neutral, identity-free reference type.
- **Possible interpretations:** the identifier-bearing drafts are early, pre-identity-layer thinking, superseded once `ExternalIdentity`/`CanonicalMedia` were introduced.
- **Evidence available:** all four `MediaRef` shapes extracted and diffed field-by-field during this audit (2026-09-29); the frozen shape is also the only one that appears unchanged in the identity-layer-era sections of the monolith.
- **Decision:** the three identifier-bearing drafts are treated as **SUPERSEDED** by the frozen `MediaRef` + `ExternalIdentity` split.
- **Decision rationale:** the identity-bearing `MediaRef` predates the entire identity layer (§384+ in the original monolith numbering); every occurrence written after the identity layer was introduced uses the identifier-free shape. Chronological + majority evidence supports treating the split design as authoritative, not a coin flip.
- **Status:** `RESOLVED` (superseded, not merged) — recorded here rather than silently deleted; the superseded text remains in `docs/architecture/02-domain.md`, annotated in place.

### OPEN-6 — `CanonicalMedia` has three non-equivalent historical shapes

- **Affected documents:** `docs/contracts/identity.md`, `docs/architecture/02-domain.md` (3 non-frozen `CanonicalMedia` occurrences)
- **Observed contradiction:** one draft conflates identity with presentation fields (`title`, `year`, `imdbId`, `tmdbId` all directly on `CanonicalMedia`); one represents `identities` as `ReadonlyMap<IdentityKind, string>` (no per-identity provenance); the frozen shape uses `readonly ExternalIdentity[]` (full provenance per identity).
- **Why it matters:** the `Map`-based draft cannot represent *when* or *from which source* an identity was observed — it silently loses the evidence-preservation invariant that the rest of the documentation set treats as load-bearing (see `docs/architecture/07-evidence.md`).
- **Possible interpretations:** the frozen, provenance-preserving shape is correct; the other two are earlier design stages that predate the evidence model being formalized.
- **Evidence available:** all four shapes extracted and diffed during this audit (2026-09-29).
- **Decision:** the presentation-conflated and `Map`-based drafts are treated as **SUPERSEDED**.
- **Decision rationale:** the frozen shape is the only one consistent with the evidence-preservation invariants stated repeatedly and explicitly in `07-evidence.md`, which post-dates both superseded drafts in the monolith's own narrative order.
- **Status:** `RESOLVED` (superseded, not merged) — annotated in place in `docs/architecture/02-domain.md`.

### OPEN-7 — An early `SourceCandidate` draft represents authorization as a boolean

- **Affected documents:** `docs/contracts/stream.md`, `docs/architecture/02-domain.md`
- **Observed contradiction:** the earliest `SourceCandidate` draft has `capabilities.authorized: boolean`. Every later occurrence, `README.md`, and `docs/architecture/05-policy.md` treat authorization as an explicit tri-state (`"authorized" | "unknown" | "denied"`), with the invariant that `unknown` must never be silently treated as `authorized`. A boolean field cannot represent `unknown` at all.
- **Why it matters:** this is not a stylistic difference — implementing the boolean shape would make the "`unknown` is never `authorized`" invariant impossible to express, let alone enforce.
- **Possible interpretations:** none plausible other than supersession; the boolean shape is incompatible with a core, repeatedly-stated invariant.
- **Evidence available:** the tri-state model appears in `README.md`, `docs/architecture/05-policy.md`, and the frozen `docs/contracts/stream.md`, i.e. in every later and higher-authority location.
- **Decision:** the boolean-authorization draft is **SUPERSEDED**.
- **Decision rationale:** keeping it live would contradict a core safety invariant stated in multiple authoritative locations; there is no ambiguity to preserve.
- **Status:** `RESOLVED` (superseded) — annotated in place, not deleted.

### OPEN-8 — `SourceAdapter` has 6 shapes; the frozen one may be the wrong tier

- **Affected documents:** `docs/contracts/source-adapter.md`, `docs/architecture/04-providers.md`
- **Observed contradiction:** the frozen `SourceAdapter` operates on a raw `MediaRef` and a single `supports()` check. The monolith's **last and most evolved** `SourceAdapter` draft instead splits `supportsMedia()`/`supportsIdentity()` and resolves against a `CanonicalMedia` (i.e., an already identity-resolved reference) plus declares `capabilities: SourceCapabilities`.
- **Why it matters:** this changes where identity resolution sits relative to adapter selection. The frozen contract implies adapters see identity-unresolved requests; the later draft implies adapters are only ever invoked after identity resolution and capability negotiation. `docs/architecture/03-resolution.md` describes a pipeline with `identity resolution → adapter selection`, which is actually more consistent with the *later*, identity-aware adapter shape than with the currently-frozen one.
- **Possible interpretations:** (1) the frozen shape is the correct v0.1 minimal contract, and the identity/capability-aware shape is a deliberately deferred v-next extension (consistent with `docs/architecture/13-roadmap.md`'s V0.1 freeze scope). (2) The frozen shape is wrong and should be replaced by the identity-aware one to match the documented pipeline order in `03-resolution.md`.
- **Evidence available:** both shapes extracted verbatim; the pipeline-order description in `03-resolution.md` was cross-checked during a second, independent pass (2026-09-29) across three separate sections — "Identity Layer in the Complete Pipeline," "Resulting Source-Selection Algorithm," and "Parallel vs sequential orchestration" — all three independently show `identity resolution → CanonicalMedia → adapter selection → resolve()`, not the reverse; `04-providers.md`'s own concluding sentence on its most-evolved draft states "source execution is based on resolved identity."
- **Decision:** interpretation (2) — the identity/capability-aware shape (Model C, with `health()` merged back in from the minimal draft) is adopted as the V0.1 `SourceAdapter` contract: `supportsMedia(MediaRef)` pre-identity filter, `supportsIdentity(ExternalIdentity[])` post-identity filter, `resolve(CanonicalMedia, ResolveContext)`. The previously-frozen minimal, `MediaRef`-only shape is now HISTORICAL/SUPERSEDED. See [`ADR-001`](./ADR-001-source-adapter-identity-boundary.md).
- **Decision rationale:** three independent pipeline descriptions in `03-resolution.md`, plus `04-providers.md`'s own narrative conclusion, converge on identity-before-adapter-selection; this is repository evidence, not a stylistic preference, and directly contradicts the previously-frozen minimal shape rather than merely extending it.
- **Status:** `RESOLVED` by `ADR-001` (2026-09-29). Note: resolving this surfaced a new follow-up, `OPEN-11` below (the `SourceRegistry.applicable()` method needs re-specification for the new two-stage filter).

### OPEN-9 — `ResolveContext.locale` / `userConfig` dropped, not frozen

- **Affected documents:** `docs/contracts/source-adapter.md`
- **Observed contradiction:** the very first `ResolveContext` draft included optional `locale?: string` and `userConfig?: Record<string, unknown>`. Four later, independent occurrences all converged on a smaller shape without those two fields.
- **Why it matters:** per-request locale/user-config plumbing may still be needed (e.g. for subtitle language preference, mentioned elsewhere in `docs/architecture/04-providers.md`), but there is no frozen mechanism for it once `locale`/`userConfig` are dropped from `ResolveContext`.
- **Possible interpretations:** (1) locale/user-config plumbing happens elsewhere (e.g. baked into `MediaRef` or a separate per-request preferences object) and dropping it from `ResolveContext` was intentional. (2) it was dropped by accident across drafts and should be restored.
- **Evidence available:** convergence pattern documented in `docs/contracts/source-adapter.md`.
- **Decision:** none yet.
- **Decision rationale:** N/A — proposed extension, not frozen either way.
- **Status:** `OPEN`, low severity (additive question, does not block freezing the smaller `ResolveContext` shape).

### OPEN-10 — `IdentityResolution` (3 states) vs. `IdentityReceipt.outcome` (4 states)

- **Affected documents:** `docs/architecture/02-domain.md` (`IdentityResolution`), `docs/architecture/07-evidence.md` (`IdentityReceipt`)
- **Observed contradiction:** `IdentityResolution` is a discriminated union with 3 states (`resolved`, `ambiguous`, `not_found`). `IdentityReceipt.outcome` has 4 states, adding `not_resolved` (distinct from `not_found` — e.g. a provider timeout/error vs. a genuine negative identity match).
- **Why it matters:** an implementer cannot represent "identity resolution attempt failed to complete" using `IdentityResolution` alone; it would have to be force-fit into `not_found`, conflating a negative result with an incomplete one.
- **Possible interpretations:** (1) `IdentityResolution` should gain a 4th `not_resolved` state to match `IdentityReceipt`. (2) `IdentityReceipt.outcome`'s `not_resolved` is receipt-only bookkeeping (e.g. "we have a receipt but no observations succeeded") and never needs to flow back into `IdentityResolution`.
- **Evidence available:** both type definitions located and compared during the 2026-09-29 normalization pass (discovered as a side effect of `ADR-002`).
- **Decision:** none yet.
- **Decision rationale:** insufficient evidence to prefer (1) or (2); does not block the V0.1 freeze because no currently-frozen V0.1 contract branches on `IdentityResolution` needing a 4th state.
- **Status:** `OPEN`, low severity, **non-blocking** for `CONTRACT_FREEZE`.

### OPEN-11 — `SourceRegistry.applicable()` still calls the pre-`ADR-001` `supports()` method

- **Affected documents:** `docs/contracts/source-adapter.md`
- **Observed contradiction:** the `SourceRegistry` code sample's `applicable(media: MediaRef)` method calls `adapter.supports(media)`. `ADR-001` replaced `supports()` with `supportsMedia()`/`supportsIdentity()`, a two-stage (pre-identity / post-identity) filter. The registry sample was not rewritten to avoid inventing an unreviewed method signature.
- **Why it matters:** an implementer copying `SourceRegistry` verbatim would write code against a method (`supports`) that no longer exists on `SourceAdapter`. This is a direct, mechanical consequence of `ADR-001` that has not yet been designed.
- **Possible interpretations:** (1) split `applicable()` into `applicableByMedia(media: MediaRef)` (pre-identity) and `applicableByIdentity(identities: readonly ExternalIdentity[])` (post-identity). (2) keep one `applicable()` method with an overload or a discriminated parameter. (3) move filtering entirely out of the registry and into the resolver.
- **Evidence available:** `ADR-001`'s new `SourceAdapter` shape; no evidence yet on which registry-method-splitting approach the rest of the pipeline expects.
- **Decision:** none yet — flagged explicitly in `docs/contracts/source-adapter.md` rather than silently patched with a guessed signature.
- **Decision rationale:** picking a specific method split without pipeline-level evidence for how the resolver calls the registry at each stage would be inventing a contract, not extracting one.
- **Status:** `OPEN`, **blocking for `SourceRegistry` implementation**, non-blocking for the identity/adapter-boundary decision itself (`ADR-001` is otherwise fully decided).

### OPEN-12 — `ResolutionResult` has no canonical contract-file home

- **Affected documents:** `docs/contracts/stream.md`, `docs/architecture/02-domain.md`, `docs/architecture/03-resolution.md`, `docs/architecture/13-roadmap.md`
- **Observed contradiction:** `13-roadmap.md`'s V0.1 `CORE` scope explicitly lists `ResolutionResult`, but it was never given a home in `docs/contracts/`. Two non-identical drafts exist: `02-domain.md` (`{ media: MediaRef, status: ResolutionStatus, candidates, failures, sourceCount, durationMs }`) and `03-resolution.md` (`{ media, executions, candidates }`, no `status`/`failures`/`sourceCount`/`durationMs`, plus an inline `resolveMedia()` function that produces it). Neither draft uses `CanonicalMedia` for the `media` field even though, per `ADR-001`, source resolution now happens after identity resolution.
- **Why it matters:** this is a V0.1-CORE-listed type with two competing shapes and no frozen owner — exactly the kind of gap that would let two implementers diverge while both believing they followed the docs.
- **Possible interpretations:** (1) `02-domain.md`'s richer shape is canonical (more complete, and part of the same already-frozen domain-module sequence as `MediaRef`/`SourceCandidate`). (2) `03-resolution.md`'s shape is canonical (it's the one actually returned by the one worked-through `resolveMedia()` implementation sketch). (3) Both need reconciling, and `media` should be updated to `CanonicalMedia` to stay consistent with `ADR-001`.
- **Evidence available:** both shapes extracted verbatim during the 2026-09-29 normalization pass; discovered as a side effect of auditing V0.1 CORE scope against `docs/contracts/`.
- **Decision:** none yet. This was discovered late in this pass and evidence does not clearly favor one draft strongly enough to avoid guessing (richness alone is not sufficient justification, unlike the chronological/majority evidence available for `OPEN-5`/`OPEN-6`/`OPEN-7`).
- **Decision rationale:** N/A — left explicitly open rather than silently resolved.
- **Status:** `OPEN`, **BLOCKING for `CONTRACT_FREEZE`** — `ResolutionResult` is named in the V0.1 CORE scope and has no single, unambiguous, frozen shape.

### RESOLVED-2 — `README.md` placed Identity/`CanonicalMedia` in a later roadmap phase, contradicting `13-roadmap.md`'s V0.1 scope

- **Affected documents:** `README.md` ("Current scope", "Roadmap Phase 2 — Identity"), `docs/architecture/13-roadmap.md`
- **Observed contradiction:** `README.md`'s "Current scope" checklist did not list identity/`CanonicalMedia` as part of the initial release, and its "Phase 2 — Identity" roadmap section implied identity resolution was a later expansion stage. `13-roadmap.md`'s explicit "V0.1 implementation freeze" `CORE` scope lists `CanonicalMedia` and `Identity` as part of V0.1 itself.
- **Why it matters:** an implementer reading only `README.md` could conclude identity resolution is out of scope for the first release, directly contradicting `13-roadmap.md` and `ADR-001`/`ADR-002` (which both assume identity resolution is a V0.1 concern).
- **Evidence available:** both documents' relevant sections read in full during the 2026-09-29 normalization pass; `13-roadmap.md`'s statement is later, more detailed, and explicitly framed as the authoritative "concrete next milestone."
- **Decision:** `13-roadmap.md` wins. `README.md`'s "Current scope" checklist was updated to list identity/`CanonicalMedia` as part of the initial release (with `ADR-001`/`ADR-002` cross-references), and "Phase 2 — Identity" was annotated as folded into the V0.1 conformance kernel, not a separate later phase.
- **Decision rationale:** `13-roadmap.md` is explicitly the more detailed, most-recently-written, and self-declared authoritative scope statement; `README.md`'s older phase breakdown predates it in the monolith's narrative order.
- **Status:** `RESOLVED` (2026-09-29) — both files updated; see `git diff` for this pass.

### RESOLVED-1 — `ResolveContext` frozen shape corrected to the converged draft

- **Affected documents:** `docs/contracts/source-adapter.md`
- **Observed contradiction:** the contract file originally froze a `ResolveContext` shape that appeared exactly **once** in the entire monolith (the very first draft), while four later, independent occurrences across `04-providers.md` and `06-runtime.md` converged on a different, smaller, fully-`readonly` shape.
- **Why it matters:** freezing the least-repeated, earliest draft as "the" contract would have contradicted the shape the design actually converged on and reused unchanged four times.
- **Possible interpretations:** N/A — evidence clearly favored the converged shape.
- **Evidence available:** line-by-line extraction of all 5 `ResolveContext` occurrences, performed during this audit (2026-09-29); see `docs/contracts/source-adapter.md`.
- **Decision:** `docs/contracts/source-adapter.md` now freezes the converged (4×-repeated) shape; the single-occurrence richer draft is tracked as `OPEN-9` (a possible future extension) rather than silently discarded.
- **Decision rationale:** repeated, independent convergence across later sections is stronger evidence of intended design than a single earliest draft — this is a repository-evidence-based correction, not a preference.
- **Status:** `RESOLVED`.

---

## How to add a new ADR

1. Create `docs/decisions/ADR-NNN-short-title.md` using the next sequential
   number.
2. State: context, decision, consequences, and status
   (`PROPOSED` / `ACCEPTED` / `SUPERSEDED` / `REJECTED`).
3. Link the ADR from this README and from any `docs/architecture/*.md` or
   `docs/contracts/*.md` file whose content it affects.
4. Never resolve a recorded `OPEN` entry by editing a contract file
   directly without recording the decision and rationale here first.
