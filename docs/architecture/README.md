# Architecture Documentation — Document Map

[⇧ Back to the architecture index](../architecture.md)

This directory contains the semantically partitioned architecture
documentation for StreamForge. It replaces the single `docs/architecture.md`
monolith (26,573 lines, 703 sections) that was used while the design was
being drafted. See `../architecture.md` for the top-level index, status
terminology, and maintenance rules.

| # | Document | Responsibility | Normative? | Primary dependencies |
|---|---|---|---|---|
| 01 | [`01-system.md`](./01-system.md) | System boundaries, topology, dependency direction; discovery ≠ authorization ≠ resolution ≠ ranking ≠ playback | Explanatory | `02-domain.md`, `04-providers.md`, `05-policy.md` |
| 02 | [`02-domain.md`](./02-domain.md) | Canonical protocol-neutral domain model and identity semantics | Normative (types) / Explanatory (rationale) | `../contracts/identity.md`, `../contracts/stream.md` |
| 03 | [`03-resolution.md`](./03-resolution.md) | Resolution pipeline: request → identity → adapter selection → parallel resolution → validation → dedup → policy filter → ranking → protocol mapping | Normative (invariants) / Explanatory (narrative) | `02-domain.md`, `04-providers.md`, `05-policy.md`, `../contracts/stream.md` |
| 04 | [`04-providers.md`](./04-providers.md) | Adapter lifecycle, capability declaration, isolation, health, registration, config | Explanatory (contract lives in `../contracts/source-adapter.md`) | `../contracts/source-adapter.md`, `05-policy.md`, `06-runtime.md` |
| 05 | [`05-policy.md`](./05-policy.md) | Caller authZ ≠ media authZ ≠ provider admission ≠ playback eligibility; unknown ≠ authorized | Normative | `02-domain.md`, `03-resolution.md` |
| 06 | [`06-runtime.md`](./06-runtime.md) | Request context, deadlines, cancellation, concurrency/rate limiting, circuit breakers, retries, caching, generations | Normative (invariants) / Explanatory (narrative) | `../contracts/runtime.md`, `09-control-plane.md` |
| 07 | [`07-evidence.md`](./07-evidence.md) | Evidence levels, receipts, provenance, replay, determinism, lineage | Normative | `../contracts/evidence.md` |
| 08 | [`08-protocols.md`](./08-protocols.md) | Stremio/HTTP/CLI protocol adapters, error algebra, partial success | Explanatory | `02-domain.md`, `03-resolution.md` |
| 09 | [`09-control-plane.md`](./09-control-plane.md) | Config lifecycle, generations, secrets separation, composition root, rollback | Normative (invariants) / Explanatory (narrative) | `06-runtime.md`, `05-policy.md`, `../contracts/runtime.md` |
| 10 | [`10-observability.md`](./10-observability.md) | Logging, request IDs, health/metrics/diagnostics, redaction | Explanatory | `06-runtime.md` |
| 11 | [`11-testing.md`](./11-testing.md) | Test strategy, CI gates, release-gate checklists, "no evidence, no VERIFIED claim" | Normative (gate discipline) / Explanatory (strategy) | all documents |
| 12 | [`12-deployment.md`](./12-deployment.md) | Local dev, containers, env/secrets, networking, health checks, shutdown, resource limits | Explanatory | `06-runtime.md`, `09-control-plane.md` |
| 13 | [`13-roadmap.md`](./13-roadmap.md) | Construction sequence and implementation status only | Explanatory | all documents |

## How to read "Normative?"

- **Normative** — the document (or the specific section/contract it points
  to) defines a requirement or exact interface. Deviating from it without
  updating the document is a defect.
- **Explanatory** — the document explains rationale, historical design
  narrative, or how normative pieces fit together. It should not be quoted
  as the source of truth for an exact interface shape; the contract files
  in `../contracts/` are.

Individual statements inside any document may still be marked
`NORMATIVE` / `EXPLANATORY` / `EXAMPLE` / `PROPOSED` / `OPEN` inline where
the document-level label in the table above is not precise enough (this is
most common in `03-resolution.md`, `06-runtime.md`, and `09-control-plane.md`,
which mix frozen invariants with still-evolving narrative from the original
monolith).

## Contracts

Exact interface/type definitions are **not** duplicated in the documents
above. They live once, each, in `../contracts/`:

- [`../contracts/source-adapter.md`](../contracts/source-adapter.md) — `SourceAdapter`, `ResolveContext`, `HealthResult`, provider registries
- [`../contracts/identity.md`](../contracts/identity.md) — `MediaRef`, `ExternalIdentity`, `CanonicalMedia`
- [`../contracts/stream.md`](../contracts/stream.md) — `SourceCandidate`, `Stream`, subtitle candidates
- [`../contracts/runtime.md`](../contracts/runtime.md) — `RuntimeSnapshot`, `ConfigurationTransaction`, `RuntimePolicy`, generation lifecycle
- [`../contracts/evidence.md`](../contracts/evidence.md) — the four evidence levels and receipt/evidence-graph shapes

## Decisions

Contradictions surfaced while migrating the monolith into this structure,
and any future architecture decisions, are recorded in
[`../decisions/README.md`](../decisions/README.md) rather than being
silently resolved.

## Audit

A deep documentation verification / contract-freeze audit was performed on
2026-09-29. Its findings (concept ownership matrix, contract-freeze status
per contract, protocol-leakage check, and precise blocking conditions) are
recorded in [`documentation-audit.md`](./documentation-audit.md). As of
that audit, **no contract in this repository is fully frozen** — see that
file and `../decisions/README.md` for exactly what remains open.

## Provenance of this structure

This directory was produced by migrating `docs/architecture.md` (a single
703-section, 26,573-line document written iteratively across many design
sessions) into topic-based files, in original section order within each
topic, with global `§N` numbering dropped in favor of descriptive headings.
No architectural content was deleted; see `../architecture.md` for the
migration summary and status terminology.
