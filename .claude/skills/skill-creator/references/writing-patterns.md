# Skill writing patterns (condensed from the open Agent Skills spec and
# Anthropic's own skill-creator skill)

## Anatomy of a skill

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter (name, description required)
│   └── Markdown instructions
└── Bundled resources (optional)
    ├── scripts/     — executable code for deterministic/repetitive tasks
    ├── references/  — docs loaded into context only as needed
    └── assets/      — files used in output (templates, icons, fonts)
```

## Progressive disclosure (three-level loading)

1. **Metadata** (`name` + `description`) — always in context, ~100 words.
   This is the *only* thing used to decide whether to activate a skill,
   so it has to carry the full triggering signal.
2. **SKILL.md body** — loaded whenever the skill activates. Keep it under
   ~500 lines; if approaching that, push detail into `references/` with a
   clear pointer from the body about when to read it.
3. **Bundled resources** — loaded only as needed. Scripts can *execute*
   without ever being loaded into context at all — this is the cheapest
   way to give a skill a large amount of deterministic capability without
   any context cost.

## Frontmatter rules (hard requirements — `validate_skill.py` checks these)

- `name`: 1–64 chars, lowercase alphanumeric + hyphens only, no leading/
  trailing hyphen, no consecutive hyphens, **must exactly match the
  parent directory name**.
- `description`: 1–1024 chars, non-empty, must describe both *what* the
  skill does and *when* to use it — this is the trigger condition, not
  human-facing marketing copy.
- Optional: `license`, `compatibility` (runtime requirements — most
  skills don't need this), `metadata` (arbitrary key-value pairs),
  `allowed-tools` (experimental tool allowlist).

## Writing a good description

The description is the *only* signal used to decide whether to trigger a
skill — there is a documented tendency for agents to **under-trigger**
skills (not use them when they'd help). Counteract this by being a little
"pushy": state what the skill does, then explicitly list several phrasings
of when to use it, including cases the user might not phrase as an
explicit request for this exact capability.

Bad: `"Helps with documentation."`

Good: `"Verifies a Markdown documentation tree has no unbalanced code
fences or broken internal links. Use whenever Markdown files have just
been edited, before committing documentation changes, or whenever the
user asks to check the docs, verify links, or check for broken links.
Always run this after any batch of documentation edits, not just when
explicitly asked."`

## Domain organization for multi-variant skills

When a skill covers multiple frameworks/domains, split by variant instead
of writing one giant SKILL.md:

```
cloud-deploy/
├── SKILL.md (workflow + selection logic)
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```

The agent reads only the reference file relevant to the current task.

## The Principle of Lack of Surprise

A skill's contents must not surprise the user relative to what it claims
to do. Never create a skill whose real behavior differs from its
description, and never create a skill designed to facilitate unauthorized
access, data exfiltration, malware, or any other malicious activity —
this applies even if asked to frame it as something else.
