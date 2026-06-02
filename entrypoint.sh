#!/bin/bash
# F-10.3 — Entrypoint for the CORE audit-gate Docker action.
#
# Invokes `core-admin code audit --offline --format=<F> --severity=<S>`
# in the consumer's workspace, then derives the action's `verdict`
# output from the CLI's exit code (sysexits.h convention from F-10.1b
# cli/utils/exit_codes.py).

set +e

INTENT_PATH="${INPUT_INTENT_PATH:-.intent/}"
SEVERITY="${INPUT_SEVERITY:-block}"
FORMAT="${INPUT_FORMAT:-github-annotations}"

# GH Actions mounts the consumer's checkout at /github/workspace.
cd "${GITHUB_WORKSPACE:-/github/workspace}" || {
  echo "::error::Cannot enter workspace ${GITHUB_WORKSPACE:-/github/workspace}"
  exit 64
}

# intent-path is declared as an input for forward-compat; MVP supports
# only the default. Non-default values get a clear error rather than
# silent fallback.
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
  --format="$FORMAT" \
  --severity="$SEVERITY"
EXIT_CODE=$?

# Exit codes per cli/utils/exit_codes.py:
#   0  -> EXIT_OK            (no findings)
#   1  -> EXIT_FINDINGS      (findings at or above severity)
#   2  -> EXIT_CONFIG_ERROR  (missing .intent/, malformed rule)
#   64 -> EXIT_INTERNAL_ERROR (unexpected exception escaped)
case $EXIT_CODE in
  0) VERDICT="PASS" ;;
  1) VERDICT="FAIL" ;;
  *) VERDICT="ERROR" ;;
esac

if [ -n "$GITHUB_OUTPUT" ]; then
  echo "verdict=$VERDICT" >> "$GITHUB_OUTPUT"
fi

echo "::notice title=CORE audit::Verdict: $VERDICT (exit $EXIT_CODE)"

exit $EXIT_CODE
