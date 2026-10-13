#!/usr/bin/env bash
# infra/scripts/custody-ledger-move.sh — give the custody ledger a durable home.
#
# Until now every law apply appended its signed line to
# .intent/custody/ledger.jsonl in the development tree (/opt/dev/CORE) and in
# the release law (/opt/core/law). Neither is a place a record may live: a
# checkout reset drops the dev-tree lines, a law resync can overwrite the
# release-law copy. From the commit that ships this script, law apply writes
# to /opt/core/custody/ledger.jsonl whenever that directory exists.
#
# This script:
#   1. creates /opt/core/custody (core-law, 0755);
#   2. copies the release-law ledger there byte for byte (it holds every
#      record: the committed history plus each deploy's line);
#   3. checks the copy's sha256 and that the dev-tree ledger holds nothing the
#      copy lacks;
#   4. resets both working-tree ledgers to the committed version, so neither
#      tree carries uncommitted law.
#
# Run it after the commit that ships it is deployed (a deploy before then
# still writes the old places; the copy picks those lines up either way).
#
# Usage (as darek):
#   sudo bash infra/scripts/custody-ledger-move.sh --dry-run
#   sudo bash infra/scripts/custody-ledger-move.sh
set -euo pipefail

DRY=0
if [[ "${1:-}" == "--dry-run" ]]; then DRY=1; fi

LAW_USER=core-law
CUSTODY_DIR=/opt/core/custody
DURABLE="$CUSTODY_DIR/ledger.jsonl"
RELEASE_LEDGER=/opt/core/law/.intent/custody/ledger.jsonl
DEV_REPO=/opt/dev/CORE
DEV_LEDGER="$DEV_REPO/.intent/custody/ledger.jsonl"
REL=.intent/custody/ledger.jsonl

say() { printf '%s\n' "$*"; }
die() { printf 'REFUSED: %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "run with sudo"
[[ -f "$RELEASE_LEDGER" ]] || die "no release-law ledger at $RELEASE_LEDGER"
[[ -f "$DEV_LEDGER" ]] || die "no dev-tree ledger at $DEV_LEDGER"

COMMITTED="$(mktemp)"
trap 'rm -f "$COMMITTED"' EXIT
git -c safe.directory="$DEV_REPO" -C "$DEV_REPO" show "HEAD:$REL" > "$COMMITTED" \
  || die "cannot read the committed ledger from $DEV_REPO HEAD"

# Every dev-tree line must already be in the release-law ledger.
missing="$(grep -vxFf "$RELEASE_LEDGER" "$DEV_LEDGER" || true)"
[[ -z "$missing" ]] || die "the dev-tree ledger has lines the release law lacks:
$missing"
# The committed history must be the release-law ledger's first lines.
head -c "$(stat -c %s "$COMMITTED")" "$RELEASE_LEDGER" | cmp -s - "$COMMITTED" \
  || die "the release-law ledger does not start with the committed history"

src_sum="$(sha256sum < "$RELEASE_LEDGER" | cut -d' ' -f1)"
total="$(wc -l < "$RELEASE_LEDGER")"
committed="$(wc -l < "$COMMITTED")"
say "mode: $([[ $DRY == 1 ]] && echo 'DRY RUN (nothing written)' || echo 'REAL')"
say "release-law ledger: $total lines ($committed committed, $((total - committed)) recorded by deploys)"
say "records moved unchanged (deploy lines):"
tail -n +"$((committed + 1))" "$RELEASE_LEDGER" | cut -c1-140

if [[ -e "$DURABLE" ]]; then
  if [[ "$(sha256sum < "$DURABLE" | cut -d' ' -f1)" == "$src_sum" ]]; then
    say "$DURABLE already holds this ledger; only the working-tree reset remains"
  elif head -c "$(stat -c %s "$RELEASE_LEDGER")" "$DURABLE" | cmp -s - "$RELEASE_LEDGER"; then
    say "already moved: $DURABLE holds every release-law line; nothing to do"
    exit 0
  else
    die "$DURABLE exists with different content; nothing changed"
  fi
fi

if [[ $DRY == 1 ]]; then
  say "would create $CUSTODY_DIR ($LAW_USER, 0755) and copy the ledger to $DURABLE ($src_sum)"
  say "would reset $DEV_LEDGER and $RELEASE_LEDGER to the committed $committed lines"
  exit 0
fi

install -d -o "$LAW_USER" -g "$LAW_USER" -m 0755 "$CUSTODY_DIR"
if [[ ! -e "$DURABLE" ]]; then
  install -o "$LAW_USER" -g "$LAW_USER" -m 0644 "$RELEASE_LEDGER" "$DURABLE"
fi
[[ "$(sha256sum < "$DURABLE" | cut -d' ' -f1)" == "$src_sum" ]] || die "copy does not match; working trees left untouched"
say "durable ledger: $DURABLE ($(wc -l < "$DURABLE") lines, sha256 $src_sum)"

for target in "$DEV_LEDGER" "$RELEASE_LEDGER"; do
  install -o "$LAW_USER" -g "$LAW_USER" -m 0644 "$COMMITTED" "$target"
  say "reset $target to the committed $committed lines"
done
