# tests/body/services/test_fix_run_service.py
"""Unit tests for the persisted atomic-action execution service (ADR-154 D1).

The central claim under test: a call to submit_and_persist_fix produces a
durable core.fix_runs row indistinguishable, to build_validated_candidate,
from one produced by the existing /fix/run API path — RemediationCeremony's
D1 validate-diff gate needs a real validation_run_id, not just an in-memory
ActionResult, because build_validated_candidate (ADR-154 D2) never trusts an
in-memory verdict; it always re-reads the persisted row.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from body.services.fix_run_service import submit_and_persist_fix
from body.services.validated_candidate_service import build_validated_candidate
from shared.action_types import ActionImpact, ActionResult
from shared.models.validated_remediation_candidate import (
    ValidatedRemediationCandidate,
)


_PATCH = "--- a/src/x.py\n+++ b/src/x.py\n"
_PATCH_SHA = hashlib.sha256(_PATCH.encode("utf-8")).hexdigest()


class _FakeExecResult:
    def __init__(self, scalar: Any = None) -> None:
        self._scalar = scalar

    def scalar_one(self) -> Any:
        return self._scalar


class _FakeFixRunsSession:
    """Minimal in-memory stand-in for the AsyncSession, just capable enough
    to exercise submit_and_persist_fix's exact INSERT/UPDATE sequence and
    hand the resulting row to a build_validated_candidate-shaped reader."""

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self._next = 1

    async def execute(self, stmt: Any, params: dict[str, Any] | None = None) -> Any:
        sql = str(stmt)
        params = params or {}
        if "INSERT INTO core.fix_runs" in sql:
            run_id = f"run-{self._next}"
            self._next += 1
            self.rows[run_id] = {
                "fix_id": params["fix_id"],
                "status": "pending",
                "error": None,
                "result": None,
            }
            return _FakeExecResult(scalar=run_id)
        if "status = 'executing'" in sql:
            self.rows[params["rid"]]["status"] = "executing"
            return _FakeExecResult()
        if "status = 'failed'" in sql and ":result" not in sql:
            row = self.rows[params["rid"]]
            row["status"] = "failed"
            row["error"] = params["err"]
            return _FakeExecResult()
        if "status = :status" in sql:
            row = self.rows[params["rid"]]
            row["status"] = params["status"]
            row["error"] = params["err"]
            row["result"] = json.loads(params["result"])
            return _FakeExecResult()
        raise AssertionError(f"unexpected SQL in fake session: {sql}")

    async def commit(self) -> None:
        return None


def _patch_fix_run_service_session(fake: _FakeFixRunsSession):
    @asynccontextmanager
    async def _session():
        yield fake

    return patch("body.services.fix_run_service.service_registry.session", _session)


def _passing_validate_diff_result(
    production_set: list[str] | None = None,
    validation_results: dict[str, bool] | None = None,
) -> ActionResult:
    return ActionResult(
        action_id="assisted.validate_diff",
        ok=True,
        data={
            "validation_results": validation_results
            or {"patch_applies": True, "audit_rule_cleared:rule.a": True},
            "production_set": production_set or ["src/x.py"],
            "finding_rules": ["rule.a"],
            "patch_sha256": _PATCH_SHA,
            "validated_base_sha": "base-sha-777",
        },
        impact=ActionImpact.WRITE_DATA,
        duration_sec=0.1,
    )


@pytest.mark.asyncio
async def test_submit_and_persist_fix_writes_completed_row_on_pass() -> None:
    fake = _FakeFixRunsSession()
    with (
        _patch_fix_run_service_session(fake),
        patch("body.services.fix_run_service.ActionExecutor") as MockExecutor,
    ):
        MockExecutor.return_value.execute = AsyncMock(
            return_value=_passing_validate_diff_result()
        )
        run_id, result = await submit_and_persist_fix(
            context=MagicMock(),
            fix_id="assisted.validate_diff",
            write=True,
            params={"patch": _PATCH},
        )

    assert result.ok is True
    row = fake.rows[run_id]
    assert row["fix_id"] == "assisted.validate_diff"
    assert row["status"] == "completed"
    assert row["result"]["ok"] is True
    assert row["result"]["data"]["patch_sha256"] == _PATCH_SHA


@pytest.mark.asyncio
async def test_submit_and_persist_fix_writes_failed_row_on_action_failure() -> None:
    fake = _FakeFixRunsSession()
    failing = ActionResult(
        action_id="assisted.validate_diff",
        ok=False,
        data={"error": "rule.a still fires"},
        impact=ActionImpact.WRITE_DATA,
    )
    with (
        _patch_fix_run_service_session(fake),
        patch("body.services.fix_run_service.ActionExecutor") as MockExecutor,
    ):
        MockExecutor.return_value.execute = AsyncMock(return_value=failing)
        run_id, result = await submit_and_persist_fix(
            context=MagicMock(), fix_id="assisted.validate_diff", write=True
        )

    assert result.ok is False
    row = fake.rows[run_id]
    assert row["status"] == "failed"
    assert row["error"] == "rule.a still fires"


@pytest.mark.asyncio
async def test_submit_and_persist_fix_never_raises_records_failed_row() -> None:
    """An exception from ActionExecutor.execute must be caught, persisted,
    and surfaced as a synthetic failed ActionResult — never propagated —
    so RemediationCeremony's uniform '.ok' check still works."""
    fake = _FakeFixRunsSession()
    with (
        _patch_fix_run_service_session(fake),
        patch("body.services.fix_run_service.ActionExecutor") as MockExecutor,
    ):
        MockExecutor.return_value.execute = AsyncMock(side_effect=RuntimeError("boom"))
        run_id, result = await submit_and_persist_fix(
            context=MagicMock(), fix_id="assisted.validate_diff", write=True
        )

    assert result.ok is False
    assert "boom" in result.data["error"]
    row = fake.rows[run_id]
    assert row["status"] == "failed"
    assert "boom" in row["error"]


