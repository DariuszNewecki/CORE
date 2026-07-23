# src/cli/logic/demo/scenario_runner.py
"""
Isolated consequence-chain demo — Phase 2 chain scenario (ADR-155 D6).

Runs *inside* the child process Phase 1's substrate spawns: cwd rooted in
the disposable clone, the clone's own `src/` first on `PYTHONPATH`, its own
`.env` pointing at disposable Postgres/Qdrant with LLM disabled (D5). This
module is that child process's entire job.

Orchestrates only real production components — no demo-only audit,
proposal, approval, execution, or evidence path (D6):

1. One `AuditViolationSensor` cycle (`audit_sensor_linkage` declaration).
2. Resolve exactly one matching finding by exact subject (D8) — never
   "latest", never a wildcard-y match (LIKE metacharacters escaped).
3. One `ViolationRemediatorWorker` cycle.
4. Resolve the linked proposal from the finding's own `payload.proposal_id`
   (D8) and cross-verify the reverse link via
   `constitutional_constraints.finding_ids` (D8).
5. Execute via `POST /v1/proposals/{id}/execute` over an in-process ASGI
   transport (D6) — no live server, no extra port.
6. Fetch evidence via `GET /v1/proposals/{id}/chain` over the same
   transport (D6/D12) — direct SQL and "latest" selection are prohibited;
   every fact below comes from this one response.
7. A second `AuditViolationSensor` cycle for re-audit closure (D10
   assertion 13).

Writes the full result to `<state_dir>/scenario_result.json` via
`cli.logic.demo.isolation.write_state_json` — the parent orchestrator
(which alone holds the D7 seed proofs and invoking-repo/.intent
fingerprints) reads this back to evaluate the full D10 assertion set.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any


# D5: this module is invoked as the child process's own top-level script
# (``python src/cli/logic/demo/scenario_runner.py ...``), rooted at the
# clone via the process's cwd. A script invocation only puts its own
# containing directory on sys.path — never the repo's `src/` root — so the
# `cli.*` imports below would otherwise fail. Must run before those
# imports; this is the one legitimate exception to import-ordering
# convention in this file.
_SRC_ROOT = str(Path(__file__).resolve().parents[3])
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

import httpx
import yaml

from cli.logic.demo.isolation import write_state_json
from cli.logic.demo.models import (
    ChainEvidence,
    ChainScenarioResult,
    FindingIdentity,
    ProposalIdentity,
)


_SENSOR_DECLARATION = "audit_sensor_linkage"
_REMEDIATOR_DECLARATION = "violation_remediator"
_TARGET_RULE_ID = "linkage.assign_ids"
_ASGI_BASE_URL = "http://demo.internal"


def _escape_like_pattern(value: str) -> str:
    """Escape SQL LIKE metacharacters so a caller gets exact-string matching.

    ``fetch_open_findings_by_patterns`` matches via ``LIKE ANY(:patterns)``
    with the ANSI-default backslash escape. Path-derived subjects routinely
    contain ``_`` (e.g. ``demo_onramp_<run>.py``), which LIKE treats as
    "match any single character" unless escaped — D8 requires an *exact*
    match, not an incidental one that only holds because this disposable
    database happens to contain nothing else yet.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _load_worker_declaration(declaration_name: str) -> dict[str, Any]:
    """Load one `.intent/workers/<name>.yaml` declaration.

    Mirrors ``cli.resources.workers.run._load_worker_declarations`` (the
    real `core-admin workers run` path) but for a single named declaration,
    since this scenario needs exactly two, not a full listing.
    """
    from shared.config import settings

    yaml_path = settings.MIND / "workers" / f"{declaration_name}.yaml"
    return yaml.safe_load(yaml_path.read_text(encoding="utf-8"))


async def _instantiate_and_run_worker(declaration_name: str, core_context: Any) -> None:
    """Instantiate a worker from its declaration and run exactly one cycle.

    Mirrors ``cli.resources.workers.run.workers_run_cmd``'s constructor-kwargs
    build precisely — same declaration-driven ``rule_namespace``/
    ``implementation.params`` merge — so a run-required parameter (e.g.
    ``audit_sensor_linkage``'s ``dry_run: false``) is never silently dropped
    for a demo-specific hardcoded call.
    """
    import importlib

    declaration = _load_worker_declaration(declaration_name)
    impl = declaration["implementation"]
    module = importlib.import_module(impl["module"])
    worker_class = getattr(module, impl["class"])

    kwargs: dict[str, Any] = {"declaration_name": declaration_name}
    rule_namespace = declaration.get("mandate", {}).get("scope", {}).get(
        "rule_namespace", ""
    )
    if rule_namespace:
        kwargs["rule_namespace"] = rule_namespace

    protected = {"declaration_name", "rule_namespace", "core_context", "cognitive_service"}
    for key, value in (impl.get("params") or {}).items():
        if key not in protected:
            kwargs[key] = value

    try:
        worker = worker_class(core_context=core_context, **kwargs)
    except TypeError:
        worker = worker_class(core_context=core_context)

    if not worker.declaration_name:
        worker.declaration_name = declaration_name

    await worker.start()


