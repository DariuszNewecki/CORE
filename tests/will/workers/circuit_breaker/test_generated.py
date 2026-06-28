"""
Generated tests for will.workers.circuit_breaker.

Covers load_circuit_breaker_config and trip — the two public functions
not exercised by the sibling tests (test_circuit_breaker_signature.py
covers canonical_signature; test_circuit_breaker_count.py covers
recent_consecutive_identical_count via live DB).

All tests are pure-unit: no live DB, no file I/O.
"""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.circuit_breaker import (
    load_circuit_breaker_config,
    trip,
)


# ── load_circuit_breaker_config ───────────────────────────────────────────────


# ID: 31bc674a-7cd1-4e5a-b5e3-095ef8ab3cc2
def test_load_config_returns_fallbacks_when_repo_raises() -> None:
    """When IntentRepository is unavailable the function returns fallback defaults."""
    with patch(
        "shared.infrastructure.intent.intent_repository.get_intent_repository",
        side_effect=RuntimeError("unavailable"),
    ):
        cfg = load_circuit_breaker_config()

    assert cfg.threshold_n == 5
    assert cfg.signature_window_chars == 200
    assert cfg.max_lookback == 25


# ID: 7bb504b2-7c33-4311-bed4-3ac9b93fe895
def test_load_config_reads_custom_threshold_n() -> None:
    """Custom threshold_n from .intent/ is respected."""
    mock_repo = MagicMock()
    mock_repo.resolve_rel.return_value = "/fake/circuit_breaker.yaml"
    mock_repo.load_document.return_value = {
        "threshold_n": 3,
        "signature_window_chars": 100,
        "max_lookback": 10,
    }

    with patch(
        "shared.infrastructure.intent.intent_repository.get_intent_repository",
        return_value=mock_repo,
    ):
        cfg = load_circuit_breaker_config()

    assert cfg.threshold_n == 3
    assert cfg.signature_window_chars == 100


# ID: dc4d78bc-5847-4222-9749-f970e50b8b4a
def test_load_config_max_lookback_floored_to_threshold_n() -> None:
    """max_lookback is always >= threshold_n even when YAML says otherwise."""
    mock_repo = MagicMock()
    mock_repo.resolve_rel.return_value = "/fake/circuit_breaker.yaml"
    mock_repo.load_document.return_value = {
        "threshold_n": 10,
        "max_lookback": 1,  # deliberately below threshold_n
    }

    with patch(
        "shared.infrastructure.intent.intent_repository.get_intent_repository",
        return_value=mock_repo,
    ):
        cfg = load_circuit_breaker_config()

    assert cfg.max_lookback >= cfg.threshold_n


# ID: 70f659af-2038-401a-a71e-20565392f3f5
def test_load_config_compiles_custom_volatile_patterns() -> None:
    """Custom volatile_patterns entries are compiled into re.Pattern objects."""
    mock_repo = MagicMock()
    mock_repo.resolve_rel.return_value = "/fake/circuit_breaker.yaml"
    mock_repo.load_document.return_value = {
        "volatile_patterns": [{"name": "mypattern", "regex": r"\d+"}],
    }

    with patch(
        "shared.infrastructure.intent.intent_repository.get_intent_repository",
        return_value=mock_repo,
    ):
        cfg = load_circuit_breaker_config()

    assert len(cfg.volatile_patterns) == 1
    assert isinstance(cfg.volatile_patterns[0], re.Pattern)


# ID: 362ab02e-d7fa-420d-901d-52cdbaf5f5bb
def test_load_config_skips_malformed_volatile_patterns() -> None:
    """Malformed regex entries are dropped with a warning; no crash."""
    mock_repo = MagicMock()
    mock_repo.resolve_rel.return_value = "/fake/circuit_breaker.yaml"
    mock_repo.load_document.return_value = {
        "volatile_patterns": [
            {"name": "bad", "regex": r"[unclosed"},
            {"name": "good", "regex": r"\d+"},
        ],
    }

    with patch(
        "shared.infrastructure.intent.intent_repository.get_intent_repository",
        return_value=mock_repo,
    ):
        cfg = load_circuit_breaker_config()  # must not raise

    assert len(cfg.volatile_patterns) == 1


