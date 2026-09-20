#!/bin/bash
# F-10.3 — Entrypoint for the CORE audit-gate Docker action.
#
# Supports two invocation shapes (#577):
#
#   GH Actions (GITHUB_ACTIONS=true):
#     Inputs come from INPUT_* env vars (set by the actions runner).
#     Workspace is $GITHUB_WORKSPACE (default /github/workspace).
#     Findings are emitted as ::error:: / ::warning:: annotations.
#     Verdict is written to $GITHUB_OUTPUT.
#
#   Plain docker run:
#     docker run --rm -v "$PWD:/workspace" ghcr.io/dariusznewecki/core-audit-gate
#     Inputs come from CORE_* env vars (CORE_SEVERITY, CORE_FORMAT).
#     Repo is mounted at /workspace (the conventional mount point).
#     Findings are emitted as plain text to stdout.
#     Exit code is 0 (PASS), 1 (DEGRADED or FAIL), 2 (config error),
#     64 (internal error / unrecognised verdict).
#
# Invokes `core-admin code audit --offline --format=json --severity=<S>`
# and keeps the complete JSON result. The verdict is derived from that JSON
# (#907), never from the exit code alone, so DEGRADED (blocking rules not
# evaluated in stateless mode) is reported as DEGRADED -- not relabelled
# FAIL, never relabelled PASS. The requested --format is rendered from the
# same JSON afterwards (github-annotations via the runtime's own formatter).
#
# Verdict -> exit mapping (exit codes per cli/utils/exit_codes.py):
#   PASS      -> 0   (requires the CLI to have exited 0; otherwise ERROR/64)
#   DEGRADED  -> CLI exit, forced non-zero (1)  blocking rule(s) not evaluated
#   FAIL      -> CLI exit, forced non-zero (1)  findings at/above severity
#   ERROR     -> CLI exit, forced non-zero (2 config / 64 internal)
#   anything else (missing/unknown verdict, malformed or missing JSON,
#   crashed command) -> ERROR, exit 64: fail closed.

set +e

# resolve_verdict <result.json> <raw_exit>
# Prints "VERDICT EXIT SKIPPED_BLOCKING_IDS" on one line, derived from the
# JSON; fails closed to "ERROR 64" on anything it cannot read or recognise.
resolve_verdict() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

path, raw_exit = sys.argv[1], int(sys.argv[2])
CANONICAL = {"PASS", "DEGRADED", "FAIL", "ERROR"}
try:
    with open(path, encoding="utf-8") as fh:
        result = json.load(fh)
    verdict = result.get("verdict") if isinstance(result, dict) else None
except Exception:  # noqa: BLE001 - any parse/IO failure fails closed
    verdict = None
if verdict not in CANONICAL:
    print("ERROR 64")
    sys.exit(0)
if verdict == "PASS":
    exit_code = 0 if raw_exit == 0 else 64
    verdict = "PASS" if raw_exit == 0 else "ERROR"
elif verdict == "ERROR":
    exit_code = raw_exit if raw_exit != 0 else 64
else:  # DEGRADED / FAIL: non-success, keep the CLI's distinction if it gave one
    exit_code = raw_exit if raw_exit != 0 else 1
skipped = result.get("skipped_rules") or []
ids = ",".join(s.get("rule_id", "?") for s in skipped if s.get("enforcement") == "blocking")
print(f"{verdict} {exit_code} {ids}")
PY
}

# render_output <result.json> <format> <severity>
render_output() {
  case "$2" in
    json) cat "$1"; echo ;;
    github-annotations)
      python3 -c 'import json, sys; from cli.utils.annotation_formatter import format_payload; sys.stdout.write(format_payload(json.load(open(sys.argv[1], encoding="utf-8"))))' "$1" \
        || echo "::error title=CORE audit::could not render annotations from $1"
      ;;
    *)
      # text: the runtime's own Rich renderer, driven from the saved JSON;
      # plain fallback if the pinned runtime does not expose it.
      python3 - "$1" "$3" <<'PY' \
        || python3 -c 'import json, sys; r = json.load(open(sys.argv[1], encoding="utf-8")); print(f"Verdict: {r.get(\"verdict\")} (passed={r.get(\"passed\")}); findings={len(r.get(\"findings\") or [])}; skipped={len(r.get(\"skipped_rules\") or [])}")' "$1"
