from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from api.dependencies import get_thesis_latest


@pytest.mark.asyncio
# ID: 96cd2f8a-6712-4ba5-8a8b-9d4211d8bf61
async def test_get_thesis_latest():
    records = [{"report": "a"}, {"report": "b"}]
    mock_daily_records = AsyncMock(return_value=records)
    with patch(
        "body.services.thesis.record.daily_records",
        new=mock_daily_records,
    ):
        result = await get_thesis_latest()

    mock_daily_records.assert_awaited_once()
    assert result == {"report": "b"}


from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
# ID: 2e83dbd6-380e-4d89-8927-290b6f78a1a2
async def test_get_secrets_service_dep():
    from api.dependencies import get_secrets_service_dep

    session = MagicMock()
    expected_service = MagicMock()

    with patch(
        "api.dependencies._get_secrets_svc",
        new=AsyncMock(return_value=expected_service),
    ) as mock_get_secrets_svc:
        result = await get_secrets_service_dep(session=session)

    assert result is expected_service
    mock_get_secrets_svc.assert_awaited_once_with(session)


from api.dependencies import get_capability_docs_generator


# ID: 31559c0d-b0b6-429d-a03f-bbc766d1d10e
def test_get_capability_docs_generator():
    sentinel = object()
    with patch("api.dependencies._generate_capability_docs", sentinel):
        result = get_capability_docs_generator()
    assert result is sentinel


from api.dependencies import get_drift_analysis


# ID: 45fd08fa-5ce2-48de-9aae-2aeb47361f00
def test_get_drift_analysis():
    from api.dependencies import run_drift_analysis_async

    result = get_drift_analysis()

    assert result is run_drift_analysis_async
    assert callable(result)


from api.dependencies import get_scout_analyzer


# ID: be1860e5-190b-454e-88c1-cc113baaf7c0
def test_get_scout_analyzer():
    with patch("api.dependencies.ScoutAnalyzer") as mock_analyzer_cls:
        instance = MagicMock()
        mock_analyzer_cls.return_value = instance

        result = get_scout_analyzer()

        mock_analyzer_cls.assert_called_once_with()
        assert result is instance


from api.dependencies import get_consequence_log_service


# ID: a4fd966f-d296-4073-988d-5c6ba4124ab9
def test_get_consequence_log_service():
    with patch("api.dependencies.ConsequenceLogService") as mock_service_cls:
        mock_instance = MagicMock()
        mock_service_cls.return_value = mock_instance

        result = get_consequence_log_service()

        mock_service_cls.assert_called_once_with()
        assert result is mock_instance
