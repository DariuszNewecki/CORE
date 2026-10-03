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


# ID: c2ced4ec-8585-4ae0-85e9-9045e2f76872
def test_PromptModelChecks_check_prompt_model_required() -> None:
    checks = PromptModelChecks()
    source = "client.make_request_async('prompt')\nobj.other_method()\n"
    tree = ast.parse(source)
    params = {"forbidden_calls": ["make_request_async"]}

    violations = checks.check_prompt_model_required(tree, params)

    assert isinstance(violations, list)
    assert len(violations) == 1
    assert "make_request_async()" in violations[0]
    assert "[ai.prompt.model_required]" in violations[0]

    assert checks.check_prompt_model_required(tree, {"forbidden_calls": []}) == []
