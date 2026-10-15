#!/usr/bin/env bash
# CORE verdict before commit — ADR-168 D4.1 experiment (draft ADR, started 2026-10-04).
#
# Claude Code PreToolUse hook (matcher: Bash). When the assistant's command
# runs `git commit`, CORE's per-file change check runs first — the
# change_verdict tool, through `core-admin code verify` — and the commit is
# refused when it says BLOCKED. It is continued only on CLEAR_IN_SCOPE or
# NO_CHANGES; anything else fails closed (NOT_EVALUATED, crash, timeout,
# malformed JSON, unknown verdict).
#
# This is fast producer feedback, not the authoritative verdict. The full
# offline audit, including the whole-repository rules this check names as not
# evaluated, runs in CI and gates the merge (#907). The hook ran that full
# audit until 2026-10-15; it took minutes per commit and duplicated CI.
#
# The files judged are the commit's change as far as it can be known before
# git runs: every path in the tree that differs from HEAD, untracked included
# (so `git add new.py && git commit` judges new.py). It reads the working
# tree, not the index: unstaged edits count, and a file staged then edited is
# judged as edited.
#
# Scope, honestly: this governs the assistant's normal commit path only. It is
# producer-side configuration — the governor's own shell (`! git commit ...`)
# is not hooked, which is the deliberate escape hatch. Bypass resistance is
# D4.2 (required CI + branch protection), not this hook.
#
# The tree judged is the one each commit lands on, decided by
# core-commit-target.py beside this file: the payload's cwd, then a `cd <dir>`
# or `git -C <dir>` in the command. A worktree of this repository is judged
# with REPO_PATH and PYTHONPATH naming it (its own law and code); another
# repository governed by CORE (it has .intent/) is judged with REPO_PATH only;
# a repository without .intent/ is not judged.
#
# The check runs the DEPLOYED release's core-admin (/opt/core/current), not
# the development checkout's .venv: the checkout lags main and its .env is
# not the assistant's to read (governor 2026-10-15, #942). CORE_ADMIN
# overrides the path (tests). A missing release refuses (fail closed).
#
# `git -C <dir> commit`, `git -c k=v commit` and `/usr/bin/git commit` are
# commits. Commands built by hand-quoting (`bash -c "git commit"`, eval, xargs)
# are out of scope. An unreadable payload, or a detector that cannot run,
# refuses (fail closed).
#
# The installed copy lives in .claude/hooks/ (core-law, not in git); this
# file in infra/claude-hooks/ is its source and what CI tests, and core-deploy
# installs it from main on every deploy (governor 2026-10-15).
#
# Every run appends one JSON line to var/experiments/adr168/verdicts.jsonl so
# the experiment can be evaluated from evidence.

set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-/opt/dev/CORE}"
LOG_DIR="$REPO/var/experiments/adr168"
LOG="$LOG_DIR/verdicts.jsonl"
CORE_ADMIN="${CORE_ADMIN:-/opt/core/current/venv/bin/core-admin}"
# The per-file gates (ruff, mypy, vulture) resolve from the release, then
# the dev venv (the release has no dev tools); never "not installed".
PATH="$(dirname "$CORE_ADMIN"):$REPO/.venv/bin:$PATH"
export PATH

payload="$(cat)"

# Only `git commit` (anywhere in a compound command). Everything else passes untouched.
if ! trees="$(printf '%s' "$payload" | python3 -I "$(dirname "$0")/core-commit-target.py" "$REPO")"; then
  echo "CORE verdict: command refused — the hook could not tell whether it commits (see above)." >&2
  exit 2
fi
[ -n "$trees" ] || exit 0

if [ ! -x "$CORE_ADMIN" ]; then
  echo "CORE verdict: commit refused — no deployed core-admin at $CORE_ADMIN." >&2
  exit 2
fi

mkdir -p "$LOG_DIR"
result="$LOG_DIR/last-verdict.json"
errlog="$LOG_DIR/last-verdict.err"
payload_file="$LOG_DIR/last-payload.json"
printf '%s' "$payload" >"$payload_file"
while IFS= read -r TREE; do
  start=$(date +%s)
  # A CORE tree runs its own code (PYTHONPATH); any other repository runs
  # the release's.
  if [ -f "$TREE/src/cli/admin_cli.py" ]; then pypath="$TREE/src"; else pypath=""; fi
  ( cd "$TREE" && REPO_PATH="$TREE" PYTHONPATH="$pypath" timeout 180 "$CORE_ADMIN" code verify >"$result" 2>"$errlog" )
  raw_exit=$?
  duration=$(( $(date +%s) - start ))
  python3 -I - "$result" "$raw_exit" "$duration" "$LOG" "$TREE" "$payload_file" <<'PY' || exit 2
import json, sys, datetime

result_path, raw_exit, duration, log_path, tree, payload_path = sys.argv[1:7]
with open(payload_path, encoding="utf-8") as fh:
    payload = json.load(fh)
session = str(payload.get("session_id") or "")
cmd = payload["tool_input"]["command"]
raw_exit, duration = int(raw_exit), int(duration)
ACCEPTED = {"CLEAR_IN_SCOPE", "NO_CHANGES"}

verdict, blocking, files, reason = None, [], [], None
try:
    with open(result_path, encoding="utf-8") as fh:
        data = json.load(fh)
    verdict = data.get("verdict")
    blocking = data.get("blocking") or []
    files = (data.get("scope") or {}).get("files") or []
    if raw_exit == 124:
        reason = "change check timed out (180s)"
    elif verdict == "BLOCKED":
        reason = f"{len(blocking)} blocking violation(s) in the changed files"
    elif verdict not in ACCEPTED:
        reason = f"verdict={verdict!r} is not an accepted verdict {sorted(ACCEPTED)}"
        if data.get("error"):
            reason += f": {str(data['error'])[:300]}"
    elif raw_exit != 0:
        reason = f"verdict {verdict} but the change check exited {raw_exit}"
except Exception as exc:  # crash, missing or malformed JSON -> fail closed
    reason = f"change check result unreadable ({type(exc).__name__}: {exc}); raw exit {raw_exit}"

decision = "deny" if reason else "allow"
entry = {
    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "session": session,
    "tree": tree,
    "command": cmd[:300],
    "verdict": verdict,
    "block_count": len(blocking),
    "block_rules": sorted({str(f.get("rule_id")) for f in blocking}),
    "check": "change_verdict",
    "file_count": len(files),
    "raw_exit": raw_exit,
    "duration_sec": duration,
    "decision": decision,
    "reason": reason,
}
with open(log_path, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(entry) + "\n")

if reason:
    lines = [f"CORE verdict: commit refused — {reason} (audited {tree})."]
    for f in blocking[:10]:
        lines.append(f"  - {f.get('rule_id')}: {f.get('file')}:{f.get('line') or ''} — {str(f.get('message'))[:300]}")
    if len(blocking) > 10:
        lines.append(f"  … and {len(blocking) - 10} more (see var/experiments/adr168/last-verdict.json)")
    lines.append("Fix the finding, or ask the governor; the governor can commit from their own shell.")
    print("\n".join(lines), file=sys.stderr)
    sys.exit(2)
sys.exit(0)
PY
done <<<"$trees"
exit 0
