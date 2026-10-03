#!/usr/bin/env bash
#
# verify.sh — regression guard for the starter constitution.
#
# Proves the starter still catches its own planted violation: src/hello.py is
# authored to break starter.no_bare_except (blocking), so a correct audit must
# exit non-zero AND name that rule. If CORE's schemas or engines drift in a way
# that breaks the starter, this fails loudly in CI instead of rotting silently.
#
# Runs against THIS directory's .intent/ (get_repo_root walks up to the nearest
# .intent, which is right here). Override the runner with CORE_ADMIN= if the
# wheel is pip-installed rather than run via poetry.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ADMIN="${CORE_ADMIN:-poetry run core-admin}"

cd "$HERE" || exit 1
# JSON, not text: the text report is a Rich table that truncates rule ids
# ("starter.no_bare_…") on a narrow, non-TTY CI log.
OUT="$($ADMIN code audit --offline --format=json --severity=block 2>/dev/null)"
CODE=$?

if [[ $CODE -eq 0 ]]; then
  echo "FAIL: audit passed, but src/hello.py must violate starter.no_bare_except."
  exit 1
fi
if ! python3 -c '
import json, sys
findings = json.loads(sys.stdin.read()).get("findings") or []
ids = {f.get("check_id") or f.get("rule_id") for f in findings}
print("findings:", ", ".join(sorted(i for i in ids if i)))
sys.exit(0 if "starter.no_bare_except" in ids else 1)
' <<<"$OUT"; then
  echo "FAIL: expected a 'starter.no_bare_except' finding; none was reported."
  exit 1
fi

echo "OK: starter caught its planted violation (exit $CODE; starter.no_bare_except fired)."
