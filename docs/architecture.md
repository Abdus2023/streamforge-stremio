# StreamForge Architecture — Index

## 1. Purpose

StreamForge is a legitimate, authorization-first Stremio addon for
multi-source stream aggregation — a Popcorn-Time-style *experience*
(one title → many sources → normalized metadata → ranked stream list)
built without embedding a torrent client, without scraping copyrighted
content, and without distributing anything the operator is not
authorized to distribute. This document is the entry point to the full
architecture documentation set. It does not contain the architecture
itself — it maps to where each part of it lives.

## 2. Scope

This index, and the documents it links to, cover the **design** of
StreamForge: domain model, resolution pipeline, provider/adapter
contract, authorization and policy model, runtime and control-plane
mechanics, evidence/provenance model, protocol surface, observability,
testing strategy, deployment shape, and the implementation roadmap.
It does not cover product/business decisions, and it does not grant or
imply authorization to access any specific third-party service — that
remains an operator responsibility described in `05-policy.md`.

## 3. Architecture map

```text
   caller (Stremio / HTTP / CLI)
              │
      ┌───────┴────────┐
      │ Protocol layer  │  08-protocols.md
      └───────┬────────┘
              │
      ┌───────┴────────┐
      │ Resolution      │  03-resolution.md  (identity, dedup, ranking)
      │ pipeline        │
      └───────┬────────┘
       ┌───────┼────────┐
       │       │        │
  ┌────┴──┐ ┌──┴───┐ ┌──┴────┐
  │Policy │ │Domain│ │Providers│   05-policy.md / 02-domain.md / 04-providers.md
  └────┬──┘ └──────┘ └──┬────┘
       │                │
  ┌────┴────────────────┴───┐
  │  Runtime & control plane │   06-runtime.md / 09-control-plane.md
  └────┬──────────────────┬─┘
       │                  │
  ┌────┴───┐        ┌─────┴─────┐
  │Evidence│        │Observability│   07-evidence.md / 10-observability.md
  └────────┘        └────────────┘

  Cross-cutting: 11-testing.md (verification), 12-deployment.md (ops),
  13-roadmap.md (what actually exists vs. what is designed)
```

## 4. Document map

Full responsibility/normativity/dependency matrix:
[`docs/architecture/README.md`](./architecture/README.md).

| Document | Covers |
|---|---|
| [`architecture/01-system.md`](./architecture/01-system.md) | Boundaries, topology, dependency direction |
| [`architecture/02-domain.md`](./architecture/02-domain.md) | Canonical domain model, identity semantics |
| [`architecture/03-resolution.md`](./architecture/03-resolution.md) | Resolution pipeline, ranking, dedup |
| [`architecture/04-providers.md`](./architecture/04-providers.md) | Adapter lifecycle, capability, isolation |
| [`architecture/05-policy.md`](./architecture/05-policy.md) | Authorization, admission, eligibility |
| [`architecture/06-runtime.md`](./architecture/06-runtime.md) | Execution mechanics, caching, generations |
| [`architecture/07-evidence.md`](./architecture/07-evidence.md) | Evidence levels, receipts, provenance |
| [`architecture/08-protocols.md`](./architecture/08-protocols.md) | Stremio/HTTP/CLI protocol adapters |
| [`architecture/09-control-plane.md`](./architecture/09-control-plane.md) | Config lifecycle, generations, secrets |
| [`architecture/10-observability.md`](./architecture/10-observability.md) | Logging, metrics, health, redaction |
| [`architecture/11-testing.md`](./architecture/11-testing.md) | Test strategy, CI gates |
| [`architecture/12-deployment.md`](./architecture/12-deployment.md) | Local dev, containers, ops |
| [`architecture/13-roadmap.md`](./architecture/13-roadmap.md) | Construction sequence, implementation status |

Normative interface contracts (defined once, linked everywhere):
[`docs/contracts/`](./contracts/) — `source-adapter.md`, `identity.md`,
`stream.md`, `runtime.md`, `evidence.md`.

Architecture decisions and open contradictions:
[`docs/decisions/README.md`](./decisions/README.md).

## 5. Normative vs. explanatory

Every document in `docs/architecture/` is labeled **Normative** or
**Explanatory** in the document map (§4, and in full in
`architecture/README.md`):

- **Normative** text states a requirement or an exact interface. The
  exact interface shapes are never normative *inside* an architecture
  document — they live once in `docs/contracts/*.md`, which architecture
  documents link to instead of redefining.
- **Explanatory** text gives rationale, historical narrative, or shows
  how normative pieces compose. It must not be read as a frozen
  interface definition.

