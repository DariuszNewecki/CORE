# tests/mind/governance/test_rule_executor__regex_gate_binary.py
"""#1050: a regex_gate rule over '**/*' meets binary files (ruff's cache).

Their content is not evaluated and is reported once per rule, never as an
enforcement_failure; the naming pattern still applies to them; any other
read error still fails.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from mind.governance.executable_rule import ExecutableRule
from mind.governance.rule_executor import clear_eval_cache, execute_rule
from mind.logic.engines.regex_gate import RegexGateEngine
from shared.models import AuditSeverity


BINARY = b"\x00\x01\xffruff cache\x00"


@pytest.fixture(autouse=True)
def _reset_eval_cache() -> None:
    clear_eval_cache()
    yield
    clear_eval_cache()


@pytest.fixture(autouse=True)
def _real_regex_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = RegexGateEngine()
    monkeypatch.setattr(
        "mind.logic.engines.registry.EngineRegistry.get", lambda engine_id: engine
    )


def _context(repo_path: Path, files: list[Path]) -> Any:
    ctx = MagicMock()
    ctx.repo_path = repo_path
    ctx.force_llm = False
    ctx.get_files.return_value = files
    return ctx


def _rule(params: dict[str, Any]) -> ExecutableRule:
    return ExecutableRule(
        rule_id="test.no_secrets",
        engine="regex_gate",
        params=params,
        enforcement="blocking",
        scope=["**/*"],
        rule_content_hash="abc123",
    )


def _failures(findings: list) -> list:
    return [f for f in findings if f.check_id.endswith(".enforcement_failure")]


async def test_a_binary_file_is_not_evaluated_not_a_failure(tmp_path: Path) -> None:
    binary = tmp_path / ".ruff_cache" / "0.6.0" / "123456"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(BINARY)
    latin1 = tmp_path / "legacy.txt"
    latin1.write_bytes("caf\xe9".encode("latin-1"))
    text = tmp_path / "module.py"
    text.write_text("x = 1\n", encoding="utf-8")
    rule = _rule({"forbidden_patterns": ["SECRET_KEY=.*"]})
    ctx = _context(tmp_path, [binary, latin1, text])

    for _ in range(2):  # the second run hits the cache for module.py
        findings = await execute_rule(rule, ctx)
        assert _failures(findings) == []
        [report] = findings
        assert report.check_id == "test.no_secrets.content_not_evaluated"
        assert report.severity == AuditSeverity.INFO
        assert report.context["finding_type"] == "CONTENT_NOT_EVALUATED"
        assert report.context["file_count"] == 2
        assert sorted(report.context["sample_files"]) == [
            ".ruff_cache/0.6.0/123456",
            "legacy.txt",
        ]


async def test_the_naming_pattern_still_applies_to_a_binary_file(
    tmp_path: Path,
) -> None:
    binary = tmp_path / "Bad Name.bin"
    binary.write_bytes(BINARY)
    rule = _rule({"naming_pattern": r"^[a-z_.]+$", "forbidden_patterns": ["x"]})

    findings = await execute_rule(rule, _context(tmp_path, [binary]))

    assert _failures(findings) == []
    assert [f.check_id for f in findings if "Naming Violation" in f.message] == [
        "test.no_secrets"
    ]


async def test_a_naming_only_rule_reports_nothing_for_a_binary_file(
    tmp_path: Path,
) -> None:
    binary = tmp_path / "cache.bin"
    binary.write_bytes(BINARY)
    rule = _rule({"naming_pattern": r"^[a-z_.]+$"})

    assert await execute_rule(rule, _context(tmp_path, [binary])) == []


async def test_any_other_read_error_still_fails(tmp_path: Path) -> None:
    missing = tmp_path / "gone.txt"
    rule = _rule({"forbidden_patterns": ["x"]})

    findings = await execute_rule(rule, _context(tmp_path, [missing]))

    [failure] = _failures(findings)
    assert failure.severity == AuditSeverity.BLOCK
    assert "IO Error" in failure.message
