"""Tests for cli.reference_current (ADR-167 D2).

Fires/passes through the real ``CliGateEngine.verify_context`` dispatch with
the live mapping params (ADR-076 D6). Trees are small fixture Typer apps.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import typer
import yaml

from mind.governance.audit_context import AuditorContext
from mind.logic.engines.cli_gate.checks.reference_current import (
    ReferenceCurrentCheck,
)
from mind.logic.engines.cli_gate.engine import CliGateEngine
from shared.cli.reference_markdown import (
    CORE_ADMIN_PAGE,
    CORE_CLI_PAGE,
    build_reference_pages,
    click_command_for,
)


_REPO_ROOT = Path(__file__).resolve().parents[7]
_MAPPING = _REPO_ROOT / ".intent/enforcement/mappings/cli/docs_correspondence.yaml"


def _tree(name: str):
    app = typer.Typer()
    group = typer.Typer()
    app.add_typer(group, name="grp")

    @group.command(name)
    def cmd() -> None:
        """A command."""

    return click_command_for(app)


_CORE_CLI = (_tree("list"), "9.9.9")


async def _run(repo_root: Path, core_cli=_CORE_CLI) -> list:
    params = yaml.safe_load(_MAPPING.read_text(encoding="utf-8"))["mappings"][
        "cli.reference_current"
    ]["params"]
    resolver = MagicMock()
    resolver.repo_root = repo_root
    engine = CliGateEngine(path_resolver=resolver)
    engine._walk_registry = MagicMock(return_value=[])
    engine._checks["reference_current"] = ReferenceCurrentCheck(
        resolver,
        core_admin_tree=lambda: _tree("show"),
        core_cli_tree=lambda: core_cli,
    )
    return await engine.verify_context(AuditorContext(repo_path=repo_root), params)


def _write_current_pages(repo: Path) -> None:
    for rel, content in build_reference_pages(_tree("show"), _CORE_CLI).items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(content, encoding="utf-8")


async def test_passes_when_pages_are_current(tmp_path: Path) -> None:
    _write_current_pages(tmp_path)
    assert await _run(tmp_path) == []


async def test_fires_on_stale_and_missing_pages(tmp_path: Path) -> None:
    _write_current_pages(tmp_path)
    (tmp_path / CORE_ADMIN_PAGE).write_text("stale\n", encoding="utf-8")
    (tmp_path / CORE_CLI_PAGE).unlink()
    findings = await _run(tmp_path)
    assert sorted(f.file_path for f in findings) == [CORE_ADMIN_PAGE, CORE_CLI_PAGE]
    assert all(f.check_id == "cli_gate.reference_current" for f in findings)
    assert all("docs generate --write" in f.message for f in findings)


async def test_never_passes_with_core_page_uncompared(tmp_path: Path) -> None:
    """core-cli absent: the core-admin page is still compared, and the skipped
    core comparison is itself a finding (no silent green)."""
    _write_current_pages(tmp_path)
    findings = await _run(tmp_path, core_cli=None)
    assert len(findings) == 1
    assert findings[0].file_path == CORE_CLI_PAGE
    assert findings[0].context["not_compared"] is True
