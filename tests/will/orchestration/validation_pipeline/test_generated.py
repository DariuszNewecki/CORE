from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from will.orchestration.validation_pipeline import validate_code_async


@pytest.mark.asyncio
# ID: 16b41933-751e-4371-965f-815cd8f769da
async def test_validate_code_async():
    with (
        patch(
            "will.orchestration.validation_pipeline.get_file_classification",
            return_value="python",
        ),
        patch(
            "will.orchestration.validation_pipeline.validate_python_code_async",
            new=AsyncMock(return_value=("formatted_code", [])),
        ) as mock_validate_python,
    ):
        result = await validate_code_async(
            file_path="module.py",
            code="print('hi')",
            quiet=True,
            auditor_context=object(),
        )

    assert result == {
        "status": "clean",
        "violations": [],
        "code": "formatted_code",
    }
    mock_validate_python.assert_awaited_once()