Within a document, individual statements may carry an inline tag —
`NORMATIVE` / `EXPLANATORY` / `EXAMPLE` / `PROPOSED` / `OPEN` — where the
document-level label isn't precise enough. An `EXAMPLE` never silently
becomes a requirement just because it appears in prose next to one.

## 6. Status terminology

Every non-trivial claim about the system should be read against one of:

| Status | Meaning |
|---|---|
| `IMPLEMENTED` | Working code exists in this repository and matches the claim. |
| `PARTIALLY_IMPLEMENTED` | Some code exists, but it does not yet fully satisfy the claim. |
| `DESIGNED` | The architecture is specified in enough detail to implement, but no code exists yet. |
| `PROPOSED` | An idea/direction has been written down but is not yet a settled design. |
| `OPEN` | An explicit open question or contradiction, not yet resolved (see §8 and `decisions/README.md`). |

The same distinction chain applies throughout:
**DESIGNED ≠ IMPLEMENTED ≠ EXECUTED ≠ VERIFIED.** Passing a design review
is not "implemented." Writing code is not "executed." Running code once
locally is not "verified" — verification requires the evidence described
in `architecture/11-testing.md`.

## 7. Implementation / repository mapping

As of this revision, the repository contains:

- `README.md`, `package.json` (identity fields only: name, version
  `0.1.0`, license, `engines.node >= 22` — no dependencies, no scripts)
- `docs/architecture.md` (this index), `docs/architecture/*.md`,
  `docs/contracts/*.md`, `docs/decisions/README.md`

There is **no** `src/`, `test/`, `Dockerfile`, `compose.yaml`,
`tsconfig.json`, or CI workflow anywhere in this repository.

**Consequence:** every architectural claim in `docs/architecture/` and
`docs/contracts/` is `DESIGNED` or `PROPOSED`, not `IMPLEMENTED`, unless a
specific sentence states otherwise with a concrete repository reference
(file path, commit hash, or CI run link). See
[`architecture/13-roadmap.md`](./architecture/13-roadmap.md) for the
authoritative implemented/partial/next/future/blocked breakdown, and
[`architecture/11-testing.md`](./architecture/11-testing.md) for why local
inspection is never treated as a substitute for real CI execution.

## 8. Open questions

See [`docs/decisions/README.md`](./decisions/README.md) for the full,
current list of `OPEN — architectural contradiction` items surfaced while
migrating this documentation (as of this revision: `HealthResult` vs. the
provider health state machine, `CanonicalMedia` confidence, the
unfrozen subtitle candidate shape, and the two coexisting provider
registry shapes). Do not resolve any of these by silently editing a
contract file — open or update an ADR first.

## 9. Provenance of this document set

This documentation set was produced by migrating a single 703-section,
26,573-line `docs/architecture.md` monolith (written iteratively across
many design sessions) into the topic-partitioned structure described
above. All content was moved, not deleted; global `§N` numbering was
dropped in favor of descriptive headings and per-document anchors.
No source code was changed as part of this migration — none existed to
change. A temporary migration matrix (original section → destination
document) was used during the split and is not part of this repository.

## 10. Maintenance rules

1. **Single ownership per concept.** If you are about to write more than
   a sentence re-explaining something that already has a home (e.g. the
   `SourceAdapter` shape, an evidence level, a policy distinction), link
   to that document/contract instead of duplicating it.
2. **Contracts change alone.** Interface/type shapes are edited only in
   `docs/contracts/*.md`. Architecture documents may explain a contract
   but must not restate its exact fields as if they were a second source
   of truth.
3. **No silent status inflation.** Do not change a claim from `DESIGNED`
   to `IMPLEMENTED` without a concrete repository reference (file, commit,
   or CI run) in the same edit.
4. **No silent contradiction resolution.** If migrating or editing text
   surfaces two documents disagreeing, record it in
   `docs/decisions/README.md` as `OPEN — architectural contradiction` (or
   as an ADR) — do not just pick one and delete the other silently.
5. **Keep this index thin.** This file should stay roughly 100–250 lines.
   If it starts accumulating architecture detail, that detail belongs in
   `docs/architecture/*.md` instead.

## 11. Where to start reading

- New to the project? Start with
  [`architecture/01-system.md`](./architecture/01-system.md).
- Implementing an adapter? Start with
  [`contracts/source-adapter.md`](./contracts/source-adapter.md), then
  [`architecture/04-providers.md`](./architecture/04-providers.md) and
  [`architecture/05-policy.md`](./architecture/05-policy.md).
- Checking what's actually built vs. only designed? Go straight to
  [`architecture/13-roadmap.md`](./architecture/13-roadmap.md).
