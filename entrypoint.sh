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
#     Exit code is 0 (PASS), 1 (FAIL), 2 (config error), 64 (internal error).
#
# Invokes `core-admin code audit --offline --format=<F> --severity=<S>`.
# Exit codes per cli/utils/exit_codes.py:
#   0  -> EXIT_OK            (no findings)
#   1  -> EXIT_FINDINGS      (findings at or above severity)
#   2  -> EXIT_CONFIG_ERROR  (missing .intent/, malformed rule)
#   64 -> EXIT_INTERNAL_ERROR (unexpected exception escaped)

set +e

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
    --format="$FORMAT" \
    --severity="$SEVERITY"
  EXIT_CODE=$?

  case $EXIT_CODE in
    0) VERDICT="PASS" ;;
    1) VERDICT="FAIL" ;;
    *) VERDICT="ERROR" ;;
  esac

  if [ -n "${GITHUB_OUTPUT:-}" ]; then
    echo "verdict=$VERDICT" >> "$GITHUB_OUTPUT"
  fi

  echo "::notice title=CORE audit::Verdict: $VERDICT (exit $EXIT_CODE)"

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
    --format="$FORMAT" \
    --severity="$SEVERITY"
  EXIT_CODE=$?

  case $EXIT_CODE in
    0) VERDICT="PASS" ;;
    1) VERDICT="FAIL" ;;
    *) VERDICT="ERROR" ;;
  esac

  echo ""
  echo "CORE audit verdict: $VERDICT (exit $EXIT_CODE)"

fi

exit $EXIT_CODE
