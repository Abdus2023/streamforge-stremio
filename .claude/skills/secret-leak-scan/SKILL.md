---
name: secret-leak-scan
description: Scans a repository's current working tree (source, config, and docs files) for hardcoded credentials — AWS/GitHub/Slack/Stripe/Google API keys, private key blocks, Slack webhook URLs, JWT-shaped strings, and generic password/token/secret assignments — using a fast, dependency-free heuristic regex scanner. Use before committing new source/config files, before a freeze/release gate, or whenever the user asks to check for leaked secrets, hardcoded credentials, or committed API keys. Not a replacement for gitleaks/trufflehog in a real CI pipeline (see Notes) — this is a same-session, zero-install substitute for a sandboxed agent that can't or shouldn't install those.
---

# Secret Leak Scan

Public GitHub repositories very commonly end up with committed
credentials — API keys pasted in during local testing and never removed,
`.env` files added by accident, hardcoded database passwords in a config
file. Dedicated tools for this exist (`gitleaks`, `trufflehog` — see
Notes) but installing and configuring one mid-session is often more
overhead than a sandboxed agent turn can afford, and many agent sessions
never think to check for this at all. This skill is a lightweight
zero-dependency stand-in: a single Python script with no installs
required, good enough to catch the common, obvious cases before a commit.

## Steps

1. Run:
   ```bash
   python3 scripts/scan_secrets.py [path ...]
   ```
   (defaults to `.` if no path given — but prefer scanning specific
   source/config roots like `src test docs` explicitly, since scanning
   `node_modules`/`.git`/lockfiles wastes time and the script already
   skips those directories/files by name).

2. **Every `HIGH` hit needs an immediate decision**, in this order:
   - If the matched value is a real, live credential: remove it from the
     working tree, and — critically — **rotate/revoke the credential**.
     Deleting the line from source does not undo the exposure if it was
     ever committed or pushed; git history (and any fork/clone) still has
     it. A HIGH hit found before the first commit is the cheap case:
     fix it and it never enters history.
   - If it's a placeholder/example that the scanner's placeholder filter
     didn't catch (rare — check `PLACEHOLDER_RE` in the script first),
     confirm by eye that it truly isn't a real value, then proceed;
     consider tightening the placeholder filter if this recurs.

3. **`LOW` hits are advisory only** (they don't fail the scan) — generic
   patterns like `token = "..."` also match plenty of non-secrets (a
   parser's token type name, a config schema field). Skim them, but don't
   treat a LOW hit alone as actionable without reading the surrounding
   code.

4. If this scan is part of a larger freeze/release gate (see
   `contract-freeze-gate` / `contract-normalization-pass`), run it
   alongside `authorization-boundary-scan` — they check different things
   (leaked credentials vs. unauthorized-distribution mechanisms) and a
   clean result from one says nothing about the other.

## Notes

- **This is not a substitute for `gitleaks` or `trufflehog` in a real
  CI/CD pipeline.** Those tools scan full git history (not just the
  current working tree — a secret removed in a later commit is still
  exposed in history unless history itself is rewritten), and
  `trufflehog` additionally does live credential verification (an actual
  API call confirming whether a found credential still works), which
  this script does not attempt. If the project has (or can have) a real
  CI pipeline, add one of those there; use this skill for the
  same-session, no-network, no-install check in the meantime.
- The regex patterns are deliberately conservative (specific vendor key
  formats for `HIGH`, generic assignment shapes for `LOW`) to keep false
  positives manageable. Extend `PATTERNS` in the script for any
  project-specific credential format (an internal service's token
  prefix, for example) the same way `authorization-boundary-scan` extends
  its own deny-list for a project's specific prohibited-behavior list.
- A clean scan is not proof of safety — read it the same way as
  `authorization-boundary-scan`'s clean result: "no obviously-shaped
  secret found in the current tree," not "certified secret-free."
