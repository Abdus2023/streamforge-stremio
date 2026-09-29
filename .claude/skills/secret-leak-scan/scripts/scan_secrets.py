#!/usr/bin/env python3
"""
Scan a directory tree for hardcoded credentials / secrets committed to source.

This is a lightweight, dependency-free heuristic scanner (regex-based,
no network calls, no live credential verification) for use inside a
sandboxed agent session where installing a full tool like gitleaks or
trufflehog may not be possible or worth the time. It is deliberately
conservative in what it flags as HIGH-confidence vs LOW-confidence, and
it is NOT a replacement for a real scanner (gitleaks/trufflehog) in a
real CI pipeline — see the skill's SKILL.md for when to prefer those.

Usage:
    scan_secrets.py [path ...]

Exit code 0 if no HIGH-confidence hit is found, 1 otherwise. LOW-confidence
hits are always printed but never affect the exit code (too many
plausible false positives, e.g. "token" used as a parser/lexer term).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Directories never worth descending into.
SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "out", "coverage",
    ".venv", "venv", "__pycache__", ".next", ".turbo", ".cache",
}

# File extensions worth scanning. Binary/lock/minified files are skipped
# both because secrets rarely live there in a way this scanner could read,
# and because lockfiles are full of long opaque strings (hashes) that
# would otherwise dominate false positives.
SCAN_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".py", ".rb", ".go", ".java", ".kt", ".rs", ".php", ".cs",
    ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".env",
    ".sh", ".bash", ".zsh",
    ".md", ".txt",
}
SKIP_FILENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Cargo.lock", "Gemfile.lock", "composer.lock",
}

# Values that are almost always placeholders, not real secrets — used to
# suppress a HIGH-confidence hit down to informational when the matched
# text itself looks like a template/placeholder rather than a real value.
PLACEHOLDER_RE = re.compile(
    r"(?i)(your[_-]?|<|>|xxx|\.\.\.|changeme|example|placeholder|"
    r"insert[_-]?|redacted|dummy|fake|test[_-]?key|sample)"
)

# (label, confidence, compiled regex). HIGH = specific enough vendor
# format that a match is very unlikely to be anything else. LOW = generic
# assignment-shaped pattern that also matches many legitimate non-secrets
# (config schema fields, function parameter names, etc.) — report but
# don't fail the build on these alone.
PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("AWS Access Key ID", "HIGH", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("AWS Secret Access Key (context)", "HIGH", re.compile(
        r"(?i)aws_secret_access_key\s*[:=]\s*['\"][A-Za-z0-9/+=]{40}['\"]"
    )),
    ("GitHub token", "HIGH", re.compile(
        r"\b(ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}\b"
    )),
    ("Slack token", "HIGH", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("Stripe live key", "HIGH", re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b")),
    ("Google API key", "HIGH", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Private key block", "HIGH", re.compile(
        r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"
    )),
    ("Slack webhook URL", "HIGH", re.compile(
        r"https://hooks\.slack\.com/services/[A-Za-z0-9/]{20,}"
    )),
    ("Generic hardcoded credential assignment", "LOW", re.compile(
        r"""(?i)\b(api[_-]?key|secret|password|passwd|token|client[_-]?secret)\b
            \s*[:=]\s*
            (['"])(?!\s*\2)[^'"\s]{8,}\2
        """,
        re.VERBOSE,
    )),
    ("JWT-shaped string", "LOW", re.compile(
        r"\bey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
    )),
]

# Lines containing these are almost never a real secret even if a pattern
# matches — they read the value from the environment or a secrets
# manager rather than embedding it.
SAFE_CONTEXT_RE = re.compile(
    r"process\.env|os\.environ|import\.meta\.env|getenv\(|ENV\[|"
    r"\$\{[A-Z0-9_]+\}|vault\.|secretsmanager|keyvault"
)


def iter_files(roots: list[str]):
    for root in roots:
        p = Path(root)
        if p.is_file():
            yield p
            continue
        for path in p.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.name in SKIP_FILENAMES:
                continue
            if path.suffix not in SCAN_EXTENSIONS:
                continue
            yield path


def scan(paths: list[str]):
    high_hits = []
    low_hits = []
    for path in iter_files(paths):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if SAFE_CONTEXT_RE.search(line):
                continue
            for label, confidence, pattern in PATTERNS:
                m = pattern.search(line)
                if not m:
                    continue
                snippet = line.strip()
                if len(snippet) > 160:
                    snippet = snippet[:157] + "..."
                if PLACEHOLDER_RE.search(m.group(0)):
                    # Looks like a template/placeholder, not a real secret.
                    continue
                entry = (str(path), lineno, label, snippet)
                if confidence == "HIGH":
                    high_hits.append(entry)
                else:
                    low_hits.append(entry)
    return high_hits, low_hits


def main() -> int:
    paths = sys.argv[1:] or ["."]
    high_hits, low_hits = scan(paths)

    for path, lineno, label, snippet in high_hits:
        print(f"HIGH {path}:{lineno}: {label}: {snippet}")
    for path, lineno, label, snippet in low_hits:
        print(f"LOW  {path}:{lineno}: {label}: {snippet}")

    print()
    print(
        f"{len(high_hits)} high-confidence hit(s), {len(low_hits)} "
        f"low-confidence hit(s) — scanned {', '.join(paths)}."
    )
    print(
        "This is a heuristic regex scanner, not a verified-credential "
        "detector (unlike trufflehog) or a git-history scanner (unlike "
        "gitleaks) — it only looks at the current working tree. A clean "
        "result does not prove no secret was ever committed; check git "
        "history separately for anything sensitive, and always rotate "
        "any credential a HIGH hit confirms is real, even after removing "
        "it from the tree."
    )
    return 1 if high_hits else 0


if __name__ == "__main__":
    sys.exit(main())
