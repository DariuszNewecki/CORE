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
