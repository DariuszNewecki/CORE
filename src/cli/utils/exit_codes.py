# src/cli/utils/exit_codes.py

"""F-10.1b — CLI exit code constants.

A small closed set of exit codes so CI systems (GitHub Actions, GitLab
CI, pre-commit hooks) can distinguish legitimate findings from
configuration errors and internal crashes. The CI gate (F-10) is the
first invocation surface that materially needs this distinction —
prior to F-10.1b every CLI command exited 0 or 1 only, which
conflates "audit ran with findings" and "audit crashed."

The values follow common Unix conventions:

- 0 = success
- 1 = expected failure (generic)
- 2 = misuse / configuration error
- 64+ = reserved for unexpected internal errors (mirrors sysexits.h's
  EX_USAGE / EX_NOPERM / EX_SOFTWARE range, conservatively)

ADR-085 D5 lists "CI/CD gate ... merge-blocking demonstrated against a
real external repo" as F-10's exit criterion. A merge-blocking gate
must report exit 1 (findings) distinctly from exit 64 (crash) so the
external repo's branch protection rules treat them differently.
"""

from __future__ import annotations


EXIT_OK: int = 0
"""Audit ran, no findings at or above the configured severity threshold."""


EXIT_FINDINGS: int = 1
"""Audit ran, found N findings at or above the severity threshold.

Mirrors the existing `typer.Exit(1)` behaviour across the CLI surface so
existing scripts that check for non-zero exit continue to work. The
``EXIT_FINDINGS`` name is the intent-bearing label; the value 1 is
backwards-compatible."""


EXIT_CONFIG_ERROR: int = 2
"""Configuration error: missing .intent/, malformed rule, unreadable file.

Distinguished from EXIT_FINDINGS so a CI gate can surface "your CORE
setup is broken" differently from "your code has constitutional
violations." A misconfigured gate is the operator's problem; a finding
is the developer's."""


EXIT_INTERNAL_ERROR: int = 64
"""Unexpected internal exception escaped the command boundary.

A merge-blocking branch protection rule should treat this distinctly
from EXIT_FINDINGS — a crash means the gate did not actually run, so
the audit's verdict is unknown rather than negative. The 64 value sits
in sysexits.h's reserved range (64-78) and signals "this was not a
normal failure path." Set by the top-level try/except in audit
invocations, not propagated from arbitrary subroutine exits."""
