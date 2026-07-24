# src/cli/resources/demo/rendering.py
"""
Truthful evidence rendering for the isolated consequence-chain demo (ADR-155 D12).

Every fact rendered here is read from the ``PhaseResult`` the orchestration
returned — whose ``scenario`` field is the *exact* ``ChainScenarioResult`` the
real chain produced (D6). Nothing here re-queries, re-derives, or selects a
"latest" row: the renderer is a projection of already-proven facts, never a
second source of truth.

Two honesty invariants (D9/D12/U11) are structural, not stylistic:

- The proposal's approval authority is rendered as *policy* authority
  (``risk_classification.safe_auto_approval``) with its recorded approver
  identity. The demo never claims a human operator approved the proposal.
- The operator's terminal confirmation is rendered as a *separate* line
  labelled ``human`` or ``simulated`` — consent to continue the
  demonstration, explicitly not a proposal-approval event.

The single ``_report_payload`` builder feeds the terminal summary, the
Markdown report, and the JSON companion, so the three can never disagree on an
identity (U14).
"""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table

from cli.logic.demo.models import PhaseResult


_PROOF_STATEMENT = (
    "This demonstration proves one isolated consequence chain. "
    "It is not a production-readiness attestation."
)


# ID: 7599d054-5a12-4716-9963-c00362b3859c
def _report_payload(result: PhaseResult, confirmation_mode: str) -> dict[str, Any]:
    """Build the single source dict shared by every rendering (D12/U14).

    Reads only from ``result`` — no query, no re-derivation. Absent evidence
    (a run that failed before a stage) surfaces as ``None`` rather than a
    fabricated placeholder, so a downstream reader cannot mistake a missing
    fact for a proven one.
    """
    scenario = result.scenario
    finding = scenario.finding if scenario else None
    proposal = scenario.proposal if scenario else None
    chain = scenario.chain if scenario else None

    return {
        "run_id": result.run_id,
        "assessed_commit": result.assessed_commit,
        "verdict": "passed" if result.ok else "failed",
        "operator_confirmation": confirmation_mode,
        "finding": (
            {
                "finding_id": finding.entry_id,
                "rule": finding.rule_id,
                "path": finding.file_path,
                "original_status": finding.status,
            }
            if finding
            else None
        ),
        "proposal": (
            {
                "proposal_id": proposal.proposal_id,
                "actions": proposal.action_ids,
                "scope_files": proposal.scope_files,
                "risk": proposal.overall_risk,
                "approval_authority": proposal.approval_authority,
                "approver_identity": proposal.approved_by,
                "finding_ids": proposal.finding_ids,
            }
            if proposal
            else None
        ),
        "execution": (
            {
                "claimer": chain.execution_claimer,
                "terminal_status": chain.lifecycle_status,
                "pre_execution_sha": chain.pre_execution_sha,
                "post_execution_sha": chain.post_execution_sha,
                "files_changed": chain.files_changed,
                "findings_resolved": chain.findings_resolved,
            }
            if chain
            else None
        ),
        "resolved_finding_id": scenario.finding_final_proposal_id if scenario else None,
        "resolved_finding_status": scenario.finding_final_status if scenario else None,
        "reaudit": (
            {
                "clean": scenario.reaudit_clean,
                "match_count": scenario.reaudit_matches_count,
            }
            if scenario
            else None
        ),
        "cleanup": {
            "workspace_removed": result.cleaned_up,
            "retained_path": None if result.cleaned_up else str(result.state_dir),
        },
        "assertions": [
            {"name": a.name, "passed": a.passed, "detail": a.detail}
            for a in result.assertions
        ],
        "error": scenario.error if scenario else None,
        "proof_statement": _PROOF_STATEMENT,
    }


# ID: 1c753f99-2ea4-479f-b011-cb90db9689ff
def render_summary(
    console: Console, result: PhaseResult, confirmation_mode: str
) -> None:
    """Render the D12 terminal evidence summary from the exact chain response."""
    payload = _report_payload(result, confirmation_mode)

    verdict_style = "bold green" if result.ok else "bold red"
    verdict_word = "PASSED" if result.ok else "FAILED"
    console.print()
    console.print(
        f"[{verdict_style}]Consequence-chain demo: {verdict_word}[/{verdict_style}]"
    )
    console.print(f"  run id           : {payload['run_id']}")
    console.print(f"  assessed commit  : {payload['assessed_commit']}")

    finding = payload["finding"]
    if finding:
        console.print(
            f"  finding          : {finding['finding_id']} "
            f"({finding['rule']} @ {finding['path']}, was {finding['original_status']})"
        )
    proposal = payload["proposal"]
    if proposal:
        console.print(
            f"  proposal         : {proposal['proposal_id']} "
            f"actions={proposal['actions']} risk={proposal['risk']}"
        )
        # D9/U11: policy authority + approver identity — never "human approved".
        console.print(
            f"  approval         : policy authority "
            f"'{proposal['approval_authority']}' (approver: {proposal['approver_identity']})"
        )
    execution = payload["execution"]
    if execution:
        console.print(
            f"  execution        : claimer={execution['claimer']} "
            f"status={execution['terminal_status']}"
        )
        console.print(
            f"  consequence      : {execution['pre_execution_sha']} "
            f"-> {execution['post_execution_sha']}  files={execution['files_changed']}"
        )
    console.print(
        f"  resolved finding : status={payload['resolved_finding_status']}"
    )
    reaudit = payload["reaudit"]
    if reaudit:
        console.print(
            f"  re-audit         : clean={reaudit['clean']} "
            f"matches={reaudit['match_count']}"
        )
    # D9/D12: operator confirmation is its own line, distinct from approval.
    console.print(f"  operator confirm : {payload['operator_confirmation']}")
    cleanup = payload["cleanup"]
    if cleanup["workspace_removed"]:
        console.print("  cleanup          : workspace removed")
    else:
        console.print(
            f"  cleanup          : workspace RETAINED at {cleanup['retained_path']}"
        )
        console.print(
            f"                     remove with: core-admin demo cleanup {payload['run_id']}"
        )

    if not result.ok:
        table = Table(title="Failed assertions", show_lines=False)
        table.add_column("assertion")
        table.add_column("detail", overflow="fold")
        for a in result.assertions:
            if not a.passed:
                table.add_row(a.name, a.detail)
        console.print(table)

    console.print()
    console.print(f"[dim]{_PROOF_STATEMENT}[/dim]")


