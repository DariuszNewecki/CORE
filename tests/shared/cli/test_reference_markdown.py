"""Tests for ``shared.cli.reference_markdown`` — CLI tree → Markdown reference."""

from __future__ import annotations

from pathlib import Path

import typer

from shared.cli.reference_markdown import (
    GENERATED_MARKER,
    click_command_for,
    render_cli_reference,
)


def _fixture_app() -> typer.Typer:
    root = typer.Typer()
    alpha = typer.Typer(help="Alpha group does alpha things.\n\nMore detail.")
    beta = typer.Typer(help="Beta group.")
    sub = typer.Typer(help="Nested group.")
    root.add_typer(alpha, name="alpha")
    root.add_typer(beta, name="beta")
    beta.add_typer(sub, name="sub")

    @alpha.command("run")
    def run(
        target: str = typer.Argument(..., help="What to run."),
        out: Path = typer.Option(Path("var/out"), "--out", "-o", help="Out | dir."),
        write: bool = typer.Option(False, "--write", help="Apply changes."),
        secret: str = typer.Option("x", "--secret", hidden=True),
    ) -> None:
        """Run a thing.

        Writes into core-daemon-worker@<stem>.service, see ``var/<stem>.pid``.
        \f
        Internal note hidden from --help.
        """

    @alpha.command("old", hidden=True)
    def old() -> None:
        """Deprecated alias."""

    @sub.command("go")
    def go() -> None:
        """Go somewhere."""

    @root.command("version")
    def version() -> None:
        """Print the version."""

    return root


def _render() -> str:
    return render_cli_reference(click_command_for(_fixture_app()), "tool", "Intro.")


def test_page_starts_with_generated_marker_and_title() -> None:
    page = _render()
    assert page.splitlines()[0] == GENERATED_MARKER
    assert "# `tool` command reference" in page
    assert "Intro." in page
    assert "3 commands." in page


def test_hidden_commands_and_options_are_omitted() -> None:
    page = _render()
    assert "tool alpha old" not in page
    assert "--secret" not in page


def test_group_index_and_sections() -> None:
    page = _render()
    assert "| [`alpha`](#alpha) | 1 | Alpha group does alpha things. |" in page
    assert "| [`beta`](#beta) | 1 | Beta group. |" in page
    assert "| [`(top level)`](#top-level) | 1 |  |" in page
    assert "## `tool alpha` {#alpha}" in page
    assert "### `tool beta sub go` {#beta-sub-go}" in page


def test_command_entry_has_usage_help_and_option_table() -> None:
    page = _render()
    assert "### `tool alpha run` {#alpha-run}" in page
    assert "tool alpha run TARGET [OPTIONS]" in page
    assert "| `TARGET` | required |" in page
    assert "| `--out`, `-o` | `var/out` | Out \\| dir. |" in page
    assert "| `--write` | off | Apply changes. |" in page


def test_click_form_feed_tail_is_dropped() -> None:
    assert "Internal note" not in _render()


def test_angle_brackets_escaped_outside_code_spans_only() -> None:
    page = _render()
    assert "core-daemon-worker@&lt;stem>.service" in page
    assert "``var/<stem>.pid``" in page


def test_rendering_is_deterministic() -> None:
    assert _render() == _render()


def test_real_core_admin_tree_renders() -> None:
    from cli.admin_cli import app

    page = render_cli_reference(click_command_for(app), "core-admin")
    assert "### `core-admin docs generate` {#docs-generate}" in page
    assert "cognitive-roles diff" not in page  # hidden deprecated alias