import json, sys
from cli.commands.check.converters import parse_min_severity
from cli.resources.code.audit import _render_text_summary
with open(sys.argv[1], encoding="utf-8") as fh:
    _render_text_summary(json.load(fh), parse_min_severity(sys.argv[2]))
PY
      ;;
  esac
}

RESULT_DIR="${RUNNER_TEMP:-$(mktemp -d)}"
RESULT="$RESULT_DIR/core-audit-result.json"

if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
  # ── GitHub Actions shape ──────────────────────────────────────────────────
  INTENT_PATH="${INPUT_INTENT_PATH:-.intent/}"
  SEVERITY="${INPUT_SEVERITY:-block}"
  FORMAT="${INPUT_FORMAT:-github-annotations}"
  WORKSPACE="${GITHUB_WORKSPACE:-/github/workspace}"

  cd "$WORKSPACE" || {
    echo "::error::Cannot enter workspace $WORKSPACE"
    exit 64
  }

  if [ "$INTENT_PATH" != ".intent/" ] && [ "$INTENT_PATH" != ".intent" ]; then
    echo "::error::intent-path: '$INTENT_PATH' not yet supported. MVP requires .intent/ at the repo root. File an issue at https://github.com/DariuszNewecki/CORE/issues if you need a custom path."
    exit 2
  fi

  if [ ! -d ".intent" ]; then
    echo "::error::CORE audit requires a .intent/ directory at the repo root. See https://github.com/DariuszNewecki/CORE for the constitutional governance model."
    exit 2
  fi

  core-admin code audit \
    --offline \
    --format=json \
    --severity="$SEVERITY" > "$RESULT"
  RAW_EXIT=$?

  read -r VERDICT EXIT_CODE SKIPPED_BLOCKING <<< "$(resolve_verdict "$RESULT" "$RAW_EXIT")"
  render_output "$RESULT" "$FORMAT" "$SEVERITY"

  if [ -n "${GITHUB_OUTPUT:-}" ]; then
    echo "verdict=$VERDICT" >> "$GITHUB_OUTPUT"
  fi

  case "$VERDICT" in
    DEGRADED)
      echo "::warning title=CORE audit DEGRADED::blocking rule(s) NOT evaluated in stateless mode (not PASS): ${SKIPPED_BLOCKING:-none listed}"
      ;;
    ERROR)
      echo "::error title=CORE audit ERROR::audit did not produce a recognised verdict (raw exit $RAW_EXIT); failing closed"
      ;;
  esac
  echo "::notice title=CORE audit::Verdict: $VERDICT (exit $EXIT_CODE, raw exit $RAW_EXIT)"

else
  # ── Plain docker run shape ────────────────────────────────────────────────
  # Mount the repo at /workspace:
  #   docker run --rm -v "$PWD:/workspace" ghcr.io/dariusznewecki/core-audit-gate
  SEVERITY="${CORE_SEVERITY:-block}"
  FORMAT="${CORE_FORMAT:-text}"
  WORKSPACE="/workspace"

  cd "$WORKSPACE" 2>/dev/null || {
    echo "ERROR: /workspace is empty or not mounted."
    echo "Mount your repository: docker run --rm -v \"\$PWD:/workspace\" ghcr.io/dariusznewecki/core-audit-gate"
    exit 64
  }

  if [ ! -d ".intent" ]; then
    echo "ERROR: No .intent/ directory found at the repository root."
    echo "CORE requires a constitutional intent directory. See https://github.com/DariuszNewecki/CORE for setup."
    exit 2
  fi

  core-admin code audit \
    --offline \
    --format=json \
    --severity="$SEVERITY" > "$RESULT"
  RAW_EXIT=$?

  read -r VERDICT EXIT_CODE SKIPPED_BLOCKING <<< "$(resolve_verdict "$RESULT" "$RAW_EXIT")"
  render_output "$RESULT" "$FORMAT" "$SEVERITY"

  echo ""
  if [ "$VERDICT" = "DEGRADED" ]; then
    echo "CORE audit: blocking rule(s) NOT evaluated in stateless mode (not PASS): ${SKIPPED_BLOCKING:-none listed}"
  fi
  echo "CORE audit verdict: $VERDICT (exit $EXIT_CODE, raw exit $RAW_EXIT)"

fi

exit "$EXIT_CODE"
