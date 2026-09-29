---
name: docs-normalization-commit-plan
description: Plans and executes a coherent, ordered sequence of git commits for a documentation/contract normalization pass (new ADRs, rewritten contracts, architecture-doc annotations, roadmap/audit refresh, ledger freeze) without mixing in implementation changes or fabricating test/CI evidence. Use whenever the user asks how to commit a batch of documentation changes, wants "clean commits" for a normalization pass, or right after adr-writer/contract-freeze-gate have produced a batch of documentation edits that need to land in git.
---

# Docs Normalization Commit Plan

Turns a pile of uncommitted documentation edits (from `doc-symbol-audit`
+ `adr-writer` + `contract-freeze-gate` work) into a small number of
coherent, individually-reviewable git commits, in a sensible order, with
commit messages that carry the actual reasoning — not just a diff
summary.

## Steps

1. Read `references/commit-ordering-checklist.md` for the recommended
   commit sequence (per-concept contract commits → roadmap/scope-lock →
   audit regeneration → ledger freeze) and the hard rules (never mix
   implementation with normalization, never fabricate test/CI evidence,
   push after each safe checkpoint).

2. Inspect the actual working-tree diff (`git status --short`, `git
   diff`) and group changed files by which decision/concept they belong
   to. If two concerns turn out to be inseparably interleaved in one
   file's edits, don't force an artificial split — commit them together
   and say so plainly in the commit message and/or final report, rather
   than claiming a cleaner split happened than actually did.

3. Before each commit: run `docs-integrity-check` on the full
   documentation tree (not just the files about to be committed — a
   broken cross-reference can appear in a file you didn't touch this
   round).

4. Write each commit message to state: what changed, which `OPEN` ledger
   item(s) it resolves (if any), what becomes historical/superseded as a
   result, and an explicit note that no implementation/test/CI evidence
   is added or claimed. A future reader should be able to reconstruct the
   decision from `git log` alone.

5. Commit and push after each logical checkpoint (not only at the very
   end) if there's any risk of losing uncommitted work between turns/
   sessions.

6. After the full sequence lands, do a final `git status --short` to
   confirm a clean working tree, and a final `docs-integrity-check` run
   to confirm nothing broke across the whole sequence.

## Output

At the end, be able to state: base commit, final HEAD, the exact list of
commits created (hash + one-line message), and the full file list
touched — this is exactly the evidence a "Changes Made" / "Commits
Created" section of a final report needs (see `contract-normalization-pass`
for the full report templates).