@pytest.mark.asyncio
async def test_submit_and_persist_fix_params_forwarded_to_action_executor() -> None:
    fake = _FakeFixRunsSession()
    with (
        _patch_fix_run_service_session(fake),
        patch("body.services.fix_run_service.ActionExecutor") as MockExecutor,
    ):
        MockExecutor.return_value.execute = AsyncMock(
            return_value=_passing_validate_diff_result()
        )
        await submit_and_persist_fix(
            context=MagicMock(),
            fix_id="assisted.validate_diff",
            write=True,
            params={
                "patch": _PATCH,
                "finding_rules": ["rule.a", "rule.b"],
                "subject_files": ["src/x.py"],
                "base_sha": "base-sha-777",
            },
        )

    MockExecutor.return_value.execute.assert_awaited_once_with(
        "assisted.validate_diff",
        write=True,
        patch=_PATCH,
        finding_rules=["rule.a", "rule.b"],
        subject_files=["src/x.py"],
        base_sha="base-sha-777",
    )


def _patch_validated_candidate_session(row: dict | None):
    session = AsyncMock()
    exec_result = MagicMock()
    exec_result.mappings.return_value.first.return_value = row
    session.execute = AsyncMock(return_value=exec_result)

    @asynccontextmanager
    async def _session():
        yield session

    return patch(
        "body.services.validated_candidate_service.service_registry.session",
        _session,
    )


@pytest.mark.asyncio
async def test_build_validated_candidate_reconstructs_from_ceremony_produced_run() -> (
    None
):
    """End-to-end proof (the governor's exact ask): a validation_run_id
    produced by submit_and_persist_fix — the path RemediationCeremony now
    calls — is a row build_validated_candidate can successfully re-read and
    build a privileged ValidatedRemediationCandidate from. This is the
    connective tissue D1 was missing: without it, D3 would have nothing
    trustworthy to submit."""
    fake = _FakeFixRunsSession()
    with (
        _patch_fix_run_service_session(fake),
        patch("body.services.fix_run_service.ActionExecutor") as MockExecutor,
    ):
        MockExecutor.return_value.execute = AsyncMock(
            return_value=_passing_validate_diff_result(
                production_set=["src/x.py", "src/base.py"],
                validation_results={
                    "patch_applies": True,
                    "ruff": True,
                    "audit_rule_cleared:rule.a": True,
                },
            )
        )
        validation_run_id, action_result = await submit_and_persist_fix(
            context=MagicMock(),
            fix_id="assisted.validate_diff",
            write=True,
            params={"patch": _PATCH},
        )

    assert action_result.ok is True

    # build_validated_candidate re-reads core.fix_runs by validation_run_id —
    # feed it the exact row submit_and_persist_fix just wrote.
    persisted_row = fake.rows[validation_run_id]
    select_shaped_row = {
        "fix_id": persisted_row["fix_id"],
        "status": persisted_row["status"],
        "result": persisted_row["result"],
    }

    with _patch_validated_candidate_session(select_shaped_row):
        candidate = await build_validated_candidate(
            finding_ids=["f-1"],
            rule_ids=["rule.a"],
            patch=_PATCH,
            validation_run_id=validation_run_id,
        )

    assert isinstance(candidate, ValidatedRemediationCandidate)
    assert candidate.patch == _PATCH
    assert candidate.patch_digest == _PATCH_SHA
    assert candidate.production_set == ["src/x.py", "src/base.py"]
    assert candidate.validated_base_sha == "base-sha-777"
    assert candidate.validation_results == {
        "patch_applies": True,
        "ruff": True,
        "audit_rule_cleared:rule.a": True,
    }
    assert candidate.rule_ids == ["rule.a"]