async def _resolve_finding(
    seed_rel_path: str,
) -> tuple[FindingIdentity | None, int]:
    """Resolve the exact seeded finding by subject (D8).

    Returns (finding_identity_or_none, match_count) — the caller records
    both; zero or multiple matches is itself a D10 failure, never silently
    picked-first.
    """
    from body.services.blackboard_service.blackboard_query_service import (
        BlackboardQueryService,
    )

    expected_subject = f"python::{_TARGET_RULE_ID}::{seed_rel_path}"
    query = BlackboardQueryService()
    matches = await query.fetch_open_findings_by_patterns(
        [_escape_like_pattern(expected_subject)], limit=10
    )
    if len(matches) != 1:
        return None, len(matches)

    entry = matches[0]
    payload = entry["payload"]
    finding = FindingIdentity(
        entry_id=entry["id"],
        subject=entry["subject"],
        rule_id=payload.get("rule", ""),
        file_path=payload.get("file_path", ""),
        status="open",
    )
    return finding, 1


async def _resolve_proposal(finding_entry_id: str) -> ProposalIdentity | None:
    """Resolve the proposal linked from the finding's own payload (D8).

    Reads ``payload.proposal_id`` off the finding (re-fetched by id, since
    remediation already moved it out of 'open') and cross-verifies the
    reverse link via the proposal's own
    ``constitutional_constraints.finding_ids`` — genuine bidirectional
    linkage, never "latest".
    """
    from body.services.blackboard_service.blackboard_query_service import (
        BlackboardQueryService,
    )
    from body.services.service_registry import service_registry
    from will.autonomy.proposal_repository import ProposalRepository

    entry = await BlackboardQueryService().fetch_entry_by_id(finding_entry_id)
    if entry is None:
        return None
    proposal_id = entry["payload"].get("proposal_id")
    if not proposal_id:
        return None

    async with service_registry.session() as session:
        proposal = await ProposalRepository(session).get(proposal_id)
    if proposal is None:
        return None

    finding_ids = proposal.constitutional_constraints.get("finding_ids", [])
    if finding_entry_id not in finding_ids:
        # Recorded linkage does not point back at the finding it came
        # from — a real D8 failure, not a code bug to swallow.
        return None

    action_ids = [a.action_id for a in proposal.actions if a.action_id]
    risk = proposal.risk.overall_risk if proposal.risk else ""
    return ProposalIdentity(
        proposal_id=proposal.proposal_id,
        goal=proposal.goal,
        status=proposal.status.value,
        overall_risk=risk,
        approval_required=proposal.approval_required,
        approval_authority=proposal.approval_authority,
        approved_by=proposal.approved_by,
        finding_ids=finding_ids,
        action_ids=action_ids,
        scope_files=list(proposal.scope.files),
    )