# ID: 0d546fe2-94e8-45de-9224-df612dce08b2
def build_json_report(result: PhaseResult, confirmation_mode: str) -> str:
    """Serialize the D12 evidence payload as JSON (the ``--output`` companion)."""
    return json.dumps(_report_payload(result, confirmation_mode), indent=2)


# ID: 631b2ee4-6a26-4528-8ac5-e020a50391b6
def build_markdown_report(result: PhaseResult, confirmation_mode: str) -> str:
    """Render the D12 Markdown report body (the ``--output`` document).

    Carries the same identities as :func:`build_json_report` by construction
    (both read one ``_report_payload``), satisfying U14's matching-identity
    requirement.
    """
    p = _report_payload(result, confirmation_mode)
    lines: list[str] = []
    lines.append("# CORE — Isolated Consequence-Chain Demo Report")
    lines.append("")
    lines.append(f"> {_PROOF_STATEMENT}")
    lines.append("")
    lines.append(f"- **Verdict:** {p['verdict']}")
    lines.append(f"- **Run ID:** `{p['run_id']}`")
    lines.append(f"- **Assessed commit:** `{p['assessed_commit']}`")
    lines.append(f"- **Operator confirmation:** {p['operator_confirmation']}")
    lines.append("")

    finding = p["finding"]
    lines.append("## Finding")
    if finding:
        lines.append(f"- **ID:** `{finding['finding_id']}`")
        lines.append(f"- **Rule:** `{finding['rule']}`")
        lines.append(f"- **Path:** `{finding['path']}`")
        lines.append(f"- **Original status:** {finding['original_status']}")
    else:
        lines.append("- _no finding produced_")
    lines.append("")

    proposal = p["proposal"]
    lines.append("## Proposal")
    if proposal:
        lines.append(f"- **ID:** `{proposal['proposal_id']}`")
        lines.append(f"- **Actions:** {proposal['actions']}")
        lines.append(f"- **Scope files:** {proposal['scope_files']}")
        lines.append(f"- **Risk:** {proposal['risk']}")
        lines.append(f"- **Approval authority (policy):** `{proposal['approval_authority']}`")
        lines.append(f"- **Approver identity:** `{proposal['approver_identity']}`")
        lines.append(f"- **Linked finding IDs:** {proposal['finding_ids']}")
    else:
        lines.append("- _no proposal produced_")
    lines.append("")

    execution = p["execution"]
    lines.append("## Execution & consequence")
    if execution:
        lines.append(f"- **Execution claimer:** {execution['claimer']}")
        lines.append(f"- **Terminal status:** {execution['terminal_status']}")
        lines.append(f"- **Pre-execution SHA:** `{execution['pre_execution_sha']}`")
        lines.append(f"- **Post-execution SHA:** `{execution['post_execution_sha']}`")
        lines.append(f"- **Files changed:** {execution['files_changed']}")
        lines.append(f"- **Findings resolved:** {execution['findings_resolved']}")
    else:
        lines.append("- _execution did not complete_")
    lines.append("")

    reaudit = p["reaudit"]
    lines.append("## Re-audit")
    if reaudit:
        lines.append(f"- **Clean:** {reaudit['clean']}")
        lines.append(f"- **Match count:** {reaudit['match_count']}")
    lines.append("")

    lines.append("## Cleanup")
    if p["cleanup"]["workspace_removed"]:
        lines.append("- Workspace removed.")
    else:
        lines.append(f"- Workspace retained at `{p['cleanup']['retained_path']}`.")
    lines.append("")

    lines.append("## Fail-closed assertions")
    lines.append("")
    lines.append("| Assertion | Passed | Detail |")
    lines.append("| --- | --- | --- |")
    for a in p["assertions"]:
        detail = a["detail"].replace("|", "\\|")
        lines.append(f"| {a['name']} | {'✅' if a['passed'] else '❌'} | {detail} |")
    lines.append("")

    if p["error"]:
        lines.append(f"**Error:** {p['error']}")
        lines.append("")

    return "\n".join(lines)
