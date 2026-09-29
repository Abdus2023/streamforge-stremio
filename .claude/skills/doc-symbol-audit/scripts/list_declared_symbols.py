#!/usr/bin/env python3
"""list_declared_symbols.py — inventory every `interface`/`type`/`class`
declaration across a documentation tree, grouped by name.

This is the discovery step of a contradiction audit: before diffing any
one symbol field-by-field, find out which symbols are declared more than
once anywhere in the docs (candidates for contradiction) versus declared
exactly once (no audit needed yet).

Usage:
    list_declared_symbols.py [root-dir]

root-dir defaults to "docs". Prints two sections:
  1. Symbols declared 2+ times (sorted by occurrence count, descending) —
     these are the audit candidates.
  2. Symbols declared exactly once — informational only.

Note: this is a textual/regex inventory, not a TypeScript parser. It is
deliberately simple (per the "not every repeated name is a duplicate"
principle) — use extract_symbol_occurrences.py next to actually pull the
body of each occurrence for a human/agent to diff.

Known false-positive source: prose sentences that happen to start a line
with the bare word "interface"/"type"/"class" (e.g. a wrapped sentence
like "...frozen\n  interface definition." or "...`SourceAdapter`\ninterface
narrowed;") can look like a declaration. To cut this down, only names
starting with an uppercase letter are matched (real TS interface/type/
class names are conventionally PascalCase) — this alone eliminates most
prose false positives, but always sanity-check the results by eye,
especially any single-occurrence entries with an unfamiliar name.
"""
import glob
import os
import re
import sys
from collections import defaultdict

DECL_RE = re.compile(
    r"^\s*(?:export\s+)?(interface|type|class)\s+([A-Z][A-Za-z0-9_]*)\b"
)



def scan(root):
    occurrences = defaultdict(list)
    for path in sorted(glob.glob(os.path.join(root, "**", "*.md"), recursive=True)):
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                m = DECL_RE.match(line)
                if m:
                    kind, name = m.group(1), m.group(2)
                    occurrences[name].append((kind, path, lineno))
    return occurrences


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "docs"
    if not os.path.isdir(root):
        print(f"list_declared_symbols.py: '{root}' is not a directory", file=sys.stderr)
        sys.exit(2)

    occurrences = scan(root)
    multi = {n: v for n, v in occurrences.items() if len(v) > 1}
    single = {n: v for n, v in occurrences.items() if len(v) == 1}

    print(f"# Symbol inventory under '{root}'\n")
    print(f"## Declared 2+ times — audit candidates ({len(multi)})\n")
    for name, occs in sorted(multi.items(), key=lambda kv: -len(kv[1])):
        print(f"- `{name}` — {len(occs)} occurrences:")
        for kind, path, lineno in occs:
            print(f"    - {kind} {path}:{lineno}")

    print(f"\n## Declared exactly once ({len(single)})\n")
    for name, occs in sorted(single.items()):
        kind, path, lineno = occs[0]
        print(f"- `{name}` — {kind} {path}:{lineno}")


if __name__ == "__main__":
    main()
