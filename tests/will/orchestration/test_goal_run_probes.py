# tests/will/orchestration/test_goal_run_probes.py

"""ADR-159 apparatus-integrity probes I-5 / I-6 (#895 U3).

Mechanism-level fixtures for the refusals live elsewhere
(test_file_handler__repository_containment.py for I-5's FileHandler boundary,
test_safe_auto_approval_envelope.py for I-6's envelope). These tests pin what
the probes DO with those mechanisms: the exact attempt shape, the pass
criterion (refusal names the expected rule and nothing was mutated), the
record shape, and the fail-closed recording path.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.orchestration import goal_run_probes as probes


def _binding(tmp_path):
    from shared.models.target_binding import TargetBinding

    subject = tmp_path / "subject"
    subject.mkdir()
    return TargetBinding(
        subject_path=str(subject),
        subject_sha="a" * 40,
        subject_tree_hash="b" * 40,
        bound_repo_path=str(tmp_path / "copy"),
        bound_sha="c" * 40,
        bound_tree_hash="d" * 40,
        floor_hash="e" * 64,
        overlay_hash="f" * 64,
        displaced=(),
    )


class _Executor:
    """Stands in for ActionExecutor: records the call, returns a scripted result."""

    calls: ClassVar[list[dict[str, Any]]] = []
    result: ClassVar[Any] = None

    def __init__(self, context: Any) -> None:
        pass

    async def execute(self, action_id: str, **kwargs: Any) -> Any:
        _Executor.calls.append({"action_id": action_id, **kwargs})
        return _Executor.result


def _refused_result() -> Any:
    return SimpleNamespace(
        ok=False,
        data={
            "error": "Attempted to escape repository boundary: /subject/x",
            "error_type": "RepositoryBoundaryViolationError",
            "rule_id": probes.CONTAINMENT_RULE_ID,
            "refusal": {"rule_id": probes.CONTAINMENT_RULE_ID, "attempted_path": "x"},
        },
    )


@pytest.fixture(autouse=True)
def _rule_loaded_in_bound_law(monkeypatch: pytest.MonkeyPatch):
    """Default: the bound law declares both probe rules (the Trial 0 overlay
    delivers both documents). Individual tests override to prove the gate."""

    def _loaded(rule_id: str) -> dict:
        return {
            "loaded": True,
            "rule_id": rule_id,
            "document": "rules/x.json",
            "content_hash": "h",
        }

    monkeypatch.setattr(probes, "rule_in_bound_law", _loaded)


# ------------------------------------------------------------------ I-5


async def test_i5_attempts_write_true_at_absolute_original_subject_path(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = SimpleNamespace(target_binding=_binding(tmp_path))
    _Executor.calls, _Executor.result = [], _refused_result()
    monkeypatch.setattr("body.atomic.executor.ActionExecutor", _Executor)

    record = await probes.run_probe_i5(ctx, "run-1")

    call = _Executor.calls[0]
    assert call["action_id"] == "file.create" and call["write"] is True
    assert call["file_path"] == str(
        (tmp_path / "subject").resolve() / "_core_probe_I-5.py"
    )
    assert record["probe"] == "I-5" and record["run_id"] == "run-1"
    assert record["passed"] is True
    assert record["result"]["rule_id"] == probes.CONTAINMENT_RULE_ID
    assert record["artefact_exists_after"] is False
    assert record["expected_rule_id"] == probes.CONTAINMENT_RULE_ID


async def test_i5_fails_when_refusal_does_not_name_the_rule(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = SimpleNamespace(target_binding=_binding(tmp_path))
    _Executor.calls = []
    _Executor.result = SimpleNamespace(
        ok=False, data={"error": "boom", "error_type": "ValueError"}
    )
    monkeypatch.setattr("body.atomic.executor.ActionExecutor", _Executor)

    record = await probes.run_probe_i5(ctx, "run-1")
    assert record["passed"] is False
    assert record["reason"] == "refusal_did_not_name_rule"


async def test_i5_fails_when_the_write_landed(tmp_path, monkeypatch) -> None:
    ctx = SimpleNamespace(target_binding=_binding(tmp_path))
    _Executor.calls = []
    _Executor.result = SimpleNamespace(ok=True, data={"written": True})

    class _Landing(_Executor):
        async def execute(self, action_id: str, **kwargs: Any) -> Any:
            from pathlib import Path

            Path(kwargs["file_path"]).write_text("x = 1\n")
            return _Executor.result

    monkeypatch.setattr("body.atomic.executor.ActionExecutor", _Landing)

    record = await probes.run_probe_i5(ctx, "run-1")
    assert record["passed"] is False
    assert record["reason"] == "write_landed"
    assert record["artefact_exists_after"] is True


async def test_i5_without_binding_is_a_failed_probe_not_a_crash() -> None:
    record = await probes.run_probe_i5(SimpleNamespace(), "run-1")
    assert record["passed"] is False and record["reason"] == "no_target_binding"


# ------------------------------------------------------------------ I-6


class _SessionCM:
    def __init__(self, session: Any) -> None:
        self._s = session

    async def __aenter__(self) -> Any:
        return self._s

    async def __aexit__(self, *exc: object) -> None:
        return None


def _i6_patches(
    monkeypatch: pytest.MonkeyPatch, *, deny: bool, status: str = "pending"
):
    from will.autonomy.safe_auto_approval_envelope import SafeAutoApprovalDeniedError

    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    monkeypatch.setattr(
        "body.services.service_registry.service_registry.session",
        lambda: _SessionCM(session),
    )
    repo = MagicMock()
    repo.create = AsyncMock(return_value="prop-1")
    repo.get = AsyncMock(
        return_value=SimpleNamespace(status=SimpleNamespace(value=status))
    )
    monkeypatch.setattr(
        "will.autonomy.proposal_repository.ProposalRepository", lambda s: repo
    )
    manager = MagicMock()
    if deny:
        manager.approve = AsyncMock(
            side_effect=SafeAutoApprovalDeniedError(
                "denied by envelope", authorization_mode="deny_all"
            )
        )
    else:
        manager.approve = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "will.autonomy.proposal_state_manager.ProposalStateManager", lambda s: manager
    )
    return repo, manager, session


async def test_i6_denial_under_safe_auto_approval_passes_and_leaves_row_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, manager, _session = _i6_patches(monkeypatch, deny=True)

    record = await probes.run_probe_i6(SimpleNamespace(), "run-1")

    created = repo.create.call_args.args[0]
    assert created.created_by == "probe.I-6"
    assert [a.action_id for a in created.actions] == ["file.create"]
    assert created.scope.files == ["src/_core_probe_I-6.py"]
    assert manager.approve.call_args.kwargs["approval_authority"] == (
        probes.SAFE_AUTO_APPROVAL
    )
    assert record["passed"] is True
    assert record["proposal_id"] == "prop-1"
    assert record["result"]["denial"]["rule_id"] == probes.ENVELOPE_RULE_ID
    assert record["result"]["denial"]["authorization_mode"] == "deny_all"
    assert record["result"]["proposal_status_after"] == "pending"
    # the row is left as the denial left it: no reject, no second update
    assert not manager.reject.called


async def test_i6_fails_when_approval_is_granted(monkeypatch) -> None:
    _i6_patches(monkeypatch, deny=False)
    record = await probes.run_probe_i6(SimpleNamespace(), "run-1")
    assert record["passed"] is False and record["reason"] == "approval_granted"


# ------------------------------------------------------------------ recording


async def test_run_and_record_probes_posts_records_and_fails_closed() -> None:
    worker = MagicMock()
    worker._context = SimpleNamespace()
    worker.goal, worker.workflow_type = "g", "evaluation"
    worker.post_report = AsyncMock()
    worker.post_observation = AsyncMock()
    records = [
        {"probe": "I-5", "passed": True},
        {"probe": "I-6", "passed": False, "reason": "approval_granted"},
    ]
    with patch.object(probes, "run_apparatus_probes", AsyncMock(return_value=records)):
        passed = await probes.run_and_record_probes(worker, "run-9")

    assert passed is False
    subjects = [c.args[0] for c in worker.post_report.call_args_list]
    assert subjects == ["goal_run.run-9.probe.I-5", "goal_run.run-9.probe.I-6"]
    subject, payload = worker.post_observation.call_args.args
    assert subject == "goal_run.run-9.outcome"
    assert payload["reason"] == "apparatus_integrity_failed"
    assert payload["failed_probes"] == ["I-6"]
    assert payload["outcome"] == "APPARATUS_INTEGRITY_FAILED"
    assert worker.probe_records == records
    assert worker.result.ok is False


async def test_run_apparatus_probes_records_a_crashing_probe() -> None:
    with (
        patch.object(probes, "run_probe_i5", AsyncMock(side_effect=RuntimeError("x"))),
        patch.object(
            probes,
            "run_probe_i6",
            AsyncMock(return_value={"probe": "I-6", "passed": True}),
        ),
    ):
        records = await probes.run_apparatus_probes(SimpleNamespace(), "r")
    assert records[0]["probe"] == "I-5" and records[0]["passed"] is False
    assert (
        records[0]["reason"] == "probe_crashed"
        and "RuntimeError" in records[0]["detail"]
    )
    assert records[1]["passed"] is True


# ---------------------------------------- the named rule must be LOADED law (M1)


async def test_i5_fails_when_the_named_rule_is_not_in_the_bound_law(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Document A I-5/I-6: "names a rule that exists at the pinned commit". A
    refusal naming a constant that exists only in CORE's source is not enough;
    the bound process must have loaded the rule's document."""
    monkeypatch.setattr(
        probes,
        "rule_in_bound_law",
        lambda rule_id: {
            "loaded": False,
            "rule_id": rule_id,
            "reason": "Rule ID not found",
        },
    )
    context = SimpleNamespace(target_binding=_binding(tmp_path))
    _Executor.result = _refused_result()
    monkeypatch.setattr("body.atomic.executor.ActionExecutor", _Executor)
    record = await probes.run_probe_i5(context, "run-1")
    assert record["passed"] is False, (
        "the refusal named the rule, but it is not loaded law"
    )
    assert record["reason"] == "named_rule_not_in_bound_law"
    assert record["rule_in_bound_law"]["loaded"] is False


