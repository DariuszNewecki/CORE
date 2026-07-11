# tests/api/v1/test_chain_routes.py

"""Unit tests for the governance chain endpoints.

Passes a mock ConsequenceLogService directly as a kwarg — FastAPI DI defaults
are bypassed when the argument is supplied explicitly, so no patching needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from api.v1.findings_routes import get_finding_chain
from api.v1.proposals_routes import get_proposal_chain


def _mock_session() -> AsyncMock:
    return AsyncMock()


def _mock_svc(**method_returns: object) -> MagicMock:
    svc = MagicMock()
    for method, return_value in method_returns.items():
        setattr(svc, method, AsyncMock(return_value=return_value))
    return svc


def _stub_chain(proposal_id: str = "prop-abc") -> dict:
    return {
        "proposal": {
            "proposal_id": proposal_id,
            "goal": "fix import order",
            "status": "completed",
            "risk": {"overall_risk": "safe"},
            "approval_authority": "risk_classification.safe_auto_approval",
            "approved_by": None,
            "approved_at": None,
            "execution_results": {},
            "created_by": "autonomous",
            "created_at": "2026-07-11T10:00:00+00:00",
            "failure_reason": None,
        },
        "findings": [
            {
                "entry_id": "entry-001",
                "subject": "audit.violation::import_order",
                "status": "resolved",
                "check_id": "import_order",
                "rule_id": "import_order",
                "file_path": "src/body/services/foo.py",
                "severity": "error",
                "evidence": {"lines": [1, 2]},
                "evidence_class": "static_analysis",
                "created_at": "2026-07-11T09:00:00+00:00",
            }
        ],
        "consequence": {
            "pre_execution_sha": "abc123",
            "post_execution_sha": "def456",
            "files_changed": [{"path": "src/body/services/foo.py"}],
            "findings_resolved": ["entry-001"],
            "authorized_by_rules": ["import_order"],
            "recorded_at": "2026-07-11T10:05:00+00:00",
        },
    }


# ── get_proposal_chain ────────────────────────────────────────────────────────


async def test_get_proposal_chain_returns_chain():
    """Returns the chain dict from ConsequenceLogService as-is on 200."""
    chain = _stub_chain()
    svc = _mock_svc(get_chain_for_proposal=chain)
    result = await get_proposal_chain("prop-abc", session=_mock_session(), svc=svc)

    assert result["proposal"]["proposal_id"] == "prop-abc"
    assert result["consequence"]["post_execution_sha"] == "def456"
    assert len(result["findings"]) == 1


async def test_get_proposal_chain_not_found_raises_404():
    """Raises HTTPException(404) when ConsequenceLogService returns None."""
    svc = _mock_svc(get_chain_for_proposal=None)
    with pytest.raises(HTTPException) as exc_info:
        await get_proposal_chain("missing-id", session=_mock_session(), svc=svc)

    assert exc_info.value.status_code == 404
    assert "missing-id" in exc_info.value.detail


async def test_get_proposal_chain_null_consequence():
    """Returns chain with consequence=None for an un-executed proposal."""
    chain = _stub_chain()
    chain["consequence"] = None
    svc = _mock_svc(get_chain_for_proposal=chain)
    result = await get_proposal_chain("prop-abc", session=_mock_session(), svc=svc)

    assert result["consequence"] is None


# ── get_finding_chain ─────────────────────────────────────────────────────────


async def test_get_finding_chain_resolves_via_proposal_id():
    """Resolves entry -> proposal_id -> chain and returns chain."""
    chain = _stub_chain("prop-abc")
    svc = _mock_svc(get_finding_proposal_link="prop-abc", get_chain_for_proposal=chain)
    result = await get_finding_chain("entry-001", session=_mock_session(), svc=svc)

    assert result["proposal"]["proposal_id"] == "prop-abc"


async def test_get_finding_chain_no_link_raises_404():
    """Raises 404 when the finding has no proposal link in its payload."""
    svc = _mock_svc(get_finding_proposal_link=None)
    with pytest.raises(HTTPException) as exc_info:
        await get_finding_chain("entry-no-link", session=_mock_session(), svc=svc)

    assert exc_info.value.status_code == 404
    assert "entry-no-link" in exc_info.value.detail


async def test_get_finding_chain_orphaned_proposal_raises_404():
    """Raises 404 when the payload has a proposal_id but the proposal row is gone."""
    svc = _mock_svc(get_finding_proposal_link="ghost-prop", get_chain_for_proposal=None)
    with pytest.raises(HTTPException) as exc_info:
        await get_finding_chain("entry-001", session=_mock_session(), svc=svc)

    assert exc_info.value.status_code == 404
    assert "ghost-prop" in exc_info.value.detail
