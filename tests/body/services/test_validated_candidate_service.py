# tests/body/services/test_validated_candidate_service.py
"""Unit tests for the trusted validation / candidate-construction service
(ADR-154 D2) — the sole privileged constructor of
ValidatedRemediationCandidate.

Every failure mode is a precondition on the persisted core.fix_runs row:
unknown run, wrong action, not a completed+passing run, patch bytes that
don't match what was validated, or a passing run that recorded no
validated_base_sha. The happy path proves the returned candidate is built
entirely from that row — never from caller-supplied validation_results.
"""

from __future__ import annotations

import hashlib
import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from body.services.validated_candidate_service import build_validated_candidate
from shared.models.validated_remediation_candidate import (
    CandidateConstructionError,
    ValidatedRemediationCandidate,
)


_PATCH = "--- a/src/x.py\n+++ b/src/x.py\n"
_PATCH_SHA = hashlib.sha256(_PATCH.encode("utf-8")).hexdigest()


def _patch_session(row: dict | None):
    """Patch service_registry.session() to yield a session whose execute(...)
    .mappings().first() returns *row* (or None for 'no such run')."""
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


def _row(
    *,
    fix_id: str = "assisted.validate_diff",
    status: str = "completed",
    ok: bool = True,
    patch_sha256: str | None = _PATCH_SHA,
    production_set: list[str] | None = None,
    validated_base_sha: str | None = "base-sha-123",
    validation_results: dict[str, bool] | None = None,
    finding_rules: list[str] | None = None,
    subject_files: list[str] | None = None,
) -> dict:
    return {
        "fix_id": fix_id,
        "status": status,
        "result": {
            "ok": ok,
            "data": {
                "patch_sha256": patch_sha256,
                "production_set": (
                    production_set if production_set is not None else ["src/x.py"]
                ),
                "validated_base_sha": validated_base_sha,
                "validation_results": (
                    validation_results
                    if validation_results is not None
                    else {"patch_applies": True, "ruff": True}
                ),
                # ADR-154 D3: the persisted rule set build_validated_candidate
                # cross-checks the caller's rule_ids against. Defaults to
                # ["r"] — the rule_ids value every test in this file except
                # test_returns_frozen_candidate_built_entirely_from_the_row
                # (which overrides it) actually passes.
                "finding_rules": (
                    finding_rules if finding_rules is not None else ["r"]
                ),
                "subject_files": (subject_files if subject_files is not None else []),
            },
        },
    }


async def test_raises_on_unknown_run():
    with _patch_session(None):
        with pytest.raises(CandidateConstructionError, match="Unknown validation run"):
            await build_validated_candidate(
                finding_ids=["f-1"],
                rule_ids=["r"],
                patch=_PATCH,
                validation_run_id="missing-run",
            )


async def test_raises_on_wrong_fix_id():
    with _patch_session(_row(fix_id="assisted.apply_diff")):
        with pytest.raises(
            CandidateConstructionError,
            match=r"is not an assisted\.validate_diff run",
        ):
            await build_validated_candidate(
                finding_ids=["f-1"],
                rule_ids=["r"],
                patch=_PATCH,
                validation_run_id="run-1",
            )


async def test_raises_when_run_not_completed():
    with _patch_session(_row(status="executing")):
        with pytest.raises(CandidateConstructionError, match="did not pass"):
            await build_validated_candidate(
                finding_ids=["f-1"],
                rule_ids=["r"],
                patch=_PATCH,
                validation_run_id="run-1",
            )


async def test_raises_when_run_not_ok():
    with _patch_session(_row(ok=False)):
        with pytest.raises(CandidateConstructionError, match="did not pass"):
            await build_validated_candidate(
                finding_ids=["f-1"],
                rule_ids=["r"],
                patch=_PATCH,
                validation_run_id="run-1",
            )


async def test_raises_on_patch_mismatch():
    """An agent who edited the diff after validating cannot ride a stale
    PASS (ADR-109 mechanism §4)."""
    with _patch_session(_row(patch_sha256="a-different-digest-entirely")):
        with pytest.raises(CandidateConstructionError, match="does not match"):
            await build_validated_candidate(
                finding_ids=["f-1"],
                rule_ids=["r"],
                patch=_PATCH,
                validation_run_id="run-1",
            )


async def test_raises_when_validated_base_sha_missing():
    with _patch_session(_row(validated_base_sha=None)):
        with pytest.raises(
            CandidateConstructionError, match="recorded no validated_base_sha"
        ):
            await build_validated_candidate(
                finding_ids=["f-1"],
                rule_ids=["r"],
                patch=_PATCH,
                validation_run_id="run-1",
            )


# --- ADR-154 D3 hardening: rule_ids / subject_files must match the persisted run ---


async def test_raises_when_caller_understates_validated_rule_set():
    """The run validated rules A+B; a caller claiming only A must be
    refused — the candidate would misrepresent what was actually checked."""
    with _patch_session(_row(finding_rules=["rule.a", "rule.b"])):
        with pytest.raises(CandidateConstructionError, match="rule set"):
            await build_validated_candidate(
                finding_ids=["f-1"],
                rule_ids=["rule.a"],
                patch=_PATCH,
                validation_run_id="run-1",
            )


