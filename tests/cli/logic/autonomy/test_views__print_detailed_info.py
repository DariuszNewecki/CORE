"""Regression test for `core-admin proposals show` crash (issue #222).

`print_detailed_info` called `logger.info()` with no positional arguments,
raising ``TypeError: Logger.info() missing 1 required positional argument:
'msg'`` whenever a proposal carried a RiskAssessment — i.e. effectively
every real proposal. The bug aborted the show command before any record
was rendered.

2026-06-07 (#572 Cat B batch 16): ``print_detailed_info(p: dict)`` consumes
a dict, not a ``Proposal`` dataclass — the real CLI call site
(cli/resources/proposals/manage.py:27) hands it the JSON-decoded body of
the API response. The autogen vintage passed a ``Proposal`` dataclass
instance, which is not subscriptable. Tests now ``dataclasses.asdict``
the Proposal before calling, matching the CLI's actual contract.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

from cli.logic.autonomy.views import print_detailed_info
from will.autonomy.proposal import (
    Proposal,
    ProposalAction,
    ProposalScope,
    ProposalStatus,
    RiskAssessment,
)


def _proposal_with_risk() -> Proposal:
    """Mirror the real failing record: draft, has risk + risk_factors,
    has at least one action and a scope file."""
    return Proposal(
        proposal_id="95210806-71ab-49ce-95bf-89d2b4747c8a",
        goal="Autonomous remediation: fix.modularity",
        actions=[
            ProposalAction(
                action_id="fix.modularity",
                parameters={"file_path": "src/example.py", "write": True},
                order=0,
            )
        ],
        scope=ProposalScope(files=["src/example.py"]),
        risk=RiskAssessment(
            overall_risk="moderate",
            action_risks={"fix.modularity": "moderate"},
            risk_factors=["Contains moderate-impact actions"],
            mitigation=["Automated pre-flight checks", "Rollback plan prepared"],
        ),
        status=ProposalStatus.DRAFT,
        created_at=datetime(2026, 5, 3, 16, 6, 32, tzinfo=UTC),
        created_by="violation_remediator_worker",
        approval_required=True,
    )


def test_print_detailed_info_does_not_crash_on_proposal_with_risk():
    """The exact path that hit views.py:66 — proposal carries RiskAssessment
    with risk_factors, so the bare logger.info() separator was reached."""
    print_detailed_info(asdict(_proposal_with_risk()))


def test_print_detailed_info_does_not_crash_when_risk_is_none():
    """Defensive: also exercise the no-risk branch which skips the separator."""
    p = _proposal_with_risk()
    p.risk = None
    p.approval_required = False
    print_detailed_info(asdict(p))


def test_print_detailed_info_does_not_crash_on_completed_execution():
    """Exercise the completed-execution branch (started+completed timestamps).

    Source computes duration via ``datetime.fromisoformat(completed) -
    datetime.fromisoformat(started)``, which requires the timestamps to be
    ISO-string-typed at the dict surface (the CLI's real API path serialises
    them on the wire). We mirror that here by ``isoformat()``-ing the
    datetime fields after the asdict round-trip."""
    p = _proposal_with_risk()
    p.execution_started_at = datetime(2026, 5, 3, 16, 7, 0, tzinfo=UTC)
    p.execution_completed_at = datetime(2026, 5, 3, 16, 7, 30, tzinfo=UTC)
    payload = asdict(p)
    payload["execution_started_at"] = p.execution_started_at.isoformat()
    payload["execution_completed_at"] = p.execution_completed_at.isoformat()
    print_detailed_info(payload)
