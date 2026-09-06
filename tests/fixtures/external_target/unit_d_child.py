"""Unit D child process: the real governed fix.format mutation attempt.

Invoked as ``python unit_d_child.py <target_path> <result_path>`` with
``REPO_PATH``, ``MIND``, and ``DATABASE_URL`` already bound in the
environment by the parent orchestrator (``unit_d_orchestrator.py``),
before any bootstrap-sensitive CORE import -- this module's own first
import is Unit A's binding guard, mirroring
``cli.runtime_external_verify``'s import-ordering discipline exactly.

Real components only: the real ``ProposalRepository``, the real
``ProposalStateManager.approve()`` (which evaluates the target-local safe
auto-approval envelope via the real, unmodified
``will.autonomy.safe_auto_approval_envelope.validate_envelope``), and the
real, unmodified ``ProposalConsumerWorker`` class, constructed exactly as
its own public signature allows -- ``ProposalConsumerWorker(core_context)``
-- with no ``repo_root`` override, no ``__new__`` bypass, no monkeypatch,
and no widening of the target's ``.intent/`` beyond the ratified envelope.

If that construction fails, this module reports the failure honestly as
the stage where the run stopped. It does not attempt a workaround: per
the Unit D brief, "if the real governed path cannot complete without a
production correction, stop after preserving evidence" and "do not fix
the newly discovered defect in this unit."

Writes one JSON result to <result_path> and never raises past its own
outer try/except -- every failure mode becomes a structured ``ok: False``
result with a ``stage`` name, so the parent can report a specific blocker
rather than a crashed child with no evidence.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path


_SRC_ROOT = str(Path(__file__).resolve().parents[3] / "src")
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

_CORE_REPO_ROOT = Path(__file__).resolve().parents[3]

_GOAL = "Unit D: real governed format mutation of package/example.py"
_TARGET_FILE = "package/example.py"
_APPROVAL_AUTHORITY = "risk_classification.safe_auto_approval"
_APPROVED_BY = "unit_d_scenario_runner"
_REPORT_SUBJECT = "proposal_consumer_worker.run.complete"


def _fail(stage: str, error: str, **extra: object) -> dict:
    return {"ok": False, "stage": stage, "error": error, **extra}


async def _run(target: Path) -> dict:
    # Step 1 -- Unit A's binding guard, before any heavy import.
    from shared.infrastructure.external_target_binding import (
        ExternalTargetBindingError,
        validate_external_target_binding,
    )

    try:
        canonical_target = validate_external_target_binding(
            target,
            repo_path_value=os.environ.get("REPO_PATH"),
            mind_value=os.environ.get("MIND"),
            database_url_value=os.environ.get("DATABASE_URL"),
            core_repo_root=_CORE_REPO_ROOT,
        )
    except ExternalTargetBindingError as exc:
        return _fail("binding_guard", str(exc))

    # Step 2 -- construct the ordinary CoreContext, only now.
    from body.infrastructure.bootstrap import create_core_context
    from body.services.service_registry import service_registry
    from cli.runtime_external_verify import find_root_disagreements
    from shared.config import settings
    from shared.infrastructure.bootstrap_registry import bootstrap_registry
    from shared.infrastructure.intent.intent_repository import get_intent_repository

    try:
        core_context = create_core_context(service_registry)
    except Exception as exc:
        return _fail("bootstrap", f"{type(exc).__name__}: {exc}")

    canonical_mind = canonical_target / ".intent"
    disagreements = find_root_disagreements(
        git_service_repo_path=core_context.git_service.repo_path,
        settings_repo_path=settings.REPO_PATH,
        settings_mind=settings.MIND,
        bootstrap_registry_repo_path=bootstrap_registry.get_repo_path(),
        service_registry_repo_path=(
            Path(service_registry.repo_path)
            if service_registry.repo_path is not None
            else None
        ),
        intent_repository_root=get_intent_repository().root,
        expected_target=canonical_target,
        expected_mind=canonical_mind,
    )
    if disagreements:
        return _fail(
            "root_agreement", "runtime roots disagree", disagreements=disagreements
        )

    # Step 3 -- construct exactly one deterministic Proposal via the real
    # Proposal repository. Status starts DRAFT (dataclass default); never
    # instantiated as APPROVED, never updated via raw SQL.
    import body.atomic  # noqa: F401 -- triggers action registration
    from will.autonomy.proposal import Proposal, ProposalAction, ProposalScope
    from will.autonomy.proposal_repository import ProposalRepository
    from will.autonomy.proposal_state_manager import (
        ProposalStateManager,
        SafeAutoApprovalDeniedError,
    )

    proposal = Proposal(
        goal=_GOAL,
        actions=[
            ProposalAction(
                action_id="fix.format",
                parameters={"write": True, "file_path": _TARGET_FILE},
                order=0,
            )
        ],
        scope=ProposalScope(files=[_TARGET_FILE]),
        created_by=_APPROVED_BY,
        constitutional_constraints={"source": _APPROVED_BY},
    )
    proposal.compute_risk()

    is_valid, errors = proposal.validate()
    if not is_valid:
        return _fail("proposal_validate", "; ".join(errors))

    if proposal.approval_required:
        return _fail(
            "proposal_risk",
            "fix.format is not classified safe in this target -- not "
            "eligible for the safe-auto-approval path this unit requires",
            overall_risk=proposal.risk.overall_risk if proposal.risk else None,
        )

    async with service_registry.session() as session:
        repo = ProposalRepository(session)
        proposal_id = await repo.create(proposal)
        pre_approval_status = proposal.status.value

        state_manager = ProposalStateManager(session)
        try:
            # Step 4 -- approval through the existing production path that
            # evaluates the target-local safe-auto-approval envelope.
            # Never principal.governor; never a raw-SQL status update.
            await state_manager.approve(
                proposal_id,
                approved_by=_APPROVED_BY,
                approval_authority=_APPROVAL_AUTHORITY,
            )
        except SafeAutoApprovalDeniedError as denial:
            await session.commit()
            return _fail(
                "safe_auto_approval",
                str(denial),
                proposal_id=proposal_id,
                pre_approval_status=pre_approval_status,
            )
        await session.commit()

    async with service_registry.session() as session:
        approved = await ProposalRepository(session).get(proposal_id)
    if approved is None or approved.status.value != "approved":
        return _fail(
            "post_approval_state",
            f"expected status=approved, got "
            f"{approved.status.value if approved else None}",
            proposal_id=proposal_id,
            pre_approval_status=pre_approval_status,
        )

    # Step 5 -- construct the real, unmodified ProposalConsumerWorker via
    # its own public signature: ProposalConsumerWorker(core_context). No
    # repo_root override (its __init__ does not expose one), no __new__
    # bypass, no target .intent/ widening. Worker.__init__ resolves its
    # declaration via the process-wide IntentRepository singleton, which
    # is bound to MIND -- the external target's .intent/ in this run, per
    # Units A/B's own design. The ratified target authority (fix.format /
    # package/ / rules/code/purity only) deliberately carries no
    # .intent/workers/ declaration -- extending it would widen the
    # fixture's ratified envelope, which this unit must not do.
    from will.workers.proposal_consumer_worker import ProposalConsumerWorker

    try:
        worker = ProposalConsumerWorker(core_context=core_context)
    except Exception as exc:
        return _fail(
            "worker_construction",
            f"{type(exc).__name__}: {exc}",
            proposal_id=proposal_id,
            pre_approval_status=pre_approval_status,
            final_status=approved.status.value,
        )

    # Step 6 -- invoke the worker's run() exactly once. Reached only if
    # construction above succeeded.
    await worker.run()

    # Step 7 -- gather raw evidence. All reads, no further mutation.
    async with service_registry.session() as session:
        final_proposal = await ProposalRepository(session).get(proposal_id)

    from sqlalchemy import text

    async with service_registry.session() as session:
        action_rows = (
            (
                await session.execute(
                    text(
                        "SELECT action_type, ok, file_path, error_message, "
                        "action_metadata, agent_id, duration_ms "
                        "FROM core.action_results ORDER BY id"
                    )
                )
            )
            .mappings()
            .all()
        )
        consequence_rows = (
            (
                await session.execute(
                    text(
                        "SELECT proposal_id, pre_execution_sha, post_execution_sha, "
                        "files_changed, findings_resolved, authorized_by_rules, "
                        "declared_production, consequence_source "
                        "FROM core.proposal_consequences WHERE proposal_id = :pid"
                    ),
                    {"pid": proposal_id},
                )
            )
            .mappings()
            .all()
        )

    from body.services.blackboard_service.blackboard_query_service import (
        BlackboardQueryService,
    )

    report_payload = await BlackboardQueryService().fetch_latest_report_payload(
        _REPORT_SUBJECT
    )

    return {
        "ok": True,
        "proposal_id": proposal_id,
        "canonical_target": str(canonical_target),
        "pre_approval_status": pre_approval_status,
        "final_status": final_proposal.status.value if final_proposal else None,
        "final_failure_reason": final_proposal.failure_reason
        if final_proposal
        else None,
        "action_results_rows": [dict(r) for r in action_rows],
        "consequence_rows": [dict(r) for r in consequence_rows],
        "blackboard_report": report_payload,
    }


def main() -> int:
    target = Path(sys.argv[1])
    result_path = Path(sys.argv[2])

    try:
        result = asyncio.run(_run(target))
    except Exception as exc:  # captured, never a bare crash with no evidence
        result = _fail("unhandled_exception", f"{type(exc).__name__}: {exc}")

    result_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
