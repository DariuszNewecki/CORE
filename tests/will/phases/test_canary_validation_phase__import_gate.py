"""#904: a check.imports that did not run must not be reported as violations.

ActionExecutor and the action itself return ``ok=False`` without
``violation_count`` when the check could not run (policy refusal, ruff
missing, unparseable output). The canary phase used to render that as
"? unresolvable import(s)" under ``code.imports.must_resolve``. It must
instead say the check could not run, and the audit phase must still block
(fail-closed): unknown import integrity is not a pass.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shared.action_types import ActionResult
from shared.models.workflow_models import PhaseResult
from will.phases.audit_phase import AuditPhase
from will.phases.canary_validation_phase import CanaryValidationPhase


def _canary_with(result: ActionResult) -> CanaryValidationPhase:
    phase = object.__new__(CanaryValidationPhase)
    phase.context = SimpleNamespace(
        action_executor=SimpleNamespace(execute=AsyncMock(return_value=result))
    )
    return phase


@pytest.mark.asyncio
async def test_refused_check_is_reported_as_unavailable_not_violation() -> None:
    refused = ActionResult(
        action_id="check.imports",
        ok=False,
        data={"error": "Policy validation failed", "details": {"x": 1}},
    )
    result = await _canary_with(refused).execute(SimpleNamespace(results={}))

    assert result.ok is False
    assert "?" not in result.error
    assert "unresolvable" not in result.error
    assert "Policy validation failed" in result.error
    assert "violation_count" not in result.data
    assert "rule_violated" not in result.data
    assert "import_integrity_failed" not in result.data
    assert result.data["import_check_unavailable"] is True
    assert result.data["finding_type"] == "ENFORCEMENT_UNAVAILABLE"
    assert result.data["details"] == {"x": 1}


@pytest.mark.asyncio
async def test_real_violations_still_report_count_and_rule() -> None:
    found = ActionResult(
        action_id="check.imports",
        ok=False,
        data={"violation_count": 3, "violations": [{"code": "F821"}] * 3},
    )
    result = await _canary_with(found).execute(SimpleNamespace(results={}))

    assert result.ok is False
    assert "3 unresolvable import(s)" in result.error
    assert result.data["import_integrity_failed"] is True
    assert result.data["rule_violated"] == "code.imports.must_resolve"
    assert result.data["violation_count"] == 3


@pytest.mark.asyncio
async def test_audit_phase_blocks_when_import_check_unavailable() -> None:
    unavailable = PhaseResult(
        name="canary_validation",
        ok=False,
        error="Import integrity check could not run: ruff not found",
        data={"import_check_unavailable": True},
    )
    audit = object.__new__(AuditPhase)
    audit._canary = SimpleNamespace(execute=AsyncMock(return_value=unavailable))
    audit._style = SimpleNamespace(execute=AsyncMock())
    context = SimpleNamespace(workflow_type="refactor_modularity", results={})

    result = await audit.execute(context)

    assert result.ok is False
    assert result.error.startswith("canary_validation blocked:")
    audit._style.execute.assert_not_called()
