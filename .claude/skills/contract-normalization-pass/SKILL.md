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

1. **Partition check.** Confirm (or establish, if this is the first
   pass) a clean split: normative contracts / explanatory architecture /
   decision authority (ADRs + ledger) / implementation. No two locations
   should both plausibly be authoritative for the same concept. If the
   split doesn't exist yet, propose one before continuing.

2. **Symbol/contradiction audit.** Use **doc-symbol-audit** to find every
   symbol declared more than once, extract each occurrence's full body,
   and build a contradiction matrix (`Symbol | Canonical location |
   Historical definitions | Conflict | Status`). Cover, at minimum, every
   symbol named in whatever spec/task commissioned this pass.

3. **Decision-making.** For each contradiction with enough evidence to
   resolve, use **adr-writer** to write an ADR and update the decision
   ledger. For each contradiction without enough evidence, leave it as an
   explicit `OPEN` ledger item with a stated severity — don't force a
   decision. If a directive gave a literal canonical shape for something,
   treat it as binding but document explicitly any conflict with a prior
   ADR (see operating principle 11).

4. **Historical annotation.** As part of each ADR (per `adr-writer`'s own
   steps), annotate every non-canonical occurrence found in step 2 as
   historical/non-normative, pointing back at the new canonical location.

5. **Scope lock.** Update the project's roadmap/scope document to state
   explicitly (a) which previously-ambiguous items are now resolved and
   how, and (b) an explicit list of what remains deferred out of scope.
   Don't let scope drift silently during cleanup — see operating
   principle 7.

6. **Freeze gate.** Use **contract-freeze-gate** to regenerate the
   documentation-audit artifact from current `HEAD` and evaluate the
   freeze-gate checklist, producing exactly one verdict:
   `<PROJECT>_FREEZE_READY` or `<PROJECT>_FREEZE_BLOCKED`.

7. **Commit discipline.** Use **docs-normalization-commit-plan** to land
   the whole pass as a small number of coherent, ordered, docs-only
   commits (never mixed with implementation), each pushed as a safe
   checkpoint.

8. **Final report.** Produce a structured report using either
   `assets/final-report-short-template.md` (a follow-up pass closing
   known gaps) or `assets/final-report-long-template.md` (a first/deep
   audit establishing the partition and matrix from scratch) — pick
   whichever the commissioning task specifies, or the short form by
   default if unspecified. Fill every section; never omit a section
   because it's empty — state "none" explicitly instead.

9. **Only if the verdict is `READY`:** implementation may begin, as the
   smallest reasonable vertical slice, not every subsystem at once, and
   must not implement anything the scope-lock step (5) marked as
   deferred.

## Sub-skills this orchestrates

| Skill | Used for |
|---|---|
| `docs-integrity-check` | Fence-balance and link-validity checks — run after every batch of edits in every phase above, not just once at the end. |
| `doc-symbol-audit` | Phase 2 (finding and diffing contradictions). |
| `adr-writer` | Phase 3–4 (recording decisions, annotating historical material). |
| `contract-freeze-gate` | Phase 6 (regenerating the audit artifact, running the checklist). |
| `docs-normalization-commit-plan` | Phase 7 (landing the work in git). |

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
