# tests/proof_index/test_claim_04_audit_gap.py
"""Proof Index claim 4 (mechanizable half): a failed write-action audit is surfaced, not silent.

Standing regression check for the CI-mechanizable half of docs/proof-index.md
claim 4 (#798). When `ActionExecutor._audit_log` exhausts its INSERT retries for a
`write=True` action, it MUST log an `AUDIT_GAP` error — the mutation already
landed, so the gap is surfaced loudly, never swallowed. The live-trail half (rows
actually accumulating) is attestation-only; see .specs/attestations/proof-index.yaml.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from body.atomic.executor import ActionExecutor
from shared.action_types import ActionImpact, ActionResult


class _RaisingRegistry:
    """Every session attempt fails, forcing _audit_log to exhaust its retries."""

    def session(self):
        raise RuntimeError("db unavailable")


async def test_audit_gap_logged_loud_on_write_action_failure() -> None:
    exe = ActionExecutor.__new__(ActionExecutor)
    exe.core_context = SimpleNamespace(session_id=None, registry=_RaisingRegistry())
    exe._AUDIT_MAX_ATTEMPTS = 2
    exe._AUDIT_BACKOFF_BASE_SEC = 0.0

    definition = SimpleNamespace(action_id="proof.claim4.demo", impact_level="safe")
    result = ActionResult(
        action_id="proof.claim4.demo",
        ok=True,
        data={},
        impact=ActionImpact.WRITE_CODE,
        duration_sec=0.0,
    )

    with patch("body.atomic.executor.logger") as mock_logger:
        # Must NOT raise: the mutation stands; the gap is surfaced via the log.
        await exe._audit_log(definition, result, write=True)

    assert mock_logger.error.called
    assert any(
        "AUDIT_GAP" in str(call.args[0]) for call in mock_logger.error.call_args_list
    ), mock_logger.error.call_args_list
