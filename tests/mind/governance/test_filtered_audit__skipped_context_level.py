"""#961 -- a context-level rule skipped under --files is not "executed".

run_filtered_audit skips every context-level rule when a file filter is
active (it cannot be narrowed to a file list). It used to add those rules
to executed_rule_ids anyway, so a scoped audit claimed to have run rules
it never evaluated. It now leaves them out, lists them by id, and names
the blocking subset so a caller's verdict cannot be PASS.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mind.governance.filtered_audit import run_filtered_audit


def _rule(rule_id: str, *, context_level: bool, enforcement: str) -> MagicMock:
    rule = MagicMock()
    rule.rule_id = rule_id
    rule.policy_id = "p"
    rule.is_context_level = context_level
    rule.enforcement = enforcement
    return rule


def _context(repo: Path) -> MagicMock:
    ctx = MagicMock()
    ctx.repo_path = repo
    ctx.policies = []
    ctx.enforcement_loader = MagicMock()
    ctx.sweep_llm_gate_cache = AsyncMock()
    return ctx


async def _run(tmp_path: Path, rules: list[MagicMock], files: list[str] | None):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n")
    with (
        patch(
            "mind.governance.rule_extractor.extract_executable_rules",
            return_value=rules,
        ),
        patch(
            "mind.governance.rule_executor.execute_rule",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        return await run_filtered_audit(_context(tmp_path), files=files)


_RULES = [
    lambda: _rule("per.file", context_level=False, enforcement="blocking"),
    lambda: _rule("ctx.blocking", context_level=True, enforcement="blocking"),
    lambda: _rule("ctx.reporting", context_level=True, enforcement="reporting"),
]


@pytest.mark.asyncio
async def test_skipped_context_level_rules_are_not_executed(tmp_path: Path) -> None:
    _, executed, stats = await _run(tmp_path, [r() for r in _RULES], ["src/a.py"])
    assert executed == {"per.file"}
    assert stats["executed_rules"] == 1
    assert stats["skipped_context_level"] == 2
    assert stats["skipped_context_level_ids"] == ["ctx.blocking", "ctx.reporting"]
    assert stats["skipped_context_level_blocking_ids"] == ["ctx.blocking"]


@pytest.mark.asyncio
async def test_without_a_file_filter_nothing_is_skipped(tmp_path: Path) -> None:
    _, executed, stats = await _run(tmp_path, [r() for r in _RULES], None)
    assert executed == {"per.file", "ctx.blocking", "ctx.reporting"}
    assert stats["skipped_context_level_ids"] == []
    assert stats["skipped_context_level_blocking_ids"] == []
