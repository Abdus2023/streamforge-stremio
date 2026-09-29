#!/usr/bin/env python3
"""extract_symbol_occurrences.py — pull the full body of every declaration
of a given symbol (interface/class/type) across a documentation tree, so
they can be diffed field-by-field instead of eyeballed from grep snippets.

This is the workhorse of a contradiction audit: for `interface`/`class`
declarations it does brace-matched extraction (counts `{`/`}` from the
first opening brace after the declaration line to find the true end,
handling nesting); for `type` alias declarations (which have no braces
for e.g. union types) it captures from the declaration line to the first
subsequent line ending in `;` at or before a line-count safety cap.

Usage:
    extract_symbol_occurrences.py <SymbolName> [root-dir]

root-dir defaults to "docs". Prints each occurrence as a fenced code
block labelled with its file:line, plus a final occurrence count. Exits 1
if the symbol was not found anywhere (likely a typo), 0 otherwise.

Caveats (read before trusting the output blindly):
  - This is a textual heuristic, not a real TypeScript parser. Braces
    inside string literals or comments are not specially handled — this
    is rare in practice for the short illustrative interfaces typically
    found in architecture docs, but re-check by eye if a body looks
    truncated or over-extended.
  - `type` alias extraction has a hard 40-line cap as a safety valve
    against runaway capture; if a type body is legitimately longer than
    that, extend TYPE_LINE_CAP below or extract it manually.
"""
import glob
import os
import re
import sys

TYPE_LINE_CAP = 40

DECL_RE = re.compile(
    r"^\s*(?:export\s+)?(interface|type|class)\s+" r"({name})\b"
)


def find_matching_brace(text, open_idx):
    """Given the index of an opening '{', return the index just past its
    matching closing '}' (simple depth counter, no string/comment awareness)."""
    depth = 0
    i = open_idx
    while i < len(text):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)  # unbalanced; return end of file as a fallback


def extract_interface_or_class(text, decl_start):
    brace_idx = text.find("{", decl_start)
    if brace_idx == -1:
        return text[decl_start:].splitlines()[0]
    end_idx = find_matching_brace(text, brace_idx)
    return text[decl_start:end_idx]


def extract_type_alias(lines, decl_lineno_0based):
    out = []
    for i in range(decl_lineno_0based, min(decl_lineno_0based + TYPE_LINE_CAP, len(lines))):
        out.append(lines[i])
        if lines[i].rstrip().endswith(";"):
            break
    return "\n".join(out)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    symbol = sys.argv[1]
    root = sys.argv[2] if len(sys.argv) > 2 else "docs"
    if not os.path.isdir(root):
        print(f"extract_symbol_occurrences.py: '{root}' is not a directory", file=sys.stderr)
        sys.exit(2)

    decl_re = re.compile(DECL_RE.pattern.format(name=re.escape(symbol)))
    found = 0

    for path in sorted(glob.glob(os.path.join(root, "**", "*.md"), recursive=True)):
        text = open(path, encoding="utf-8").read()
        lines = text.splitlines(keepends=True)
        offset = 0
        line_offsets = []
        for line in lines:
            line_offsets.append(offset)
            offset += len(line)

        for lineno0, line in enumerate(lines):
            m = decl_re.match(line)
            if not m:
                continue
            found += 1
            kind = m.group(1)
            decl_start = line_offsets[lineno0]
            if kind in ("interface", "class"):
                body = extract_interface_or_class(text, decl_start)
            else:
                body = extract_type_alias(lines, lineno0)
            print(f"### {path}:{lineno0 + 1}  ({kind} {symbol})\n")
            print("```ts")
            print(body.rstrip("\n"))
            print("```\n")

    print(f"--- {found} occurrence(s) of `{symbol}` found under '{root}' ---")
    sys.exit(0 if found else 1)


if __name__ == "__main__":
    main()
