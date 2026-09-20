# tests/will/workers/test_audit_ingest_worker.py
"""Tests for AuditIngestWorker's audit path.

Regression for the 2026-09-20 LocalCoder spend finding: both ingest workers
ran ConstitutionalAuditor.run_full_audit_async() in-process, which executed
every mapped engine — llm_gate included — with no DB session, so the ADR-044
verdict cache was ineligible and ~10 paid LLM calls per cycle were re-bought
and discarded, while the worker YAML declared `permitted_tools: []`.

Covers:
- _run_audit() routes through normalize_audit_findings with rule_ids scoped
  to the single target rule (the audit_sensor_* filtered path).
- line_number is taken from the finding when present, else parsed from the
  message; findings with neither are dropped.
- __symbol_pair__ sentinels and off-target rule ids are dropped.
- Static drift guard: neither ingest worker module calls
  run_full_audit_async anywhere in its source (docstrings excluded).
"""

from __future__ import annotations

import ast
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.workers import audit_ingest_worker, quality_ingest_worker
from will.workers.audit_ingest_worker import AuditIngestWorker


_TARGET = "ai.prompt.model_required"


def _worker() -> AuditIngestWorker:
    return AuditIngestWorker(core_context=MagicMock())


# ID: 3cc19621-03f2-4d79-8934-312beace6b78
@pytest.mark.asyncio
async def test_run_audit_uses_filtered_path_scoped_to_target_rule() -> None:
    worker = _worker()
    normalize = AsyncMock(return_value=[])
    with patch("will.audit_violation.normalizer.normalize_audit_findings", normalize):
        result = await worker._run_audit()

    assert result == []
    normalize.assert_awaited_once_with(
        worker._core_context, rule_namespace=_TARGET, rule_ids=[_TARGET]
    )


# ID: 5e1ea58c-9f06-4e47-b218-fbe19fa19ba8
@pytest.mark.asyncio
async def test_run_audit_line_number_from_finding_or_message() -> None:
    worker = _worker()
    raw = [
        {
            "rule_id": _TARGET,
            "file_path": "src/a.py",
            "message": "direct call",
            "severity": "error",
            "line_number": 7,
            "context": {},
        },
        {
            "rule_id": _TARGET,
            "file_path": "src/b.py",
            "message": "Line 163: direct call to 'make_request_async()'",
            "severity": "error",
            "line_number": None,
            "context": {},
        },
        {
            "rule_id": _TARGET,
            "file_path": "src/c.py",
            "message": "no line here",
            "severity": "error",
            "line_number": None,
            "context": {},
        },
    ]
    with patch(
        "will.audit_violation.normalizer.normalize_audit_findings",
        AsyncMock(return_value=raw),
    ):
        result = await worker._run_audit()

    assert [(v["file_path"], v["line_number"]) for v in result] == [
        ("src/a.py", 7),
        ("src/b.py", 163),
    ]


# ID: a3188a5e-16ca-46a5-8e5c-5ea56a71e6b6
@pytest.mark.asyncio
async def test_run_audit_drops_sentinels_and_off_target_rules() -> None:
    worker = _worker()
    raw = [
        {
            "rule_id": _TARGET,
            "file_path": "__symbol_pair__Foo",
            "message": "Line 1: x",
            "severity": "error",
            "line_number": 1,
            "context": {},
        },
        {
            "rule_id": "ai.prompt.system_prompt_required",
            "file_path": "src/d.py",
            "message": "Line 2: y",
            "severity": "error",
            "line_number": 2,
            "context": {},
        },
        {
            "rule_id": _TARGET,
            "file_path": "",
            "message": "Line 3: z",
            "severity": "error",
            "line_number": 3,
            "context": {},
        },
    ]
    with patch(
        "will.audit_violation.normalizer.normalize_audit_findings",
        AsyncMock(return_value=raw),
    ):
        result = await worker._run_audit()

    assert result == []


def _calls_full_audit(module: object) -> list[int]:
    """Line numbers of every `.run_full_audit_async(` call in the module source."""
    tree = ast.parse(inspect.getsource(module))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run_full_audit_async"
    ]


# ID: ab53d5bb-0535-42bb-bade-c52e1d0d19b2
@pytest.mark.parametrize("module", [audit_ingest_worker, quality_ingest_worker])
def test_ingest_workers_never_call_full_audit(module: object) -> None:
    """A worker declaring `permitted_tools: []` must not run the full audit:
    the full audit executes llm_gate, which makes paid LLM calls."""
    assert _calls_full_audit(module) == [], (
        f"{module.__name__} calls run_full_audit_async — full audit executes "
        "llm_gate; use normalize_audit_findings (filtered) instead"
    )
