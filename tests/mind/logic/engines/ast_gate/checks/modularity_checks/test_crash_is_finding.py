# tests/mind/logic/engines/ast_gate/checks/modularity_checks/test_crash_is_finding.py
"""A crashing modularity check is a finding, not a clean file.

Each rule-aligned modularity check used to catch its own exceptions, log
them and return [] -- which the audit reads as "no violations". These
tests break one helper per check and run the rule through the real
ast_gate engine and rule_executor: the result must be an
ENFORCEMENT_FAILURE finding for that rule and file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from mind.governance.executable_rule import ExecutableRule
from mind.governance.rule_executor import clear_eval_cache, execute_rule
from mind.logic.engines.ast_gate.checks.modularity_checks import ModularityChecker
from mind.logic.engines.ast_gate.engine import ASTGateEngine


@pytest.fixture(autouse=True)
def _reset_eval_cache() -> None:
    clear_eval_cache()
    yield
    clear_eval_cache()


def _boom(*args: Any, **kwargs: Any) -> Any:
    raise RuntimeError("helper exploded")


@pytest.mark.parametrize(
    ("check_method", "broken_helper", "params"),
    [
        ("check_refactor_score", "_detect_responsibilities", {"max_score": 60}),
        ("check_needs_split", "_detect_responsibilities", {"max_lines": 0}),
        ("check_class_too_large", "_find_dominant_class", {"max_lines": 400}),
        ("check_needs_refactor", "_extract_imports", {"max_concerns": 3}),
    ],
)
async def test_check_crash_becomes_enforcement_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    check_method: str,
    broken_helper: str,
    params: dict[str, Any],
) -> None:
    target = tmp_path / "module.py"
    target.write_text("import os\n\n\ndef f():\n    return os.sep\n")
    monkeypatch.setattr(ModularityChecker, broken_helper, _boom)

    engine = ASTGateEngine(MagicMock())
    monkeypatch.setattr(
        "mind.logic.engines.registry.EngineRegistry.get", lambda engine_id: engine
    )
    ctx = MagicMock()
    ctx.repo_path = tmp_path
    ctx.force_llm = False
    ctx.get_files.return_value = [target]
    ctx.get_tree.return_value = None
    rule = ExecutableRule(
        rule_id="modularity.test_rule",
        engine="ast_gate",
        params={"check_type": "modularity", "check_method": check_method, **params},
        enforcement="blocking",
        scope=["**/*.py"],
        rule_content_hash="abc123",
    )

    findings = await execute_rule(rule, ctx)

    assert [f.check_id for f in findings] == [
        "modularity.test_rule.enforcement_failure"
    ]
    assert findings[0].file_path == "module.py"
    assert "helper exploded" in findings[0].message
