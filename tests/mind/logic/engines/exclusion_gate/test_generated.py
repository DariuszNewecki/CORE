from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from mind.logic.engines.exclusion_gate import find_dead_excludes


# ID: 5c53d705-27b8-4002-92e5-ca4bd051e7d7
def test_find_dead_excludes() -> None:
    rule = SimpleNamespace(
        rule_id="rule-1",
        scope=["src/**"],
        exclusions=["src/**"],
        is_context_level=False,
        engine="ast_gate",
    )

    probe = AsyncMock(return_value=True)

    with patch(
        "mind.governance.audit_context._include_matches",
        side_effect=lambda path, pattern: (
            pattern == "src/**" and path.startswith("src/")
        ),
    ):
        result = asyncio.run(
            find_dead_excludes(
                rules=[rule],
                repo_files=["src/a.py", "src/b.py"],
                repo_root=Path("/repo"),
                probe=probe,
            )
        )

    assert result == []


from unittest.mock import MagicMock

import pytest

from mind.logic.engines.exclusion_gate import ExclusionGateEngine


@pytest.mark.asyncio
# ID: b1863002-208c-4337-9733-10706fc61034
async def test_ExclusionGateEngine_verify_context():
    from mind.logic.engines.exclusion_gate import _CHECK

    engine = ExclusionGateEngine()

    dead_entry = MagicMock()
    dead_entry.rule_id = "rule.one"
    dead_entry.entry = "src/legacy"
    dead_entry.reason = "matched no files"

    fake_rule = MagicMock()
    fake_rule.rule_id = "rule.one"

    context = MagicMock()
    context.repo_path = "/tmp/repo"
    context.policies = MagicMock()
    context.enforcement_loader = MagicMock()

    with (
        patch(
            "mind.governance.rule_extractor.extract_executable_rules",
            return_value=[fake_rule],
        ),
        patch(
            "mind.logic.engines.exclusion_gate.find_dead_excludes",
            new=AsyncMock(return_value=[dead_entry]),
        ),
        patch(
            "mind.logic.engines.exclusion_gate._repo_files",
            return_value=iter([Path("/tmp/repo/a.py")]),
        ),
    ):
        findings = await ExclusionGateEngine.verify_context(
            engine, context, {"check_type": _CHECK}
        )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.context == {
        "rule_id": "rule.one",
        "entry": "src/legacy",
        "reason": "matched no files",
    }
