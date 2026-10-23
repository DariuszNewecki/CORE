from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from mind.logic.engines.cli_gate.checks.reference_current import ReferenceCurrentCheck


# ID: 34f3a95f-1240-400c-988b-265470498c19
def test_ReferenceCurrentCheck_verify(tmp_path: Path) -> None:
    # Arrange
    reference_page = tmp_path / "docs" / "cli_reference.md"
    reference_page.parent.mkdir(parents=True, exist_ok=True)
    reference_page.write_text("expected content", encoding="utf-8")

    rel_path = "docs/cli_reference.md"
    expected_content = "expected content"

    path_resolver = MagicMock()
    path_resolver.repo_root = tmp_path

    fake_core_admin_tree = MagicMock(return_value=MagicMock())
    fake_core_cli_tree = MagicMock(return_value=(MagicMock(), "some_source"))

    check = ReferenceCurrentCheck(
        path_resolver=path_resolver,
        core_admin_tree=fake_core_admin_tree,
        core_cli_tree=fake_core_cli_tree,
    )

    pages = {rel_path: expected_content}

    with patch(
        "mind.logic.engines.cli_gate.checks.reference_current.build_reference_pages",
        return_value=pages,
    ) as mock_build_pages:
        # Act
        findings = check.verify(commands=[], params={})

    # Assert
    mock_build_pages.assert_called_once()
    assert findings == []


# ID: e26ccada-de73-42fb-a8bf-2c77892da96b
def test_ReferenceCurrentCheck(tmp_path):
    from mind.logic.engines.cli_gate.checks.reference_current import (
        ReferenceCurrentCheck,
    )

    page_rel = "docs/reference/core-admin.md"
    page_content = "# Core Admin Reference\n"
    page_file = tmp_path / page_rel
    page_file.parent.mkdir(parents=True, exist_ok=True)
    page_file.write_text(page_content, encoding="utf-8")

    path_resolver = MagicMock()
    path_resolver.repo_root = tmp_path

    core_admin_tree = MagicMock(return_value=MagicMock())
    core_cli_tree = MagicMock(return_value=(MagicMock(), "core-cli-version"))

    with patch(
        "mind.logic.engines.cli_gate.checks.reference_current.build_reference_pages",
        return_value={page_rel: page_content},
    ) as mock_build:
        check = ReferenceCurrentCheck(
            path_resolver=path_resolver,
            core_admin_tree=core_admin_tree,
            core_cli_tree=core_cli_tree,
        )
        findings = check.verify([], {})

    mock_build.assert_called_once()
    core_admin_tree.assert_called_once()
    core_cli_tree.assert_called_once()
    assert findings == []


# ID: a5506aaa-545d-4352-ba85-46ad667fbae7
def test_live_core_admin_tree():
    from mind.logic.engines.cli_gate.checks.reference_current import (
        live_core_admin_tree,
    )

    fake_app = MagicMock(name="app")
    sentinel_command = MagicMock(name="command")

    with (
        patch("cli.admin_cli.app", fake_app),
        patch(
            "mind.logic.engines.cli_gate.checks.reference_current.click_command_for",
            return_value=sentinel_command,
        ) as mock_click_command_for,
    ):
        result = live_core_admin_tree()

    mock_click_command_for.assert_called_once_with(fake_app)
    assert result is sentinel_command
