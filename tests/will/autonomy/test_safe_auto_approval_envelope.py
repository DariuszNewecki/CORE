"""will.autonomy.safe_auto_approval_envelope.validate_envelope (#853).

Pure, DB-free unit coverage of the safe-auto-approval action-and-path
envelope: an independently governed boundary beyond ProposalScope,
enforced centrally in ProposalStateManager.approve() (see
tests/will/autonomy/test_proposal_state_manager_approve.py for the
real-dispatch proof through approve() itself, and
tests/will/workers/test_violation_remediator_approval_path.py /
tests/will/workers/test_test_remediator_safe_auto_approval_envelope.py
for end-to-end proof through both autonomous proposal creators).

This file is also the G2 fixture-pair source for the blocking rule
autonomy.proposals.safe_auto_approval_envelope
(.specs/verification/g2_blocking_rule_registry.yaml).
"""

from __future__ import annotations

import pytest

from will.autonomy.safe_auto_approval_envelope import (
    SafeAutoApprovalDeniedError,
    validate_envelope,
)


_AUTHORIZED_ACTIONS = [
    "fix.imports",
    "fix.ids",
    "fix.logging",
    "fix.headers",
    "fix.format",
]


def _action(
    action_id: str | None, file_path: str | None, *, flow_id: str | None = None
) -> dict:
    params: dict = {}
    if file_path is not None:
        params["file_path"] = file_path
    return {
        "action_id": action_id,
        "flow_id": flow_id,
        "parameters": params,
        "order": 0,
    }


def _scope(*files: str) -> dict:
    return {"files": list(files), "modules": [], "symbols": [], "policies": []}


# --- Governor ruling 2/3: each of the five actions, src/ and tests/, direct
# and nested children --------------------------------------------------------


@pytest.mark.parametrize("action_id", _AUTHORIZED_ACTIONS)
@pytest.mark.parametrize(
    "file_path",
    [
        "src/foo.py",
        "src/pkg/foo.py",
        "src/pkg/sub/deep/foo.py",
        "tests/foo.py",
        "tests/pkg/foo.py",
        "tests/pkg/sub/deep/foo.py",
    ],
)
def test_authorized_action_within_src_approves(action_id: str, file_path: str) -> None:
    """Each of the five envelope actions auto-approves for direct-child and
    nested Python paths under both src/ and tests/."""
    validate_envelope(
        [_action(action_id, file_path)], _scope(file_path)
    )  # must not raise


# --- Governor ruling 5: unlisted action ------------------------------------


def test_action_outside_envelope_denies() -> None:
    """An action not in the five-item envelope must never auto-approve --
    canonical violating fixture for autonomy.proposals.safe_auto_approval_envelope."""
    with pytest.raises(
        SafeAutoApprovalDeniedError, match="not in the safe auto-approval envelope"
    ):
        validate_envelope(
            [_action("check.imports", "src/foo.py")], _scope("src/foo.py")
        )


def test_moderate_action_outside_envelope_denies() -> None:
    with pytest.raises(
        SafeAutoApprovalDeniedError, match="not in the safe auto-approval envelope"
    ):
        validate_envelope(
            [_action("fix.docstrings", "src/foo.py")], _scope("src/foo.py")
        )


# --- Governor ruling 4: no flow, including test-generation flows -----------


def test_flow_denies() -> None:
    with pytest.raises(
        SafeAutoApprovalDeniedError, match="not authorized for safe auto-approval"
    ):
        validate_envelope(
            [_action(None, None, flow_id="flow.build_test_for_symbol")],
            _scope(),
        )


def test_test_generation_flow_denies_even_with_valid_looking_scope() -> None:
    """A flow with a scope that otherwise looks plausible still denies --
    flows are categorically excluded, not evaluated on path shape."""
    action = {
        "action_id": None,
        "flow_id": "flow.build_test_for_symbol",
        "parameters": {"source_file": "src/foo.py", "test_file": "tests/test_foo.py"},
        "order": 0,
    }
    with pytest.raises(
        SafeAutoApprovalDeniedError, match="not authorized for safe auto-approval"
    ):
        validate_envelope([action], _scope("src/foo.py", "tests/test_foo.py"))


# --- Governor ruling 3/5: non-Python files, .intent/, infra/ ---------------


@pytest.mark.parametrize(
    "file_path",
    [
        "src/foo.txt",
        "src/foo.md",
        "src/foo",
        "tests/data/fixture.json",
        ".intent/rules/code/imports.json",
        ".intent/enforcement/config/action_risk.yaml",
        "infra/deploy.yaml",
        "infra/terraform/main.tf",
        "docs/README.md",
        "pyproject.toml",
    ],
)
def test_out_of_envelope_path_denies(file_path: str) -> None:
    with pytest.raises(SafeAutoApprovalDeniedError):
        validate_envelope([_action("fix.format", file_path)], _scope(file_path))


# --- Governor ruling 5: traversal, absolute paths, missing paths -----------


@pytest.mark.parametrize(
    "file_path",
    [
        "src/../etc/passwd",
        "src/pkg/../../etc/passwd",
        "../src/foo.py",
        "src/./foo.py",
        "src//foo.py",
    ],
)
def test_traversal_path_denies(file_path: str) -> None:
    with pytest.raises(SafeAutoApprovalDeniedError):
        validate_envelope([_action("fix.format", file_path)], _scope(file_path))


