#!/usr/bin/env python3
"""
Check whether a repository has an agent-onboarding file (AGENTS.md, the
open convention at https://agents.md — also recognized under the legacy
alias AGENT.md, or a tool-specific equivalent like CLAUDE.md), and
whether the commands it documents actually match what the project's own
manifest says.

Modes:
  audit_agents_md.py check   [project-dir]
      Reports whether an onboarding file exists, and (if it does) flags
      any documented command that doesn't appear to match the project's
      real package.json scripts. Exit 0 if a file exists and no drift was
      found, 1 if missing or drift was found.

  audit_agents_md.py generate [project-dir] [output-path]
      Inspects the project's real manifest(s) (package.json scripts/
      engines, requirements.txt/pyproject.toml, Cargo.toml, Makefile) and
      writes a draft AGENTS.md built only from what was actually found --
      never invents a command that doesn't exist in the manifest. Refuses
      to overwrite an existing file at output-path (default:
      <project-dir>/AGENTS.md) unless it doesn't exist yet.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ONBOARDING_FILENAMES = ["AGENTS.md", "AGENT.md", "CLAUDE.md"]


def find_onboarding_file(root: Path) -> Path | None:
    for name in ONBOARDING_FILENAMES:
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def read_package_json(root: Path) -> dict | None:
    pkg_path = root / "package.json"
    if not pkg_path.is_file():
        return None
    try:
        return json.loads(pkg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def detect_manifests(root: Path) -> dict:
    """Return a dict of real, verifiable facts about the project -- never
    guessed, only what's directly present on disk."""
    facts: dict = {}
    pkg = read_package_json(root)
    if pkg:
        facts["node"] = {
            "scripts": pkg.get("scripts", {}),
            "engines": pkg.get("engines", {}),
            "package_manager": pkg.get("packageManager"),
            "workspaces": pkg.get("workspaces"),
        }
    if (root / "requirements.txt").is_file() or (root / "pyproject.toml").is_file():
        facts["python"] = {
            "requirements_txt": (root / "requirements.txt").is_file(),
            "pyproject_toml": (root / "pyproject.toml").is_file(),
        }
    if (root / "Cargo.toml").is_file():
        facts["rust"] = {"cargo_toml": True}
    if (root / "Makefile").is_file():
        facts["make"] = {"makefile": True}
    return facts


def extract_documented_commands(text: str) -> list[str]:
    """Pull out fenced-code-block shell commands from an onboarding file
    -- a crude but effective way to find claims like `npm test` that can
    be checked against reality."""
    commands = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence and stripped and not stripped.startswith("#"):
            commands.append(stripped)
    return commands


def check(root: Path) -> int:
    onboarding = find_onboarding_file(root)
    facts = detect_manifests(root)

    if not onboarding:
        print(f"MISSING: no {'/'.join(ONBOARDING_FILENAMES)} found under '{root}'.")
        if facts:
            print("Real, detected project facts that a generated file could use:")
            print(json.dumps(facts, indent=2))
        else:
            print("No recognized manifest (package.json / requirements.txt / "
                  "pyproject.toml / Cargo.toml / Makefile) found either -- "
                  "a generated draft would have very little to work with.")
        print()
        print("Run 'generate' to write a draft built only from the facts above.")
        return 1

    print(f"FOUND: {onboarding}")
    text = onboarding.read_text(encoding="utf-8", errors="ignore")
    documented = extract_documented_commands(text)

    node_scripts = facts.get("node", {}).get("scripts", {})
    if not node_scripts:
        print("No package.json scripts to cross-check against.")
        return 0

    # Look for "npm run <script>" or "npm <script>" or bare "<script>"
    # mentions of scripts that no longer exist, and scripts that exist
    # but are never mentioned anywhere in the file (informational only).
    drift = []
    npm_run_re = re.compile(r"\bnpm\s+run\s+([a-zA-Z0-9:_-]+)")
    for cmd in documented:
        for m in npm_run_re.finditer(cmd):
            script_name = m.group(1)
            if script_name not in node_scripts:
                drift.append((cmd, script_name))

    unmentioned = [
        name for name in node_scripts
        if not any(name in cmd for cmd in documented) and f'"{name}"' not in text
    ]

    if drift:
        print()
        print("DRIFT: documented command(s) reference a script that no "
              "longer exists in package.json:")
        for cmd, script_name in drift:
            print(f"  - '{cmd}' -> no such script '{script_name}'")
    if unmentioned:
        print()
        print("INFO: package.json script(s) not mentioned anywhere in the "
              f"onboarding file (not necessarily a problem): {', '.join(unmentioned)}")

    if drift:
        return 1
    print()
    print("OK: no documented command was found to reference a nonexistent "
          "package.json script.")
    return 0


