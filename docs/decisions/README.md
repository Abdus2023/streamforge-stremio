# Architecture Decisions

[⇧ Back to the architecture index](../architecture.md)

This is the contradiction/decision ledger for StreamForge. No formal,
numbered ADRs existed before the documentation split; this file is both
the ADR index (currently empty — no `ADR-NNN-*.md` files exist yet) and
the ledger of contradictions surfaced while migrating and auditing the
documentation.

**Rule:** an entry moves from `OPEN` to `RESOLVED` only when there is a
stated decision *and* a stated rationale grounded in repository evidence
(not a guess). If a reconciliation cannot be justified from existing
evidence, it stays `OPEN` — see `docs/architecture.md`, "Maintenance
rules."

Last updated: 2026-09-29 (deep documentation verification / contract-freeze
audit pass).

---

### OPEN-1 — `HealthResult` vs. `SourceHealth` (two shapes) vs. circuit-breaker state

- **Affected documents:** `docs/contracts/source-adapter.md`, `docs/architecture/04-providers.md` (`interface SourceHealth { successes; failures; timeouts; latencyMs }`), `docs/architecture/10-observability.md` (`interface SourceHealth { adapterId; requests; successes; empty; failures; timeoutCount; consecutiveFailures; latency: {p50,p95,p99} }`), `docs/architecture/06-runtime.md` ("Health state machine", `CircuitBreaker`/`BreakerState`)
- **Observed contradiction:** at least three different "is this provider okay" shapes exist and none reference each other: a point-in-time `HealthResult` (frozen contract), a simple provider-local counter struct `SourceHealth` in `04-providers.md`, and a richer metrics-oriented `SourceHealth` in `10-observability.md`.
- **Why it matters:** an implementer cannot tell whether these are (a) the same concept renamed across drafts, (b) three legitimately different layers (point-in-time probe / running counters / exported metrics snapshot), or (c) two accidental duplicates plus one real concept.
- **Possible interpretations:** (1) `HealthResult` = adapter-authored point-in-time probe; provider-local `SourceHealth` = internal counters the runtime keeps to *decide* health/circuit state; observability `SourceHealth` = a *derived, exported* snapshot for metrics — three legitimately distinct layers that only need distinct names to stop looking like duplicates. (2) The two `SourceHealth` structs are an accidental duplicate that should be merged.
- **Evidence available:** field-level diffs performed during this audit (2026-09-29); no code exists to check against.
- **Decision:** none yet.
- **Decision rationale:** insufficient evidence to prefer interpretation (1) or (2) over the other without an implementer choosing an actual consumer for each struct.
- **Status:** `OPEN`.

### OPEN-2 — Identity confidence exists in the design but is not wired into the frozen identity contract

- **Affected documents:** `docs/contracts/identity.md` (`CanonicalMedia`, `ExternalIdentity`), `docs/architecture/07-evidence.md` (`MediaIdentity`, `IdentityEvidence { provider; matchedBy; confidence: "verified"|"probable"|"ambiguous" }`)
- **Observed contradiction:** `docs/architecture/02-domain.md` discusses "Identity Confidence" as an important concept, and `07-evidence.md` independently defines a full evidence-bearing identity model (`MediaIdentity`/`IdentityEvidence`) that already includes a `confidence` field — but the frozen `CanonicalMedia`/`ExternalIdentity` contract has no confidence field and does not reference `MediaIdentity`/`IdentityEvidence` at all.
- **Why it matters:** confidence is not an unmet requirement — it is a requirement that was already designed once, in a different type family, and never connected to the type family that got frozen. Implementing against the frozen contract alone would silently drop confidence tracking.
- **Possible interpretations:** (1) `ExternalIdentity` gains a `confidence` field directly. (2) `CanonicalMedia` gains an `readonly evidence: readonly IdentityEvidence[]` field alongside `identities`. (3) `MediaIdentity`/`CanonicalMedia` are the same concept under two names and should be merged into one type.
- **Evidence available:** exact type definitions of both families, located and diffed during this audit (2026-09-29).
- **Decision:** none yet — this requires a design choice, not just a textual reconciliation.
- **Decision rationale:** merging two independently-designed type families without an implementer present to validate call sites would be guessing, not resolving.
- **Status:** `OPEN`.

