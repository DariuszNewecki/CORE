"""#1377: `law apply` / `law apply-merge` start without the CoreContext.

Promotion #1376 added the action setup.llm and its action_risk.yaml line.
core-deploy runs the NEW release's `core-admin law apply-merge` while the OLD
law is installed; building the CoreContext checks every registered action
against that law and refused, so the line that rates setup.llm could never
be applied. The commands that install law now skip that build.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from body.atomic.registry import ConstitutionalError
from cli import admin_cli
from cli.admin_cli import _installs_law


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["law", "apply-merge", "p1", "--write"], True),
        (["law", "apply", "p1"], True),
        (["--readonly", "law", "apply", "p1"], True),
        (["law", "check-tree"], False),
        (["law", "auto-apply"], False),
        (["code", "audit", "--offline"], False),
        ([], False),
    ],
)
def test_installs_law(argv: list[str], expected: bool) -> None:
    assert _installs_law(argv) is expected


def test_apply_merge_runs_although_the_installed_law_refuses_the_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _refuse(_registry):
        raise ConstitutionalError(
            "action_risk policy is missing impact_level for registered "
            "actions: ['setup.llm']."
        )

    monkeypatch.setattr(admin_cli, "create_core_context", _refuse)
    argv = [
        "law",
        "apply-merge",
        "p1",
        "--proposals-dir",
        "/nonexistent",
        "--merge-commit",
        "0" * 40,
        "--merged-by",
        "x",
        "--repo",
        "/nonexistent",
    ]
    monkeypatch.setattr(admin_cli.sys, "argv", ["core-admin", *argv])
    result = CliRunner().invoke(admin_cli.app, argv)
    # It reached the command itself, which refuses to run outside core-law.
    assert "runs only as core-law" in result.output, result.output
    assert "missing impact_level" not in result.output
