---
name: docs-integrity-check
description: Verifies a Markdown documentation tree has no unbalanced code fences (which silently swallow everything after them as "code") and no broken internal links. Use this whenever Markdown files have just been edited, before committing documentation changes, before treating a documentation set as trustworthy, or whenever the user asks to "check the docs," "verify links," "check for broken links," or "make sure the fences/formatting are OK." Always run this after any batch of documentation edits, not just when explicitly asked.
---

# Docs Integrity Check

Two fast, deterministic checks that catch the most common
documentation-corruption failure modes: an unclosed ``` fence (which
turns every following paragraph into a literal code block until the next
fence, silently hiding content) and a Markdown link that points at a file
that doesn't exist (usually from a rename, a typo, or a moved file).

Run both after **every** batch of edits to a documentation tree, not just
when the user explicitly asks — broken links and unbalanced fences are
cheap to introduce silently and expensive to notice later.

## Steps

1. Run the fence-balance check:
   ```bash
   scripts/check_fences.sh <root-dir>
   ```
   `<root-dir>` defaults to `docs` if omitted. Exit code `0` means every
   file has an even number of ``` markers. A nonzero exit code lists each
   unbalanced file and its fence count — open that file, find the missing
   closing fence (usually near the printed count/2 mismatch), and fix it.

2. Run the link check:
   ```bash
   python3 scripts/check_links.py <root-dir> [more-roots...]
   ```
   Pass every root you want covered (e.g. `docs README.md`). It resolves
   every non-`http(s)`, non-`#fragment` link relative to the file that
   contains it and reports any that don't point at an existing file.
   Note: it does **not** verify that a `#fragment` anchor matches an
   actual heading — only that the file-path portion of a link exists.

3. If either check fails, fix the reported files and re-run both checks
   until they pass. Do not proceed to commit, present, or hand off
   documentation changes while either check is failing.

4. When reporting results to the user, state the exact command output
   (file counts, broken link list, etc.) rather than summarizing "looks
   good" — these are cheap, mechanical checks and their exact output is
   the evidence a downstream reader would want, per the general
   evidence-before-claims discipline used across this skill set.

## Notes

- Both scripts are self-contained (bash + stdlib Python 3, no
  dependencies) and safe to run repeatedly; they only read files.
- They generalize the ad hoc `grep -c '^```'` / Python link-walk snippets
  that would otherwise get re-typed by hand on every documentation pass.
- If a repo has documentation outside `docs/` (e.g. a root `README.md`,
  a `CONTRIBUTING.md`), pass those paths explicitly to `check_links.py`;
  `check_fences.sh` only takes one root at a time — invoke it once per
  root if needed.
