# tests/body/atomic/test_assisted_actions.py
"""Guard tests for the assisted.validate_diff safety gate (ADR-109 #654, ADR-141).

The action is @atomic_action-governed, so a direct call raises
GovernanceBypassError by design; full behavioral validation (apply the diff in a
hermetic worktree, run audit + ruff + mapped tests, gate approval) is an
integration concern exercised through ActionExecutor. These unit tests cover the
guards via the underlying function (``.__wrapped__``): the gate must REFUSE
(ok=False) on missing inputs — never silently pass, since a missing patch or rule
reading as success would defeat the gate.

ADR-141 D2 adds ``_EngineTouchResult`` — a named tuple partitioning engine-touching
files into ``serviceable`` (subprocess audit) and ``must_refuse`` (graph-dependent,
always refuse). The ``_touches_audit_engine`` tests are updated accordingly.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from body.atomic.assisted_actions import (
    _EngineTouchResult,
    _rule_cleared,
    _touches_audit_engine,
    action_assisted_apply_diff,
    action_assisted_validate_diff,
)


async def test_refuses_without_patch() -> None:
    fn = action_assisted_validate_diff.__wrapped__
    result = await fn(
        patch=None, finding_rule="purity.no_orphan_files", core_context=MagicMock()
    )
    assert result.ok is False
    assert "patch" in result.data["error"]


async def test_refuses_without_finding_rule() -> None:
    fn = action_assisted_validate_diff.__wrapped__
    result = await fn(
        patch="--- a/x\n+++ b/x\n", finding_rule=None, core_context=MagicMock()
    )
    assert result.ok is False
    assert "finding_rule" in result.data["error"]


async def test_refuses_without_git_service() -> None:
    fn = action_assisted_validate_diff.__wrapped__
    ctx = MagicMock()
    ctx.git_service = None
    result = await fn(
        patch="--- a/x\n+++ b/x\n",
        finding_rule="purity.no_orphan_files",
        core_context=ctx,
    )
    assert result.ok is False
    assert "git_service" in result.data["error"]


def test_rule_cleared_true_when_subject_not_flagged() -> None:
    # Fix lives in the detector (touched), subject file is unchanged; the
    # full-scope audit no longer flags the subject → cleared.
    findings = [{"file_path": "src/other/unrelated.py"}]
    assert (
        _rule_cleared(
            findings,
            subject_files=["src/mind/coherence/llm_judge.py"],
            touched_py=["src/mind/logic/engines/knowledge_gate.py"],
        )
        is True
    )


def test_rule_cleared_false_when_subject_still_flagged() -> None:
    # The subject is still among the flagged paths → the gate must NOT clear,
    # even though the touched file is clean. This is the case a touched-files-
    # only check would have passed vacuously.
    findings = [{"file_path": "src/mind/coherence/llm_judge.py"}]
    assert (
        _rule_cleared(
            findings,
            subject_files=["src/mind/coherence/llm_judge.py"],
            touched_py=["src/mind/logic/engines/knowledge_gate.py"],
        )
        is False
    )


def test_rule_cleared_false_when_touched_file_flagged() -> None:
    findings = [{"file_path": "src/cli/resources/lane/next.py"}]
    assert (
        _rule_cleared(
            findings,
            subject_files=None,
            touched_py=["src/cli/resources/lane/next.py"],
        )
        is False
    )


def test_rule_cleared_normalizes_dot_slash_prefix() -> None:
    # Finding paths and git-diff paths can differ by a leading "./"; the
    # guarded/flagged comparison must still match.
    findings = [{"file_path": "./src/mind/coherence/llm_judge.py"}]
    assert (
        _rule_cleared(
            findings,
            subject_files=["src/mind/coherence/llm_judge.py"],
            touched_py=[],
        )
        is False
    )


def test_rule_cleared_true_when_nothing_guarded() -> None:
    assert (
        _rule_cleared([{"file_path": "x.py"}], subject_files=[], touched_py=[]) is True
    )


# --- _touches_audit_engine tests (ADR-141 D2: named-tuple return) ---

_ENGINES = frozenset(
    {
        "src/mind/logic/engines/knowledge_gate.py",
        "src/mind/logic/engines/ast_gate.py",
    }
)
_GRAPH_ENGINES = frozenset({"src/mind/logic/engines/knowledge_gate.py"})


def test_touches_audit_engine_returns_named_tuple() -> None:
    result = _touches_audit_engine([], _ENGINES, _GRAPH_ENGINES)
    assert isinstance(result, _EngineTouchResult)
    assert isinstance(result.serviceable, list)
    assert isinstance(result.must_refuse, list)


def test_touches_audit_engine_graph_dependent_goes_to_must_refuse() -> None:
    # knowledge_gate is graph-dependent → must_refuse, not serviceable.
    result = _touches_audit_engine(
        ["src/mind/logic/engines/knowledge_gate.py"], _ENGINES, _GRAPH_ENGINES
    )
    assert result.must_refuse == ["src/mind/logic/engines/knowledge_gate.py"]
    assert result.serviceable == []


def test_touches_audit_engine_graph_independent_goes_to_serviceable() -> None:
    # ast_gate is graph-independent → serviceable, not must_refuse.
    result = _touches_audit_engine(
        ["src/mind/logic/engines/ast_gate.py"], _ENGINES, _GRAPH_ENGINES
    )
    assert result.serviceable == ["src/mind/logic/engines/ast_gate.py"]
    assert result.must_refuse == []


def test_touches_audit_engine_clears_non_engine_fix() -> None:
    # A fix to a non-engine file: both lists are empty.
    result = _touches_audit_engine(
        ["src/cli/resources/lane/next.py"], _ENGINES, _GRAPH_ENGINES
    )
    assert result.serviceable == []
    assert result.must_refuse == []


def test_touches_audit_engine_normalizes_dot_slash() -> None:
    # Leading "./" in the touched path must match the normalized engine set.
    result = _touches_audit_engine(
        ["./src/mind/logic/engines/ast_gate.py"], _ENGINES, _GRAPH_ENGINES
    )
    assert result.serviceable == ["./src/mind/logic/engines/ast_gate.py"]
    assert result.must_refuse == []


def test_touches_audit_engine_mixed_touch_partitions_correctly() -> None:
    # Diff touching both a graph-dependent and a graph-independent engine
    # splits correctly across the two lists.
    result = _touches_audit_engine(
        [
            "src/mind/logic/engines/knowledge_gate.py",
            "src/mind/logic/engines/ast_gate.py",
        ],
        _ENGINES,
        _GRAPH_ENGINES,
    )
    assert result.must_refuse == ["src/mind/logic/engines/knowledge_gate.py"]
    assert result.serviceable == ["src/mind/logic/engines/ast_gate.py"]


# --- action_assisted_apply_diff guards ---


async def test_apply_diff_refuses_without_patch() -> None:
    fn = action_assisted_apply_diff.__wrapped__
    result = await fn(patch=None, core_context=MagicMock())
    assert result.ok is False
    assert "patch" in result.data["error"]


async def test_apply_diff_refuses_without_git_service() -> None:
    fn = action_assisted_apply_diff.__wrapped__
    ctx = MagicMock()
    ctx.git_service = None
    result = await fn(patch="--- a/x\n+++ b/x\n", core_context=ctx)
    assert result.ok is False
    assert "git_service" in result.data["error"]
