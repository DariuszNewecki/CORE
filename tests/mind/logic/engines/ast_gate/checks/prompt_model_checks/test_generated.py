from __future__ import annotations

import ast
from unittest.mock import MagicMock, patch

from mind.logic.engines.ast_gate.checks.prompt_model_checks import PromptModelChecks


# ID: 6d6f1c42-8291-4617-92bd-42c327ba92a5
def test_PromptModelChecks():
    source = "writer_client.make_request_async(prompt='hi')\n"
    tree = ast.parse(source)

    with patch(
        "mind.logic.engines.ast_gate.checks.prompt_model_checks.ASTHelpers"
    ) as mock_helpers:
        mock_helpers.full_attr_name = MagicMock(
            return_value="writer_client.make_request_async"
        )
        result = PromptModelChecks.check_prompt_model_required(
            tree, {"forbidden_calls": ["make_request_async"]}
        )

    assert isinstance(result, list)
    assert len(result) == 1
    assert "make_request_async" in result[0]
