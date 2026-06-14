#!/usr/bin/env bash
#
# sync-to-demo.sh — publish the starter into the core-audit-demo checkout.
#
# Source of truth: this directory (examples/starter-intent in the CORE repo).
# Destination:     a git clone of DariuszNewecki/core-audit-demo.
#
# One-way only (CORE -> demo). Overwrites only the governed surfaces
# (.intent/, src/, the audit workflow). Leaves the demo's own LICENSE, README,
# .gitignore, and .git history untouched. Does NOT push — review and push the
# demo checkout yourself.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="${1:-$HERE/../../var/external/core-audit-demo}"

[[ -d "$DEST/.git" ]] || {
  echo "ERROR: '$DEST' is not a git checkout of core-audit-demo." >&2
  echo "Clone it first, or pass the path as \$1." >&2
  exit 1
}
DEST="$(cd "$DEST" && pwd)"

echo "Syncing starter -> $DEST"
rm -rf "$DEST/.intent" "$DEST/src"
cp -r "$HERE/.intent" "$DEST/.intent"
cp -r "$HERE/src" "$DEST/src"
mkdir -p "$DEST/.github/workflows"
cp "$HERE/.github/workflows/audit.yml" "$DEST/.github/workflows/audit.yml"
# The demo's consumer-facing README is CORE-owned too (DEMO-README.md here).
cp "$HERE/DEMO-README.md" "$DEST/README.md"

echo "Done."
echo "Review:  git -C \"$DEST\" status"
echo "Publish: git -C \"$DEST\" add -A && git -C \"$DEST\" commit && git -C \"$DEST\" push"
echo "(Only LICENSE and .gitignore in the demo are left untouched.)"
