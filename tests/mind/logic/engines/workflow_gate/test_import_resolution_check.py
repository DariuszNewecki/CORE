# tests/mind/logic/engines/workflow_gate/test_import_resolution_check.py

"""Mechanism-level coverage for ImportResolutionCheck (#855).

These tests exercise the generic params-driven dispatch mechanism itself
-- multi-tool aggregation, the filter/filter_all contract, and fail-closed
tool-absence handling -- independent of any specific rule's live mapping.
The rule-level fixtures proving must_resolve/no_stale_namespace actually
differ and actually catch real violations live in
test_g2_workflow_gate_rules.py, alongside the rest of the #842 G2 census.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mind.logic.engines.workflow_gate.base_check import StructuredViolation
from mind.logic.engines.workflow_gate.checks.import_resolution import (
    ImportResolutionCheck,
)


def _fake_process(returncode: int, stdout: bytes = b"", stderr: bytes = b""):
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    return proc


def _as_str(violation: str | StructuredViolation) -> str:
    """Narrow the check's `str | StructuredViolation` union for assertions
    on tests that only ever produce plain-string violations."""
    assert isinstance(violation, str), f"expected a plain string, got {violation!r}"
    return violation


async def test_runs_every_declared_tool_and_aggregates(tmp_path: Path) -> None:
    """Two declared tools, both reporting a violation, aggregate into one
    result list -- proving dispatch is params-driven, not hardcoded to a
    single tool."""
    check = ImportResolutionCheck()
    target = tmp_path / "f.py"
    target.write_text("x = 1\n", encoding="utf-8")

    calls: list[list[str]] = []

    async def fake_exec(*args, **kwargs):
        calls.append(list(args))
        if args[0] == "toolA":
            return _fake_process(1, stdout=b"toolA: violation on line 1\n")
        return _fake_process(1, stdout=b"toolB: violation on line 2\n")

    params = {
        "tools": [
            {"tool": "toolA", "args": ["--flag"]},
            {"tool": "toolB", "args": ["--other"]},
        ]
    }
    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        result = await check.verify(target, params)

    assert len(calls) == 2
    assert len(result) == 2
    assert any("toolA" in _as_str(v) for v in result)
    assert any("toolB" in _as_str(v) for v in result)


async def test_filter_single_substring_narrows_violations(tmp_path: Path) -> None:
    """`filter` (string) keeps only output lines containing that substring."""
    check = ImportResolutionCheck()
    target = tmp_path / "f.py"
    target.write_text("x = 1\n", encoding="utf-8")
    output = b"line one: keep-me\nline two: drop-me\n"

    params = {"tools": [{"tool": "toolA", "args": [], "filter": "keep-me"}]}
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_fake_process(1, stdout=output)),
    ):
        result = await check.verify(target, params)

    assert len(result) == 1
    violation = _as_str(result[0])
    assert "keep-me" in violation
    assert "drop-me" not in violation


async def test_filter_all_requires_every_substring_present(tmp_path: Path) -> None:
    """`filter_all` (list) keeps only lines containing ALL declared
    substrings -- AND semantics, a distinct key from `filter`."""
    check = ImportResolutionCheck()
    target = tmp_path / "f.py"
    target.write_text("x = 1\n", encoding="utf-8")
    output = (
        b"has-both: alpha beta\n"
        b"has-only-alpha: alpha\n"
        b"has-only-beta: beta\n"
        b"has-neither\n"
    )

    params = {
        "tools": [{"tool": "toolA", "args": [], "filter_all": ["alpha", "beta"]}]
    }
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_fake_process(1, stdout=output)),
    ):
        result = await check.verify(target, params)

    assert len(result) == 1
    violation = _as_str(result[0])
    assert "has-both" in violation
    assert "has-only-alpha" not in violation
    assert "has-only-beta" not in violation
    assert "has-neither" not in violation


async def test_filter_and_filter_all_combine_when_both_declared(
    tmp_path: Path,
) -> None:
    """Both keys can be declared together; a line must satisfy both."""
    check = ImportResolutionCheck()
    target = tmp_path / "f.py"
    target.write_text("x = 1\n", encoding="utf-8")
    output = b"required both: base extra\nmissing second: base only\n"

    params = {
        "tools": [
            {
                "tool": "toolA",
                "args": [],
                "filter": "base",
                "filter_all": ["extra"],
            }
        ]
    }
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_fake_process(1, stdout=output)),
    ):
        result = await check.verify(target, params)

    assert len(result) == 1
    violation = _as_str(result[0])
    assert "required both" in violation
    assert "missing second" not in violation


async def test_missing_tool_returns_single_unavailable_not_partial_results(
    tmp_path: Path,
) -> None:
    """If the first declared tool genuinely finds a violation and the
    second is absent, the whole check fails closed with exactly one
    ENFORCEMENT_UNAVAILABLE finding -- not a mix of the first tool's real
    finding plus an unavailable signal. A missing instrument makes the
    rule's overall compliance status unknown, not partially-known."""
    check = ImportResolutionCheck()
    target = tmp_path / "f.py"
    target.write_text("x = 1\n", encoding="utf-8")

    async def fake_exec(*args, **kwargs):
        if args[0] == "present-tool":
            return _fake_process(1, stdout=b"a real violation\n")
        raise FileNotFoundError(2, "No such file or directory", args[0])

    params = {
        "tools": [
            {"tool": "present-tool", "args": []},
            {"tool": "absent-tool", "args": []},
        ]
    }
    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        result = await check.verify(target, params)

    assert len(result) == 1
    violation = result[0]
    assert isinstance(violation, StructuredViolation)
    assert violation.context["finding_type"] == "ENFORCEMENT_UNAVAILABLE"
    assert violation.context["tool"] == "absent-tool"


async def test_no_tools_declared_is_a_configuration_violation(tmp_path: Path) -> None:
    """A mapping that forgets to declare `tools` is a real misconfiguration,
    not a silent pass."""
    check = ImportResolutionCheck()
    target = tmp_path / "f.py"
    target.write_text("x = 1\n", encoding="utf-8")

    result = await check.verify(target, {})

    assert len(result) == 1
    assert "tools" in _as_str(result[0])


async def test_clean_tool_output_produces_no_violations(tmp_path: Path) -> None:
    check = ImportResolutionCheck()
    target = tmp_path / "f.py"
    target.write_text("x = 1\n", encoding="utf-8")

    params = {"tools": [{"tool": "toolA", "args": []}]}
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_fake_process(0)),
    ):
        result = await check.verify(target, params)

    assert result == []
