from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from will.audit_violation.drain import drain_cleared_findings


@pytest.mark.asyncio
# ID: a81ed8ff-a506-4f20-8c7d-4c36033eb165
async def test_drain_cleared_findings():
    bb_svc = AsyncMock()
    bb_svc.adjudicate_awaiting_reaudit_findings = AsyncMock(
        return_value={
            "released_subjects": ["at::ns::a.py"],
            "resolved_subjects": ["at::ns::b.py"],
        }
    )
    bb_svc.adjudicate_indeterminate_findings = AsyncMock(
        return_value={"resolved_subjects": ["at::ns::c.py"]}
    )
    bb_svc.adjudicate_abandoned_findings = AsyncMock(
        return_value={"resolved_subjects": ["at::ns::d.py"]}
    )

    current_violations = [
        {"rule_id": "R1", "file_path": "a.py"},
        {"file_path": "e.py"},
    ]

    result = await drain_cleared_findings(
        bb_svc,
        artifact_type_id="at",
        rule_namespace="ns",
        current_violations=current_violations,
    )

    expected_subjects = {"at::R1::a.py", "at::ns::e.py"}
    bb_svc.adjudicate_awaiting_reaudit_findings.assert_awaited_once_with(
        subject_prefix="at::ns",
        current_violation_subjects=expected_subjects,
        resolved_by="audit_violation_sensor",
    )
    bb_svc.adjudicate_indeterminate_findings.assert_awaited_once_with(
        subject_prefix="at::ns",
        current_violation_subjects=expected_subjects,
        resolved_by="audit_violation_sensor",
    )
    bb_svc.adjudicate_abandoned_findings.assert_awaited_once_with(
        subject_prefix="at::ns",
        current_violation_subjects=expected_subjects,
        resolved_by="audit_violation_sensor",
    )

    assert result == {
        "rule_namespace": "ns",
        "released_count": 1,
        "resolved_count": 1,
        "released_subjects": ["at::ns::a.py"],
        "resolved_subjects": ["at::ns::b.py"],
        "indeterminate_drained": 1,
        "indeterminate_drain_subjects": ["at::ns::c.py"],
        "abandoned_drained": 1,
        "abandoned_drain_subjects": ["at::ns::d.py"],
    }