### OPEN-3 — Subtitle candidate shape never frozen

- **Affected documents:** `docs/contracts/stream.md`, `docs/architecture/04-providers.md`, `docs/architecture/08-protocols.md`, `docs/architecture/02-domain.md` (`SubtitleCandidate` appears 3 times with different fields)
- **Observed contradiction:** the monolith discusses a subtitle candidate model, subtitle ranking, and subtitle deduplication extensively, and states subtitles "follow the same candidate model" as source candidates, but `SubtitleCandidate` is defined 3 different times in `02-domain.md` alone with different fields, and none is marked as canonical.
- **Why it matters:** without a frozen shape, subtitle provider adapters and the subtitle ranking/dedup pipeline cannot be implemented against a stable contract.
- **Possible interpretations:** one of the three existing drafts should be promoted to frozen (mirroring how `SourceCandidate` was resolved), or a new shape should be authored that reconciles all three.
- **Evidence available:** three non-identical `SubtitleCandidate` definitions located in `02-domain.md`; not yet diffed field-by-field in this pass (scope limitation — see final report).
- **Decision:** none yet.
- **Decision rationale:** N/A.
- **Status:** `OPEN`.

### OPEN-4 — Two provider registry shapes coexist

- **Affected documents:** `docs/contracts/source-adapter.md`, `docs/architecture/04-providers.md` (`SourceRegistry` appears 4 times)
- **Observed contradiction:** the monolith starts with a single-purpose `SourceRegistry` class and later generalizes to `ProviderRegistry<T>` for sources/metadata/subtitles/catalogs, but never explicitly retires the earlier shape; `SourceRegistry` itself also appears 4 times in `04-providers.md` with growing responsibility (register/all/applicable → admission-aware → capability-aware).
- **Why it matters:** an implementer needs to know whether to build one generic registry or several specialized ones, and whether `SourceRegistry` is a specialization of `ProviderRegistry<SourceAdapter>` or a wholly separate, superseded class.
- **Possible interpretations:** (1) `ProviderRegistry<T>` supersedes `SourceRegistry` entirely. (2) `SourceRegistry` remains as a thin, source-specific convenience wrapper over `ProviderRegistry<SourceAdapter>`.
- **Evidence available:** both shapes captured verbatim in `docs/contracts/source-adapter.md`.
- **Decision:** none yet.
- **Decision rationale:** this looks like intentional evolution rather than a true conflict, but has not been stated as such anywhere in the source material.
- **Status:** `OPEN`, lower severity.

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
- **Evidence available:** both shapes extracted verbatim; the pipeline-order description in `03-resolution.md` was cross-checked during this audit and is more consistent with interpretation (1) treated as "not yet extended" rather than "wrong."
- **Decision:** none yet — this cannot be resolved without an implementer deciding the v0.1 boundary explicitly.
- **Decision rationale:** both interpretations are internally consistent; picking one without an ADR would be exactly the kind of silent resolution this ledger exists to prevent.
- **Status:** `OPEN` — highest-priority open item before any `SourceAdapter` implementation begins.

### OPEN-9 — `ResolveContext.locale` / `userConfig` dropped, not frozen

- **Affected documents:** `docs/contracts/source-adapter.md`
- **Observed contradiction:** the very first `ResolveContext` draft included optional `locale?: string` and `userConfig?: Record<string, unknown>`. Four later, independent occurrences all converged on a smaller shape without those two fields.
- **Why it matters:** per-request locale/user-config plumbing may still be needed (e.g. for subtitle language preference, mentioned elsewhere in `docs/architecture/04-providers.md`), but there is no frozen mechanism for it once `locale`/`userConfig` are dropped from `ResolveContext`.
- **Possible interpretations:** (1) locale/user-config plumbing happens elsewhere (e.g. baked into `MediaRef` or a separate per-request preferences object) and dropping it from `ResolveContext` was intentional. (2) it was dropped by accident across drafts and should be restored.
- **Evidence available:** convergence pattern documented in `docs/contracts/source-adapter.md`.
- **Decision:** none yet.
- **Decision rationale:** N/A — proposed extension, not frozen either way.
- **Status:** `OPEN`, low severity (additive question, does not block freezing the smaller `ResolveContext` shape).

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
