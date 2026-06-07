"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/logic/engines/workflow_gate/engine.py
- Symbol: WorkflowGateEngine
- Generated: 2026-01-11 02:27:52
- 2026-06-07 (#572 Cat B batch 9): WorkflowGateEngine.__init__ now takes
  path_resolver. Added a module-level path_resolver fixture and threaded
  it through every construction site.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mind.logic.engines.workflow_gate.engine import WorkflowGateEngine


@pytest.fixture
def path_resolver():
    """Bare MagicMock — the engine's verify() methods exercised below do not
    consult ``self._paths`` on the dispatch paths tested here."""
    return MagicMock()


@pytest.mark.asyncio
async def test_verify_missing_check_type(path_resolver):
    """Test verify with missing check_type parameter."""
    engine = WorkflowGateEngine(path_resolver=path_resolver)
    file_path = Path("/some/file.txt")
    params = {}
    result = await engine.verify(file_path, params)
    assert not result.ok
    assert "Missing check_type" == result.message
    assert ["No check_type provided"] == result.violations
    assert result.engine_id == "workflow_gate"


@pytest.mark.asyncio
async def test_verify_invalid_check_type(path_resolver):
    """Test verify with unsupported check_type."""
    engine = WorkflowGateEngine(path_resolver=path_resolver)
    file_path = Path("/some/file.txt")
    params = {"check_type": "invalid_check"}
    result = await engine.verify(file_path, params)
    assert not result.ok
    assert "Invalid check_type" == result.message
    assert ["Unsupported: invalid_check"] == result.violations
    assert result.engine_id == "workflow_gate"


@pytest.mark.asyncio
async def test_verify_with_none_file_path(path_resolver):
    """Test verify with None file_path."""
    engine = WorkflowGateEngine(path_resolver=path_resolver)
    params = {"check_type": "test_verification"}
    result = await engine.verify(None, params)
    assert result.engine_id == "workflow_gate"


@pytest.mark.asyncio
async def test_verify_exception_handling(path_resolver):
    """Test that verify handles exceptions from check logic."""
    engine = WorkflowGateEngine(path_resolver=path_resolver)
    file_path = Path("/some/file.txt")
    original_checks = engine._checks.copy()

    class FaultyCheck:
        check_type = "coverage_minimum"

        async def verify(self, file_path, params):
            raise RuntimeError("Coverage check failed")

    engine._checks["coverage_minimum"] = FaultyCheck()
    try:
        params = {"check_type": "coverage_minimum"}
        result = await engine.verify(file_path, params)
        assert not result.ok
        assert "Engine Error:" in result.message
        assert "Coverage check failed" in result.message
        assert ["Coverage check failed"] == result.violations
        assert result.engine_id == "workflow_gate"
    finally:
        engine._checks = original_checks


@pytest.mark.asyncio
async def test_verify_context_successful_check(path_resolver):
    """Test verify_context with a successful check (no violations)."""
    engine = WorkflowGateEngine(path_resolver=path_resolver)
    context = None
    original_checks = engine._checks.copy()

    class SuccessfulCheck:
        check_type = "alignment_verification"

        async def verify(self, file_path, params):
            return []

    engine._checks["alignment_verification"] = SuccessfulCheck()
    try:
        params = {"check_type": "alignment_verification"}
        findings = await engine.verify_context(context, params)
        assert len(findings) == 0
    finally:
        engine._checks = original_checks


@pytest.mark.asyncio
async def test_verify_successful_check(path_resolver):
    """Test verify with a successful check (no violations)."""
    engine = WorkflowGateEngine(path_resolver=path_resolver)
    file_path = Path("/some/file.txt")
    original_checks = engine._checks.copy()

    class SuccessfulCheck:
        check_type = "canary_deployment"

        async def verify(self, file_path, params):
            return []

    engine._checks["canary_deployment"] = SuccessfulCheck()
    try:
        params = {"check_type": "canary_deployment"}
        result = await engine.verify(file_path, params)
        assert result.ok
        assert "Workflow compliant" == result.message
        assert [] == result.violations
        assert result.engine_id == "workflow_gate"
    finally:
        engine._checks = original_checks


@pytest.mark.asyncio
async def test_verify_with_violations(path_resolver):
    """Test verify with check that returns violations."""
    engine = WorkflowGateEngine(path_resolver=path_resolver)
    file_path = Path("/some/file.txt")
    original_checks = engine._checks.copy()

    class ViolatingCheck:
        check_type = "audit_history"

        async def verify(self, file_path, params):
            return ["Missing audit log", "Incomplete history"]

    engine._checks["audit_history"] = ViolatingCheck()
    try:
        params = {"check_type": "audit_history"}
        result = await engine.verify(file_path, params)
        assert not result.ok
        assert "Workflow violations found" == result.message
        assert ["Missing audit log", "Incomplete history"] == result.violations
        assert result.engine_id == "workflow_gate"
    finally:
        engine._checks = original_checks
