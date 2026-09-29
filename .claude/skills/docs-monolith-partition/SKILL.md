---
name: docs-monolith-partition
description: Migrates a single large monolithic documentation file into a clean, topic-partitioned structure (normative contracts, explanatory architecture, decision authority, implementation), using a temporary migration matrix to guarantee every section lands somewhere without silent deletion or silent contradiction resolution. Use whenever the user has one huge architecture/design/spec document (hundreds of sections, tens of thousands of lines) they want split into multiple files, asks to "reorganize the docs," "split this monolith," or "set up a docs structure," or when a documentation set has grown large enough that finding the authoritative definition of anything requires scrolling through one giant file.
---

# Docs Monolith Partition

The first step in turning an organically-grown, single-file design
document into a maintainable documentation set: split it into a
topic-partitioned structure without losing or silently resolving
anything along the way. This is the *entry* process — run it once, before
`doc-symbol-audit`/`adr-writer`/`contract-freeze-gate` exist to have
anything to audit.

## Steps

1. **Decide the target partition** before moving anything. A structure
   that has worked well:
   - `docs/contracts/*.md` — normative interface/type/behavior
     definitions. Exactly one file owns each concept.
   - `docs/architecture/*.md` — explanatory narrative, worked examples,
     design rationale. May reference contracts but must not restate them
     as a second source of truth.
   - `docs/decisions/*.md` (or a single ledger file) — ADRs and a running
     `OPEN`/`RESOLVED` contradiction ledger.
   - `src/`, `test/`, etc. — actual implementation, kept strictly separate
     from all of the above until a freeze gate passes.

   Adapt the exact folder names/count to the project, but keep the
   underlying distinction (normative / explanatory / decision authority /
   implementation) — it's what every other skill in this set assumes
   exists.

2. **Build a migration matrix** before moving content — a table mapping
   every original section (by heading or line range) to its destination
   document. Use `assets/migration-matrix-template.md`. This is a
   *temporary working document*, not part of the final repository —
   delete it once the migration is verified complete.

3. **Move content, never delete it**, and never resolve a contradiction
   found during the move. If two sections of the monolith describe the
   same concept differently, move both to wherever they land naturally
   and leave the disagreement for `doc-symbol-audit`/`adr-writer` to
   resolve properly, later, with evidence. Drop only genuinely redundant
   boilerplate (e.g. a repeated table of contents) — see the matrix
   template's rules for what counts as safe to drop.

4. **Drop artifacts of the monolith's own internal organization** that
   don't survive a proper split cleanly — e.g. global `§N` section
   numbering — in favor of descriptive headings and per-document anchors
   that work once the content lives in multiple files.

5. **Verify completeness** before declaring the migration done: every
   matrix row resolved to `MOVED`/`SPLIT ACROSS N DOCS`/`DROPPED (reason)`
   with none left `PENDING`, and every destination file referenced in the
   matrix actually exists.

6. **Write the partition's maintenance rules into its own index
   document** — see `references/maintenance-rules.md` for the exact rule
   set (single ownership per concept, contracts change alone, no silent
   status inflation, no silent contradiction resolution, keep the index
   thin) and state provenance (what was migrated from where, and that a
   migration matrix was used and then discarded) so future readers
   understand why the structure looks the way it does.

7. **Run `docs-integrity-check`** on the new partitioned structure before
   considering the migration complete.

8. **Hand off to `doc-symbol-audit`** next — a freshly-migrated partition
   almost always has left-over contradictions (multiple sections that
   described the same concept slightly differently before the split);
   finding and resolving those is the next skill's job, not this one's.

## Notes

- This skill is about creating a clean *structure*; it deliberately does
  **not** try to resolve contradictions found during the move (see step
  3) — mixing "reorganize" with "resolve" in one pass makes both harder
  to review and easier to get wrong.
- A migration matrix documented in this repository's own history covered
  splitting a 703-section, ~26,500-line single file into the
  `docs/contracts/` / `docs/architecture/` / `docs/decisions/` structure
  now used throughout this skill set — see `docs/architecture.md` §9
  ("Provenance of this document set") for a real example write-up of this
  process's outcome.
