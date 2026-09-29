---
name: authorization-boundary-scan
description: Heuristically scans a project's actual implementation (source files and package dependencies — never the documentation, which legitimately discusses these terms when stating the boundary) for patterns associated with unauthorized-distribution or access-control-bypass mechanisms (torrent/magnet libraries, DRM-bypass keywords, permissive authorization checks). Use before a freeze gate or a release for any project with an explicit "authorized/licensed/public-domain/user-owned content only" boundary, whenever new source-adapter or provider code is added, or when the user asks to check for legal/compliance issues, torrent/piracy mechanisms, or whether an authorization check is safely restrictive.
---

# Authorization Boundary Scan

A proactive compliance gate for projects that have explicitly committed
to only handling authorized/licensed/public-domain/user-owned content —
this is common for media-aggregation projects that need to stay clearly
on the legitimate side of a Popcorn-Time-style experience. It's a
heuristic scan, not a legal audit: a clean result means no *obviously*
named violation was found, not that the project is certified compliant.

**Only scans implementation (source + dependency manifest), never
documentation.** A project's own README/architecture docs will
legitimately contain words like "torrent," "DRM," or "unauthorized" when
stating the boundary itself (e.g. "StreamForge is not designed to bypass
DRM... without embedding a torrent client...") — scanning docs for these
words would produce constant false positives on the very sentences that
state the policy. Scan `src/`, not `docs/`.

## Steps

1. Run:
   ```bash
   python3 scripts/scan_authorization_boundary.py [source-root] [package-json-path]
   ```
   (`source-root` defaults to `src`, `package-json-path` defaults to
   `package.json`.) It checks:
   - dependency names (in `dependencies`/`devDependencies`/etc.) against
     a conservative deny-list of torrent/magnet-related package name
     substrings,
   - source files for keyword patterns associated with DRM bypass,
     authentication circumvention, private/credential scraping, and
     torrent/magnet identifiers,
   - a heuristic `WARN`-only check for a specific, real bug class: an
     authorization comparison that treats "not denied" as allowed
     (permissive) instead of requiring "is authorized" (restrictive) —
     the exact mistake that would let an unknown-status source slip
     through as if it were authorized merely because it was reachable.

2. **Every `HIT` is a real finding that needs a human decision** — either
   it's a genuine problem (remove the dependency / rewrite the code) or
   it's a false positive from an unrelated use of a matched word (e.g. a
   variable literally named `torrentPolicy` documenting that the project
   explicitly rejects torrents — read the surrounding code, don't just
   trust the keyword match either way).

3. **Every `WARN` on the permissive-authorization-check heuristic needs a
   manual read of the surrounding logic** — this is a string-pattern
   heuristic, not a real data-flow analysis. Confirm by hand whether an
   unknown/missing authorization status is actually treated as
   unauthorized (the safe default) before dismissing or accepting the
   warning.

4. Run this scan before any freeze-gate verdict that includes a
   "Provider Genericity Scope" or "Source Adapter" item (see
   `contract-freeze-gate`), and again whenever a new concrete source
   adapter implementation is added (this scan's dependency/keyword checks
   only look at what exists right now — a later commit could introduce a
   violation this scan hasn't seen yet).

## Notes

- This heuristic will miss anything not textually obvious (obfuscated
  code, a dependency that itself pulls in banned functionality
  transitively without a banned name of its own, a genuinely subtle
  logic bug in an authorization check that doesn't match the specific
  permissive-pattern heuristic). Treat a clean scan as "no obvious red
  flag found," not "proven compliant" — pair it with actual code review
  for anything touching authorization or source execution.
- Extend `BANNED_DEPENDENCY_SUBSTRINGS` and `SOURCE_PATTERNS` in the
  script for a project's own specific prohibited-behavior list (most
  projects state one explicitly, e.g. in a README "is not designed to..."
  section) — the shipped list is deliberately conservative/generic and
  should be tightened to match the exact boundary your project has
  committed to.
