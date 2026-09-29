# Commit ordering for a documentation/contract normalization pass

A normalization pass typically touches many files for several distinct
reasons at once (new ADRs, new/rewritten contract files, annotations in
architecture docs, ledger updates, a regenerated audit artifact). Split
the work into a small number of coherent, reviewable commits rather than
one giant commit or one commit per file.

## Recommended order

1. **Per-concept contract commits, one per resolved concept/boundary.**
   For each concept an ADR resolved (e.g. "registry contract," "result
   boundary," "evidence/receipt contracts"), commit together: the new/
   amended ADR, the new/rewritten contract file, and the architecture-doc
   annotations that mark that concept's historical drafts non-normative.
   Keeping the contract change and its historical-annotation together in
   one commit is usually more reviewable than an artificial split — a
   reviewer wants to see "here's the new contract, and here's exactly
   what it makes obsolete" in one diff.
2. **Roadmap/scope-lock commit.** Once all per-concept commits land,
   commit the roadmap document's stale-reference cleanup and any new
   explicit "kept deferred" scope-lock list.
3. **Audit-artifact regeneration commit.** Regenerate and commit the
   documentation-audit file last, after every other change it needs to
   reference already exists — this avoids the audit file citing commit
   hashes that don't exist yet.
4. **Ledger-freeze commit.** A final, small commit updating only the
   decision ledger's summary/header line to state the freeze-gate verdict
   reached this pass. Keeping this separate makes "what did this pass
   conclude" a one-commit answer.

## Hard rules

- **Never mix implementation with documentation normalization** in the
  same commit, or even the same pass, unless a freeze gate has already
  passed and implementation is explicitly authorized. A reviewer should
  never have to untangle "did this commit change what's true, or did it
  change what exists" from a mixed diff.
- **Never fabricate test/CI evidence in a commit message.** If no tests
  or CI exist, no commit message may imply they were run or that they
  passed.
- **Write commit messages that state the reasoning, not just the diff
  summary.** A commit message like "docs: normalize source registry
  contract" should go on to say *which* `OPEN` items it resolves, *which*
  ADR is new, and *what* becomes historical as a result — a future reader
  should be able to reconstruct the decision from `git log` alone,
  without re-reading the ADR.
- **Push after each safe checkpoint**, not only at the very end, if the
  environment has any risk of losing uncommitted work between turns —
  committed and pushed work is durable; uncommitted edits are not.
- If a planned commit split turns out to be impractical because two
  concerns are inseparably interleaved within the same file edits (e.g. a
  contract file's rewrite and its historical-annotation happened in one
  continuous edit), **say so explicitly** in the final report or a later
  commit's message rather than silently claiming a split that didn't
  happen.

## Verifying before each commit

Run `docs-integrity-check` (fence balance + link validity) before every
commit in the sequence, not just once at the very end — catching a broken
link introduced by commit 2 is much easier before commit 5 lands on top
of it.
