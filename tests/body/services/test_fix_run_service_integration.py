# tests/body/services/test_fix_run_service_integration.py
"""DB-backed integration test: submit_and_persist_fix (ADR-154 D1).

Proves the persistence bridge with the actual schema — not mocks. A mock
proves the code called the right functions in the right order; it cannot
prove a fresh session actually reads back the row Postgres committed, or
that build_validated_candidate's own independent SELECT (a completely
separate service, separate session) can reconstruct a real
ValidatedRemediationCandidate from it. Governor-authorized per the D1
persistence review (ef7c931b / 832ae7f5): the missing link was exactly this
— an in-memory ActionResult with no durable core.fix_runs row for D3 to
later build a candidate from.

Only the atomic action's expensive internals (ActionExecutor.execute) are
mocked — the entire persistence path (INSERT, UPDATE, fresh-session SELECT,
and build_validated_candidate's own independent re-read) runs against the
real core_test database.
"""

from __future__ import annotations

import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.fix_run_service import submit_and_persist_fix
from body.services.service_registry import service_registry
from body.services.validated_candidate_service import build_validated_candidate
from shared.action_types import ActionImpact, ActionResult
from shared.infrastructure.database.session_manager import get_session
from shared.models.validated_remediation_candidate import (
    ValidatedRemediationCandidate,
)


pytestmark = [pytest.mark.integration]

_PATCH = "--- a/src/x.py\n+++ b/src/x.py\n"
_PATCH_SHA = hashlib.sha256(_PATCH.encode("utf-8")).hexdigest()


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    """Match production entry-point bootstrap so service_registry.session()
    (used by both submit_and_persist_fix and build_validated_candidate)
    acquires a live session against core_test."""
    service_registry.prime(get_session)


def _passing_validate_diff_result() -> ActionResult:
    """A real assisted.validate_diff success shape — only the expensive
    internals (worktree creation, subprocess audit, ruff, tests) are
    stubbed; the shape mirrors exactly what the real action returns."""
    return ActionResult(
        action_id="assisted.validate_diff",
        ok=True,
        data={
            "validation_results": {
                "patch_applies": True,
                "ruff": True,
                "audit_rule_cleared:rule.a": True,
                "tests": True,
            },
            "production_set": ["src/x.py"],
            "finding_rules": ["rule.a"],
            "patch_sha256": _PATCH_SHA,
            "validated_base_sha": "integration-test-base-sha",
        },
        impact=ActionImpact.WRITE_DATA,
        duration_sec=0.05,
    )


