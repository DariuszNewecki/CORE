# tests/cli/resources/workers/test_remediate_file_mode.py
"""Unit tests for `_run_file_pipeline` (ADR-153 D2/D3 behavior change).

File mode used to instantiate `ViolationRemediator` (a Worker) and
monkeypatch its claim/mark methods to bypass the blackboard. Post-ADR-153
it constructs `RemediationCeremony` directly with a `NullRemediationBlackboard`
and never touches `ViolationRemediator` at all — this is a deliberate,
recorded behavior change: file mode now posts nothing to the blackboard.

Tests drive Mocks for the auditor/session/ceremony layers. No DB, no LLM.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cli.resources.workers.remediate import (
    _build_synthetic_findings,
    _filter_findings_for_file,
    _run_file_pipeline,
)


def _make_core_context(repo_root):
    core_context = MagicMock()
    core_context.git_service.repo_path = repo_root
    core_context.auditor_context = MagicMock()
    core_context.auditor_context.load_knowledge_graph = AsyncMock()
    return core_context


@asynccontextmanager
async def _null_session():
    yield MagicMock()


def test_filter_findings_for_file_matches_only_target_path():
    findings = [
        {"file_path": "src/a.py", "check_id": "rule.a", "message": "m1"},
        {"file_path": "src/b.py", "check_id": "rule.b", "message": "m2"},
    ]
    result = _filter_findings_for_file(findings, "src/a.py")
    assert len(result) == 1
    assert result[0]["file_path"] == "src/a.py"
    assert result[0]["rule"] == "rule.a"


def test_build_synthetic_findings_shape():
    file_findings = [
        {"file_path": "src/a.py", "rule": "rule.a", "message": "m1", "severity": "warning"}
    ]
    synthetic = _build_synthetic_findings(file_findings, "src/a.py")
    assert len(synthetic) == 1
    entry = synthetic[0]
    assert "id" in entry
    assert entry["payload"]["file_path"] == "src/a.py"
    assert entry["payload"]["rule"] == "rule.a"
    assert entry["payload"]["status"] == "unprocessed"


@pytest.mark.asyncio
async def test_run_file_pipeline_uses_ceremony_with_null_blackboard(tmp_path):
    target = tmp_path / "src" / "a.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n")

    core_context = _make_core_context(tmp_path)

    auditor_instance = MagicMock()
    auditor_instance.run_full_audit_async = AsyncMock(
        return_value={
            "findings": [
                {"file_path": "src/a.py", "check_id": "rule.a", "message": "bad"}
            ]
        }
    )

    ceremony_instance = MagicMock()
    ceremony_instance.process_file = AsyncMock(return_value=True)

    null_blackboard_sentinel = object()

    with (
        patch(
            "cli.resources.workers.remediate.get_session",
            side_effect=_null_session,
        ),
        patch(
            "mind.governance.auditor.ConstitutionalAuditor",
            return_value=auditor_instance,
        ),
        patch(
            "will.remediation.NullRemediationBlackboard",
            return_value=null_blackboard_sentinel,
        ) as null_blackboard_cls,
        patch(
            "will.remediation.RemediationCeremony",
            return_value=ceremony_instance,
        ) as ceremony_cls,
    ):
        await _run_file_pipeline(core_context, "src/a.py", write=False)

    null_blackboard_cls.assert_called_once_with()
    ceremony_cls.assert_called_once()
    _, kwargs = ceremony_cls.call_args
    assert kwargs["core_context"] is core_context
    assert kwargs["target_rule"] == "rule.a"
    assert kwargs["write"] is False
    assert kwargs["blackboard"] is null_blackboard_sentinel

    ceremony_instance.process_file.assert_awaited_once()
    call_args = ceremony_instance.process_file.call_args
    assert call_args[0][0] == "src/a.py"
    synthetic_findings = call_args[0][1]
    assert len(synthetic_findings) == 1
    assert synthetic_findings[0]["payload"]["rule"] == "rule.a"


@pytest.mark.asyncio
async def test_run_file_pipeline_no_findings_skips_ceremony(tmp_path):
    target = tmp_path / "src" / "clean.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n")

    core_context = _make_core_context(tmp_path)

    auditor_instance = MagicMock()
    auditor_instance.run_full_audit_async = AsyncMock(return_value={"findings": []})

    with (
        patch(
            "cli.resources.workers.remediate.get_session",
            side_effect=_null_session,
        ),
        patch(
            "mind.governance.auditor.ConstitutionalAuditor",
            return_value=auditor_instance,
        ),
        patch("will.remediation.RemediationCeremony") as ceremony_cls,
    ):
        await _run_file_pipeline(core_context, "src/clean.py", write=False)

    ceremony_cls.assert_not_called()
