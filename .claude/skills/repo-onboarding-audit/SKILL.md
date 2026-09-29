---
name: repo-onboarding-audit
description: Checks whether a repository has an agent-onboarding file (AGENTS.md — the open cross-tool convention at agents.md, also recognized as AGENT.md or CLAUDE.md), flags any documented command that no longer matches the project's real package.json scripts, and can generate a draft onboarding file built only from real, detected manifest facts (never invented commands). Use at the start of work in an unfamiliar repository, whenever the user asks to check or create an AGENTS.md/CLAUDE.md file, or after changing package.json scripts (to catch onboarding-doc drift).
---

# Repo Onboarding Audit

AGENTS.md is an open, cross-tool convention (supported by Claude Code,
GitHub Copilot, Cursor, OpenAI Codex, and others) for giving coding
agents accurate setup/test/build commands without cluttering the
human-facing README. A repository without one forces every agent session
to rediscover the same setup facts from scratch; a repository with a
*stale* one is worse — it actively misleads an agent into running a
command that no longer exists. This skill checks for both failure modes
and can bootstrap a first draft from real manifest data.

## Steps

1. Run:
   ```bash
   python3 scripts/audit_agents_md.py check [project-dir]
   ```
   - `MISSING` means no `AGENTS.md`/`AGENT.md`/`CLAUDE.md` exists. It
     also prints the real project facts (package.json scripts/engines,
     detected Python/Rust/Make manifests) a generated draft could use.
   - `DRIFT` means a documented `npm run <script>` command references a
     script name that no longer exists in `package.json` — the file is
     actively wrong, not just absent.
   - `OK` means the file exists and no documented command was found to
     reference a nonexistent script (this only checks `npm run` mentions
     inside fenced code blocks — it can't verify prose instructions or
     non-npm commands are accurate, so a clean result is a floor, not a
     ceiling).

2. If `MISSING`, decide whether to generate a draft:
   ```bash
   python3 scripts/audit_agents_md.py generate [project-dir] [output-path]
   ```
   This only uses facts actually present in a manifest file (package.json
   scripts/engines/workspaces, requirements.txt/pyproject.toml,
   Cargo.toml, Makefile) — it never invents a command, coding-style rule,
   or convention that isn't derivable from a real file on disk. It
   refuses to overwrite an existing file. **Always review the draft by
   hand before committing it** — it deliberately says nothing about code
   style, PR conventions, architecture, or anything a manifest file
   can't tell it, and a human/project-owner should fill those in.

3. If `DRIFT` is reported against an existing file, don't just delete the
   stale line — check whether the *script* was renamed (fix the
   reference) or genuinely removed (the doc should explain what replaced
   it, if anything, rather than silently going quiet on that workflow
   step).

4. Re-run `check` after any change to `package.json`'s `scripts` — this
   is the same before-drift-happens philosophy as
   `contract-implementation-sync`, just applied to onboarding docs
   instead of type contracts.

## Notes

- Verified against this session's own repository: it genuinely has no
  `AGENTS.md`/`AGENT.md`/`CLAUDE.md` (confirmed via `check`, which
  correctly reported `MISSING` and printed the real detected
  `package.json` scripts/engines). `generate` was verified to produce a
  draft using only those real facts, refuse to overwrite an existing
  file, and — separately, against an injected stale file referencing
  removed `lint`/`build` scripts — correctly report `DRIFT` while
  leaving a genuinely-still-present script mentioned only as `INFO`, not
  as an error.
- This is deliberately conservative: it only cross-checks `npm run
  <script>` mentions against `package.json`, and only generates content
  for ecosystems it can directly detect (Node/Python/Rust/Make). It will
  not catch prose that describes a workflow inaccurately without naming
  a specific missing script, and it has no opinion on whether a project
  *should* adopt AGENTS.md — some projects deliberately fold this into
  README.md instead (see `docs-monolith-partition`'s partition-check
  principle: no two locations should both plausibly be authoritative for
  the same concept — don't create a second onboarding file if the
  project already has an equivalent, differently-named one this script
  doesn't recognize).
