# tests/cli/logic/demo/test_consequence_chain_assertions.py
"""Unit tests for the ADR-155 D10 fail-closed assertion model
(``cli.logic.demo.consequence_chain._evaluate_assertions``).

Covers spec §6.3's negative-claim contract: explicit proof that the demo
cannot pass when the expected rule doesn't fire, the finding/proposal
aren't linked, the approval authority is missing, execution doesn't reach
completed, the consequence lacks durable evidence, an unexpected file
changes, re-audit still finds the violation, or `.intent/` changes. Each
test starts from a fully-passing "golden" baseline and mutates exactly one
fact, proving the assertion model is precise — it fails the specific
claim under test, not everything indiscriminately.

``FindingIdentity``/``ProposalIdentity``/``ChainEvidence`` are frozen
dataclasses (by design — they're facts read from real responses, never
mutated in production code); tests use ``dataclasses.replace`` to build
mutated copies rather than in-place attribute assignment.

Real end-to-end coverage of the full chain (E01) lives in
test_consequence_chain_e2e.py, against real disposable infrastructure —
these tests are the fast, infra-free complement that exhaustively covers
the *assertion logic* itself.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from cli.logic.demo.consequence_chain import _evaluate_assertions
from cli.logic.demo.models import (
    ChainEvidence,
    ChainScenarioResult,
    FindingIdentity,
    ProposalIdentity,
)


_SEED_REL_PATH = "src/body/analyzers/demo_onramp_abc12345.py"
_FINDING_ID = "finding-1"
_PROPOSAL_ID = "proposal-1"


def _golden_finding() -> FindingIdentity:
    return FindingIdentity(
        entry_id=_FINDING_ID,
        subject=f"python::linkage.assign_ids::{_SEED_REL_PATH}",
        rule_id="linkage.assign_ids",
        file_path=_SEED_REL_PATH,
        status="open",
    )


def _golden_proposal() -> ProposalIdentity:
    return ProposalIdentity(
        proposal_id=_PROPOSAL_ID,
        goal="Autonomous remediation: fix.ids",
        status="approved",
        overall_risk="safe",
        approval_required=False,
        approval_authority="risk_classification.safe_auto_approval",
        approved_by="autonomous_self_promote",
        finding_ids=[_FINDING_ID],
        action_ids=["fix.ids"],
        scope_files=[_SEED_REL_PATH],
    )


def _golden_chain() -> ChainEvidence:
    return ChainEvidence(
        proposal=_golden_proposal(),
        lifecycle_status="completed",
        execution_claimer=None,
        pre_execution_sha="a" * 40,
        post_execution_sha="b" * 40,
        files_changed=[_SEED_REL_PATH],
        findings_resolved=[_FINDING_ID],
    )


def _golden_result() -> ChainScenarioResult:
    return ChainScenarioResult(
        run_id="run-1",
        seed_rel_path=_SEED_REL_PATH,
        finding=_golden_finding(),
        finding_matches_count=1,
        proposal=_golden_proposal(),
        chain=_golden_chain(),
        reaudit_clean=True,
        reaudit_matches_count=0,
        finding_final_status="resolved",
        finding_final_proposal_id=_PROPOSAL_ID,
    )


def _golden_kwargs() -> dict[str, Any]:
    return {
        "infra_healthy": True,
        "seed_commit_files": [_SEED_REL_PATH],
        "seed_rel_path": _SEED_REL_PATH,
        "intent_hash_before": "same-hash",
        "intent_hash_after": "same-hash",
        "result": _golden_result(),
        "source_fingerprint_matches": True,
    }


def _assertion_map(kwargs: dict[str, Any]) -> dict[str, bool]:
    return {a.name: a.passed for a in _evaluate_assertions(**kwargs)}


def test_golden_baseline_passes_every_assertion() -> None:
    assertions = _assertion_map(_golden_kwargs())
    failed = [name for name, passed in assertions.items() if not passed]
    assert failed == [], f"golden baseline should pass everything; failed: {failed}"


def test_negative_claim_expected_rule_does_not_fire() -> None:
    kwargs = _golden_kwargs()
    result = kwargs["result"]
    result.finding = dataclasses.replace(
        result.finding, rule_id="some.other.rule", subject="python::some.other.rule::" + _SEED_REL_PATH
    )
    assertions = _assertion_map(kwargs)
    assert assertions["D10.3_exactly_expected_finding"] is False


def test_negative_claim_finding_not_persisted() -> None:
    kwargs = _golden_kwargs()
    result = kwargs["result"]
    result.finding = None
    result.finding_matches_count = 0
    assertions = _assertion_map(kwargs)
    assert assertions["D10.3_exactly_expected_finding"] is False


def test_negative_claim_finding_and_proposal_not_linked_both_directions() -> None:
    """Bidirectional-linkage break: D8's reverse direction (finding's own
    recorded ``proposal_id``) no longer matches the resolved proposal.

    The forward direction (proposal's ``constitutional_constraints.
    finding_ids`` containing the finding) is enforced upstream in
    ``scenario_runner._resolve_proposal`` — a mismatch there means no
    proposal is ever resolved at all, which
    ``test_negative_claim_finding_not_persisted``-shaped cases already
    cover via D10.4/D10.5/D10.6 all failing on a ``None`` proposal.
    """
    kwargs = _golden_kwargs()
    kwargs["result"].finding_final_proposal_id = "some-other-proposal-id"
    assertions = _assertion_map(kwargs)
    assert assertions["D10.12_finding_resolved_and_still_linked"] is False


def test_negative_claim_proposal_action_differs() -> None:
    kwargs = _golden_kwargs()
    result = kwargs["result"]
    result.proposal = dataclasses.replace(result.proposal, action_ids=["fix.docstrings"])
    assertions = _assertion_map(kwargs)
    assert assertions["D10.4_exactly_one_linked_proposal"] is False


def test_negative_claim_proposal_file_scope_differs() -> None:
    kwargs = _golden_kwargs()
    result = kwargs["result"]
    result.proposal = dataclasses.replace(
        result.proposal, scope_files=["src/body/analyzers/some_other_file.py"]
    )
    assertions = _assertion_map(kwargs)
    assert assertions["D10.4_exactly_one_linked_proposal"] is False


def test_negative_claim_approval_authority_missing() -> None:
    kwargs = _golden_kwargs()
    result = kwargs["result"]
    result.proposal = dataclasses.replace(result.proposal, approval_authority=None)
    assertions = _assertion_map(kwargs)
    assert assertions["D10.5_risk_and_approval_authority_match_governed_state"] is False


def test_negative_claim_execution_success_but_not_completed() -> None:
    kwargs = _golden_kwargs()
    result = kwargs["result"]
    result.chain = dataclasses.replace(result.chain, lifecycle_status="finalizing")
    assertions = _assertion_map(kwargs)
    assert assertions["D10.6_execution_reaches_completed"] is False


def test_negative_claim_completed_lacks_consequence_timestamp_or_row() -> None:
    kwargs = _golden_kwargs()
    result = kwargs["result"]
    result.chain = dataclasses.replace(
        result.chain, pre_execution_sha=None, post_execution_sha=None
    )
    assertions = _assertion_map(kwargs)
    assert assertions["D10.7_completed_has_durable_consequence"] is False
    assert assertions["D10.9_consequence_has_non_null_pre_post_sha"] is False


def test_negative_claim_pre_post_sha_missing() -> None:
    kwargs = _golden_kwargs()
    result = kwargs["result"]
    result.chain = dataclasses.replace(result.chain, post_execution_sha=None)
    assertions = _assertion_map(kwargs)
    assert assertions["D10.9_consequence_has_non_null_pre_post_sha"] is False
    assert assertions["D10.10_post_sha_differs_from_pre_sha"] is False


def test_negative_claim_pre_post_sha_equal() -> None:
    kwargs = _golden_kwargs()
    result = kwargs["result"]
    result.chain = dataclasses.replace(
        result.chain, post_execution_sha=result.chain.pre_execution_sha
    )
    assertions = _assertion_map(kwargs)
    assert assertions["D10.10_post_sha_differs_from_pre_sha"] is False


def test_negative_claim_unexpected_file_changes() -> None:
    kwargs = _golden_kwargs()
    result = kwargs["result"]
    result.chain = dataclasses.replace(
        result.chain, files_changed=[_SEED_REL_PATH, "src/some/unexpected_file.py"]
    )
    assertions = _assertion_map(kwargs)
    assert assertions["D10.11_files_changed_is_exactly_the_seed_file"] is False


def test_negative_claim_reaudit_still_finds_violation() -> None:
    kwargs = _golden_kwargs()
    kwargs["result"].reaudit_clean = False
    kwargs["result"].reaudit_matches_count = 1
    assertions = _assertion_map(kwargs)
    assert assertions["D10.13_reaudit_no_longer_reports_violation"] is False


def test_negative_claim_intent_changes() -> None:
    kwargs = _golden_kwargs()
    kwargs["intent_hash_after"] = "different-hash"
    assertions = _assertion_map(kwargs)
    assert assertions["D10.14_clone_intent_hash_unchanged"] is False


def test_negative_claim_invoking_repo_fingerprint_changes() -> None:
    kwargs = _golden_kwargs()
    kwargs["source_fingerprint_matches"] = False
    assertions = _assertion_map(kwargs)
    assert assertions["D10.15_invoking_repo_fingerprint_unchanged"] is False


def test_negative_claim_infra_unhealthy() -> None:
    kwargs = _golden_kwargs()
    kwargs["infra_healthy"] = False
    assertions = _assertion_map(kwargs)
    assert assertions["D10.1_infra_healthy"] is False


def test_negative_claim_seed_commit_touched_more_than_seed_file() -> None:
    kwargs = _golden_kwargs()
    kwargs["seed_commit_files"] = [_SEED_REL_PATH, "src/some/other_touched_file.py"]
    assertions = _assertion_map(kwargs)
    assert assertions["D10.2_seed_commit_contains_only_seed_file"] is False


def test_negative_claim_consequence_belongs_to_different_proposal() -> None:
    kwargs = _golden_kwargs()
    result = kwargs["result"]
    result.chain = dataclasses.replace(
        result.chain,
        proposal=dataclasses.replace(result.chain.proposal, proposal_id="a-different-proposal-id"),
    )
    assertions = _assertion_map(kwargs)
    assert assertions["D10.8_consequence_belongs_to_exact_proposal"] is False
