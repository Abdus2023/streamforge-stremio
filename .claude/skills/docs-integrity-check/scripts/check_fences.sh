#!/usr/bin/env bash
# check_fences.sh — verify every Markdown file has a balanced number of
# ``` fence markers (an odd count means a code block was left open, which
# silently swallows everything after it as "code").
#
# Usage:
#   check_fences.sh [root-dir]
#
# root-dir defaults to "docs". Exits 0 if all files are balanced, 1 if any
# file has an odd fence count (prints each offender and its count).

set -euo pipefail

ROOT="${1:-docs}"

if [ ! -d "$ROOT" ]; then
  echo "check_fences.sh: '$ROOT' is not a directory" >&2
  exit 2
fi

status=0
count=0

while IFS= read -r -d '' f; do
  count=$((count + 1))
  n=$(grep -c '^```' "$f" 2>/dev/null || true)
  n=${n:-0}
  if [ $((n % 2)) -ne 0 ]; then
    echo "UNBALANCED: $f ($n fence markers)"
    status=1
  fi
done < <(find "$ROOT" -type f -name '*.md' -print0)

if [ "$status" -eq 0 ]; then
  echo "OK: $count Markdown file(s) checked under '$ROOT', all fence-balanced."
fi

exit "$status"
