#!/usr/bin/env python3
"""check_links.py — verify every local Markdown link resolves to a file
that actually exists on disk.

Skips http(s) links and pure same-file "#fragment" anchors (those aren't
checked against a heading list — this is a *file existence* check only,
not a full anchor-resolution check). Everything else is resolved relative
to the directory of the Markdown file containing the link and must exist.

Usage:
    check_links.py [root-dir ...]

root-dir defaults to the current directory if none given. Multiple roots
may be passed (useful for checking e.g. both "docs" and "README.md"'s
directory in one run). Prints one line per broken link and exits 1 if any
are found, 0 otherwise.
"""
import glob
import os
import re
import sys

LINK_RE = re.compile(r"\]\(([^)]+)\)")


def iter_markdown_files(roots):
    for root in roots:
        if os.path.isfile(root) and root.endswith(".md"):
            yield root
            continue
        yield from glob.glob(os.path.join(root, "**", "*.md"), recursive=True)


def check(roots):
    broken = []
    checked_links = 0
    files = sorted(set(iter_markdown_files(roots)))
    for f in files:
        try:
            text = open(f, encoding="utf-8").read()
        except OSError as e:
            print(f"WARN: could not read {f}: {e}", file=sys.stderr)
            continue
        base = os.path.dirname(f)
        for m in LINK_RE.finditer(text):
            target = m.group(1).strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if target.startswith("#"):
                continue  # same-file anchor; not verified by this tool
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            checked_links += 1
            full = os.path.normpath(os.path.join(base, path_part))
            if not os.path.exists(full):
                broken.append((f, target, full))
    return files, checked_links, broken


def main():
    roots = sys.argv[1:] or ["."]
    files, checked_links, broken = check(roots)
    if broken:
        print(f"BROKEN LINKS FOUND ({len(broken)}):")
        for f, target, full in broken:
            print(f"  {f} -> '{target}' (resolved: {full})")
        sys.exit(1)
    print(
        f"OK: {len(files)} Markdown file(s) checked, "
        f"{checked_links} local link(s) verified, none broken."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
