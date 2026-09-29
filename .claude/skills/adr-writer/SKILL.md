---
name: adr-writer
description: Writes an Architecture Decision Record (ADR) that resolves a documented contradiction between competing definitions/shapes/behaviors, and updates the project's decision ledger to match. Use whenever the user asks to "write an ADR," "resolve this contradiction," "document this decision," "pick a canonical shape," "resolve an OPEN item," or after doc-symbol-audit has found a contradiction that needs a recorded resolution. Always pair a new ADR with a ledger update in the same pass — never leave the two out of sync.
---

# ADR Writer

Turns a found contradiction (usually from `doc-symbol-audit`) into a
permanent, evidence-grounded decision record, and keeps the project's
decision ledger (an index of ADRs plus a running list of `OPEN`/
`RESOLVED` contradictions) consistent with it.

## Steps

1. **Confirm you have real evidence**, not just a hunch. You should be
   able to point at exact file:line occurrences and, ideally, a full
   diff of the competing definitions (see `doc-symbol-audit`). If you
   don't have this yet, go run that skill first — an ADR written without
   evidence in hand is exactly the failure mode this skill exists to
   prevent.

2. **Write the ADR** using `assets/adr-template.md`. Follow it exactly —
   every section (Context, Problem, Observed evidence, Decision, Rejected
   alternatives, Consequences, Status) should be filled in, not skipped.
   Number it sequentially against existing ADRs in the project's decision
   directory (e.g. `docs/decisions/ADR-00N-<kebab-case-title>.md`).

   Read `references/status-discipline.md` first — it defines the
   `PROVED`/`ARGUMENT`/`CONJECTURE`/`OPEN` labels the template expects and
   the operating principles (representation ≠ semantics ≠ evidence ≠
   truth ≠ authority ≠ authorization ≠ admission ≠ execution ≠ success ≠
   canonicality ≠ durability) that should shape the Decision section.

3. **If evidence turns out to be genuinely insufficient** to prefer one
   option once you sit down to write the Decision section, don't force a
   choice — write the ADR with Status `OPEN`, state exactly what evidence
   would resolve it, and record it as an `OPEN` ledger item instead of a
   `RESOLVED` one. Forcing a decision beyond what evidence supports is
   worse than leaving it open.

4. **Update the decision ledger** in the same pass:
   - Add the new ADR to the ledger's ADR index (or amend an existing
     ADR's ledger row if this ADR supersedes/amends it — say so
     explicitly, e.g. "(amended)").
   - Add or update the corresponding `OPEN-N`/`RESOLVED-N` entry using
     `assets/ledger-entry-template.md`'s field layout. If this ADR
     resolves a previously-open item, rewrite that item's Decision and
     Status fields in place — don't just add a new entry and leave the
     old one stale.
   - Update the ledger's "Last updated" summary line to name what changed
     this pass.

5. **Annotate every non-canonical occurrence** the ADR makes historical:
   in the architecture/explanatory document containing it, add a
   blockquote immediately above the occurrence stating (a) that it is
   historical/superseded/non-normative, (b) which document/ADR is now
   canonical, and (c) why (one sentence). Add an inline `// HISTORICAL`
   or `// SUPERSEDED` comment inside the code block itself if it's a code
   example, so the marking survives even if the block gets copy-pasted
   elsewhere. Never delete the historical material — the surrounding
   narrative usually still depends on it reading coherently.

6. Run **docs-integrity-check** after all edits (new ADR file, ledger
   update, and every annotated occurrence) are in place.

## Common mistakes to avoid

- Writing "these two definitions are identical" (or "clearly different")
  without having actually diffed them character-by-character — see
  `doc-symbol-audit/references/lessons-learned.md` for a real example of
  this going wrong and being caught late.
- Treating a rejected alternative as simply wrong when it's actually a
  plausible future direction — state explicitly that it's preserved as a
  future-candidate, not discarded, if that's the honest read.
- Forgetting the ledger update. A new ADR that isn't reflected in the
  ledger's index and `OPEN`/`RESOLVED` list creates exactly the kind of
  "is this actually decided?" ambiguity this skill exists to eliminate.
