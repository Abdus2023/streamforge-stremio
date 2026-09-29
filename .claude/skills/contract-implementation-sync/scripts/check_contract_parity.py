#!/usr/bin/env python3
"""check_contract_parity.py — compare a frozen contract's shape (from a
Markdown contract file) against its actual implementation (a TypeScript
source file), field-by-field or union-member-by-union-member, ignoring
formatting differences (Markdown files in this project format each
interface field or union member on its own line with blank lines between
for readability; real source code doesn't) that would otherwise swamp a
raw text diff with false positives.

Usage:
    check_contract_parity.py <SymbolName> <contract-root> <source-root>

Example:
    check_contract_parity.py SourceAdapter docs/contracts src

Finds every occurrence of <SymbolName> as an `interface`/`type`/`class`
declaration under both roots, extracts its body, normalizes it (for
`interface`: a field-name -> (optional?, type-text) map; for `type`
union aliases: an ordered list of string-literal members), and reports:
  - if not found in one or both roots
  - if found more than once in either root (ambiguous — fix the
    contradiction before trusting a parity check)
  - if found exactly once in each: a field/member-level diff

Exit code 0 if the shapes match exactly, 1 if they differ or the symbol
isn't cleanly found in both roots (details printed either way).

Caveat: this is a textual heuristic (see doc-symbol-audit's own
extraction script for the same caveat) — it does not understand generics,
extends/inheritance, or nested inline object types beyond simple
field: { ... } blocks shown as opaque text. Re-check any reported "match"
or "mismatch" by eye if the type involves anything more complex than flat
fields and union string literals.
"""
import glob
import os
import re
import sys

DECL_RE_TMPL = r"^\s*(?:export\s+)?(interface|type|class)\s+({name})\b"
FIELD_RE = re.compile(
    r"readonly\s+([A-Za-z0-9_]+)(\??)\s*:\s*([^;]+);", re.MULTILINE
)
STRING_LITERAL_RE = re.compile(r'"([^"]*)"')


def find_matching_brace(text, open_idx):
    depth = 0
    i = open_idx
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


def find_occurrences(root, symbol):
    decl_re = re.compile(DECL_RE_TMPL.format(name=re.escape(symbol)), re.MULTILINE)
    occurrences = []
    for path in sorted(glob.glob(os.path.join(root, "**", "*"), recursive=True)):
        if not (path.endswith(".md") or path.endswith(".ts")):
            continue
        if not os.path.isfile(path):
            continue
        text = open(path, encoding="utf-8").read()
        for m in decl_re.finditer(text):
            kind = m.group(1)
            decl_start = m.start()
            if kind in ("interface", "class"):
                brace_idx = text.find("{", decl_start)
                if brace_idx == -1:
                    body = text[decl_start : decl_start + 200]
                else:
                    end_idx = find_matching_brace(text, brace_idx)
                    body = text[decl_start:end_idx]
            else:
                # type alias: capture to the next top-level ';'
                end = text.find(";", decl_start)
                body = text[decl_start : end + 1] if end != -1 else text[decl_start:]
            lineno = text.count("\n", 0, decl_start) + 1
            occurrences.append((kind, path, lineno, body))
    return occurrences


def normalize_interface(body):
    fields = {}
    for m in FIELD_RE.finditer(body):
        name, optional, type_text = m.group(1), m.group(2), m.group(3)
        fields[name] = (optional == "?", re.sub(r"\s+", " ", type_text).strip())
    return fields


def normalize_union(body):
    return STRING_LITERAL_RE.findall(body)


def diff_interfaces(contract_fields, source_fields):
    problems = []
    only_contract = set(contract_fields) - set(source_fields)
    only_source = set(source_fields) - set(contract_fields)
    if only_contract:
        problems.append(f"fields in contract but missing from source: {sorted(only_contract)}")
    if only_source:
        problems.append(f"fields in source but not in contract: {sorted(only_source)}")
    for name in sorted(set(contract_fields) & set(source_fields)):
        c_opt, c_type = contract_fields[name]
        s_opt, s_type = source_fields[name]
        if c_opt != s_opt:
            problems.append(
                f"field '{name}': optional mismatch (contract={c_opt}, source={s_opt})"
            )
        if c_type != s_type:
            problems.append(
                f"field '{name}': type mismatch (contract='{c_type}', source='{s_type}')"
            )
    return problems


def diff_unions(contract_members, source_members):
    problems = []
    only_contract = set(contract_members) - set(source_members)
    only_source = set(source_members) - set(contract_members)
    if only_contract:
        problems.append(f"values in contract but missing from source: {sorted(only_contract)}")
    if only_source:
        problems.append(f"values in source but not in contract: {sorted(only_source)}")
    if not problems and contract_members != source_members:
        problems.append(
            f"same value set but different order: contract={contract_members}, "
            f"source={source_members} (usually harmless for a union type, but "
            "worth a human glance)"
        )
    return problems


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    symbol, contract_root, source_root = sys.argv[1], sys.argv[2], sys.argv[3]

    contract_occ = find_occurrences(contract_root, symbol)
    source_occ = find_occurrences(source_root, symbol)

    if len(contract_occ) != 1:
        print(
            f"FAIL: expected exactly 1 occurrence of `{symbol}` under "
            f"'{contract_root}', found {len(contract_occ)}: "
            f"{[f'{p}:{l}' for _, p, l, _ in contract_occ]}"
        )
        sys.exit(1)
    if len(source_occ) != 1:
        print(
            f"FAIL: expected exactly 1 occurrence of `{symbol}` under "
            f"'{source_root}', found {len(source_occ)}: "
            f"{[f'{p}:{l}' for _, p, l, _ in source_occ]}"
        )
        sys.exit(1)

    c_kind, c_path, c_line, c_body = contract_occ[0]
    s_kind, s_path, s_line, s_body = source_occ[0]

    print(f"contract: {c_kind} `{symbol}` at {c_path}:{c_line}")
    print(f"source:   {s_kind} `{symbol}` at {s_path}:{s_line}")

    if c_kind != s_kind:
        print(f"FAIL: declaration kind differs (contract={c_kind}, source={s_kind})")
        sys.exit(1)

    if c_kind in ("interface", "class"):
        problems = diff_interfaces(normalize_interface(c_body), normalize_interface(s_body))
    else:
        problems = diff_unions(normalize_union(c_body), normalize_union(s_body))

    if problems:
        print(f"FAIL: {len(problems)} discrepanc(y/ies):")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)

    print(f"OK: `{symbol}` matches field-for-field between contract and source.")
    sys.exit(0)


if __name__ == "__main__":
    main()
