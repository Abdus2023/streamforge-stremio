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
| [`session-git-sync-check`](./session-git-sync-check/) | Detects whether the local git checkout actually matches its remote branch's real tip, and gives exact safe recovery steps if not. Catches a real, repeatedly-observed sandboxed-environment bug (silent re-clone onto a stale ref mid-session) that hit this exact session three times. Real, tested script (`git_sync_check.sh`), exercised against all three real failure modes (stale/ancestor, ahead, diverged). | — |
| [`docs-monolith-partition`](./docs-monolith-partition/) | Migrates a single large monolithic doc into a topic-partitioned structure using a migration matrix, without resolving contradictions along the way. Captures Task 1's original process (splitting a 703-section, ~26,500-line monolith into `docs/contracts/`, `docs/architecture/`, `docs/decisions/`). | — |
| [`docs-integrity-check`](./docs-integrity-check/) | Verifies Markdown fence balance and internal link validity. Real, working scripts (`check_fences.sh`, `check_links.py`) — no dependencies beyond bash/Python 3. | — |
| [`doc-symbol-audit`](./doc-symbol-audit/) | Finds every declaration of a named type/interface/class across a docs tree and extracts each occurrence's full body for diffing. Real scripts (`list_declared_symbols.py`, `extract_symbol_occurrences.py`), tested against this repo's own `docs/` tree. | `docs-integrity-check` |
| [`adr-writer`](./adr-writer/) | Writes an Architecture Decision Record resolving a found contradiction and keeps the decision ledger in sync. Templates + a status-discipline reference. | `doc-symbol-audit` |
| [`contract-freeze-gate`](./contract-freeze-gate/) | Regenerates a documentation-audit artifact from current `HEAD` and evaluates a named freeze-gate checklist to a `READY`/`BLOCKED` verdict. | `docs-integrity-check`, `adr-writer` |
| [`authorization-boundary-scan`](./authorization-boundary-scan/) | Heuristically scans source + dependencies (never docs) for unauthorized-distribution/access-control-bypass patterns — a proactive compliance gate for the project's explicit legal/authorization boundary. Real, tested script (`scan_authorization_boundary.py`), verified clean on this repo's actual `src/` and confirmed to correctly flag injected violations. | — |
| [`docs-normalization-commit-plan`](./docs-normalization-commit-plan/) | Plans and executes a coherent, ordered git commit sequence for a normalization pass, docs-only, no fabricated test/CI evidence. | `docs-integrity-check`, `session-git-sync-check` |
| [`contract-implementation-sync`](./contract-implementation-sync/) | Bridges a frozen contract to its implementation: a real field-for-field parity checker (`check_contract_parity.py`) catching drift between `docs/contracts/*.md` and actual source, plus the `DESIGNED`→`IMPLEMENTED`→`VERIFIED` status-update discipline. Verified against this repo's real V0.1 implementation slice — all 11 checked symbols pass field-for-field, and the tool was confirmed to correctly detect an injected mismatch. | `doc-symbol-audit`, `adr-writer` |
| [`contract-normalization-pass`](./contract-normalization-pass/) | Top-level orchestrator tying all of the above into the full end-to-end pass (repo sync check → monolith migration → audit → freeze → implementation sync), plus the two final-report templates (short/long) actually used this session. | all of the above |
| [`skill-creator`](./skill-creator/) | Creates new skills, improves existing ones, and validates any skill directory against the open Agent Skills spec. Real script (`validate_skill.py`) — used to build and check every skill in this directory, and caught a real mistake in its own `SKILL.md` while being built (see its `references/lessons-learned.md`). | — |

## Where each process from this session ended up

- **The sandboxed environment silently re-cloning the repository onto a
  stale base commit mid-session** (discovered and manually diagnosed/
  recovered from three separate times across this session — via
  `git fetch` + `git log` comparison + `git reset --hard`/`git
  cherry-pick`, each time catching it before any push could go wrong) →
  `session-git-sync-check`'s script and its three-outcome diagnosis
  (stale/ancestor, ahead-of-remote, genuinely diverged), reproducing all
  three scenarios in test clones before being trusted.
- **Verifying the actual V0.1 implementation slice** (running `npm
  install`/`npm run typecheck`/`npm test` for real and getting genuine
  evidence — 0 typecheck errors, 5/5 tests passing — plus finding that
  the implementation's contract-owned types still matched every frozen
  contract field-for-field) → `contract-implementation-sync`'s parity
  checker, and the `DESIGNED`→`IMPLEMENTED`→`VERIFIED` status discipline
  modeled directly on this repo's own real `docs: record V0.1
  implementation state` commit.
- **The project's explicit "authorized/licensed/public-domain/user-owned
  content only" boundary** (stated in `README.md`'s "StreamForge is not
  designed to..." list and `docs/architecture.md` §1, but never backed by
  an automated check) → `authorization-boundary-scan`'s heuristic
  dependency/keyword scan, verified clean against this repo's real `src/`
  and confirmed to correctly flag deliberately injected violations in a
  throwaway test.
- **Splitting the original monolithic architecture document** into
  `docs/contracts/`, `docs/architecture/`, `docs/decisions/` via a
  temporary migration matrix, moving content without deleting or silently
  resolving contradictions along the way (documented in
  `docs/architecture.md` §9, "Provenance of this document set") →
  `docs-monolith-partition`, including its migration-matrix template and
  the five maintenance rules from `docs/architecture.md` §10.
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

**Always run `session-git-sync-check` first**, at the start of any
session/turn that will touch git, before trusting anything else in this
list. For a brand-new, not-yet-partitioned monolith: trigger
`docs-monolith-partition` next. For a full normalization pass over an
already-partitioned repo: trigger `contract-normalization-pass` (e.g.
"run a pre-freeze contract audit on this repo"). For a narrower request,
trigger the specific skill directly (e.g. "check the docs for broken
links" → `docs-integrity-check`; "does this interface get redefined
anywhere?" → `doc-symbol-audit`; "does the code still match the frozen
contracts?" → `contract-implementation-sync`; "check for
piracy/DRM-bypass code" → `authorization-boundary-scan`; "make this
workflow into a skill" → `skill-creator`).

All scripts are dependency-free (bash + Python 3 standard library only)
and have been smoke-tested against this repository's own `docs/` tree as
part of building this skill set. Every skill in this directory passes
`skill-creator/scripts/validate_skill.py --all .claude/skills` with zero
errors.
