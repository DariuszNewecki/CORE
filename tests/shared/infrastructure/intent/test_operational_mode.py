"""Unit tests for ``current_mode()`` per ADR-079 D4 placeholder spec.

Paper §6's "default on uncertainty is *live*" is the failsafe — any value
that is not the exact string ``"dev"`` or ``"live"`` collapses to ``"live"``.
A forged dev signal requires successfully setting ``CORE_OPERATIONAL_MODE``
to ``"dev"``; mistyping, whitespace, mixed-case all fall through to live.

These tests pin that contract so the body change scheduled when #492 lands
must preserve the strict-string semantics (or update these tests in the
same change-set).
"""

from __future__ import annotations

import pytest

from shared.infrastructure.intent import operational_mode
from shared.infrastructure.intent.operational_mode import current_mode


@pytest.fixture(autouse=True)
def _reset_first_call_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test sees a fresh first-call flag so the INFO log assertion
    is testable in isolation if added later. Also resets the env var
    before/after to avoid bleed across tests in the same process."""
    monkeypatch.setattr(operational_mode, "_first_call_logged", False)
    monkeypatch.delenv("CORE_OPERATIONAL_MODE", raising=False)


def test_default_is_live_when_env_unset() -> None:
    assert current_mode() == "live"


def test_exact_dev_returns_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORE_OPERATIONAL_MODE", "dev")
    assert current_mode() == "dev"


def test_exact_live_returns_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORE_OPERATIONAL_MODE", "live")
    assert current_mode() == "live"


@pytest.mark.parametrize(
    "raw",
    [
        "DEV",
        "Dev",
        " dev",
        "dev ",
        "development",
        "prod",
        "",
        "live ",
        "LIVE",
    ],
)
def test_non_exact_values_fall_through_to_live(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    """Anything other than the exact strings 'dev'/'live' fails closed."""
    monkeypatch.setenv("CORE_OPERATIONAL_MODE", raw)
    assert current_mode() == "live"


def test_first_call_logs_then_quiet(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """INFO log fires once on first resolution per process."""
    monkeypatch.setenv("CORE_OPERATIONAL_MODE", "dev")
    with caplog.at_level(
        "INFO", logger="shared.infrastructure.intent.operational_mode"
    ):
        current_mode()
        first_call_records = list(caplog.records)
        current_mode()
        current_mode()
        total_records = list(caplog.records)
    # Exactly one INFO record total — subsequent calls are silent.
    assert len(first_call_records) == 1
    assert len(total_records) == 1
    assert "dev" in first_call_records[0].getMessage()
