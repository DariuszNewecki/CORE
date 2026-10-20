from __future__ import annotations

from api.v1.integrity_routes import IntegrityRequest


# ID: c0369889-e6fe-41f9-961f-b2dfd1272643
def test_IntegrityRequest():
    # Test default construction
    request = IntegrityRequest()
    assert request.label == "default"

    # Test construction with explicit label
    request = IntegrityRequest(label="custom_label")
    assert request.label == "custom_label"

    # Test empty body equivalence (label defaults to "default")
    request = IntegrityRequest()
    assert request.label == "default"


from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
# ID: a12e24fc-fcdc-435a-98fe-90022b7aaf24
async def test_integrity_verify() -> None:
    from api.v1.integrity_routes import integrity_verify

    core_context = MagicMock(name="core_context")
    request = MagicMock(name="request")
    request.app.state.core_context = core_context

    payload = MagicMock(name="payload")
    payload.label = "baseline-1"

    expected = {"ok": True, "errors": []}

    with patch(
        "api.v1.integrity_routes.verify_integrity",
        return_value=expected,
    ) as mock_verify:
        result = await integrity_verify(request, payload)

    mock_verify.assert_called_once_with(core_context, "baseline-1")
    assert result is expected
    assert result["ok"] is True
    assert result["errors"] == []


import asyncio


# ID: 0c2d28ed-f654-4e01-b713-cb516395c402
def test_integrity_baseline():
    from api.v1.integrity_routes import integrity_baseline

    mock_core_context = MagicMock()

    mock_request = MagicMock()
    mock_request.app.state.core_context = mock_core_context

    mock_payload = MagicMock()
    mock_payload.label = "my-baseline"

    expected_result = {"path": "/some/baseline.json", "file_count": 42}

    with patch(
        "api.v1.integrity_routes.create_baseline",
        return_value=expected_result,
    ) as mock_create_baseline:
        result = asyncio.run(
            integrity_baseline(request=mock_request, payload=mock_payload)
        )

    mock_create_baseline.assert_called_once_with(mock_core_context, "my-baseline")
    assert result == expected_result
