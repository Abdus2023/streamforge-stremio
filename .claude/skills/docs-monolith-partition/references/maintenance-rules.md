# Maintenance rules for a partitioned documentation set

Once a monolith has been split into a topic-partitioned structure
(normative contracts / explanatory architecture / decision authority /
implementation), these rules keep the partition from degrading back into
an unmaintainable mess of duplicated, drifting definitions. State these
explicitly in the partitioned set's own index document (e.g. a top-level
`docs/architecture.md` or `docs/README.md`) so future contributors —
human or agent — see them before editing.

1. **Single ownership per concept.** If you're about to write more than a
   sentence re-explaining something that already has a home (a type
   shape, a policy distinction, an evidence level), link to that
   document/contract instead of duplicating it. Duplication is exactly
   how the original monolith accumulated contradictions in the first
   place.

2. **Contracts change alone.** Interface/type shapes are edited only in
   the normative contract location (e.g. `docs/contracts/*.md`).
   Explanatory/architecture documents may *explain* a contract in prose
   or show a worked example, but must never restate its exact fields as
   if that restatement were a second source of truth — mark any example
   shape as illustrative/historical instead (see `adr-writer`'s
   annotation convention).

3. **No silent status inflation.** Never change a claim from
   `DESIGNED`/`PROPOSED` to `IMPLEMENTED`/`VERIFIED` without a concrete,
   checkable repository reference (a file, a commit, a CI run) added in
   the same edit.

4. **No silent contradiction resolution.** If migrating or editing text
   surfaces two documents disagreeing, do not just pick one and delete
   the other. Record it explicitly as an `OPEN` ledger item (or resolve
   it properly with an ADR if there's enough evidence) — see
   `doc-symbol-audit` and `adr-writer`.

5. **Keep the top-level index thin.** The document that lists "where to
   find what" should stay short (roughly 100–250 lines is a reasonable
   target). If it starts accumulating real architecture detail, that
   detail belongs in one of the partitioned documents instead, with the
   index updated to link to it.

## Why these rules exist

Every one of these rules maps directly to a failure mode that produces
exactly the kind of contradiction `doc-symbol-audit` and `adr-writer`
exist to clean up later. Following them at partition time is cheaper than
running a full contradiction audit after the fact — but if a large
migration happens quickly (as monolith splits usually do), some drift is
expected regardless; that's what the audit/freeze-gate pass is for.
