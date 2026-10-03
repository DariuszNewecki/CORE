"""Tests for cli.docs_no_phantom_commands (ADR-167 D3).

Unit tests for the pure helpers, then a fires/passes pair through the real
``CliGateEngine.verify_context`` dispatch with params loaded from the live
mapping (ADR-076 D6 firing coverage). The core-admin tree is a small fixture
Typer app, never the real CLI.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import typer
import yaml

from mind.governance.audit_context import AuditorContext
from mind.logic.engines.cli_gate.checks.docs_no_phantom_commands import (
    CommandInventory,
    DocsNoPhantomCommandsCheck,
    find_phantom_mentions,
    inventory_from_reference,
    inventory_from_tree,
    iter_code_mentions,
    resolve_mention,
)
from mind.logic.engines.cli_gate.engine import CliGateEngine
from shared.cli.reference_markdown import click_command_for


_REPO_ROOT = Path(__file__).resolve().parents[7]
_MAPPING = _REPO_ROOT / ".intent/enforcement/mappings/cli/docs_correspondence.yaml"


def _admin_tree():
    app = typer.Typer()
    project = typer.Typer()
    coherence = typer.Typer()
    seed = typer.Typer()
    app.add_typer(project, name="project")
    app.add_typer(coherence, name="coherence")
    coherence.add_typer(seed, name="seed")

    @project.command("new")
    def new() -> None:
        """New."""

    @project.command("old", hidden=True)
    def old() -> None:
        """Deprecated alias."""

    @seed.command("bootstrap")
    def bootstrap() -> None:
        """Bootstrap."""

    return click_command_for(app)


_CORE_REFERENCE = "### `core proposals list` {#proposals-list}\n"


def test_inventory_from_tree_separates_hidden() -> None:
    inv = inventory_from_tree(_admin_tree())
    assert inv.commands == {("project", "new"), ("coherence", "seed", "bootstrap")}
    assert inv.hidden == {("project", "old")}
    assert ("coherence", "seed") in inv.groups


def test_inventory_from_reference_reads_headings() -> None:
    assert inventory_from_reference(_CORE_REFERENCE).commands == {("proposals", "list")}


def test_mentions_only_in_code() -> None:
    text = (
        "The core governance runtime runs core audit rules.\n"
        "Run `core-admin project new demo --write` now.\n"
        "```bash\n"
        "core proposals list\n"
        "```\n"
        "pip install core-cli and core_cli are not mentions: `core-cli`\n"
    )
    assert list(iter_code_mentions(text)) == [
        (2, "core-admin", ("project", "new", "demo")),
        (4, "core", ("proposals", "list")),
    ]


def test_resolve_mention() -> None:
    inv = inventory_from_tree(_admin_tree())
    assert resolve_mention(("project", "new", "demo"), inv) is None
    assert resolve_mention(("coherence", "seed", "bootstrap"), inv) is None
    assert resolve_mention(("coherence",), inv) is None  # group mention
    assert resolve_mention(("project", "old"), inv) == ("hidden", ("project", "old"))
    assert resolve_mention(("project", "onboard"), inv) == (
        "phantom",
        ("project", "onboard"),
    )
    assert resolve_mention(("secrets", "list"), inv) == ("phantom", ("secrets",))


def test_allow_mentions_exempts_exact_string() -> None:
    inventories = {
        "core-admin": inventory_from_tree(_admin_tree()),
        "core": CommandInventory(frozenset()),
    }
    docs = {"docs/a.md": "`core-admin dev chat` was removed.\n"}
    assert [p.mention for p in find_phantom_mentions(docs, inventories)] == [
        "core-admin dev"
    ]
    assert find_phantom_mentions(docs, inventories, frozenset({"core-admin dev"})) == []


async def _run(repo_root: Path) -> list:
    params = yaml.safe_load(_MAPPING.read_text(encoding="utf-8"))["mappings"][
        "cli.docs_no_phantom_commands"
    ]["params"]
    resolver = MagicMock()
    resolver.repo_root = repo_root
    engine = CliGateEngine(path_resolver=resolver)
    engine._walk_registry = MagicMock(return_value=[])
    engine._checks["docs_no_phantom_commands"] = DocsNoPhantomCommandsCheck(
        resolver, core_admin_tree=_admin_tree
    )
    return await engine.verify_context(AuditorContext(repo_path=repo_root), params)


def _repo(tmp_path: Path, doc: str) -> Path:
    (tmp_path / "docs" / "reference").mkdir(parents=True)
    (tmp_path / "docs" / "reference" / "core.md").write_text(_CORE_REFERENCE)
    # Generated pages are out of scope even when they name phantoms.
    (tmp_path / "docs" / "reference" / "core-admin.md").write_text(
        "`core-admin nothing here`\n"
    )
    (tmp_path / "docs" / "guide.md").write_text(doc)
    (tmp_path / "README.md").write_text("Run `core proposals list`.\n")
    return tmp_path


async def test_fires_on_phantom_and_hidden_mentions(tmp_path: Path) -> None:
    repo = _repo(
        tmp_path,
        "Use `core-admin project onboard x`.\n\n```\ncore-admin project old\n```\n",
    )
    findings = await _run(repo)
    assert [(f.file_path, f.line_number, f.context["kind"]) for f in findings] == [
        ("docs/guide.md", 1, "phantom"),
        ("docs/guide.md", 4, "hidden"),
    ]
    assert all(f.check_id == "cli_gate.docs_no_phantom_commands" for f in findings)


async def test_passes_when_every_mention_resolves(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "Run `core-admin project new demo --write`.\n")
    assert await _run(repo) == []


async def test_missing_core_reference_is_a_finding(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "ok\n")
    (repo / "docs" / "reference" / "core.md").unlink()
    findings = await _run(repo)
    assert len(findings) == 1
    assert "not checked" in findings[0].message