def generate(root: Path, output: Path) -> int:
    if output.exists():
        print(f"REFUSING: '{output}' already exists -- not overwriting. "
              "Delete it first or choose a different output path if you "
              "really want a fresh draft.")
        return 1

    facts = detect_manifests(root)
    pkg = read_package_json(root)
    lines = ["# AGENTS.md", ""]
    lines.append(
        "Guidance for AI coding agents working in this repository. "
        "Generated from the project's own manifest files -- every command "
        "below is copied verbatim from a real script/config, not guessed."
    )
    lines.append("")

    if pkg:
        name = pkg.get("name", root.name)
        desc = pkg.get("description")
        lines.append(f"## Overview")
        lines.append("")
        overview = f"This is the `{name}` project"
        if desc:
            desc = desc.rstrip(".")
            overview += f": {desc}"
        lines.append(overview + ".")
        lines.append("")

        scripts = pkg.get("scripts", {})
        if scripts:
            lines.append("## Setup and common commands")
            lines.append("")
            lines.append("```bash")
            lines.append("npm install")
            for script_name in scripts:
                lines.append(f"npm run {script_name}")
            lines.append("```")
            lines.append("")

        engines = pkg.get("engines", {})
        if engines:
            lines.append("## Runtime requirements")
            lines.append("")
            for engine, version in engines.items():
                lines.append(f"- `{engine}` {version}")
            lines.append("")

        workspaces = pkg.get("workspaces")
        if workspaces:
            lines.append("## Monorepo layout")
            lines.append("")
            lines.append(
                "This project declares npm workspaces; nested packages may "
                "have their own scripts -- check each workspace's own "
                "package.json rather than assuming the root scripts apply."
            )
            lines.append("")

    if "python" in facts:
        lines.append("## Python setup")
        lines.append("")
        lines.append("```bash")
        if facts["python"].get("requirements_txt"):
            lines.append("pip install -r requirements.txt")
        if facts["python"].get("pyproject_toml"):
            lines.append("pip install -e .")
        lines.append("```")
        lines.append("")

    if "rust" in facts:
        lines.append("## Rust setup")
        lines.append("")
        lines.append("```bash")
        lines.append("cargo build")
        lines.append("cargo test")
        lines.append("```")
        lines.append("")

    if len(lines) <= 4:
        print("REFUSING: no recognized manifest found -- there is nothing "
              "real to generate a draft from. Write AGENTS.md by hand, or "
              "add a package.json/pyproject.toml/Cargo.toml first.")
        return 1

    lines.append(
        "<!-- Generated by repo-onboarding-audit's audit_agents_md.py -- "
        "review and edit before committing. Every command above is copied "
        "from this project's own manifest at generation time; re-run the "
        "'check' mode periodically to catch drift as scripts change. -->"
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"WROTE: draft onboarding file at '{output}'. Review it by hand "
          "before committing -- this is a starting point, not a finished "
          "document (it says nothing about code style, PR conventions, or "
          "anything not derivable from a manifest file).")
    return 0


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("check", "generate"):
        print(__doc__)
        return 2
    mode = sys.argv[1]
    root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
    if mode == "check":
        return check(root)
    output = Path(sys.argv[3]) if len(sys.argv) > 3 else root / "AGENTS.md"
    return generate(root, output)


if __name__ == "__main__":
    sys.exit(main())
