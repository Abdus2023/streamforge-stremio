# Architecture Decisions

[⇧ Back to the architecture index](../architecture.md)

This is the index of architecture decision records (ADRs) for StreamForge,
and of contradictions that were surfaced but not yet resolved while
migrating `docs/architecture.md` from a single monolith into
`docs/architecture/` + `docs/contracts/` (see the migration note in
`../architecture.md`).

No formal, numbered ADRs existed before this migration — the design was
recorded as a single narrative document. The items below are the first
entries in this log. Future architecture decisions should be added here as
`ADR-NNN-title.md` files (or as dated entries in this README if the
decision is small); none exist yet, so no ADR files have been created in
this pass.

## Open contradictions found during migration

These are recorded as `OPEN — architectural contradiction` rather than
silently resolved, per the migration rules. Resolving any of them requires
an explicit ADR before the affected contract file is changed.

### OPEN-1 — `HealthResult` vs. the provider health state machine

- **Where:** [`../contracts/source-adapter.md`](../contracts/source-adapter.md) (`HealthResult`) vs. [`../architecture/06-runtime.md`](../architecture/06-runtime.md) ("Health state machine", "Source health versus candidate health")
- **Issue:** The original monolith defines a minimal `HealthResult { healthy, checkedAt, detail? }` early on (§4/§232), then later (control-plane era) discusses a richer per-provider health/circuit-breaker state without folding it back into a single revised `HealthResult` shape.
- **Status:** OPEN. Both describe "is this provider currently good to call," but have not been reconciled field-by-field.
- **Resolution needed:** Decide whether `HealthResult` is extended to carry circuit-breaker state directly, or whether health (liveness) and circuit-breaker state (execution policy) are intentionally two separate types. Record the decision as `ADR-001` before implementation begins.

### OPEN-2 — `CanonicalMedia` has no `confidence` field

- **Where:** [`../contracts/identity.md`](../contracts/identity.md) (`CanonicalMedia`) vs. [`../architecture/02-domain.md`](../architecture/02-domain.md) ("Identity Confidence")
- **Issue:** The monolith introduces "Identity Confidence" as an important concept for representing how sure the system is about a canonical identity mapping, but the frozen `CanonicalMedia` shape captured in the contract file has no confidence field, and no other type was shown carrying it.
- **Status:** OPEN.
- **Resolution needed:** Decide where confidence is recorded — per-`ExternalIdentity`, per-`CanonicalMedia`, or as a separate evidence artifact (see `../contracts/evidence.md`) — before implementation.

### OPEN-3 — Subtitle candidate shape never frozen

- **Where:** [`../contracts/stream.md`](../contracts/stream.md) ("Subtitle candidate") vs. [`../architecture/04-providers.md`](../architecture/04-providers.md) and [`../architecture/08-protocols.md`](../architecture/08-protocols.md)
- **Issue:** The monolith discusses a subtitle candidate model, subtitle ranking, and subtitle deduplication extensively, and states subtitles "follow the same candidate model" as source candidates, but never states a single frozen TypeScript shape for a subtitle candidate the way it does for `SourceCandidate`.
- **Status:** OPEN.
- **Resolution needed:** Freeze a `SubtitleCandidate` shape (language tag, format, provenance, dedup key) in `../contracts/stream.md` before subtitle support is implemented.

### OPEN-4 — Two provider registry shapes coexist

- **Where:** [`../contracts/source-adapter.md`](../contracts/source-adapter.md) ("Provider / adapter registry")
- **Issue:** The monolith starts with a single-purpose `SourceRegistry` and later generalizes to `ProviderRegistry<T>` for sources/metadata/subtitles/catalogs, but never explicitly retires the earlier shape.
- **Status:** OPEN, lower severity — this looks like intentional evolution rather than a true contradiction, but it has not been stated as such.
- **Resolution needed:** State explicitly (in an ADR or in `../contracts/source-adapter.md`) that `ProviderRegistry<T>` supersedes `SourceRegistry`, or that both are expected to coexist and why.

## How to add a new ADR

1. Create `docs/decisions/ADR-NNN-short-title.md` using the next sequential
   number.
2. State: context, decision, consequences, and status
   (`PROPOSED` / `ACCEPTED` / `SUPERSEDED` / `REJECTED`).
3. Link the ADR from this README and from any `docs/architecture/*.md` or
   `docs/contracts/*.md` file whose content it affects.
4. Never resolve a recorded `OPEN — architectural contradiction` by editing
   a contract file directly without an accompanying ADR explaining why.
