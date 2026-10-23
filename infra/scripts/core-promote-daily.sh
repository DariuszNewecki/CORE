#!/bin/bash
# Opens or updates the daily promotion pull request (promote/next -> live).
#
# Governor 2026-10-23 (#1255, decision 2A): core-claude opens the promotion
# every day at a fixed time, without asking; the governor's part is the
# approval. core-promote-propose.timer never ran (no token) and is removed.
# core-claude's gh login (core-claude-bot) already opens every promotion, so
# this runs from core-claude's crontab:
#   0 6 * * * git -C /opt/dev/CORE fetch -q origin main && git -C /opt/dev/CORE show origin/main:infra/scripts/core-promote-daily.sh | bash
#
# It runs `promote propose` from a detached worktree at main's head, so the
# summary is built by main's code whatever the dev checkout holds, and reads
# CORE's alarms through the read-only database login.

set -euo pipefail

repo="${CORE_DEV_REPO:-/opt/dev/CORE}"
python="${CORE_DEV_PYTHON:-$repo/.venv/bin/python}"
wt="$repo/var/tmp/wt-promote-daily"

git -C "$repo" fetch -q origin main
git -C "$repo" worktree remove --force "$wt" 2>/dev/null || rm -rf "$wt"
git -C "$repo" worktree add -q --detach "$wt" origin/main
trap 'git -C "$repo" worktree remove --force "$wt"' EXIT

cd "$wt"
CORE_GITHUB_TOKEN="$(gh auth token)" PYTHONPATH="$wt/src" \
    "$python" -m cli.admin_cli --readonly promote propose