async def _execute_and_fetch_chain(
    app: Any, proposal_id: str
) -> tuple[dict[str, Any], ChainEvidence | None]:
    """POST /execute then GET /chain over an in-process ASGI transport (D6)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=_ASGI_BASE_URL) as client:
        exec_response = await client.post(
            f"/v1/proposals/{proposal_id}/execute", json={"write": True}
        )
        exec_response.raise_for_status()
        exec_result = exec_response.json()

        chain_response = await client.get(f"/v1/proposals/{proposal_id}/chain")
        if chain_response.status_code != 200:
            return exec_result, None
        chain_json = chain_response.json()

    proposal_json = chain_json["proposal"]
    consequence_json = chain_json.get("consequence")
    proposal_identity = ProposalIdentity(
        proposal_id=proposal_json["proposal_id"],
        goal=proposal_json["goal"],
        status=proposal_json["status"],
        overall_risk=(proposal_json.get("risk") or {}).get("overall_risk", ""),
        approval_required=proposal_json["status"] not in ("draft",),
        approval_authority=proposal_json.get("approval_authority"),
        approved_by=proposal_json.get("approved_by"),
        finding_ids=[],
        action_ids=[],
        scope_files=[],
    )
    raw_files_changed = (consequence_json or {}).get("files_changed", [])
    files_changed = [
        entry["path"] if isinstance(entry, dict) else entry
        for entry in raw_files_changed
    ]
    chain_evidence = ChainEvidence(
        proposal=proposal_identity,
        lifecycle_status=exec_result.get("lifecycle_status", ""),
        execution_claimer=None,
        pre_execution_sha=(consequence_json or {}).get("pre_execution_sha"),
        post_execution_sha=(consequence_json or {}).get("post_execution_sha"),
        files_changed=files_changed,
        findings_resolved=(consequence_json or {}).get("findings_resolved", []),
    )
    return exec_result, chain_evidence


async def _reaudit_is_clean(core_context: Any, seed_rel_path: str) -> bool:
    """Run a second sensor cycle and confirm the rule no longer fires (D10 assertion 13).

    Reuses the same lifespan-initialized ``core_context`` the first sensor
    cycle used — a bare ``create_core_context`` (skipping ``core_lifespan``)
    never populates ``auditor_context``, which the sensor requires.
    """
    await _instantiate_and_run_worker(_SENSOR_DECLARATION, core_context)
    _, match_count = await _resolve_finding(seed_rel_path)
    return match_count == 0


# ID: c5caeb83-4312-4421-baa3-16d3711bd88d
async def run_scenario(state_dir: Path, seed_rel_path: str, run_id: str) -> None:
    """Drive the full Phase 2 chain scenario and write the result to state_dir.

    Entry point invoked as ``python -m cli.logic.demo.scenario_runner
    <state_dir> <seed_rel_path> <run_id>`` by the parent orchestrator's
    child-process spawn (Phase 1 D5 substrate). Never raises on a scenario
    failure — every failure mode is recorded in the result's ``error``
    field so the parent can fail closed with a specific reason rather than
    a crashed child process with no evidence.
    """
    from api.main import create_app

    error: str | None = None
    finding: FindingIdentity | None = None
    finding_matches = 0
    proposal: ProposalIdentity | None = None
    chain: ChainEvidence | None = None
    reaudit_clean = False
    reaudit_matches = 1
    finding_final_status: str | None = None
    finding_final_proposal_id: str | None = None

    try:
        app = create_app()
        async with app.router.lifespan_context(app):
            core_context = app.state.core_context

            await _instantiate_and_run_worker(_SENSOR_DECLARATION, core_context)
            finding, finding_matches = await _resolve_finding(seed_rel_path)
            if finding is None:
                error = f"expected exactly 1 finding, found {finding_matches}"
            else:
                await _instantiate_and_run_worker(_REMEDIATOR_DECLARATION, core_context)
                proposal = await _resolve_proposal(finding.entry_id)
                if proposal is None:
                    error = "no exact, bidirectionally-linked proposal found"
                else:
                    _, chain = await _execute_and_fetch_chain(app, proposal.proposal_id)
                    if chain is None:
                        error = "chain evidence unavailable after execution"

                    from body.services.blackboard_service.blackboard_query_service import (
                        BlackboardQueryService,
                    )

                    final_entry = await BlackboardQueryService().fetch_entry_by_id(
                        finding.entry_id
                    )
                    if final_entry is not None:
                        finding_final_status = final_entry["status"]
                        finding_final_proposal_id = final_entry["payload"].get(
                            "proposal_id"
                        )

            reaudit_clean = await _reaudit_is_clean(core_context, seed_rel_path)
            _, reaudit_matches = await _resolve_finding(seed_rel_path)
    except Exception as exc:  # captured into the result, not swallowed
        error = f"{type(exc).__name__}: {exc}"

    result = ChainScenarioResult(
        run_id=run_id,
        seed_rel_path=seed_rel_path,
        finding=finding,
        finding_matches_count=finding_matches,
        proposal=proposal,
        chain=chain,
        reaudit_clean=reaudit_clean,
        reaudit_matches_count=reaudit_matches,
        finding_final_status=finding_final_status,
        finding_final_proposal_id=finding_final_proposal_id,
        error=error,
    )
    write_state_json(state_dir / "scenario_result.json", result.to_dict())


def _main() -> None:
    """Process entry point — defensively guarded per architecture.no_module_async_engine
    / async.no_manual_loop_run: this is the child process's own top-level
    script (D5), never invoked from inside an already-running loop, but the
    guard is required regardless of caller identity.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    state_dir = Path(sys.argv[1])
    seed_rel_path = sys.argv[2]
    run_id = sys.argv[3]

    if loop and loop.is_running():
        raise RuntimeError(
            "scenario_runner._main() invoked inside an already-running event "
            "loop — it must be the process's own top-level entry point."
        )
    asyncio.run(run_scenario(state_dir, seed_rel_path, run_id))


if __name__ == "__main__":
    _main()
