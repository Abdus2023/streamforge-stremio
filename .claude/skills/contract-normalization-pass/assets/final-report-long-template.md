<!--
Use this longer (11-section) format for a normalization pass that is
itself the first/deep audit of a repository (establishing the
documentation partition, the full contradiction matrix, and every ADR
from scratch), rather than a follow-up pass closing out previously-known
gaps. Fill every bracketed placeholder; do not omit a section even if its
content is "none."
-->

## 1. Executive Summary

<2-4 sentences: what was audited, how many contradictions were found,
how many resolved, current freeze-readiness verdict.>

## 2. Repository Baseline

- **Branch:** `<branch>`
- **HEAD:** `<sha>`
- **Base:** `<base-branch>`
- **Ahead/behind:** `<N> ahead / <M> behind`
- **Implementation status:** `<src/tests/CI present or absent, exact
  evidence>`

## 3. Documentation Partition Established

<State the exact split adopted: which directory/location is normative
contracts, which is explanatory architecture, which is decision
authority, which is implementation. State explicitly that no two
locations are both plausibly authoritative for the same concept, or name
the remaining exceptions.>

## 4. Contradiction Matrix

| Symbol | Canonical location | Historical definitions | Conflict | Status |
|---|---|---|---|---|

<Cover at minimum every symbol named in the task/spec that commissioned
this audit.>

## 5. Decisions Made (ADRs)

| ADR | Resolves | Decision | Status |
|---|---|---|---|

## 6. Changes Made

| File | Change | Reason |
|---|---|---|

## 7. Remaining Open Items

<Full ledger snapshot: every OPEN item, its severity, and whether it
blocks the stated freeze scope.>

## 8. Verification

<One line per claim category, each labelled exactly one of `VERIFIED` /
`PARTIALLY_VERIFIED` / `PROVISIONAL` / `BLOCKED` / `NOT EXECUTED`.>

## 9. Commit Discipline

- **Base:** `<sha>`
- **HEAD:** `<sha>`
- **Commits created:** `<list, hash + message>`
- **Files changed:** `<count>`
- **Contracts normalized:** `<list>`

## 10. Freeze Gate

Full named checklist (see `contract-freeze-gate/references/
freeze-gate-checklist.md`), each item `PASS`/`BLOCKED`, ending in exactly
one overall verdict: `<PROJECT>_FREEZE_READY` or
`<PROJECT>_FREEZE_BLOCKED`.

## 11. Next Authorized Step

`BEGIN V0.1 IMPLEMENTATION` (only if READY) or `RESOLVE CONTRACT
BLOCKERS` (if BLOCKED) — or substitute the project's own two-option
phrasing.
