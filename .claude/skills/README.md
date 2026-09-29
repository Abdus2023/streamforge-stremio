# Skills index

This directory packages the repeatable processes used across this
repository's multi-pass documentation/contract normalization work
(Tasks 1–4: initial monolith split, contradiction audits, ADR authoring,
registry/result/evidence boundary decisions, and freeze-gate reporting)
into reusable [Agent Skills](https://agentskills.io/specification) —
each a self-contained `SKILL.md` plus, where useful, real executable
scripts and templates. They are generic: nothing in them is specific to
StreamForge, so the whole `.claude/skills/` directory can be copied into
any other "documentation-as-contract" repository (architecture docs that
specify interfaces before code exists) and reused as-is.

## What's here

| Skill | Role | Depends on |
|---|---|---|
| [`docs-integrity-check`](./docs-integrity-check/) | Verifies Markdown fence balance and internal link validity. Real, working scripts (`check_fences.sh`, `check_links.py`) — no dependencies beyond bash/Python 3. | — |
| [`doc-symbol-audit`](./doc-symbol-audit/) | Finds every declaration of a named type/interface/class across a docs tree and extracts each occurrence's full body for diffing. Real scripts (`list_declared_symbols.py`, `extract_symbol_occurrences.py`), tested against this repo's own `docs/` tree. | `docs-integrity-check` |
| [`adr-writer`](./adr-writer/) | Writes an Architecture Decision Record resolving a found contradiction and keeps the decision ledger in sync. Templates + a status-discipline reference. | `doc-symbol-audit` |
| [`contract-freeze-gate`](./contract-freeze-gate/) | Regenerates a documentation-audit artifact from current `HEAD` and evaluates a named freeze-gate checklist to a `READY`/`BLOCKED` verdict. | `docs-integrity-check`, `adr-writer` |
| [`docs-normalization-commit-plan`](./docs-normalization-commit-plan/) | Plans and executes a coherent, ordered git commit sequence for a normalization pass, docs-only, no fabricated test/CI evidence. | `docs-integrity-check` |
| [`contract-normalization-pass`](./contract-normalization-pass/) | Top-level orchestrator tying all of the above into the full end-to-end pass, plus the two final-report templates (short/long) actually used this session. | all of the above |

## Where each process from this session ended up

- **Symbol grep + field-by-field contradiction diffing** (used manually,
  over and over, across every task in this session, including catching a
  real "these are identical" mistake in `06-runtime.md`'s `AdapterStatus`
  drafts) → `doc-symbol-audit`'s scripts, generalizing the ad hoc
  `grep`/`sed`/Python snippets into two reusable, tested tools.
- **ADR authoring + decision ledger maintenance** (`docs/decisions/
  ADR-001` through `ADR-007`, `docs/decisions/README.md`'s `OPEN-N`/
  `RESOLVED-N` entries) → `adr-writer`'s template and status-discipline
  reference, capturing the exact section structure and the
  `PROVED`/`ARGUMENT`/`CONJECTURE`/`OPEN` labeling convention used
  throughout.
- **Historical/non-normative annotation of architecture docs**
  (blockquotes + inline `// HISTORICAL` comments added across
  `02-domain.md`, `03-resolution.md`, `04-providers.md`, `05-policy.md`,
  `06-runtime.md`, `07-evidence.md`) → folded into `adr-writer`'s
  workflow (step 5) as a required part of writing any ADR.
- **Fence-balance and link-validity sweeps** (run after nearly every
  batch of edits this session, via ad hoc bash loops and a one-off Python
  script) → `docs-integrity-check`'s two scripts.
- **`documentation-audit.md` regeneration** (three full passes this
  session, each with a repository baseline, contract status matrix,
  concept ownership matrix, and freeze-gate section) →
  `contract-freeze-gate`'s template and checklist.
- **Commit discipline** (coherent, ordered, docs-only commits, pushed as
  safe checkpoints, with reasoning-carrying messages) →
  `docs-normalization-commit-plan`.
- **The exact 7-section and 11-section final report formats** used to
  close out Task 3 and Task 4 → `contract-normalization-pass`'s two
  report templates.
- **The standing operating principles** (no evidence → no verified claim,
  don't conflate representation/semantics/evidence/truth/authority/
  authorization/admission/execution/success/canonicality/durability,
  prefer one canonical contract, don't silently broaden scope, preserve
  legal/authorization boundaries) →
  `contract-normalization-pass/references/operating-principles.md`.

## Quick start

For a full pass: trigger `contract-normalization-pass` (e.g. "run a
pre-freeze contract audit on this repo"). For a narrower request, trigger
the specific skill directly (e.g. "check the docs for broken links" →
`docs-integrity-check`; "does this interface get redefined anywhere?" →
`doc-symbol-audit`).

All scripts are dependency-free (bash + Python 3 standard library only)
and have been smoke-tested against this repository's own `docs/` tree as
part of building this skill set.