@pytest.mark.parametrize(
    "file_path",
    [
        "/etc/passwd",
        "/src/foo.py",
        "~/src/foo.py",
        "C:/Windows/System32/foo.py",
        "C:\\Windows\\System32\\foo.py",
        "src\\pkg\\foo.py",
    ],
)
def test_absolute_or_malformed_path_denies(file_path: str) -> None:
    with pytest.raises(SafeAutoApprovalDeniedError):
        validate_envelope([_action("fix.format", file_path)], _scope(file_path))


def test_missing_target_path_denies() -> None:
    with pytest.raises(
        SafeAutoApprovalDeniedError, match="declares no target file_path"
    ):
        validate_envelope([_action("fix.format", None)], _scope())


def test_empty_string_target_path_denies() -> None:
    with pytest.raises(
        SafeAutoApprovalDeniedError, match="declares no target file_path"
    ):
        validate_envelope([_action("fix.format", "")], _scope(""))


def test_no_actions_at_all_denies() -> None:
    with pytest.raises(SafeAutoApprovalDeniedError, match="declares no actions"):
        validate_envelope([], _scope())


# --- Mixed-scope / action-scope inconsistency -------------------------------


def test_action_target_not_declared_in_scope_denies() -> None:
    """An action's real target must appear in scope.files -- a proposal
    cannot act on a file it didn't declare."""
    with pytest.raises(SafeAutoApprovalDeniedError, match="inconsistent"):
        validate_envelope([_action("fix.format", "src/foo.py")], _scope("src/other.py"))


def test_scope_declares_extra_undeclared_file_denies() -> None:
    """scope.files naming a file no action actually targets is also an
    inconsistency -- the declared blast radius must match reality exactly,
    not merely be a superset."""
    with pytest.raises(SafeAutoApprovalDeniedError, match="inconsistent"):
        validate_envelope(
            [_action("fix.format", "src/foo.py")],
            _scope("src/foo.py", "src/bar.py"),
        )


def test_multi_action_multi_file_consistent_scope_approves() -> None:
    """Multiple actions across multiple files, all in-envelope and exactly
    matching scope.files, approve together -- the ADR-035 per-finding
    proposal shape violation_remediator_proposal.create_proposal builds."""
    actions = [
        _action("fix.imports", "src/a.py"),
        _action("fix.imports", "src/pkg/b.py"),
        _action("fix.imports", "tests/c.py"),
    ]
    validate_envelope(actions, _scope("src/a.py", "src/pkg/b.py", "tests/c.py"))


def test_one_out_of_envelope_action_denies_whole_proposal() -> None:
    """A mixed proposal with one in-envelope and one out-of-envelope action
    denies entirely -- partial authorization is not a thing."""
    actions = [
        _action("fix.format", "src/a.py"),
        _action("fix.docstrings", "src/b.py"),
    ]
    with pytest.raises(
        SafeAutoApprovalDeniedError, match="not in the safe auto-approval envelope"
    ):
        validate_envelope(actions, _scope("src/a.py", "src/b.py"))


# --- Envelope-load failure fails closed -------------------------------------


def test_envelope_load_failure_denies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Governor rulings 1/5: an envelope that fails to load must deny, never
    silently authorize."""
    import will.autonomy.safe_auto_approval_envelope as mod

    monkeypatch.setattr(
        mod,
        "load_safe_auto_approval_envelope",
        lambda: {"_error": True, "reason": "boom"},
    )
    with pytest.raises(SafeAutoApprovalDeniedError, match="could not be loaded"):
        validate_envelope([_action("fix.format", "src/foo.py")], _scope("src/foo.py"))


# --- Governor rulings D and F (2026-09-15, ADR-159 Trial 0): deny_all and the
# rule identifier on every denial ------------------------------------------------


from unittest.mock import patch

from will.autonomy.safe_auto_approval_envelope import ENVELOPE_RULE_ID


_DENY_ALL = {
    "authorization_mode": "deny_all",
    "authorized_actions": frozenset(),
    "authorized_path_prefixes": (),
    "authorized_extensions": (),
}


def test_deny_all_denies_an_otherwise_authorized_action_naming_mode_and_rule() -> None:
    """Probe I-6's refusal: under deny_all even fix.format on src/ is refused,
    and the refusal names the mode and the governing rule -- the rule's own
    id, not a harness-invented one."""
    with patch(
        "will.autonomy.safe_auto_approval_envelope.load_safe_auto_approval_envelope",
        return_value=_DENY_ALL,
    ):
        with pytest.raises(SafeAutoApprovalDeniedError) as excinfo:
            validate_envelope(
                [_action("fix.format", "src/foo.py")], _scope("src/foo.py")
            )
    denial = excinfo.value
    assert "authorization_mode: deny_all" in str(denial)
    assert denial.authorization_mode == "deny_all"
    assert (
        denial.rule_id
        == ENVELOPE_RULE_ID
        == "autonomy.proposals.safe_auto_approval_envelope"
    )


def test_every_denial_carries_the_rule_id() -> None:
    with pytest.raises(SafeAutoApprovalDeniedError) as excinfo:
        validate_envelope(
            [_action("check.imports", "src/foo.py")], _scope("src/foo.py")
        )
    assert excinfo.value.rule_id == ENVELOPE_RULE_ID
    assert excinfo.value.authorization_mode == "allow_listed"


def test_rule_id_names_a_rule_that_exists_in_intent() -> None:
    """The identifier must be a real rule document's id at this commit."""
    import json
    from pathlib import Path

    doc = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / ".intent/rules/will/safe_auto_approval_envelope.json"
        ).read_text()
    )
    assert ENVELOPE_RULE_ID in {r["id"] for r in doc["rules"]}
