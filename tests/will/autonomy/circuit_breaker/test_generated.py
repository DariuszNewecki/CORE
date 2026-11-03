from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from will.autonomy.circuit_breaker import trip


@pytest.mark.asyncio
# ID: dd9ac200-84cc-4fa1-ae9e-5a0ebb550fd3
async def test_trip() -> None:
    worker = MagicMock()
    worker.post_observation = AsyncMock(return_value=None)

    findings = [{"id": "f1"}, {"id": "f2"}]
    mark_delegated = AsyncMock(return_value=2)

    await trip(
        worker=worker,
        ref_id="ref-123",
        ref_kind="violation",
        file_path="src/example.py",
        findings=findings,
        count=3,
        signature="sig-abc",
        last_proposal_id="prop-42",
        last_failure_reason="boom",
        mark_delegated=mark_delegated,
    )

    mark_delegated.assert_awaited_once_with(findings)
    worker.post_observation.assert_awaited_once()
    _, kwargs = worker.post_observation.await_args
    assert kwargs["subject"] == "governance.circuit_breaker_tripped"
    assert kwargs["status"] == "abandoned"
    payload = kwargs["payload"]
    assert payload["ref_id"] == "ref-123"
    assert payload["ref_kind"] == "violation"
    assert payload["file_path"] == "src/example.py"
    assert payload["failure_count"] == 3
    assert payload["error_signature"] == "sig-abc"
    assert payload["last_proposal_id"] == "prop-42"
    assert payload["last_failure_reason"] == "boom"
    assert payload["findings_delegated"] == 2


from types import SimpleNamespace
from unittest.mock import patch


# ID: 2ac142f7-b91a-40a7-a403-8420041905f8
async def test_recent_consecutive_identical_count():
    from will.autonomy.circuit_breaker import recent_consecutive_identical_count

    config = MagicMock()
    config.max_lookback = 10

    rows = [
        SimpleNamespace(failure_reason="boom", proposal_id="p3"),
        SimpleNamespace(failure_reason="boom", proposal_id="p2"),
        SimpleNamespace(failure_reason="other", proposal_id="p1"),
    ]

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = rows
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock

    session = MagicMock()
    session.execute = AsyncMock(return_value=result_mock)

    with patch(
        "will.autonomy.circuit_breaker.canonical_signature",
        side_effect=lambda reason, cfg: reason,
    ):
        (
            count,
            signature,
            last_proposal_id,
            last_failure_reason,
        ) = await recent_consecutive_identical_count(
            session,
            ref_id="ref-1",
            ref_kind="flow",
            file_path=None,
            config=config,
        )

    assert count == 2
    assert signature == "boom"
    assert last_proposal_id == "p3"
    assert last_failure_reason == "boom"
    session.execute.assert_awaited_once()


import re

from will.autonomy.circuit_breaker import canonical_signature


# ID: 97411afd-785f-4832-84ca-503cc1a6d777
def test_canonical_signature():
    config = MagicMock()
    config.volatile_patterns = [re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")]
    config.signature_window_chars = 50

    reason = "  Connection   failed at 2024-01-15T10:30:00  retrying  "
    result = canonical_signature(reason, config)

    assert result == "Connection failed at retrying"
    assert len(result) <= config.signature_window_chars

    assert canonical_signature(None, config) == ""
    assert canonical_signature("", config) == ""


# ID: 9db3b5a7-401e-4885-9708-ad71a0b676de
def test_load_circuit_breaker_config():
    from will.autonomy.circuit_breaker import load_circuit_breaker_config

    fake_repo = MagicMock()
    fake_repo.resolve_rel.return_value = (
        "/fake/.intent/enforcement/config/circuit_breaker.yaml"
    )
    fake_repo.load_document.return_value = {
        "threshold_n": 7,
        "signature_window_chars": 150,
        "max_lookback": 12,
        "volatile_patterns": [
            {
                "name": "uuid",
                "regex": r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            },
            {"name": "timestamp", "regex": r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"},
        ],
    }

    with patch(
        "shared.infrastructure.intent.intent_repository.get_intent_repository",
        return_value=fake_repo,
    ):
        config = load_circuit_breaker_config()

    fake_repo.load_document.assert_called_once_with(
        "/fake/.intent/enforcement/config/circuit_breaker.yaml"
    )
    assert config.threshold_n == 7
    assert config.signature_window_chars == 150
    assert config.max_lookback == 12
    assert len(config.volatile_patterns) == 2
    assert config.volatile_patterns[0].search("123e4567-e89b-12d3-a456-426614174000")


from will.autonomy.circuit_breaker import CircuitBreakerConfig


# ID: 965c890d-8ca2-4a34-a97c-76801e28d82a
def test_CircuitBreakerConfig():
    config = CircuitBreakerConfig()
    assert config.threshold_n == 5
    assert config.signature_window_chars == 200
    assert config.max_lookback == 25
    assert config.volatile_patterns == ()
