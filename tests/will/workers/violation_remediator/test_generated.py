from __future__ import annotations

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

    async def test_uncommitted_file_skips_proposal_creation(self, worker):
        """Findings whose target file is not in HEAD must not generate a proposal.

        The gate prevents ENOENT failures in sandbox worktrees (ADR-071 D2.2):
        a file detected by the audit sensor but not yet committed doesn't exist
        in the worktree, so fix.format / fix.ids would always fail.  The entries
        are released back to open so the next cycle can retry once committed.
        """
        finding = {
            "id": "entry-uncommitted-1",
            "payload": {
                "check_id": "style.formatter_required",
                "file_path": "src/api/v1/new_uncommitted.py",
            },
        }
        worker._load_open_findings = AsyncMock(return_value=[finding])
        worker._get_remediation_map = MagicMock(
            return_value={
                "style.formatter_required": {
                    "ref_id": "fix.format",
                    "ref_kind": "action",
                    "status": "ACTIVE",
                }
            }
        )
        worker._get_active_proposal_id_by_action_file = AsyncMock(return_value={})
        worker._release_entries = AsyncMock(return_value=1)
        worker._create_proposal = AsyncMock()
        worker._release_unmappable = AsyncMock(return_value=0)
        worker._mark_delegated = AsyncMock(return_value=0)
        worker.post_report = AsyncMock()
        worker._is_file_committed = MagicMock(return_value=False)

        with (
            patch(
                "will.workers.violation_remediator.load_vocabulary_projection"
            ) as mock_load,
            patch(
                "will.workers.violation_remediator.load_circuit_breaker_config"
            ) as mock_cb,
        ):
            mock_load.return_value = MagicMock()
            mock_cb.return_value = MagicMock(threshold_n=5)
            await worker.run()

        worker._create_proposal.assert_not_called()
        worker._release_entries.assert_called_once_with(["entry-uncommitted-1"])
        report_payload = worker.post_report.call_args[1]["payload"]
        assert report_payload["entries_held_uncommitted"] == 1
        assert report_payload["proposals_created"] == 0

    async def test_committed_file_proceeds_to_proposal_creation(self, worker):
        """Findings whose target is committed must still reach _create_proposal."""
        finding = {
            "id": "entry-committed-1",
            "payload": {
                "check_id": "style.formatter_required",
                "file_path": "src/api/v1/committed.py",
            },
        }
        worker._load_open_findings = AsyncMock(return_value=[finding])
        worker._get_remediation_map = MagicMock(
            return_value={
                "style.formatter_required": {
                    "ref_id": "fix.format",
                    "ref_kind": "action",
                    "status": "ACTIVE",
                }
            }
        )
        worker._get_active_proposal_id_by_action_file = AsyncMock(return_value={})
        worker._create_proposal = AsyncMock(return_value="proposal-abc")
        worker._defer_to_proposal = AsyncMock(return_value=1)
        worker._release_unmappable = AsyncMock(return_value=0)
        worker._mark_delegated = AsyncMock(return_value=0)
        worker.post_report = AsyncMock()
        worker._is_file_committed = MagicMock(return_value=True)

        with (
            patch(
                "will.workers.violation_remediator.load_vocabulary_projection"
            ) as mock_load,
            patch(
                "will.workers.violation_remediator.load_circuit_breaker_config"
            ) as mock_cb,
        ):
            mock_load.return_value = MagicMock()
            mock_cb.return_value = MagicMock(threshold_n=5)
            await worker.run()

        worker._create_proposal.assert_called_once_with(
            "fix.format", "action", [finding]
        )
        report_payload = worker.post_report.call_args[1]["payload"]
        assert report_payload["entries_held_uncommitted"] == 0
        assert report_payload["proposals_created"] == 1

    async def test_flow_findings_bypass_uncommitted_gate(self, worker):
        """Flow-kind remediations have no file_path target and must not be gated."""
        finding = {
            "id": "entry-flow-1",
            "payload": {
                "check_id": "test.runner.missing",
                "file_path": None,
            },
        }
        worker._load_open_findings = AsyncMock(return_value=[finding])
        worker._get_remediation_map = MagicMock(
            return_value={
                "test.runner.missing": {
                    "ref_id": "flow.build_tests",
                    "ref_kind": "flow",
                    "status": "ACTIVE",
                }
            }
        )
        worker._get_active_proposal_id_by_action_file = AsyncMock(return_value={})
        worker._create_proposal = AsyncMock(return_value="proposal-flow-1")
        worker._defer_to_proposal = AsyncMock(return_value=1)
        worker._release_unmappable = AsyncMock(return_value=0)
        worker._mark_delegated = AsyncMock(return_value=0)
        worker.post_report = AsyncMock()
        worker._is_file_committed = MagicMock(return_value=False)

        with (
            patch(
                "will.workers.violation_remediator.load_vocabulary_projection"
            ) as mock_load,
            patch(
                "will.workers.violation_remediator.load_circuit_breaker_config"
            ) as mock_cb,
        ):
            mock_load.return_value = MagicMock()
            mock_cb.return_value = MagicMock(threshold_n=5)
            await worker.run()

        worker._create_proposal.assert_called_once()
        worker._is_file_committed.assert_not_called()
