---
name: doc-symbol-audit
description: Finds every declaration of a named type/interface/class across a documentation tree, extracts each occurrence's full body, and helps build a contradiction matrix (Symbol | Canonical location | Historical definitions | Conflict | Status) before treating any documentation set as an authoritative contract. Use this whenever the user asks to audit documentation for contradictions, check whether a type/interface is defined consistently, find duplicate or competing definitions, do a "pre-freeze audit," or when documentation is being promoted from "explanatory" to "normative/contract" status. Always run this before editing or freezing any documentation contract, not just when explicitly asked to "audit."
---

# Doc Symbol Audit

Documentation that evolves by narrative example (an architecture doc that
redefines the same interface slightly differently three times as the
story progresses) accumulates contradictions that are easy to miss by
skimming, and dangerous to leave unresolved once any one definition is
treated as authoritative. This skill finds every declaration of a symbol,
pulls its full body so it can be diffed field-by-field, and gives a
template for recording the verdict.

**Do not assume two occurrences of the same name are duplicates, and do
not assume they are legitimately different layers — check the actual
field-by-field content before deciding.** Both mistakes happened during
the session this skill set was extracted from (see
`references/lessons-learned.md`).

## Steps

1. **Discover audit candidates.** If you don't already have a specific
   symbol list to check, run:
   ```bash
   python3 scripts/list_declared_symbols.py <root-dir>
   ```
   (`<root-dir>` defaults to `docs`.) This lists every `interface`/
   `type`/`class` name declared 2+ times, sorted by occurrence count —
   these are your audit candidates. Names declared exactly once need no
   further audit.

2. **Extract every occurrence of a candidate symbol:**
   ```bash
   python3 scripts/extract_symbol_occurrences.py <SymbolName> <root-dir>
   ```
   This brace-matches `interface`/`class` bodies and line-captures `type`
   alias bodies, printing each occurrence labelled with `file:line`. Read
   every occurrence in full — do not trust a truncated grep snippet.
   **Caveat:** this is a textual heuristic, not a real parser (see the
   script's own docstring for the exact limits: no string/comment-aware
   brace matching, a 40-line cap on `type` alias capture). Re-check by
   eye if a body looks truncated.

3. **Diff the occurrences by hand.** For each pair, determine:
   - Are the field sets *identical*? (Don't assume "looks similar" means
     identical — verify character-by-character, especially for enum-like
     `type X = "a" | "b" | ...` unions. A single added/removed value is
     easy to miss by eye.)
   - If not identical, is this (a) chronological evolution where a later
     draft supersedes an earlier one, (b) legitimately different layers
     that only look similar (e.g. a point-in-time probe vs. a rolling
     counter vs. an exported metrics snapshot), or (c) an unresolved
     contradiction with no evidence yet for which one should win?

4. **Record the verdict in a contradiction matrix** with these exact
   columns: `Symbol | Canonical location | Historical definitions |
   Conflict | Status`. Status must be one of: `PROVED` (settled by
   explicit, stated evidence), `ARGUMENT` (best available reading of
   ambiguous evidence, stated as such), `CONJECTURE` (a plausible guess
   with insufficient evidence — do not silently promote this to
   `PROVED`), `OPEN` (genuinely unresolved, needs a decision).

5. For every symbol resolved as `PROVED` or `ARGUMENT`, hand off to the
   **adr-writer** skill to record the decision and its rationale, and
   annotate every non-canonical occurrence in place (a blockquote stating
   which document/section is canonical, pointing to the ADR, plus an
   inline `// HISTORICAL` or `// SUPERSEDED` comment in the code block
   itself) — never delete historical drafts outright; mark them
   non-normative instead so the narrative they belong to still reads
   correctly.

6. Run **docs-integrity-check** after making any annotation edits.

## Notes

- `references/lessons-learned.md` documents two real mistakes caught in
  the session this skill set was extracted from: once claiming two
  occurrences were "identical" when a field-by-field re-check found they
  weren't, and once needing to distinguish "duplicate" from "legitimately
  layered" for a receipt/evidence type family. Read it before doing a
  large audit.
- This skill only inventories `interface`/`type`/`class` declarations
  inside fenced code blocks or plain text — it does not understand a
  real module graph, imports, or actual compiled types. It is meant for
  narrative/architecture documentation, not a real codebase (for a real
  TypeScript codebase, use the compiler/type-checker instead).
