#!/usr/bin/env bash
# CORE verdict before commit — ADR-168 D4.1 experiment (draft ADR, started 2026-10-04).
#
# Claude Code PreToolUse hook (matcher: Bash). When the assistant's command
# runs `git commit`, the same blocking offline audit CI runs is executed first,
# and the commit is refused on the same terms as the CI gate (#907 policy):
# continue only on verdict PASS/DEGRADED with zero BLOCK-severity findings;
# fail closed on anything else (crash, timeout, malformed JSON, unknown verdict).
#
# Scope, honestly: this governs the assistant's normal commit path only. It is
# producer-side configuration — the governor's own shell (`! git commit ...`)
# is not hooked, which is the deliberate escape hatch. Bypass resistance is
# D4.2 (required CI + branch protection), not this hook.
#
# The tree audited is the one each commit lands on, decided by
# core-commit-target.py beside this file (shared with core-develop-ancestry.sh):
# the payload's cwd, then a `cd <dir>` or `git -C <dir>` in the command, when
# that tree is this repository or one of its worktrees; otherwise this
# repository. The audit runs there with REPO_PATH and PYTHONPATH naming that
# tree, so it judges the tree's own law and code, not the development
# checkout's. It still reads the working tree, not the index: unstaged edits
# count, and a file staged then edited is judged as edited.
#
# `git -C <dir> commit`, `git -c k=v commit` and `/usr/bin/git commit` are
# commits. Commands built by hand-quoting (`bash -c "git commit"`, eval, xargs)
# are out of scope. An unreadable payload, or a detector that cannot run,
# refuses (fail closed).
#
# The installed copy lives in .claude/hooks/ (core-law, not in git); this
# file in infra/claude-hooks/ is its source and what CI tests.
#
# Every run appends one JSON line to var/experiments/adr168/verdicts.jsonl so
# the experiment can be evaluated from evidence.

set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-/opt/dev/CORE}"
LOG_DIR="$REPO/var/experiments/adr168"
LOG="$LOG_DIR/verdicts.jsonl"
# The audit gates (ruff, mypy, vulture) must resolve from the venv, as in CI;
# otherwise they report "tool not installed" findings.
export PATH="$REPO/.venv/bin:$PATH"

payload="$(cat)"

# Only `git commit` (anywhere in a compound command). Everything else passes untouched.
if ! trees="$(printf '%s' "$payload" | python3 -I "$(dirname "$0")/core-commit-target.py" "$REPO")"; then
  echo "CORE verdict: command refused — the hook could not tell whether it commits (see above)." >&2
  exit 2
fi
[ -n "$trees" ] || exit 0

mkdir -p "$LOG_DIR"
result="$LOG_DIR/last-audit.json"
errlog="$LOG_DIR/last-audit.err"
payload_file="$LOG_DIR/last-payload.json"
printf '%s' "$payload" >"$payload_file"
while IFS= read -r TREE; do
  start=$(date +%s)
  ( cd "$TREE" && REPO_PATH="$TREE" PYTHONPATH="$TREE/src" timeout 540 "$REPO/.venv/bin/core-admin" code audit --offline --severity=block --format=json >"$result" 2>"$errlog" )
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
ACCEPTED = {"PASS", "DEGRADED"}
BLOCK = {"block", "blocking"}

verdict, blocking, reason = None, [], None
try:
    with open(result_path, encoding="utf-8") as fh:
        data = json.load(fh)
    verdict = data.get("verdict")
    findings = data.get("findings") or []
    blocking = [f for f in findings if str(f.get("severity", "")).lower() in BLOCK]
    if raw_exit == 124:
        reason = "audit timed out (540s)"
    elif verdict not in ACCEPTED:
        reason = f"verdict={verdict!r} is not an accepted verdict {sorted(ACCEPTED)}"
    elif blocking:
        reason = f"{len(blocking)} BLOCK-severity finding(s) (verdict {verdict})"
    elif verdict == "PASS" and raw_exit != 0:
        reason = f"verdict PASS but audit exited {raw_exit}"
    elif verdict == "DEGRADED" and raw_exit not in (0, 1):
        reason = f"verdict DEGRADED but audit exited {raw_exit}"
except Exception as exc:  # crash, missing or malformed JSON -> fail closed
    reason = f"audit result unreadable ({type(exc).__name__}: {exc}); raw exit {raw_exit}"

decision = "deny" if reason else "allow"
entry = {
    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "session": session,
    "tree": tree,
    "command": cmd[:300],
    "verdict": verdict,
    "block_count": len(blocking),
    "block_rules": sorted({str(f.get("check_id") or f.get("rule_id")) for f in blocking}),
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
        lines.append(f"  - {f.get('check_id') or f.get('rule_id')}: {f.get('file_path')}:{f.get('line_number') or ''} — {str(f.get('message'))[:300]}")
    if len(blocking) > 10:
        lines.append(f"  … and {len(blocking) - 10} more (see var/experiments/adr168/last-audit.json)")
    lines.append("Fix the finding, or ask the governor; the governor can commit from their own shell.")
    print("\n".join(lines), file=sys.stderr)
    sys.exit(2)
sys.exit(0)
PY
done <<<"$trees"
exit 0
