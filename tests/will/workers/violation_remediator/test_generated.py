from dataclasses import dataclass
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@dataclass
class MockProposalAction:
    action_id: str | None = None
    flow_id: str | None = None
    parameters: dict[str, Any] | None = None
    order: int = 0

    @property
    def ref_id(self) -> str:
        return self.action_id or self.flow_id or ""


@dataclass
class MockProposal:
    proposal_id: str = ""
    goal: str = ""
    actions: list[MockProposalAction] = None
    scope: Any = None
    created_by: str = ""
    constitutional_constraints: dict[str, Any] = None
    approval_required: bool = False
    risk: Any = None
    created_at: datetime = None

    def compute_risk(self) -> None:
        pass

    def validate(self) -> tuple[bool, list[str]]:
        return True, []


class TestViolationRemediatorWorker:
    """Tests for ViolationRemediatorWorker class."""

    @pytest.fixture
    def mock_core_context(self):
        """Create a mock core context for testing."""
        context = MagicMock()
        context.git_service.repo_path = "/fake/repo"
        return context

    @pytest.fixture
    def worker(self, mock_core_context):
        """Create a ViolationRemediatorWorker instance for testing."""
        from will.workers.violation_remediator import ViolationRemediatorWorker

        inst = ViolationRemediatorWorker(
            core_context=mock_core_context, declaration_name="violation_remediator"
        )
        inst._worker_uuid = "test-worker-uuid"
        return inst

    @pytest.mark.asyncio
    async def test_run_no_open_findings(self, worker):
        """Test run method when there are no open findings."""
        worker._load_open_findings = AsyncMock(return_value=[])
        worker.post_heartbeat = AsyncMock()
        worker.post_report = AsyncMock()

        with patch(
            "will.workers.violation_remediator.load_vocabulary_projection"
        ) as mock_load:
            mock_load.return_value = MagicMock()
            await worker.run()

        worker.post_heartbeat.assert_called_once()
        worker._load_open_findings.assert_called_once()
        worker.post_report.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_with_vocabulary_projection_error(self, worker):
        """When vocabulary projection is broken, run() short-circuits to
        post a ``governance.instrument_degraded`` observation and bails
        out before loading findings.

        2026-06-07 (#572 Cat B batch 20): two drift shapes corrected.
        (a) Source checks
        ``isinstance(projection, VocabularyProjectionError)`` (file:116),
        so a bare MagicMock with a ``.reason`` attribute slips past the
        guard. We construct a real VocabularyProjectionError.
        (b) Source calls ``self.post_observation(subject=..., payload=...,
        status='abandoned')`` — NOT ``self.post_finding(...)``."""
        from will.workers.violation_remediator import VocabularyProjectionError

        projection_error = VocabularyProjectionError(
            state="broken", reason="Broken projection"
        )
        worker.post_observation = AsyncMock()
        worker.post_heartbeat = AsyncMock()
        # Mock _load_open_findings so we can assert it's never reached on
        # the projection-broken short-circuit path.
        worker._load_open_findings = AsyncMock()

        with patch(
            "will.workers.violation_remediator.load_vocabulary_projection"
        ) as mock_load:
            mock_load.return_value = projection_error
            await worker.run()

        worker.post_observation.assert_awaited_once_with(
            subject="governance.instrument_degraded",
            payload={
                "instrument": "vocabulary_projection",
                "reason": "Broken projection",
                "worker": worker.declaration_name,
            },
            status="abandoned",
        )
        worker._load_open_findings.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_with_findings_no_remediation(self, worker):
        """Test run method when findings have no remediation mapping."""
        worker._load_open_findings = AsyncMock(
            return_value=[
                {
                    "id": "finding-1",
                    "subject": "audit.violation.test",
                    "payload": {
                        "check_id": "unknown_rule",
                        "file_path": "src/test.py",
                    },
                }
            ]
        )
        worker._get_remediation_map = MagicMock(return_value={})
        worker._release_unmappable = AsyncMock(return_value=1)
        worker._mark_delegated = AsyncMock(return_value=0)
        worker.post_heartbeat = AsyncMock()
        worker.post_report = AsyncMock()

        with patch(
            "will.workers.violation_remediator.load_vocabulary_projection"
        ) as mock_load:
            mock_load.return_value = MagicMock()
            await worker.run()
