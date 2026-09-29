---
name: contract-freeze-gate
description: Regenerates a full documentation-audit artifact from the current repository state and evaluates a named freeze-gate checklist to produce an explicit CONTRACT_FREEZE_READY or CONTRACT_FREEZE_BLOCKED verdict. Use whenever the user asks "are we ready to freeze the contracts," "regenerate the documentation audit," "run the freeze gate," "can we start implementation yet," or before any implementation work begins on top of a documentation-as-contract repository. Always regenerate the audit from current HEAD — never reuse a stale one with old commit hashes or counts.
---

# Contract Freeze Gate

Produces the two artifacts a "may we start implementing yet" decision
needs: a fully regenerated documentation-audit file (evidence) and an
explicit freeze-gate verdict (the decision itself, as a named
`PASS`/`BLOCKED` checklist plus one final combined verdict).

**This skill depends on `doc-symbol-audit` and `adr-writer` having
already been used to resolve (or explicitly leave `OPEN` with a stated
severity) every contradiction in scope.** Run this skill last, after
contradictions are found and either resolved or deliberately left open.

## Steps

1. **Re-verify the repository baseline independently** — don't reuse
   anything from a previous session's memory. Run, fresh:
   ```bash
   git branch --show-current
   git rev-parse HEAD
   git fetch origin <base>
   git rev-list --left-right --count origin/<base>...HEAD
   find . -maxdepth 2 -iname src -o -iname tests -o -iname .github
   ```
   plus whatever else establishes implementation status (package
   manifest scripts/dependencies, lockfiles, `tsconfig`/build config).

2. **Regenerate the documentation-audit file** using
   `assets/documentation-audit-template.md`. Do not incrementally patch
   an old one in place if it would leave stale hashes/counts — a full
   regeneration from current `HEAD` is required by this skill's own
   trigger condition. Carry forward the "Changes made across all passes"
   history section rather than deleting prior entries.

3. **Run `docs-integrity-check`** against the full documentation tree
   before finalizing the audit — a freeze gate built on top of broken
   links or unbalanced fences is not trustworthy.

4. **Evaluate the freeze-gate checklist** in
   `references/freeze-gate-checklist.md`, adapting its domain-specific
   items (4–7 in the template) to the actual concepts named in whatever
   spec/task commissioned this pass. Grade each item `PASS` or `BLOCKED`
   with a one-line reason. Remember: the gate is a conjunction — a single
   `BLOCKED` item blocks the whole thing regardless of how many other
   items pass.

5. **State the final verdict** as exactly one of
   `<PROJECT>_FREEZE_READY` / `<PROJECT>_FREEZE_BLOCKED` (substitute the
   project's own naming convention, e.g. `CONTRACT_FREEZE_READY`). If
   `BLOCKED`, name every blocking item explicitly, each tied to a
   specific `OPEN` ledger entry or missing piece of evidence — never a
   vague "some things still need work."

6. **Do not let a `PASS` freeze-gate verdict imply anything about
   implementation, tests, or CI.** Per
   `adr-writer/references/status-discipline.md`'s "What PASS does NOT
   mean" section, a freeze-ready contract layer and a working
   implementation are two entirely separate claims — state both
   separately if both are relevant, and never claim the second based on
   evidence for only the first.

## When the verdict is `READY`

State explicitly what is authorized next (e.g. "begin implementation as
the smallest vertical slice, not every subsystem at once") and what
remains explicitly out of scope (the Scope Lock list from step 4) so
implementation doesn't silently regrow scope that was deliberately
deferred.

## When the verdict is `BLOCKED`

Do not proceed to implementation. Route each blocking item back through
`doc-symbol-audit` (if it needs more evidence) or `adr-writer` (if
evidence exists but no decision has been recorded yet).
