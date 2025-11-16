# tests/admin/test_guard_drift_cli.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from features.introspection.drift_service import run_drift_analysis_async
from shared.models import CapabilityMeta


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


@pytest.mark.anyio
async def test_drift_analysis_clean(tmp_path: Path, mocker):
    """
    Tests that drift analysis reports a clean state when manifest and
    (mocked) code capabilities are in sync.
    """
    # ARRANGE
    # Mock the two data sources the service uses.
    # --- THIS IS THE FIX ---
    # The mocked return value MUST be a dictionary mapping strings to CapabilityMeta instances.
    mocker.patch(
        "features.introspection.drift_service.load_manifest_capabilities",
        return_value={
            "alpha.cap": CapabilityMeta(key="alpha.cap"),
            "beta.cap": CapabilityMeta(key="beta.cap"),
        },
    )
    # --- END OF FIX ---

    mock_graph_data = {
        "symbols": {
            "file1::func_a": {"key": "alpha.cap"},
            "file2::func_b": {"key": "beta.cap"},
        }
    }
    mocker.patch(
        "services.knowledge.knowledge_service.KnowledgeService.get_graph",
        new_callable=AsyncMock,
        return_value=mock_graph_data,
    )

    # ACT
    report = await run_drift_analysis_async(tmp_path)

    # ASSERT
    assert not report.missing_in_code
    assert not report.undeclared_in_manifest
    assert not report.mismatched_mappings


@pytest.mark.anyio
async def test_drift_analysis_detects_drift(tmp_path: Path, mocker):
    """
    Tests that drift analysis correctly identifies discrepancies between
    the manifest and the (mocked) code capabilities.
    """
    # ARRANGE
    # Mock the manifest to declare one capability
    # --- THIS IS THE FIX ---
    mocker.patch(
        "features.introspection.drift_service.load_manifest_capabilities",
        return_value={"manifest.only.cap": CapabilityMeta(key="manifest.only.cap")},
    )
    # --- END OF FIX ---

    # Mock the code scan to find a different capability
    mock_graph_data = {"symbols": {"file1::func_a": {"key": "code.only.cap"}}}
    mocker.patch(
        "services.knowledge.knowledge_service.KnowledgeService.get_graph",
        new_callable=AsyncMock,
        return_value=mock_graph_data,
    )

    # ACT
    report = await run_drift_analysis_async(tmp_path)

    # ASSERT
    assert report.missing_in_code == ["manifest.only.cap"]
    assert report.undeclared_in_manifest == ["code.only.cap"]
