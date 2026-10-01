from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

from mind.logic.engines.ast_gate.checks.protected_namespace_access_check import (
    ProtectedNamespaceAccessCheck,
)


# ID: 2813f383-066b-4264-835e-c9f72fb0082c
def test_ProtectedNamespaceAccessCheck_check_protected_namespace_access() -> None:
    cls = ProtectedNamespaceAccessCheck

    tree = ast.parse("import os\nx = 1\n")

    fake_alias_map = MagicMock()

    with (
        patch.object(
            cls,
            "_collect_tainted_assignments",
            return_value=set(),
        ),
        patch.object(
            cls,
            "_check_call",
            return_value=[],
        ),
        patch(
            "mind.logic.engines.ast_gate.checks.protected_namespace_access_check.ASTHelpers"
        ) as mock_helpers,
    ):
        mock_helpers.build_import_alias_map.return_value = fake_alias_map

        result = cls.check_protected_namespace_access(
            tree=tree,
            file_path=Path("/tmp/not_gateway/file.py"),
        )

        mock_helpers.build_import_alias_map.assert_called_once_with(tree)

        gateway_result = cls.check_protected_namespace_access(
            tree=ast.parse("pass"),
            file_path=Path("/some/gateway/path/file.py"),
        )

    assert result == []
    assert gateway_result == []