async def test_raises_when_caller_overstates_validated_rule_set():
    """The run validated only rule.a; a caller claiming rule.a+rule.c must
    be refused — rule.c was never validated."""
    with _patch_session(_row(finding_rules=["rule.a"])):
        with pytest.raises(CandidateConstructionError, match="rule set"):
            await build_validated_candidate(
                finding_ids=["f-1"],
                rule_ids=["rule.a", "rule.c"],
                patch=_PATCH,
                validation_run_id="run-1",
            )


async def test_subject_files_check_skipped_when_caller_omits_it():
    """subject_files is optional — external Lane 1b callers that never
    supply it (the pre-D3 call shape) must be unaffected."""
    with _patch_session(_row(subject_files=["src/other.py"])):
        candidate = await build_validated_candidate(
            finding_ids=["f-1"],
            rule_ids=["r"],
            patch=_PATCH,
            validation_run_id="run-1",
        )
    assert candidate.patch == _PATCH


async def test_raises_when_caller_subject_files_mismatch_persisted():
    with _patch_session(_row(subject_files=["src/x.py"])):
        with pytest.raises(CandidateConstructionError, match="subject_files"):
            await build_validated_candidate(
                finding_ids=["f-1"],
                rule_ids=["r"],
                patch=_PATCH,
                validation_run_id="run-1",
                subject_files=["src/different.py"],
            )


async def test_subject_files_check_passes_when_matching():
    with _patch_session(_row(subject_files=["src/x.py"])):
        candidate = await build_validated_candidate(
            finding_ids=["f-1"],
            rule_ids=["r"],
            patch=_PATCH,
            validation_run_id="run-1",
            subject_files=["src/x.py"],
        )
    assert candidate.patch == _PATCH


async def test_returns_frozen_candidate_built_entirely_from_the_row():
    with _patch_session(
        _row(
            production_set=["src/x.py", "src/base.py"],
            validated_base_sha="base-sha-999",
            validation_results={"patch_applies": True, "ruff": True, "tests": True},
            finding_rules=["modularity.class_too_large"],
        )
    ):
        candidate = await build_validated_candidate(
            finding_ids=["f-1", "f-2"],
            rule_ids=["modularity.class_too_large"],
            patch=_PATCH,
            validation_run_id="run-1",
        )

    assert isinstance(candidate, ValidatedRemediationCandidate)
    assert candidate.patch == _PATCH
    assert candidate.patch_digest == _PATCH_SHA
    assert candidate.production_set == ["src/x.py", "src/base.py"]
    assert candidate.validated_base_sha == "base-sha-999"
    assert sorted(candidate.validation_checks) == ["patch_applies", "ruff", "tests"]
    assert candidate.validation_results == {
        "patch_applies": True,
        "ruff": True,
        "tests": True,
    }
    assert candidate.finding_ids == ["f-1", "f-2"]
    assert candidate.rule_ids == ["modularity.class_too_large"]
    assert isinstance(candidate.candidate_id, str) and candidate.candidate_id
    assert isinstance(candidate.created_at, datetime)


async def test_candidate_is_frozen():
    """The contract must actually be immutable — a caller cannot mutate a
    constructed candidate's fields after the fact."""
    with _patch_session(_row()):
        candidate = await build_validated_candidate(
            finding_ids=["f-1"],
            rule_ids=["r"],
            patch=_PATCH,
            validation_run_id="run-1",
        )

    with pytest.raises(AttributeError):
        candidate.patch = "tampered"


# --- privileged construction is structural, not merely documented (ADR-154 D2) ---


def _dummy_kwargs() -> dict:
    return dict(
        candidate_id="forged",
        patch="x",
        patch_digest="y",
        production_set=[],
        validated_base_sha="z",
        validation_checks=[],
        validation_results={},
        finding_ids=[],
        rule_ids=[],
        created_at=datetime.now(),
    )


def test_direct_construction_without_token_raises():
    """A caller that imports the dataclass and manufactures a candidate
    directly — asserting validation happened without ever going through
    build_validated_candidate — is rejected at construction time, not
    merely discouraged by convention or documentation."""
    with pytest.raises(CandidateConstructionError):
        ValidatedRemediationCandidate(**_dummy_kwargs(), _construction_token=object())


def test_direct_construction_with_no_token_at_all_raises():
    """The token is a required field — omitting it entirely is a TypeError
    (missing argument), not a silent default-to-unprivileged."""
    with pytest.raises(TypeError):
        ValidatedRemediationCandidate(**_dummy_kwargs())  # type: ignore[call-arg]


def test_no_production_code_constructs_candidate_outside_trusted_service():
    """Static boundary sweep: outside the two files that define/construct
    the type, no production module in src/ may call
    ValidatedRemediationCandidate(...) directly. Complements the runtime
    _construction_token guard — catches future drift at test time, before
    any code path exercises the bad call and hits the runtime raise."""
    src_root = Path(__file__).resolve().parents[3] / "src"
    allowed = {
        src_root / "body" / "services" / "validated_candidate_service.py",
        src_root / "shared" / "models" / "validated_remediation_candidate.py",
    }
    pattern = re.compile(r"\bValidatedRemediationCandidate\s*\(")

    offenders = [
        str(path)
        for path in src_root.rglob("*.py")
        if path not in allowed and pattern.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == [], f"unauthorized construction site(s): {offenders}"