# ID: e9d4ed48-95d1-4600-984d-2acc6c11fe5c
def test_load_config_returns_fallbacks_when_yaml_not_dict() -> None:
    """When the loaded YAML is not a dict fallback defaults are used."""
    mock_repo = MagicMock()
    mock_repo.resolve_rel.return_value = "/fake/circuit_breaker.yaml"
    mock_repo.load_document.return_value = ["unexpected", "list"]

    with patch(
        "shared.infrastructure.intent.intent_repository.get_intent_repository",
        return_value=mock_repo,
    ):
        cfg = load_circuit_breaker_config()

    assert cfg.threshold_n == 5  # fallback


# ── trip ──────────────────────────────────────────────────────────────────────


# ID: da5fc528-941a-4c30-a73f-a7042ec5ae61
async def test_trip_calls_mark_delegated_with_findings() -> None:
    """trip() awaits mark_delegated with the full findings list."""
    mock_worker = MagicMock()
    mock_worker.post_observation = AsyncMock()
    mark_delegated = AsyncMock(return_value=2)
    findings = [{"id": "e1"}, {"id": "e2"}]

    await trip(
        worker=mock_worker,
        ref_id="fix.tests",
        ref_kind="action",
        file_path="src/foo.py",
        findings=findings,
        count=3,
        signature="same error",
        last_proposal_id="prop-id-1",
        last_failure_reason="CoderAgent timed out",
        mark_delegated=mark_delegated,
    )

    mark_delegated.assert_awaited_once_with(findings)


# ID: 471051db-8600-4d14-a1c6-821ada5f3a09
async def test_trip_posts_observation_with_correct_payload() -> None:
    """trip() calls worker.post_observation with the expected subject, status and payload."""
    mock_worker = MagicMock()
    mock_worker.post_observation = AsyncMock()
    mark_delegated = AsyncMock(return_value=1)

    await trip(
        worker=mock_worker,
        ref_id="fix.tests",
        ref_kind="action",
        file_path="src/foo.py",
        findings=[],
        count=5,
        signature="timeout",
        last_proposal_id="p1",
        last_failure_reason="timeout reason",
        mark_delegated=mark_delegated,
    )

    call_kwargs = mock_worker.post_observation.await_args.kwargs
    assert call_kwargs["subject"] == "governance.circuit_breaker_tripped"
    assert call_kwargs["status"] == "abandoned"
    payload = call_kwargs["payload"]
    assert payload["ref_id"] == "fix.tests"
    assert payload["failure_count"] == 5
    assert payload["findings_delegated"] == 1


# ID: 1a83eb21-7050-4d8f-8fc6-15cd982123f8
async def test_trip_handles_mark_delegated_exception_gracefully() -> None:
    """If mark_delegated raises, trip() still posts the observation."""
    mock_worker = MagicMock()
    mock_worker.post_observation = AsyncMock()
    mark_delegated = AsyncMock(side_effect=RuntimeError("db down"))

    await trip(  # must not raise
        worker=mock_worker,
        ref_id="fix.tests",
        ref_kind="action",
        file_path=None,
        findings=[{"id": "e1"}],
        count=3,
        signature="sig",
        last_proposal_id=None,
        last_failure_reason=None,
        mark_delegated=mark_delegated,
    )

    mock_worker.post_observation.assert_awaited_once()


# ID: 142e7deb-1354-446b-8d44-7a7c27737d3a
async def test_trip_handles_post_observation_exception_gracefully() -> None:
    """If post_observation raises, trip() does not propagate the error."""
    mock_worker = MagicMock()
    mock_worker.post_observation = AsyncMock(side_effect=RuntimeError("network"))
    mark_delegated = AsyncMock(return_value=0)

    await trip(  # must not raise
        worker=mock_worker,
        ref_id="fix.tests",
        ref_kind="action",
        file_path=None,
        findings=[],
        count=3,
        signature="sig",
        last_proposal_id=None,
        last_failure_reason=None,
        mark_delegated=mark_delegated,
    )
