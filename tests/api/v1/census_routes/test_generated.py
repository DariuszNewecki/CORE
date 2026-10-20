from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from api.v1.census_routes import census_diff


@pytest.mark.asyncio
# ID: 8e8d770f-8e88-4b56-8dc3-f6171cdff8a7
async def test_census_diff():
    mock_request = MagicMock()
    mock_core_context = MagicMock()
    mock_request.app.state.core_context = mock_core_context

    expected_result = {"some": "diff"}
    with patch(
        "api.v1.census_routes.get_diff", return_value=expected_result
    ) as mock_get_diff:
        result = await census_diff(request=mock_request, baseline="some_baseline")
        mock_get_diff.assert_called_once_with(
            mock_core_context, baseline="some_baseline"
        )
        assert result == expected_result


import asyncio

from api.v1.census_routes import list_census_baselines


# ID: 58aa8ffb-06c3-4b31-93c7-7ebe809b19d9
def test_list_census_baselines():
    core_context = MagicMock()
    request = MagicMock()
    request.app.state.core_context = core_context

    expected = [{"id": "b2"}, {"id": "b1"}]

    with patch(
        "api.v1.census_routes.list_baselines", return_value=expected
    ) as mock_list:
        result = asyncio.run(list_census_baselines(request))

    mock_list.assert_called_once_with(core_context)
    assert result == expected
