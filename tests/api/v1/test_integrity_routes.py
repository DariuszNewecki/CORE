# tests/api/v1/test_integrity_routes.py

"""Unit tests for integrity_routes (ADR-055 D6, closes #353).

Synchronous endpoints — no background tasks, no session. Both routes
delegate entirely to will.governance.integrity_runner.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from api.v1.integrity_routes import (
    IntegrityRequest,
    integrity_baseline,
    integrity_verify,
)


def _mock_request():
    request = MagicMock()
    request.app.state.core_context = MagicMock()
    return request


# ── integrity_baseline ────────────────────────────────────────────────────────

async def test_integrity_baseline_returns_runner_result():
    """POST /integrity/baseline delegates to create_baseline and returns its dict."""
    expected = {"path": "var/integrity/default.json", "file_count": 142}
    with patch(
        "api.v1.integrity_routes.create_baseline",
        return_value=expected,
    ) as mock_fn:
        out = await integrity_baseline(
            request=_mock_request(),
            payload=IntegrityRequest(label="default"),
        )
    mock_fn.assert_called_once()
    assert out == expected


async def test_integrity_baseline_passes_label_to_runner():
    """The label field is forwarded as the second positional arg to create_baseline."""
    with patch(
        "api.v1.integrity_routes.create_baseline",
        return_value={"path": "var/integrity/release.json", "file_count": 10},
    ) as mock_fn:
        await integrity_baseline(
            request=_mock_request(),
            payload=IntegrityRequest(label="release"),
        )
    assert mock_fn.call_args.args[1] == "release"


async def test_integrity_baseline_uses_default_label():
    """Empty body defaults to label='default'."""
    with patch(
        "api.v1.integrity_routes.create_baseline",
        return_value={"path": "var/integrity/default.json", "file_count": 5},
    ) as mock_fn:
        await integrity_baseline(
            request=_mock_request(),
            payload=IntegrityRequest(),
        )
    assert mock_fn.call_args.args[1] == "default"


# ── integrity_verify ──────────────────────────────────────────────────────────

async def test_integrity_verify_returns_ok_true_on_clean():
    """POST /integrity/verify returns the runner result when the baseline matches."""
    expected = {
        "ok": True,
        "errors": [],
        "checked_at": "2026-07-06T12:00:00Z",
    }
    with patch(
        "api.v1.integrity_routes.verify_integrity",
        return_value=expected,
    ) as mock_fn:
        out = await integrity_verify(
            request=_mock_request(),
            payload=IntegrityRequest(label="default"),
        )
    mock_fn.assert_called_once()
    assert out["ok"] is True
    assert out["errors"] == []


async def test_integrity_verify_failure_is_not_an_http_error():
    """verify_integrity returning ok=False does NOT raise — the route returns the
    dict and lets the caller decide how to handle hash mismatches."""
    failure = {
        "ok": False,
        "errors": ["hash mismatch: src/body/foo.py"],
        "checked_at": "2026-07-06T12:00:00Z",
    }
    with patch(
        "api.v1.integrity_routes.verify_integrity",
        return_value=failure,
    ):
        out = await integrity_verify(
            request=_mock_request(),
            payload=IntegrityRequest(label="default"),
        )
    assert out["ok"] is False
    assert len(out["errors"]) == 1
    assert "src/body/foo.py" in out["errors"][0]


async def test_integrity_verify_passes_label_to_runner():
    """The label field is forwarded to verify_integrity."""
    with patch(
        "api.v1.integrity_routes.verify_integrity",
        return_value={"ok": True, "errors": [], "checked_at": "2026-07-06T00:00:00Z"},
    ) as mock_fn:
        await integrity_verify(
            request=_mock_request(),
            payload=IntegrityRequest(label="pre-release"),
        )
    assert mock_fn.call_args.args[1] == "pre-release"
