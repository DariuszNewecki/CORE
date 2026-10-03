from __future__ import annotations

from unittest.mock import MagicMock, patch

from mind.logic.engines.workflow_gate.checks.coverage import CoverageMinimumCheck


# ID: 2fb6de7e-7864-4cd6-b41e-c58fe387faac
async def test_coverage_minimum_check_verify() -> None:
    path_resolver = MagicMock()
    check = CoverageMinimumCheck(path_resolver)

    with patch.object(
        CoverageMinimumCheck, "_load_coverage_threshold", return_value=80
    ):
        result = await check.verify(None, {"current_coverage": 95.0})

    assert result == []


from pathlib import Path


# ID: 15818d3c-202a-43d4-a743-846ad5082215
def test_CoverageMinimumCheck() -> None:
    # Arrange
    path_resolver = MagicMock()
    check = CoverageMinimumCheck(path_resolver=path_resolver)

    # Patch the path resolver's policy call to return a non-existent path
    # so _load_coverage_threshold falls back to the configured threshold.
    nonexistent = MagicMock(spec=Path)
    nonexistent.exists.return_value = False
    path_resolver.policy.return_value = nonexistent

    # Act — coverage above threshold -> empty list (happy path)
    import asyncio

    with patch.object(check, "_load_coverage_threshold", return_value=75.0):
        result = asyncio.run(
            check.verify(file_path=None, params={"current_coverage": 90.0})
        )

    # Assert
    assert result == []


# ID: 41e3712f-9742-4d52-b297-0fcbdb0f785d
async def test_CoverageMinimumCheck_verify() -> None:
    path_resolver = MagicMock()
    check = CoverageMinimumCheck(path_resolver)

    check._load_coverage_threshold = MagicMock(return_value=80)

    result = await check.verify(
        Path("src/example.py"),
        {"current_coverage": 95.0},
    )

    assert result == []
    check._load_coverage_threshold.assert_called_once()
