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

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
        patch=None, finding_rules=["purity.no_orphan_files"], core_context=MagicMock()
    )
    assert result.ok is False
    assert "patch" in result.data["error"]


async def test_refuses_without_finding_rules() -> None:
    fn = action_assisted_validate_diff.__wrapped__
    result = await fn(
        patch="--- a/x\n+++ b/x\n", finding_rules=None, core_context=MagicMock()
    )
    assert result.ok is False
    assert "finding_rules" in result.data["error"]


async def test_refuses_with_empty_finding_rules() -> None:
    """An empty list must refuse identically to None — never validate a
    diff against zero rules and call that a pass."""
    fn = action_assisted_validate_diff.__wrapped__
    result = await fn(
        patch="--- a/x\n+++ b/x\n", finding_rules=[], core_context=MagicMock()
    )
    assert result.ok is False
    assert "finding_rules" in result.data["error"]


async def test_refuses_without_git_service() -> None:
    fn = action_assisted_validate_diff.__wrapped__
    ctx = MagicMock()
    ctx.git_service = None
    result = await fn(
        patch="--- a/x\n+++ b/x\n",
        finding_rules=["purity.no_orphan_files"],
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


# --- action_assisted_apply_diff base-SHA / patch-digest fail-closed checks (ADR-154 D2) ---

_APPLY_PATCH = "--- a/x\n+++ b/x\n"
_APPLY_PATCH_DIGEST = hashlib.sha256(_APPLY_PATCH.encode("utf-8")).hexdigest()


async def test_apply_diff_refuses_without_validated_base_sha() -> None:
    fn = action_assisted_apply_diff.__wrapped__
    result = await fn(
        patch=_APPLY_PATCH, validated_base_sha=None, core_context=MagicMock()
    )
    assert result.ok is False
    assert "validated_base_sha" in result.data["error"]


async def test_apply_diff_refuses_without_patch_digest() -> None:
    fn = action_assisted_apply_diff.__wrapped__
    result = await fn(
        patch=_APPLY_PATCH,
        validated_base_sha="some-sha",
        patch_digest=None,
        core_context=MagicMock(),
    )
    assert result.ok is False
    assert "patch_digest" in result.data["error"]


async def test_apply_diff_refuses_on_intervening_commit() -> None:
    """A repository whose HEAD has moved since validation (an intervening
    commit) must refuse — never apply against a tree the candidate was not
    actually validated against."""
    fn = action_assisted_apply_diff.__wrapped__
    ctx = MagicMock()
    ctx.git_service.get_current_commit.return_value = "actual-head-sha"

    with patch("body.atomic.assisted_actions.ToolRunner.run_git") as run_git:
        result = await fn(
            patch=_APPLY_PATCH,
            validated_base_sha="validated-sha",
            patch_digest=_APPLY_PATCH_DIGEST,
            core_context=ctx,
        )

    assert result.ok is False
    assert result.data["applied"] is False
    assert result.data["validated_base_sha"] == "validated-sha"
    assert result.data["executing_sha"] == "actual-head-sha"
    assert "Base-SHA mismatch" in result.data["error"]
    # Must refuse before ever attempting to apply.
    run_git.assert_not_called()


async def test_apply_diff_refuses_on_patch_digest_mismatch() -> None:
    """Even with a matching base SHA, patch bytes that no longer hash to the
    approved digest must refuse — the approved evidence no longer matches
    what would actually be applied (ADR-154 D2)."""
    fn = action_assisted_apply_diff.__wrapped__
    ctx = MagicMock()
    ctx.git_service.get_current_commit.return_value = "same-sha"

    with patch("body.atomic.assisted_actions.ToolRunner.run_git") as run_git:
        result = await fn(
            patch=_APPLY_PATCH,
            validated_base_sha="same-sha",
            patch_digest="not-the-real-digest",
            core_context=ctx,
        )

    assert result.ok is False
    assert result.data["applied"] is False
    assert result.data["patch_digest"] == "not-the-real-digest"
    assert result.data["actual_digest"] == _APPLY_PATCH_DIGEST
    assert "Patch-digest mismatch" in result.data["error"]
    # Must refuse before ever attempting to apply.
    run_git.assert_not_called()


async def test_apply_diff_applies_when_base_sha_and_digest_both_match() -> None:
    fn = action_assisted_apply_diff.__wrapped__
    ctx = MagicMock()
    ctx.git_service.get_current_commit.return_value = "same-sha"
    ctx.git_service.repo_path = "/repo"

    with patch("body.atomic.assisted_actions.ToolRunner.run_git") as run_git:
        run_git.return_value = MagicMock(returncode=0, stderr="")
        result = await fn(
            patch=_APPLY_PATCH,
            validated_base_sha="same-sha",
            patch_digest=_APPLY_PATCH_DIGEST,
            core_context=ctx,
        )

    assert result.ok is True
    assert result.data["applied"] is True
    run_git.assert_called_once()


# --- action_assisted_validate_diff records validated_base_sha (ADR-154 D2) ---


async def test_validate_diff_records_validated_base_sha_for_passing_run() -> None:
    """The worktree's actual commit SHA — captured at worktree creation, not a
    later HEAD read — is recorded on a passing run so a subsequent apply can
    fail closed against it."""
    fn = action_assisted_validate_diff.__wrapped__

    worktree = MagicMock()
    worktree.repo_path = "/tmp/fake-worktree"
    worktree.get_current_commit.return_value = "worktree-sha-123"

    ctx = MagicMock()
    ctx.git_service.create_worktree.return_value = worktree

    def _run_git(_wt_path, *args, **kwargs):
        if args[:1] == ("apply",):
            return MagicMock(returncode=0, stderr="")
        if args[:2] == ("diff", "--name-only"):
            # A non-Python touched file keeps ruff/engine-touch/test routing
            # trivial (all short-circuit to True with no further subprocess
            # or DB-backed calls) so this stays a focused unit test.
            return MagicMock(stdout="README.md\n")
        raise AssertionError(f"unexpected git invocation: {args}")

    with patch("body.atomic.assisted_actions.ToolRunner.run_git", side_effect=_run_git):
        result = await fn(
            patch="--- a/README.md\n+++ b/README.md\n",
            finding_rules=["purity.no_orphan_files"],
            subject_files=None,
            core_context=ctx,
        )

    assert result.ok is True
    assert result.data["validated_base_sha"] == "worktree-sha-123"
    worktree.cleanup.assert_called_once()


# --- action_assisted_validate_diff base_sha parameter (ADR-154 D1) ---


async def test_validate_diff_creates_worktree_at_explicit_base_sha() -> None:
    """When base_sha is supplied, the validation worktree must be created at
    that exact commit — never an implicit floating HEAD. This is the
    invariant that keeps patch-generation base and validation base aligned:
    a caller (RemediationCeremony) that captured plan.baseline_sha earlier
    must validate against precisely that commit."""
    fn = action_assisted_validate_diff.__wrapped__

    worktree = MagicMock()
    worktree.repo_path = "/tmp/fake-worktree"
    worktree.get_current_commit.return_value = "pinned-sha-456"

    ctx = MagicMock()
    ctx.git_service.create_worktree.return_value = worktree

    def _run_git(_wt_path, *args, **kwargs):
        if args[:1] == ("apply",):
            return MagicMock(returncode=0, stderr="")
        if args[:2] == ("diff", "--name-only"):
            return MagicMock(stdout="README.md\n")
        raise AssertionError(f"unexpected git invocation: {args}")

    with patch("body.atomic.assisted_actions.ToolRunner.run_git", side_effect=_run_git):
        result = await fn(
            patch="--- a/README.md\n+++ b/README.md\n",
            finding_rules=["purity.no_orphan_files"],
            subject_files=None,
            base_sha="pinned-sha-456",
            core_context=ctx,
        )

    ctx.git_service.create_worktree.assert_called_once_with("pinned-sha-456")
    assert result.ok is True
    assert result.data["validated_base_sha"] == "pinned-sha-456"


async def test_validate_diff_defaults_worktree_to_head_without_base_sha() -> None:
    """Omitting base_sha (the external-agent Lane 1b path, which has no
    captured base commit) must preserve prior behavior exactly: worktree at
    HEAD."""
    fn = action_assisted_validate_diff.__wrapped__

    worktree = MagicMock()
    worktree.repo_path = "/tmp/fake-worktree"
    worktree.get_current_commit.return_value = "head-sha"

    ctx = MagicMock()
    ctx.git_service.create_worktree.return_value = worktree

    def _run_git(_wt_path, *args, **kwargs):
        if args[:1] == ("apply",):
            return MagicMock(returncode=0, stderr="")
        if args[:2] == ("diff", "--name-only"):
            return MagicMock(stdout="README.md\n")
        raise AssertionError(f"unexpected git invocation: {args}")

    with patch("body.atomic.assisted_actions.ToolRunner.run_git", side_effect=_run_git):
        await fn(
            patch="--- a/README.md\n+++ b/README.md\n",
            finding_rules=["purity.no_orphan_files"],
            subject_files=None,
            core_context=ctx,
        )

    ctx.git_service.create_worktree.assert_called_once_with("HEAD")


# --- action_assisted_validate_diff multi-rule evidence (ADR-154 D1) ---


def _mk_ctx_for_multi_rule(touched_names: str) -> tuple[MagicMock, MagicMock]:
    worktree = MagicMock()
    worktree.repo_path = "/tmp/fake-worktree"
    worktree.get_current_commit.return_value = "sha-multi"
    ctx = MagicMock()
    ctx.git_service.create_worktree.return_value = worktree
    return ctx, worktree


async def test_validate_diff_all_rules_clear_passes() -> None:
    """N rules, none of them still flags the subject → per-rule keys for
    every rule, verdict passes."""
    fn = action_assisted_validate_diff.__wrapped__
    ctx, _worktree = _mk_ctx_for_multi_rule("README.md\n")

    def _run_git(_wt_path, *args, **kwargs):
        if args[:1] == ("apply",):
            return MagicMock(returncode=0, stderr="")
        if args[:2] == ("diff", "--name-only"):
            return MagicMock(stdout="README.md\n")
        raise AssertionError(f"unexpected git invocation: {args}")

    with patch("body.atomic.assisted_actions.ToolRunner.run_git", side_effect=_run_git):
        result = await fn(
            patch="--- a/README.md\n+++ b/README.md\n",
            finding_rules=["rule.a", "rule.b"],
            subject_files=None,
            core_context=ctx,
        )

    assert result.ok is True
    checks = result.data["validation_results"]
    assert checks["audit_rule_cleared:rule.a"] is True
    assert checks["audit_rule_cleared:rule.b"] is True
    assert result.data["finding_rules"] == ["rule.a", "rule.b"]


async def test_validate_diff_one_of_n_rules_still_flagged_fails() -> None:
    """One of N rules still flags the subject file → that rule's key is
    False, overall verdict fails, but the OTHER rule's key still reads True
    — per-rule evidence, not a collapsed aggregate."""
    fn = action_assisted_validate_diff.__wrapped__
    ctx, _worktree = _mk_ctx_for_multi_rule("src/pkg/mod.py\n")

    def _run_git(_wt_path, *args, **kwargs):
        if args[:1] == ("apply",):
            return MagicMock(returncode=0, stderr="")
        if args[:2] == ("diff", "--name-only"):
            return MagicMock(stdout="src/pkg/mod.py\n")
        if args[:1] == ("diff",):
            return MagicMock(stdout="")
        raise AssertionError(f"unexpected git invocation: {args}")

    async def _fake_run_filtered_audit(actx, *, rule_ids, files):
        # rule.a's own file is still flagged; rule.b clears.
        return (
            [
                {"check_id": "rule.a", "file_path": "src/pkg/mod.py"},
            ],
            set(rule_ids),
            {},
        )

    with (
        patch("body.atomic.assisted_actions.ToolRunner.run_git", side_effect=_run_git),
        patch("body.atomic.assisted_actions.ToolRunner.run_ruff", return_value=True),
        patch(
            "mind.governance.filtered_audit.run_filtered_audit",
            side_effect=_fake_run_filtered_audit,
        ),
        patch("mind.governance.audit_context.AuditorContext") as MockCtx,
    ):
        MockCtx.return_value.load_knowledge_graph = AsyncMock(return_value=None)
        result = await fn(
            patch="--- a/src/pkg/mod.py\n+++ b/src/pkg/mod.py\n",
            finding_rules=["rule.a", "rule.b"],
            subject_files=["src/pkg/mod.py"],
            core_context=ctx,
        )

    checks = result.data["validation_results"]
    assert checks["audit_rule_cleared:rule.a"] is False
    assert checks["audit_rule_cleared:rule.b"] is True
    assert result.ok is False


def test_findings_by_rule_attributes_crash_suffix_to_owning_rule() -> None:
    """A rule that crashed during evaluation is recorded with a
    '.enforcement_failure'/'.engine_missing' suffixed check_id — attribution
    must still land on the owning rule, not be dropped."""
    from body.atomic.assisted_actions import _findings_by_rule

    findings = [
        {"check_id": "rule.a.enforcement_failure", "file_path": "x.py"},
        {"check_id": "rule.b", "file_path": "y.py"},
    ]
    by_rule = _findings_by_rule(findings, ["rule.a", "rule.b"])
    assert len(by_rule["rule.a"]) == 1
    assert len(by_rule["rule.b"]) == 1


async def test_validate_diff_subprocess_path_emits_per_rule_evidence() -> None:
    """The subprocess (engine-touch) audit path must produce the same
    per-rule flat evidence shape as the in-process path — one rule clears,
    one doesn't, both keys present."""
    fn = action_assisted_validate_diff.__wrapped__

    worktree = MagicMock()
    worktree.repo_path = "/tmp/fake-worktree"
    worktree.get_current_commit.return_value = "sha-sub"
    ctx = MagicMock()
    ctx.git_service.create_worktree.return_value = worktree
    ctx.file_handler.repo_path = Path("/repo")

    engine_file = "src/mind/logic/engines/ast_gate.py"

    def _run_git(_wt_path, *args, **kwargs):
        if args[:1] == ("apply",):
            return MagicMock(returncode=0, stderr="")
        if args[:2] == ("diff", "--name-only"):
            return MagicMock(stdout=f"{engine_file}\n")
        raise AssertionError(f"unexpected git invocation: {args}")

    with (
        patch("body.atomic.assisted_actions.ToolRunner.run_git", side_effect=_run_git),
        patch("body.atomic.assisted_actions.ToolRunner.run_ruff", return_value=True),
        patch(
            "mind.logic.engines.registry.EngineRegistry.engine_source_files",
            return_value=frozenset({engine_file}),
        ),
        patch(
            "mind.logic.engines.registry.EngineRegistry.graph_dependent_engine_files",
            return_value=frozenset(),
        ),
        patch(
            "body.atomic.assisted_actions.ToolRunner.run_audit_rule_subprocess",
            return_value={
                "ok": True,
                "findings": [
                    {"check_id": "rule.a", "file_path": engine_file},
                ],
                "error": None,
            },
        ),
    ):
        result = await fn(
            patch="--- a/x\n+++ b/x\n",
            finding_rules=["rule.a", "rule.b"],
            subject_files=None,
            core_context=ctx,
        )

    checks = result.data["validation_results"]
    assert checks["subprocess_audit:rule.a"] is False  # engine_file still flagged
    assert checks["subprocess_audit:rule.b"] is True  # no finding for rule.b
    assert result.ok is False
    assert checks["not_graph_engine"] is True


def test_findings_by_rule_duplicate_rule_ids_normalize() -> None:
    """Requesting the same rule id twice (a caller that failed to
    deduplicate) must not duplicate or drop evidence — dict keys collapse
    duplicates deterministically."""
    from body.atomic.assisted_actions import _findings_by_rule

    by_rule = _findings_by_rule(
        [{"check_id": "rule.a", "file_path": "x.py"}], ["rule.a", "rule.a"]
    )
    assert list(by_rule.keys()) == ["rule.a"]
    assert len(by_rule["rule.a"]) == 1
