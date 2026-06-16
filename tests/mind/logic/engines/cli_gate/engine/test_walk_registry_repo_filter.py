"""Regression test for #547 — cli_gate drops out-of-repo commands.

When ``core-runtime`` is pip-installed against a consumer repository,
``from cli.admin_cli import app`` resolves to the wheel under
site-packages, not to the consumer's repo. The cli_gate engine walks
the resulting Typer app and would otherwise surface findings against
framework code the consumer didn't author and can't act on. The fix
filters those commands out of ``_walk_registry`` so only commands
rooted in the consumer's ``repo_root`` reach the per-check verifiers.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from mind.logic.engines.cli_gate.engine import CliGateEngine


def _make_command(name: str, file_path: str | None) -> dict[str, object]:
    """Synthetic walk_typer_app output entry."""
    return {
        "command": name,
        "file_path": file_path,
        "verb": "show",
        "resource": "thing",
    }


def test_walk_registry_drops_commands_rooted_outside_repo() -> None:
    """A command whose source file lives outside repo_root is filtered out.

    Reproduces the #547 demo-PR scenario: core-runtime is pip-installed
    at /usr/local/lib/python3.12/site-packages/cli/..., consumer's
    repo_root is /github/workspace. The wheel's commands must not
    appear in the audited registry.
    """
    repo_root = Path("/github/workspace")
    path_resolver = MagicMock()
    path_resolver.repo_root = repo_root

    fake_commands = [
        _make_command(
            "admin.health",
            "/usr/local/lib/python3.12/site-packages/cli/resources/admin/health.py",
        ),
        _make_command(
            "context.build",
            "/usr/local/lib/python3.12/site-packages/cli/resources/context/build.py",
        ),
    ]

    with (
        patch("cli.admin_cli.app", MagicMock()),
        patch(
            "shared.cli.app_introspection.walk_typer_app",
            return_value=fake_commands,
        ),
    ):
        engine = CliGateEngine(path_resolver=path_resolver)
        result = engine._walk_registry()

    assert result == [], (
        "Expected all out-of-repo commands to be filtered out; "
        f"got {[c['command'] for c in result]}"
    )


def test_walk_registry_normalises_in_repo_commands_to_relative_paths() -> None:
    """Commands rooted inside repo_root keep their entry, repo-relative.

    The in-tree case (CORE auditing CORE): ``cli.admin_cli`` resolves
    to ``/opt/dev/CORE/src/cli/admin_cli.py``; the absolute path
    normalises to ``src/cli/admin_cli.py`` so downstream finding
    subjects render repo-relative (#486).
    """
    repo_root = Path("/opt/dev/CORE")
    path_resolver = MagicMock()
    path_resolver.repo_root = repo_root

    fake_commands = [
        _make_command(
            "admin.health", "/opt/dev/CORE/src/cli/resources/admin/health.py"
        ),
        _make_command(
            "context.build", "/opt/dev/CORE/src/cli/resources/context/build.py"
        ),
    ]

    with (
        patch("cli.admin_cli.app", MagicMock()),
        patch(
            "shared.cli.app_introspection.walk_typer_app",
            return_value=fake_commands,
        ),
    ):
        engine = CliGateEngine(path_resolver=path_resolver)
        result = engine._walk_registry()

    assert len(result) == 2
    assert {c["file_path"] for c in result} == {
        "src/cli/resources/admin/health.py",
        "src/cli/resources/context/build.py",
    }


def test_walk_registry_mixed_in_repo_and_out_of_repo() -> None:
    """Mixed input: in-repo entries normalise; out-of-repo entries drop.

    Defensive — covers the case where a consumer has SOME of their own
    CLI in-repo plus the framework wheel mounted alongside.
    """
    repo_root = Path("/github/workspace")
    path_resolver = MagicMock()
    path_resolver.repo_root = repo_root

    fake_commands = [
        _make_command(
            "framework.show",
            "/usr/local/lib/python3.12/site-packages/cli/show.py",
        ),
        _make_command(
            "consumer.show",
            "/github/workspace/src/cli/my_cmd.py",
        ),
    ]

    with (
        patch("cli.admin_cli.app", MagicMock()),
        patch(
            "shared.cli.app_introspection.walk_typer_app",
            return_value=fake_commands,
        ),
    ):
        engine = CliGateEngine(path_resolver=path_resolver)
        result = engine._walk_registry()

    assert [c["command"] for c in result] == ["consumer.show"]
    assert result[0]["file_path"] == "src/cli/my_cmd.py"


def test_walk_registry_preserves_entries_with_unresolved_file_path() -> None:
    """Commands with file_path absent/'none'/'unknown' are kept verbatim.

    Registry-shape checks (no_duplicates, resource_first) operate on
    the command tree regardless of source-file resolution status.
    Dropping these would mask real duplication/structure issues.
    """
    repo_root = Path("/opt/dev/CORE")
    path_resolver = MagicMock()
    path_resolver.repo_root = repo_root

    fake_commands = [
        _make_command("orphan_no_path", None),
        _make_command("orphan_none", "none"),
        _make_command("orphan_unknown", "unknown"),
    ]

    with (
        patch("cli.admin_cli.app", MagicMock()),
        patch(
            "shared.cli.app_introspection.walk_typer_app",
            return_value=fake_commands,
        ),
    ):
        engine = CliGateEngine(path_resolver=path_resolver)
        result = engine._walk_registry()

    assert [c["command"] for c in result] == [
        "orphan_no_path",
        "orphan_none",
        "orphan_unknown",
    ]


def test_walk_registry_preserves_relative_paths_untouched() -> None:
    """If the upstream walker returned a relative path, it's kept as-is.

    walk_typer_app today emits absolute paths via ``inspect.getfile``,
    but the engine shouldn't break if a future variant emits
    pre-normalised relative paths. Trust the caller for non-absolute
    inputs rather than guessing whether to re-anchor against repo_root.
    """
    repo_root = Path("/opt/dev/CORE")
    path_resolver = MagicMock()
    path_resolver.repo_root = repo_root

    fake_commands = [_make_command("pre_relative", "src/cli/relative_cmd.py")]

    with (
        patch("cli.admin_cli.app", MagicMock()),
        patch(
            "shared.cli.app_introspection.walk_typer_app",
            return_value=fake_commands,
        ),
    ):
        engine = CliGateEngine(path_resolver=path_resolver)
        result = engine._walk_registry()

    assert len(result) == 1
    assert result[0]["file_path"] == "src/cli/relative_cmd.py"
