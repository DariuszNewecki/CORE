"""Tests for ``core-admin docs generate``.

Calls the undecorated coroutine (``generate_docs_command.__wrapped__``) so the
``@core_command`` machinery stays out of the way. The core-admin tree comes
from a fake Typer context and the core-cli tree from a patched loader, so the
tests do not depend on core-cli being installed; pages land in ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import typer

from cli.resources.docs import generate as gen
from shared.cli.reference_markdown import GENERATED_MARKER, click_command_for


def _tree(name: str) -> typer.Typer:
    app = typer.Typer()
    group = typer.Typer(help=f"{name} group.")
    app.add_typer(group, name="grp")

    @group.command("show")
    def show() -> None:
        """Show something."""

    return app


def _ctx() -> SimpleNamespace:
    root = SimpleNamespace(command=click_command_for(_tree("admin")))
    return SimpleNamespace(find_root=lambda: root)


async def _run(repo: Path, *, write: bool, core_cli: object = "default") -> None:
    loaded = (
        (click_command_for(_tree("consumer")), "9.9.9")
        if core_cli == "default"
        else core_cli
    )
    with (
        patch.object(gen, "core_source_root", return_value=repo),
        patch.object(gen, "_load_core_cli", return_value=loaded),
    ):
        await gen.generate_docs_command.__wrapped__(ctx=_ctx(), write=write)


@pytest.mark.asyncio
async def test_preview_writes_nothing(tmp_path: Path) -> None:
    await _run(tmp_path, write=False)
    assert not (tmp_path / "docs").exists()


@pytest.mark.asyncio
async def test_write_creates_both_pages(tmp_path: Path) -> None:
    await _run(tmp_path, write=True)
    admin = (tmp_path / gen.CORE_ADMIN_PAGE).read_text(encoding="utf-8")
    consumer = (tmp_path / gen.CORE_CLI_PAGE).read_text(encoding="utf-8")
    assert admin.startswith(GENERATED_MARKER)
    assert "### `core-admin grp show` {#grp-show}" in admin
    assert "### `core grp show` {#grp-show}" in consumer
    assert "version 9.9.9" in consumer


@pytest.mark.asyncio
async def test_second_write_leaves_pages_unchanged(tmp_path: Path) -> None:
    await _run(tmp_path, write=True)
    page = tmp_path / gen.CORE_ADMIN_PAGE
    before = page.stat().st_mtime_ns
    await _run(tmp_path, write=True)
    assert page.stat().st_mtime_ns == before


@pytest.mark.asyncio
async def test_missing_core_cli_refuses_and_writes_nothing(tmp_path: Path) -> None:
    with pytest.raises(typer.Exit) as exc:
        await _run(tmp_path, write=True, core_cli=None)
    assert exc.value.exit_code == 1
    assert not (tmp_path / "docs").exists()


@pytest.mark.asyncio
async def test_installed_wheel_without_source_checkout_refuses(tmp_path: Path) -> None:
    with (
        patch.object(gen, "core_source_root", return_value=None),
        pytest.raises(typer.Exit) as exc,
    ):
        await gen.generate_docs_command.__wrapped__(ctx=_ctx(), write=True)
    assert exc.value.exit_code == 1


def test_change_summary() -> None:
    assert gen._change_summary(None, "a\n") == "new"
    assert gen._change_summary("a\n", "a\n") == "unchanged"
    assert gen._change_summary("a\nb\n", "a\nc\nd\n") == "changed (+2 / -1 lines)"
