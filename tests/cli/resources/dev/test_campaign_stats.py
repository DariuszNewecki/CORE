# tests/cli/resources/dev/test_campaign_stats.py

"""Unit tests for _tally and _pct helpers in campaign_review.py.

The stats command's rendering depends on correct tally logic. These tests
exercise the helper functions in isolation — no CLI invocation, no DB.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from cli.resources.dev.campaign_review import _pct, _review_state, _tally


def _make_cluster(
    *,
    assigned_role: str = "AutonomousDeveloper",
    status: str = "pending",
    requires_approval: bool = True,
) -> MagicMock:
    c = MagicMock()
    c.assigned_role = assigned_role
    c.status = status
    c.requires_approval = requires_approval
    return c


# ── _review_state ─────────────────────────────────────────────────────────────

# ID: 3416f62b-0db1-490a-8282-b52837d96f73
def test_review_state_escalation() -> None:
    assert _review_state(_make_cluster(assigned_role="Human")) == "escalation"


# ID: c205a560-3610-4f94-9b30-1ee73f0a817b
def test_review_state_rejected() -> None:
    assert _review_state(_make_cluster(status="blocked")) == "rejected"


# ID: da0af175-6345-47b4-8031-d299f378e75d
def test_review_state_approved() -> None:
    assert _review_state(_make_cluster(status="pending", requires_approval=False)) == "approved"


# ID: 32008f70-d430-4d30-84c3-8493f495ea39
def test_review_state_awaiting_review() -> None:
    assert _review_state(_make_cluster(status="pending", requires_approval=True)) == "awaiting review"


# ── _tally ────────────────────────────────────────────────────────────────────

# ID: 0695788a-2aed-4917-a13c-b5e1a4e4408a
def test_tally_empty_cluster_list() -> None:
    result = _tally([])
    assert result == {"approved": 0, "rejected": 0, "pending": 0, "escalation": 0}


# ID: 71d590ea-3373-43cc-95d0-88024c605f22
def test_tally_mixed_cluster_states() -> None:
    clusters = [
        _make_cluster(status="pending", requires_approval=False),   # approved
        _make_cluster(status="pending", requires_approval=False),   # approved
        _make_cluster(status="blocked"),                            # rejected
        _make_cluster(status="pending", requires_approval=True),    # pending
        _make_cluster(assigned_role="Human"),                       # escalation
    ]
    result = _tally(clusters)
    assert result["approved"] == 2
    assert result["rejected"] == 1
    assert result["pending"] == 1
    assert result["escalation"] == 1


def test_tally_counts_executing_and_completed_as_approved() -> None:
    clusters = [
        _make_cluster(status="executing", requires_approval=False),
        _make_cluster(status="completed", requires_approval=False),
    ]
    result = _tally(clusters)
    assert result["approved"] == 2
    assert result["rejected"] == 0


def test_tally_all_rejected() -> None:
    clusters = [_make_cluster(status="blocked") for _ in range(5)]
    result = _tally(clusters)
    assert result["rejected"] == 5
    assert result["approved"] == 0
    assert result["pending"] == 0


# ── _pct ──────────────────────────────────────────────────────────────────────

def test_pct_zero_total_returns_dash() -> None:
    assert _pct(0, 0) == "—"


def test_pct_calculates_correctly() -> None:
    assert _pct(1, 4) == "25%"
    assert _pct(3, 4) == "75%"
    assert _pct(4, 4) == "100%"
    assert _pct(0, 4) == "0%"
