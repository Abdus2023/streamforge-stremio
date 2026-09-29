---
name: contract-normalization-pass
description: Runs a full end-to-end documentation/contract normalization and pre-freeze audit pass over a "documentation-as-contract" repository (one where interfaces/types are specified in Markdown before any code exists) — auditing for contradictions, resolving them with ADRs, regenerating the audit artifact, running a freeze gate, and producing a structured final report. Use whenever the user asks for a "pre-freeze audit," "contract normalization pass," wants to know if documentation contradictions block starting implementation, or references a multi-phase contract-freeze/decision-ledger workflow. This is the top-level orchestrator skill — it coordinates doc-symbol-audit, adr-writer, contract-freeze-gate, and docs-normalization-commit-plan; use those individually for narrower requests, and this one when the ask is the whole pass end-to-end.
---

# Contract Normalization Pass

The end-to-end workflow for taking a documentation-as-contract repository
(architecture docs that specify interfaces/types in prose and code
examples, ahead of any actual implementation) from "possibly internally
contradictory" to "either frozen and safe to implement against, or
explicitly blocked with named reasons" — and reporting the result in a
fixed, checkable format.

This skill is an orchestrator: each stage below hands off to a more
specific skill. Read `references/operating-principles.md` in full before
starting — it's the constitution the rest of this pass operates under.

## The pass, phase by phase

0. **Repository sync check (always first, every session/turn).** Use
   **session-git-sync-check** before trusting `git log`/`git status`/
   `HEAD` for anything, and again immediately before any commit-and-push
   sequence in phase 8. Sandboxed environments can silently re-clone onto
   a stale ref mid-session; skipping this check risks a final report
   describing the wrong repository state, or a push that discards real
   history.

1. **Monolith migration (first time only).** If the documentation doesn't
   yet exist as a partitioned structure — it's still one large design
   document — use **docs-monolith-partition** first to split it into
   normative contracts / explanatory architecture / decision authority /
   implementation, via a migration matrix, without resolving any
   contradictions the split surfaces. Skip this phase entirely on any
   later pass over an already-partitioned repository.

2. **Partition check.** Confirm (or establish, if this is the first
   pass) a clean split: normative contracts / explanatory architecture /
   decision authority (ADRs + ledger) / implementation. No two locations
   should both plausibly be authoritative for the same concept. If the
   split doesn't exist yet, propose one before continuing.

3. **Symbol/contradiction audit.** Use **doc-symbol-audit** to find every
   symbol declared more than once, extract each occurrence's full body,
   and build a contradiction matrix (`Symbol | Canonical location |
   Historical definitions | Conflict | Status`). Cover, at minimum, every
   symbol named in whatever spec/task commissioned this pass.

4. **Decision-making.** For each contradiction with enough evidence to
   resolve, use **adr-writer** to write an ADR and update the decision
   ledger. For each contradiction without enough evidence, leave it as an
   explicit `OPEN` ledger item with a stated severity — don't force a
   decision. If a directive gave a literal canonical shape for something,
   treat it as binding but document explicitly any conflict with a prior
   ADR (see operating principle 11).

5. **Historical annotation.** As part of each ADR (per `adr-writer`'s own
   steps), annotate every non-canonical occurrence found in step 2 as
   historical/non-normative, pointing back at the new canonical location.

6. **Scope lock.** Update the project's roadmap/scope document to state
   explicitly (a) which previously-ambiguous items are now resolved and
   how, and (b) an explicit list of what remains deferred out of scope.
   Don't let scope drift silently during cleanup — see operating
   principle 7.

7. **Freeze gate.** Use **contract-freeze-gate** to regenerate the
   documentation-audit artifact from current `HEAD` and evaluate the
   freeze-gate checklist, producing exactly one verdict:
   `<PROJECT>_FREEZE_READY` or `<PROJECT>_FREEZE_BLOCKED`. If the project
   has an explicit authorization/legal boundary (see operating principle
   8), also run **authorization-boundary-scan** over the current
   implementation before finalizing the verdict — a boundary violation
   found here blocks the gate regardless of how clean the contract layer
   itself is.

8. **Commit discipline.** Re-run **session-git-sync-check** first (state
   can drift between phases in a long session), then use
   **docs-normalization-commit-plan** to land the whole pass as a small
   number of coherent, ordered, docs-only commits (never mixed with
   implementation), each pushed as a safe checkpoint.

9. **Final report.** Produce a structured report using either
   `assets/final-report-short-template.md` (a follow-up pass closing
   known gaps) or `assets/final-report-long-template.md` (a first/deep
   audit establishing the partition and matrix from scratch) — pick
   whichever the commissioning task specifies, or the short form by
   default if unspecified. Fill every section; never omit a section
   because it's empty — state "none" explicitly instead.

10. **Only if the verdict is `READY`:** implementation may begin, as the
    smallest reasonable vertical slice, not every subsystem at once, and
    must not implement anything the scope-lock step (6) marked as
    deferred. Use **contract-implementation-sync** for this phase — it
    keeps the code and the frozen contracts from silently drifting apart,
    and keeps each contract's documented status (`DESIGNED` →
    `IMPLEMENTED` → `VERIFIED`) honest and evidence-backed as
    implementation actually happens. Re-run
    **authorization-boundary-scan** after implementing anything that adds
    a concrete source adapter or provider integration.

## Sub-skills this orchestrates

| Skill | Used for |
|---|---|
| `session-git-sync-check` | Phase 0 (always first) and again before phase 8's commit/push. |
| `docs-monolith-partition` | Phase 1 (first-time migration from a single monolith into a partitioned structure). |
| `docs-integrity-check` | Fence-balance and link-validity checks — run after every batch of edits in every phase above, not just once at the end. |
| `doc-symbol-audit` | Phase 3 (finding and diffing contradictions). |
| `adr-writer` | Phase 4–5 (recording decisions, annotating historical material). |
| `contract-freeze-gate` | Phase 7 (regenerating the audit artifact, running the checklist). |
| `authorization-boundary-scan` | Phase 7 (gating the freeze verdict) and again after phase 10's implementation work. |
| `docs-normalization-commit-plan` | Phase 8 (landing the work in git). |
| `contract-implementation-sync` | Phase 10 (only once the gate is `READY`). |
| `skill-creator` | Not part of the pass itself — use it separately if a step of this pass turns out to need a new reusable tool/skill of its own. |


## Common failure modes to avoid (see `references/operating-principles.md` for the full list)

- Claiming two documentation drafts are identical without diffing them
  character-by-character.
- Letting a `CONTRACT_FREEZE_READY` verdict imply anything about tests,
  CI, or actual implementation — it only means the documentation/contract
  layer is internally consistent.
- Starting implementation, even "just a little," while the gate is
  `BLOCKED`.
- Regenerating the audit artifact by patching stale numbers instead of a
  true from-`HEAD` regeneration.
