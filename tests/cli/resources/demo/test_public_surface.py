# tests/cli/resources/demo/test_public_surface.py
"""Wrapper + installer contract tests (ADR-155 U02/U03/U04).

These assert against the repository's own ``scripts/demo.sh`` and
``install-core.sh`` — the public on-ramp surface — so a regression that
reintroduces a destructive git op, an auto-run demo, or a swallowed failure is
caught mechanically.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# tests/cli/resources/demo/ -> repo root is parents[4]
REPO_ROOT = Path(__file__).resolve().parents[4]
DEMO_SH = (REPO_ROOT / "scripts" / "demo.sh").read_text(encoding="utf-8")
INSTALLER = (REPO_ROOT / "install-core.sh").read_text(encoding="utf-8")


# ── U03: the wrapper delegates only ───────────────────────────────────────────


# ID: b890dc35-1865-4614-86de-e165f18d5a93
def test_wrapper_delegates_to_the_command() -> None:
    assert "core-admin demo consequence-chain" in DEMO_SH
    assert "exec " in DEMO_SH  # passes the exit code straight through


# ID: fe22d691-a500-47a7-99a6-4d23f1722765
def test_wrapper_has_no_scenario_logic() -> None:
    lowered = DEMO_SH.lower()
    # No git mutation of the invoking checkout (U03/U04).
    for forbidden in (
        "git reset",
        "git clean",
        "git commit",
        "git add",
        "git checkout",
        "psql",
        "docker ",
    ):
        assert forbidden not in lowered, f"wrapper must not contain {forbidden!r}"
    # No swallowed failures.
    assert "|| true" not in DEMO_SH


# ── U02: installation never runs the demo ─────────────────────────────────────


@pytest.mark.parametrize(
    "invocation",
    [
        "bash scripts/demo.sh",
        "sh scripts/demo.sh",
        "./scripts/demo.sh",
        "source scripts/demo.sh",
    ],
)
# ID: 374be55f-81ea-4ee7-af5a-bbaf33211c1f
def test_installer_never_executes_the_demo_script(invocation: str) -> None:
    """The old installer ran `bash scripts/demo.sh` automatically (ADR-155 §2 defect 3).

    No non-comment line may invoke the wrapper script — that is the concrete
    auto-run mechanism U02 forbids. A comment or printed offer is fine.
    """
    for line in INSTALLER.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert invocation not in stripped, f"installer must not run {invocation!r}"


# ID: a9d417a0-0da6-4cce-94c4-f4ff288e5786
def test_installer_offers_optin_command_text() -> None:
    # The command is offered (printed) so the operator can opt in explicitly.
    assert "core-admin demo consequence-chain" in INSTALLER
