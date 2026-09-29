#!/usr/bin/env python3
"""scan_authorization_boundary.py — lightweight, heuristic scan of a
project's actual implementation (source + dependencies, NOT documentation
— docs that *discuss* these terms in a prohibition context are expected
and correct) for patterns associated with unauthorized-distribution /
access-control-bypass mechanisms.

This is a proactive compliance gate for projects with an explicit,
documented "authorized/licensed/public-domain/user-owned content only"
boundary. It is a heuristic grep, not a legal audit or a security
scanner — it catches obviously-named dependencies and keywords, nothing
more. A clean scan is evidence of absence of the obvious cases, not proof
of full compliance; a flagged hit needs human judgment, not an automatic
verdict.

Usage:
    scan_authorization_boundary.py [source-root] [package-json-path]

source-root defaults to "src"; package-json-path defaults to
"package.json" (skipped if it doesn't exist). Prints every hit with
file:line and the matched pattern. Exits 1 if any hit was found (so it
can gate a commit/CI step), 0 if clean.
"""
import glob
import json
import os
import re
import sys

# Dependency name substrings associated with unauthorized-distribution
# tooling. Intentionally conservative (specific terms, not broad words
# like "stream" or "download" that have many legitimate uses).
BANNED_DEPENDENCY_SUBSTRINGS = [
    "torrent", "webtorrent", "bittorrent", "peerflix", "magnet-uri",
    "parse-torrent", "create-torrent", "libtorrent", "dht-rpc",
]

# Source-code keyword patterns associated with the specific prohibited
# behaviors this kind of project typically states explicitly (see
# README.md's "StreamForge is not designed to..." list, or your own
# project's equivalent boundary statement). Case-insensitive.
SOURCE_PATTERNS = [
    (re.compile(r"\btorrent\b", re.I), "torrent-related identifier"),
    (re.compile(r"magnet:", re.I), "magnet URI literal"),
    (re.compile(r"bypass\w*\s*(drm|widevine|playready|fairplay)", re.I), "DRM bypass"),
    (re.compile(r"(crack|defeat)\w*\s*(drm|widevine|playready|fairplay|access\s*control)", re.I), "DRM/access-control defeat"),
    (re.compile(r"circumvent\w*\s*auth", re.I), "authentication circumvention"),
    (re.compile(r"scrape\w*\s*(private|credential)", re.I), "private/credential scraping"),
    (re.compile(r"steal\w*\s*credential", re.I), "credential theft"),
]

# Heuristic, WARN-only check: an authorization comparison that treats
# "not denied" as allowed (permissive) rather than "is authorized"
# (restrictive) is the exact bug this class of project must avoid (an
# unknown-status source should never be treated as authorized merely
# because it wasn't explicitly denied). This is a *heuristic string
# match*, not a real data-flow check — always read the surrounding code
# by eye before trusting either a PASS or a WARN here.
PERMISSIVE_AUTH_PATTERN = re.compile(r'authoriz\w*\.\w*\s*!==\s*"denied"', re.I)
RESTRICTIVE_AUTH_PATTERN = re.compile(
    r'authoriz\w*\.\w*\s*(===|!==)\s*"authorized"', re.I
)


def scan_dependencies(package_json_path):
    hits = []
    if not os.path.isfile(package_json_path):
        return hits
    data = json.load(open(package_json_path, encoding="utf-8"))
    all_deps = {}
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        all_deps.update(data.get(key, {}) or {})
    for name in all_deps:
        for banned in BANNED_DEPENDENCY_SUBSTRINGS:
            if banned in name.lower():
                hits.append((package_json_path, 0, f"dependency '{name}' matches banned term '{banned}'"))
    return hits


def scan_source(source_root):
    hits = []
    warnings = []
    saw_restrictive_pattern = False
    for path in sorted(glob.glob(os.path.join(source_root, "**", "*"), recursive=True)):
        if not os.path.isfile(path):
            continue
        if not re.search(r"\.(ts|tsx|js|jsx|mjs|cjs)$", path):
            continue
        text = open(path, encoding="utf-8", errors="replace").read()
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern, label in SOURCE_PATTERNS:
                if pattern.search(line):
                    hits.append((path, lineno, f"{label}: {line.strip()}"))
            if PERMISSIVE_AUTH_PATTERN.search(line):
                warnings.append(
                    (path, lineno, f"possibly-permissive authorization check: {line.strip()}")
                )
            if RESTRICTIVE_AUTH_PATTERN.search(line):
                saw_restrictive_pattern = True
    return hits, warnings, saw_restrictive_pattern


def main():
    source_root = sys.argv[1] if len(sys.argv) > 1 else "src"
    package_json_path = sys.argv[2] if len(sys.argv) > 2 else "package.json"

    if not os.path.isdir(source_root):
        print(f"scan_authorization_boundary.py: '{source_root}' is not a directory", file=sys.stderr)
        sys.exit(2)

    dep_hits = scan_dependencies(package_json_path)
    source_hits, warnings, saw_restrictive = scan_source(source_root)

    all_hits = dep_hits + source_hits
    for path, lineno, msg in all_hits:
        loc = f"{path}:{lineno}" if lineno else path
        print(f"HIT  {loc}: {msg}")
    for path, lineno, msg in warnings:
        print(f"WARN {path}:{lineno}: {msg}")

    if saw_restrictive:
        print("INFO: found at least one restrictive ('=== \"authorized\"') "
              "authorization comparison — the recommended pattern.")

    print(
        f"\n{len(all_hits)} hit(s), {len(warnings)} warning(s) — "
        f"scanned '{source_root}' and '{package_json_path}'."
    )
    print(
        "This is a heuristic scan, not a legal audit — a clean result means "
        "no obviously-named violation was found, not that the project is "
        "certified compliant. Review any HIT/WARN by hand."
    )
    sys.exit(1 if all_hits else 0)


if __name__ == "__main__":
    main()
