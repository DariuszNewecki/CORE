from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from mind.logic.engines.cli_gate.checks.docs_no_phantom_commands import (
    CORE_CLI_PAGE,
    DocsNoPhantomCommandsCheck,
)


# ID: c6797709-13de-4f5f-b215-920c7a0e728a
def test_DocsNoPhantomCommandsCheck_verify(tmp_path: Path) -> None:
    reference = tmp_path / CORE_CLI_PAGE
    reference.parent.mkdir(parents=True, exist_ok=True)
    reference.write_text("core foo\n", encoding="utf-8")

    path_resolver = MagicMock()
    path_resolver.repo_root = tmp_path

    core_admin_tree = MagicMock()

    check = DocsNoPhantomCommandsCheck(
        path_resolver=path_resolver,
        core_admin_tree=core_admin_tree,
    )

    check._docs = MagicMock(return_value=[])

    with (
        patch(
            "mind.logic.engines.cli_gate.checks.docs_no_phantom_commands.inventory_from_tree",
            return_value=MagicMock(),
        ) as mock_inv_tree,
        patch(
            "mind.logic.engines.cli_gate.checks.docs_no_phantom_commands.inventory_from_reference",
            return_value=MagicMock(),
        ) as mock_inv_ref,
        patch(
            "mind.logic.engines.cli_gate.checks.docs_no_phantom_commands.find_phantom_mentions",
            return_value=[],
        ) as mock_find,
    ):
        result = check.verify(commands=[], params={})

    assert result == []
    check._docs.assert_called_once_with({})
    mock_inv_tree.assert_called_once()
    mock_inv_ref.assert_called_once()
    mock_find.assert_called_once()
