---
name: skill-creator
description: Creates new Agent Skills from scratch, improves or restructures existing ones, and validates any skill directory against the open Agent Skills specification. Use whenever the user says "turn this into a skill," "make this reusable," "create a skill for X," "package this workflow," asks to check/lint/validate a SKILL.md or a skills directory, or wants to improve how reliably a skill triggers. Always use this before hand-writing a new SKILL.md from scratch, and always validate a skill with this skill's script after creating or editing one.
---

# Skill Creator

Turns a workflow — either one just demonstrated in the current
conversation, or one described by the user — into a well-formed,
reusable Agent Skill, and validates the result against the open Agent
Skills specification (`agentskills.io/specification`).

## Creating a skill

### 1. Capture intent

If the conversation already contains a workflow the user wants captured
(e.g. "turn this into a skill"), extract from the conversation history
first: the tools/commands actually used, the sequence of steps, any
corrections made along the way, and the input/output formats observed.
Otherwise, work out:

1. What should this skill enable the agent to do?
2. When should it trigger — what phrases/contexts?
3. What's the expected output format?
4. Does the output need verifiable test cases, or is it subjective
   (writing style, art) where that doesn't apply? Skills with objectively
   checkable output (file transforms, data extraction, fixed workflow
   steps, validators) benefit most from being paired with a real script.

### 2. Decide the anatomy

Read `references/writing-patterns.md` for the full anatomy, progressive-
disclosure model, and frontmatter rules before writing anything. In
short: `SKILL.md` (required) plus optional `scripts/` (executable,
deterministic), `references/` (loaded only as needed, use for anything
that would push the SKILL.md body over ~500 lines), `assets/` (templates/
files used in the skill's actual output).

**Prefer a real script over prose instructions whenever the task is
mechanical/deterministic** (e.g. counting fence markers, checking link
targets, extracting a brace-matched code block) — a script that a
future run can simply execute is more reliable than re-deriving the same
logic from prose each time, and it doesn't cost context to run (only to
read, and scripts don't need to be read to be executed).

### 3. Write SKILL.md

Fill in, in order: `name` (kebab-case, must match the folder name),
`description` (what it does AND when to use it — be a little "pushy," per
`references/writing-patterns.md`, since agents tend to under-trigger
skills), then the body as numbered, imperative steps. Reference any
bundled `scripts/`/`references/`/`assets/` explicitly, with guidance on
when to read/run each one.

### 4. Validate

Always run, immediately after writing or editing any skill:
```bash
python3 scripts/validate_skill.py <path-to-new-skill-dir>
```
or, to check every skill in a directory at once:
```bash
python3 scripts/validate_skill.py --all <skills-root>
```
Fix every `ERROR` before considering the skill done. Treat `WARN` lines
(e.g. body over 500 lines) as strong suggestions, not blockers — use
judgment about whether the extra length is actually justified.

### 5. Smoke-test it

If the skill bundles a script, actually run it against real input before
calling the skill done — a script that's never been executed is not yet
trustworthy tooling, it's an unverified guess. If the skill produced a
real mistake during authoring (a false positive, a wrong assumption), fix
it and record the lesson in a `references/lessons-learned.md` file inside
that skill, so the mistake doesn't get silently repeated later.

## Improving an existing skill

1. Run `python3 scripts/validate_skill.py <skill-dir>` first — fix any
   structural errors before touching content.
2. Re-read the `description` with fresh eyes: does it name specific
   trigger phrases, or is it generic ("helps with X")? Under-triggering
   is the most common failure mode — sharpen the description before
   changing the body.
3. If the body is approaching or over 500 lines, split detail into
   `references/`, leaving the body as the step list plus pointers to
   exactly when to read each reference file.
4. Re-validate and re-test after every change.

## What this skill does not do

This is a lightweight version of skill-creation tooling — it does not run
automated evals or benchmark variance across many test prompts (that
requires an eval-runner harness this environment doesn't have). What it
does provide — structural validation and a concrete writing-patterns
reference — covers the two mistakes most likely to actually break a
skill: malformed frontmatter, and a description too vague to ever
trigger.
