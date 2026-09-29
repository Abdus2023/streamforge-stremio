<!--
Temporary working document only — do not commit this file to the
repository once the migration is complete. Its job is to make sure every
section of the monolith lands somewhere and nothing is silently dropped;
once the migration is verified complete, delete it.
-->

# Migration matrix: <monolith file> → partitioned structure

| # | Original section (heading / line range) | Destination document | Status |
|---|---|---|---|
| 1 | | `docs/contracts/...` / `docs/architecture/...` / `docs/decisions/...` | `MOVED` / `SPLIT ACROSS N DOCS` / `DROPPED (reason)` / `PENDING` |

## Rules while filling this in

- Every row must end in `MOVED`, `SPLIT ACROSS N DOCS` (list the N
  destinations), or `DROPPED (reason)` — never leave a row `PENDING` when
  the migration is declared complete.
- `DROPPED` is only valid for genuinely redundant boilerplate (e.g. a
  repeated table of contents) — never for a section containing a type
  definition, a decision, or a distinct explanatory point. If in doubt,
  move it rather than drop it; a slightly-misplaced section is easy to
  relocate later, a silently deleted one is not recoverable from the
  documentation alone.
- If a section describes a concept that conflicts with another section
  found elsewhere in the monolith, do **not** resolve the conflict here.
  Move both, annotate neither as canonical yet, and record the conflict
  as an `OPEN` item in the decision ledger for a later pass
  (`doc-symbol-audit` + `adr-writer` handle that pass).
- When complete, do a final pass confirming: total original line count
  accounted for (via row count / line ranges), zero `PENDING` rows, and
  every `docs/**/*.md` destination file exists.