async def test_i6_fails_when_the_named_rule_is_not_in_the_bound_law(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        probes,
        "rule_in_bound_law",
        lambda rule_id: {
            "loaded": False,
            "rule_id": rule_id,
            "reason": "Rule ID not found",
        },
    )
    _i6_patches(monkeypatch, deny=True)
    record = await probes.run_probe_i6(SimpleNamespace(target_binding=None), "run-1")
    assert record["passed"] is False
    assert record["reason"] == "named_rule_not_in_bound_law"


def test_rule_in_bound_law_reads_the_bound_intent_repository(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from shared.infrastructure.intent import intent_repository as ir

    monkeypatch.undo()  # drop the autouse stub; this test exercises the real helper
    ref = SimpleNamespace(
        source_path=tmp_path / ".intent" / "rules" / "will" / "x.json",
        rule_content_hash="abc",
    )
    repo = MagicMock()
    repo.root = tmp_path / ".intent"
    repo.get_rule = lambda rid: ref
    monkeypatch.setattr(ir, "get_intent_repository", lambda: repo)
    got = probes.rule_in_bound_law("some.rule")
    assert got == {
        "loaded": True,
        "rule_id": "some.rule",
        "document": "rules/will/x.json",
        "content_hash": "abc",
    }

    def _missing(rid):
        raise ir.GovernanceError(f"Rule ID not found: {rid}")

    repo.get_rule = _missing
    assert probes.rule_in_bound_law("nope")["loaded"] is False
