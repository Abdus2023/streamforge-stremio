# Freeze-gate checklist (generic template)

A "freeze gate" is a named list of items, each graded `PASS`/`BLOCKED`,
that must all pass before implementation work is authorized to begin on
top of a documentation-as-contract layer. Adapt the middle, domain-specific
items to the project; keep the structural ones (1–3, and the last one) in
every freeze gate regardless of domain.

1. **Documentation Partition** — is there a clean split between
   normative contracts, explanatory architecture docs, decision
   authority (ADRs/ledger), and implementation, with no two documents
   both plausibly authoritative for the same concept?
2. **Repository Baseline** — are branch/HEAD/base/ahead-behind and the
   presence/absence of `src/`/tests/CI independently re-verified this
   pass (not carried over from memory)?
3. **Status Discipline** — does every document use
   `DESIGNED`/`PROPOSED`/`IMPLEMENTED`/`VERIFIED` (or an equivalent
   explicit scale) correctly, with no claim of completed/working
   functionality unsupported by a concrete repository reference?
4. **<Domain concept 1> Boundary** — e.g. "Identity Model," "Source
   Adapter," "Resolution Result" — one item per major contract-owned
   concept named in the task/spec. Each needs its own PASS/BLOCKED
   verdict, not a single blended "contracts are fine" line.
5. **<Domain concept 2> Boundary** — repeat for every concept with a
   plausible ownership ambiguity (e.g. "who owns admission vs.
   registration," "where does execution evidence live vs. final
   outcome").
6. **<Cross-cutting invariant>** — e.g. "Protocol Isolation" (does a
   supposedly protocol-agnostic core leak protocol-specific types?),
   "Legal/Authorization Boundary" (does anything imply unauthorized
   distribution mechanisms?). Include one item per invariant the project
   has explicitly committed to.
7. **Scope Lock** — is there an explicit, current list of what's
   deferred past this freeze (not just what's included)? A freeze without
   a stated "kept deferred" list tends to silently regrow scope later.
8. **Audit Artifact Freshness** — was the audit artifact (see
   `contract-freeze-gate`'s `documentation-audit-template.md`) actually
   regenerated from current `HEAD` this pass, with no stale counts or
   hashes carried over from a previous revision?

## Verdict rule

The overall gate is `<PROJECT>_FREEZE_READY` only if **every** item is
`PASS`. If any item is `BLOCKED`, the overall gate is
`<PROJECT>_FREEZE_BLOCKED` and the blockers must be named explicitly (not
just "some items still need work") — each blocker should trace back to a
specific `OPEN` ledger item or a specific missing piece of evidence.

**A single `BLOCKED` item blocks the whole gate, even if every other item
passes.** Do not average, round up, or let an unrelated majority of
passing items imply readiness — this checklist is a conjunction (AND),
not a score.

## What "PASS" does NOT mean

`PASS` on this checklist means the *documentation/contract layer* is
internally consistent and ready to implement against. It does not mean:

- any code has been written,
- any test has been run,
- CI exists or has run,
- the design is necessarily correct or complete for every future need —
  only that it has no known internal contradiction for the frozen scope.

State the freeze verdict and any implementation-readiness claim as two
separate statements, never conflated into one.
