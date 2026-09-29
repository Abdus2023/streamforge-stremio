# Skills index

This directory packages the repeatable processes used across this
repository's multi-pass documentation/contract normalization work
(Tasks 1–4: initial monolith split, contradiction audits, ADR authoring,
registry/result/evidence boundary decisions, and freeze-gate reporting),
plus a second layer of general-purpose repository-hygiene skills found by
researching common gaps across public repositories and Agent Skill
libraries more broadly (git-sync verification, dependency vulnerability
auditing, secret-leak scanning, agent-onboarding-file auditing), into
reusable [Agent Skills](https://agentskills.io/specification) — each a
self-contained `SKILL.md` plus, where useful, real executable scripts and
templates. They are generic: nothing in them is specific to StreamForge,
so the whole `.claude/skills/` directory can be copied into any other
repository and reused as-is — the documentation-normalization skills are
most relevant to a "documentation-as-contract" repository specifically
(architecture docs that specify interfaces before code exists), while the
repository-hygiene skills (`session-git-sync-check`,
`dependency-vulnerability-audit`, `secret-leak-scan`,
`repo-onboarding-audit`) apply to essentially any git repository.

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
| [`secret-leak-scan`](./secret-leak-scan/) | Zero-dependency heuristic scanner (`scan_secrets.py`) for hardcoded credentials (AWS/GitHub/Slack/Stripe/Google keys, private key blocks, generic password/token assignments) in the current working tree. Verified clean on this repo's real `src/test/docs`, and confirmed to correctly flag injected AWS/GitHub/private-key secrets while suppressing an env-var-sourced value and an obvious placeholder. Not a replacement for gitleaks/trufflehog in real CI — see its Notes. | — |
| [`dependency-vulnerability-audit`](./dependency-vulnerability-audit/) | Detects a project's package manager from its lockfile and runs the matching native audit tool (`npm audit`/`pip-audit`/`cargo audit`), normalizing the result to a severity summary. Real script (`run_dependency_audit.sh`), verified against this repo's real `package-lock.json` (0 vulnerabilities) and against a deliberately pinned known-vulnerable package in a throwaway project (correctly flagged `critical: 1`, exit 1). | — |
| [`repo-onboarding-audit`](./repo-onboarding-audit/) | Checks for an agent-onboarding file (`AGENTS.md`/`AGENT.md`/`CLAUDE.md`), flags documented commands that no longer match real `package.json` scripts, and can generate a draft from real manifest facts only. Real script (`audit_agents_md.py`) — confirmed this very repo had no onboarding file (a genuine gap), generated its actual `AGENTS.md` (hand-reviewed and extended afterward), and separately verified drift detection against an injected stale file. | — |
| [`docs-normalization-commit-plan`](./docs-normalization-commit-plan/) | Plans and executes a coherent, ordered git commit sequence for a normalization pass, docs-only, no fabricated test/CI evidence. | `docs-integrity-check`, `session-git-sync-check` |
| [`contract-implementation-sync`](./contract-implementation-sync/) | Bridges a frozen contract to its implementation: a real field-for-field parity checker (`check_contract_parity.py`) catching drift between `docs/contracts/*.md` and actual source, plus the `DESIGNED`→`IMPLEMENTED`→`VERIFIED` status-update discipline. Verified against this repo's real V0.1 implementation slice — all 11 checked symbols pass field-for-field, and the tool was confirmed to correctly detect an injected mismatch. | `doc-symbol-audit`, `adr-writer` |
| [`contract-normalization-pass`](./contract-normalization-pass/) | Top-level orchestrator tying all of the above into the full end-to-end pass (repo sync check → monolith migration → audit → freeze → implementation sync), plus the two final-report templates (short/long) actually used this session. | all of the above |
| [`skill-creator`](./skill-creator/) | Creates new skills, improves existing ones, and validates any skill directory against the open Agent Skills spec. Real script (`validate_skill.py`) — used to build and check every skill in this directory, and caught a real mistake in its own `SKILL.md` while being built (see its `references/lessons-learned.md`). | — |

## Where each process from this session ended up

- **The sandboxed environment silently re-cloning the repository onto a
  stale base commit mid-session** (this recurred a fourth time while
  researching this very layer of skills — that time with a genuinely
  dirty working tree sitting on the stale base, not a clean one,
  requiring a new WIP-snapshot-and-diff recovery path; root-caused to
  `.git/config` not reliably persisting across turns in this sandbox,
  consistent with credential-related files being excluded from cross-turn
  snapshots) → `session-git-sync-check`'s script and its diagnosis
  branches (clean stale/ancestor, dirty stale/ancestor, ahead-of-remote,
  genuinely diverged), each reproduced faithfully in throwaway test
  clones — including using `git update-ref` rather than `git reset
  --hard` to simulate the dirty case accurately, after an initial,
  less-faithful test with `reset --hard` revealed the recovery recipe
  would be destructive if blindly applied to a *genuinely* stale working
  tree (not just stale git metadata) — hence the mandatory `git diff
  --stat` safety check the script now prints before its apply step.
- **Researching public conventions for how other repositories guide
  coding agents** (the open `AGENTS.md` standard, adopted by tens of
  thousands of public repositories) surfaced that this repository itself
  had no onboarding file at all → `repo-onboarding-audit`, whose
  `generate` mode was used to create this repo's real `AGENTS.md` from
  its actual `package.json` facts, then hand-extended with pointers into
  `docs/contracts/`, the legal/authorization boundary, and this skills
  directory.
- **Checking this repo's own dependency tree and source tree for two
  extremely common public-repository gaps** (known-vulnerable pinned
  dependencies, and accidentally committed credentials) → both came back
  genuinely clean here (`npm audit`: 0 vulnerabilities;
  `secret-leak-scan`: 0 hits), but both checks were verified as
  real/working via deliberately injected true-positive cases (a pinned
  `minimist@0.0.8` with a public critical CVE; fake AWS/GitHub/private
  keys) before trusting the clean result → `dependency-vulnerability-audit`
  and `secret-leak-scan`.
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
piracy/DRM-bypass code" → `authorization-boundary-scan`; "check for
leaked secrets/API keys" → `secret-leak-scan`; "any known-vulnerable
dependencies?" → `dependency-vulnerability-audit`; "does this repo have
an AGENTS.md?" → `repo-onboarding-audit`; "make this workflow into a
skill" → `skill-creator`).

For a first look at any unfamiliar repository (not just this one), a
reasonable general-purpose opening sequence is: `session-git-sync-check`
→ `repo-onboarding-audit check` → `dependency-vulnerability-audit` →
`secret-leak-scan` — none of the four depend on the documentation-
normalization skills or on this being a "documentation-as-contract"
project specifically.

All scripts are dependency-free (bash + Python 3 standard library only,
using each ecosystem's own native tool for `dependency-vulnerability-
audit` specifically) and have been tested against this repository's own
real `docs/`, `src/`, `package.json`, and git history as part of building
this skill set — including deliberately injected true-positive cases for
every scanner-shaped skill, not just clean-pass smoke tests. Every skill
in this directory passes `skill-creator/scripts/validate_skill.py --all
.claude/skills` with zero errors.
