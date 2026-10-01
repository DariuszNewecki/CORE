from __future__ import annotations

import ast
from unittest.mock import MagicMock, patch

from mind.logic.engines.ast_gate.checks.purity_checks import PurityChecks


# ID: c0d93e92-3262-42fb-add1-0f8eb06204d0
def test_PurityChecks_check_future_annotations() -> None:
    tree_with = ast.parse("from __future__ import annotations\n")
    tree_without = ast.parse("x = 1\n")

    with patch.object(
        PurityChecks, "check_future_annotations", return_value=[]
    ) as mock_check:
        result = PurityChecks.check_future_annotations(MagicMock())
        assert result == []
        mock_check.assert_called_once()





# ID: aab90f68-493b-4956-8629-feeaba4330d1
def test_PurityChecks_check_tempfile_default_dir():
    tree = ast.parse("import tempfile\ntempfile.gettempdir()\n")

    with (
        patch(
            "mind.logic.engines.ast_gate.checks.purity_checks.ASTHelpers.build_import_alias_map",
            return_value={},
        ),
        patch(
            "mind.logic.engines.ast_gate.checks.purity_checks.ASTHelpers.full_attr_name",
            return_value="tempfile.gettempdir",
        ),
        patch(
            "mind.logic.engines.ast_gate.checks.purity_checks.ASTHelpers.resolve_qualified_name",
            return_value="tempfile.gettempdir",
        ),
        patch(
            "mind.logic.engines.ast_gate.checks.purity_checks.ASTHelpers.lineno",
            return_value=2,
        ),
    ):
        result = PurityChecks.check_tempfile_default_dir(tree)

    assert isinstance(result, list)
    assert len(result) == 1
    assert "tempfile.gettempdir" in result[0]