async def _fetch_fix_run_row(session: AsyncSession, run_id: str) -> dict | None:
    result = await session.execute(
        text(
            "SELECT id, kind, fix_id, status, requested_by, result, error "
            "FROM core.fix_runs WHERE id = cast(:rid as uuid)"
        ),
        {"rid": run_id},
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def test_submit_and_persist_fix_against_real_db_reconstructs_candidate(
    db_session: AsyncSession,
) -> None:
    """The full governor-specified proof, end to end against core_test:

    1. submit_and_persist_fix creates a real core.fix_runs row.
    2. The row reaches status='completed'.
    3. A FRESH session (not the one that wrote it) reads back result.data
       containing patch digest, production set, flat per-rule validation
       evidence, and validated_base_sha.
    4. build_validated_candidate(validation_run_id=<real row id>) — a
       wholly separate service, its own independent SELECT — reconstructs
       the privileged candidate from that real row.
    5. Cleanup leaves zero synthetic rows (verified, not just attempted).
    """
    requested_by = f"integration-test-{uuid.uuid4().hex[:8]}"
    run_id: str | None = None
    try:
        with patch("body.services.fix_run_service.ActionExecutor") as MockExecutor:
            MockExecutor.return_value.execute = AsyncMock(
                return_value=_passing_validate_diff_result()
            )
            run_id, action_result = await submit_and_persist_fix(
                context=MagicMock(),  # never touched — ActionExecutor is mocked
                fix_id="assisted.validate_diff",
                write=True,
                params={"patch": _PATCH, "finding_rules": ["rule.a"]},
                requested_by=requested_by,
            )

        assert action_result.ok is True
        assert run_id is not None

        # 1 + 3: a genuinely fresh session — never the one submit_and_persist_fix
        # used internally — reads the durably committed row.
        async with service_registry.session() as fresh:
            row = await _fetch_fix_run_row(fresh, run_id)

        assert row is not None, "fix_runs row must exist after a real INSERT+commit"
        assert row["kind"] == "atomic"
        assert row["fix_id"] == "assisted.validate_diff"
        # 2: reached completed, not stuck at pending/executing.
        assert row["status"] == "completed"
        assert row["requested_by"] == requested_by
        assert row["error"] is None

        data = row["result"]["data"]
        assert data["patch_sha256"] == _PATCH_SHA
        assert data["production_set"] == ["src/x.py"]
        assert data["validated_base_sha"] == "integration-test-base-sha"
        # Flat per-rule evidence (not nested) — the governor's D1 shape call.
        assert data["validation_results"]["audit_rule_cleared:rule.a"] is True
        assert data["validation_results"]["patch_applies"] is True

        # 4: an entirely separate service, its own independent SELECT,
        # reconstructs a privileged candidate from the SAME real row.
        candidate = await build_validated_candidate(
            finding_ids=["f-integration-1"],
            rule_ids=["rule.a"],
            patch=_PATCH,
            validation_run_id=run_id,
        )

        assert isinstance(candidate, ValidatedRemediationCandidate)
        assert candidate.patch == _PATCH
        assert candidate.patch_digest == _PATCH_SHA
        assert candidate.production_set == ["src/x.py"]
        assert candidate.validated_base_sha == "integration-test-base-sha"
        assert candidate.validation_results["audit_rule_cleared:rule.a"] is True
        assert candidate.rule_ids == ["rule.a"]
    finally:
        # 5: cleanup — deleted, and verified deleted, not just attempted.
        if run_id is not None:
            await db_session.execute(
                text("DELETE FROM core.fix_runs WHERE id = cast(:rid as uuid)"),
                {"rid": run_id},
            )
            await db_session.commit()

            async with service_registry.session() as verify:
                leftover = await _fetch_fix_run_row(verify, run_id)
            assert leftover is None, "cleanup must leave zero synthetic rows"


async def test_submit_and_persist_fix_failed_action_persists_failed_row_real_db(
    db_session: AsyncSession,
) -> None:
    """The failure path against the real DB: a failing action_result
    produces a real status='failed' row with the error text, and
    build_validated_candidate correctly refuses to build a candidate from
    it (it is not a passing run)."""
    from body.services.validated_candidate_service import (
        CandidateConstructionError,
    )

    requested_by = f"integration-test-fail-{uuid.uuid4().hex[:8]}"
    run_id: str | None = None
    try:
        failing = ActionResult(
            action_id="assisted.validate_diff",
            ok=False,
            data={"error": "rule.a still fires"},
            impact=ActionImpact.WRITE_DATA,
        )
        with patch("body.services.fix_run_service.ActionExecutor") as MockExecutor:
            MockExecutor.return_value.execute = AsyncMock(return_value=failing)
            run_id, action_result = await submit_and_persist_fix(
                context=MagicMock(),
                fix_id="assisted.validate_diff",
                write=True,
                requested_by=requested_by,
            )

        assert action_result.ok is False

        async with service_registry.session() as fresh:
            row = await _fetch_fix_run_row(fresh, run_id)
        assert row is not None
        assert row["status"] == "failed"
        assert row["error"] == "rule.a still fires"

        with pytest.raises(CandidateConstructionError, match="did not pass"):
            await build_validated_candidate(
                finding_ids=["f-integration-2"],
                rule_ids=["rule.a"],
                patch=_PATCH,
                validation_run_id=run_id,
            )
    finally:
        if run_id is not None:
            await db_session.execute(
                text("DELETE FROM core.fix_runs WHERE id = cast(:rid as uuid)"),
                {"rid": run_id},
            )
            await db_session.commit()

            async with service_registry.session() as verify:
                leftover = await _fetch_fix_run_row(verify, run_id)
            assert leftover is None, "cleanup must leave zero synthetic rows"
