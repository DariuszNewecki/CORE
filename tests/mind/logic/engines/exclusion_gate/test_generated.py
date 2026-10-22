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


# ID: f952055e-a37d-4b5b-ab43-be5aef711a64
def test_ExclusionGateEngine_verify():
    engine = ExclusionGateEngine.__new__(ExclusionGateEngine)
    engine_id = "exclusion_gate"
    type(engine).engine_id = engine_id

    file_path = MagicMock(spec=Path)
    params = {"check_type": "exclusion_level"}

    result = asyncio.run(engine.verify(file_path, params))

    assert result.ok is False
    assert result.violations == []
    assert result.engine_id == engine_id
    assert "exclusion_level" in result.message
    assert "verify_context" in result.message


import pytest


@pytest.mark.asyncio
# ID: afd963fa-7340-4b49-ab02-24f0b79f2925
async def test_ExclusionGateEngine():
    engine = ExclusionGateEngine()
    assert engine.engine_id == "exclusion_gate"

    # Happy path for verify_context: one dead exclude entry reported.
    context = MagicMock()
    context.repo_path = "/tmp/repo"
    context.policies = MagicMock()
    context.enforcement_loader = MagicMock()

    rule = MagicMock()
    rule.rule_id = "architecture.intent.some_other_rule"
    rule.engine = "some_engine"
    rule.params = {}

    dead = MagicMock()
    dead.rule_id = rule.rule_id
    dead.entry = "src/generated/**"
    dead.reason = "matches no files"

    with (
        patch(
            "mind.governance.rule_extractor.extract_executable_rules",
            return_value=[rule],
        ),
        patch(
            "mind.logic.engines.registry.EngineRegistry",
        ) as mock_registry,
        patch(
            "mind.logic.engines.exclusion_gate.find_dead_excludes",
            new=AsyncMock(return_value=[dead]),
        ),
        patch(
            "mind.logic.engines.exclusion_gate._repo_files",
            return_value=MagicMock(),
        ),
    ):
        mock_registry.get.return_value.verify = AsyncMock(
            return_value=MagicMock(violations=[], ok=True)
        )

        findings = await engine.verify_context(
            context, {"check_type": "excludes_exempt_something"}
        )

    assert len(findings) == 1
    assert findings[0].check_id == "architecture.intent.excludes_exempt_something"
    assert findings[0].context == {
        "rule_id": rule.rule_id,
        "entry": dead.entry,
        "reason": dead.reason,
    }


from dataclasses import fields, is_dataclass

from mind.logic.engines.exclusion_gate import DeadExclude


# ID: 295bd7a7-c9dc-4d00-b274-9a3e5c5262c9
def test_DeadExclude():
    dead = DeadExclude(
        rule_id="rule_42",
        entry="some/redundant/path.py",
        reason="redundant with project-wide exclude",
    )

    assert dead.rule_id == "rule_42"
    assert dead.entry == "some/redundant/path.py"
    assert dead.reason == "redundant with project-wide exclude"

    assert is_dataclass(DeadExclude)
    field_names = {f.name for f in fields(DeadExclude)}
    assert field_names == {"rule_id", "entry", "reason"}
