#!/usr/bin/env python3
"""validate_skill.py — check one or more skill directories against the
open Agent Skills specification's structural rules, plus a few practical
lints this skill set's own authoring caught in practice.

Usage:
    validate_skill.py <skill-dir> [<skill-dir> ...]
    validate_skill.py --all <skills-root>     # validate every immediate
                                               # subdirectory of the root

Checks performed (each printed as ERROR or WARN):
  - SKILL.md exists, named exactly that (case-sensitive)
  - YAML frontmatter present, delimited by --- lines
  - name: present, 1-64 chars, lowercase alnum + hyphens only, no
    leading/trailing/consecutive hyphens, matches the parent directory
    name exactly
  - description: present, 1-1024 chars, non-empty
  - body (content after frontmatter): warns if over 500 lines
    (progressive-disclosure guidance, not a hard spec limit)
  - every relative path referenced in the body that looks like it points
    at scripts/, references/, or assets/ actually exists on disk
    (catches a stale reference after a rename — a real mistake made and
    caught while authoring this skill set)

Exit code 0 if no ERRORs (WARNs are still printed but don't fail the
run); exit code 1 if any ERROR was found.
"""
import glob
import os
import re
import sys

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
RESOURCE_REF_RE = re.compile(r"`((?:scripts|references|assets)/[^`\s]+)`")


def parse_frontmatter(text):
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return None, text
    end = text.find("\n---", 4)
    if end == -1:
        return None, text
    fm_text = text[4:end]
    body = text[end + 4 :].lstrip("\n")
    fields = {}
    current_key = None
    for line in fm_text.splitlines():
        if not line.strip():
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            current_key = m.group(1)
            fields[current_key] = m.group(2).strip()
        elif current_key:
            fields[current_key] += " " + line.strip()
    return fields, body


def validate(skill_dir):
    errors = []
    warnings = []
    name = os.path.basename(os.path.normpath(skill_dir))
    skill_md = os.path.join(skill_dir, "SKILL.md")

    if not os.path.isfile(skill_md):
        # case-sensitivity check: is there a wrongly-cased variant?
        variants = [
            f for f in os.listdir(skill_dir) if f.lower() == "skill.md"
        ] if os.path.isdir(skill_dir) else []
        if variants:
            errors.append(
                f"SKILL.md must be named exactly 'SKILL.md' (found '{variants[0]}')"
            )
        else:
            errors.append("SKILL.md not found")
        return errors, warnings

    text = open(skill_md, encoding="utf-8").read()
    fields, body = parse_frontmatter(text)
    if fields is None:
        errors.append("no YAML frontmatter found (must start with '---')")
        return errors, warnings

    # name field
    fm_name = fields.get("name")
    if not fm_name:
        errors.append("frontmatter missing required 'name' field")
    else:
        if not (1 <= len(fm_name) <= 64):
            errors.append(f"name length {len(fm_name)} outside 1-64 chars")
        if "--" in fm_name:
            errors.append("name contains consecutive hyphens")
        if fm_name.startswith("-") or fm_name.endswith("-"):
            errors.append("name starts or ends with a hyphen")
        if not NAME_RE.match(fm_name):
            errors.append(
                "name must be lowercase alphanumeric and hyphens only"
            )
        if fm_name != name:
            errors.append(
                f"name '{fm_name}' does not match directory name '{name}'"
            )

    # description field
    desc = fields.get("description")
    if not desc:
        errors.append("frontmatter missing required 'description' field")
    elif not (1 <= len(desc) <= 1024):
        errors.append(f"description length {len(desc)} outside 1-1024 chars")

    # body length (guidance, not a hard spec rule)
    body_lines = body.count("\n") + (1 if body else 0)
    if body_lines > 500:
        warnings.append(
            f"SKILL.md body is {body_lines} lines (>500 recommended max — "
            "consider moving detail into references/)"
        )

    # resource references actually exist
    for ref in RESOURCE_REF_RE.findall(body):
        full = os.path.join(skill_dir, ref)
        if not os.path.exists(full):
            errors.append(f"referenced resource does not exist: {ref}")

    return errors, warnings


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)

    if args[0] == "--all":
        root = args[1] if len(args) > 1 else "."
        skill_dirs = sorted(
            d for d in glob.glob(os.path.join(root, "*"))
            if os.path.isfile(os.path.join(d, "SKILL.md"))
            or os.path.isdir(d)
        )
    else:
        skill_dirs = args

    total_errors = 0
    for d in skill_dirs:
        errors, warnings = validate(d)
        label = os.path.basename(os.path.normpath(d))
        if not errors and not warnings:
            print(f"OK    {label}")
            continue
        for e in errors:
            print(f"ERROR {label}: {e}")
        for w in warnings:
            print(f"WARN  {label}: {w}")
        total_errors += len(errors)

    print(f"\n{len(skill_dirs)} skill(s) checked, {total_errors} error(s).")
    sys.exit(1 if total_errors else 0)


if __name__ == "__main__":
    main()
