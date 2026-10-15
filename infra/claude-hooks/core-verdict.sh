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
cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')"
session="$(printf '%s' "$payload" | jq -r '.session_id // empty')"

# Only `git commit` (anywhere in a compound command). Everything else passes untouched.
if ! printf '%s' "$cmd" | grep -Eq '(^|[;&|(][[:space:]]*|[[:space:]])git([[:space:]]+-[^[:space:]]+)*[[:space:]]+commit([[:space:]]|$)'; then
  exit 0
fi

mkdir -p "$LOG_DIR"
result="$LOG_DIR/last-audit.json"
errlog="$LOG_DIR/last-audit.err"
start=$(date +%s)
( cd "$REPO" && timeout 540 "$REPO/.venv/bin/core-admin" code audit --offline --severity=block --format=json >"$result" 2>"$errlog" )
raw_exit=$?
duration=$(( $(date +%s) - start ))

python3 - "$result" "$raw_exit" "$duration" "$LOG" "$session" "$cmd" <<'PY'
import json, sys, datetime

result_path, raw_exit, duration, log_path, session, cmd = sys.argv[1:7]
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
    lines = [f"CORE verdict: commit refused — {reason}."]
    for f in blocking[:10]:
        lines.append(f"  - {f.get('check_id') or f.get('rule_id')}: {f.get('file_path')}:{f.get('line_number') or ''} — {str(f.get('message'))[:300]}")
    if len(blocking) > 10:
        lines.append(f"  … and {len(blocking) - 10} more (see var/experiments/adr168/last-audit.json)")
    lines.append("Fix the finding, or ask the governor; the governor can commit from their own shell.")
    print("\n".join(lines), file=sys.stderr)
    sys.exit(2)
sys.exit(0)
PY
