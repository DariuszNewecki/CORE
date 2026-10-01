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
