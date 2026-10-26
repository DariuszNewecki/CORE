from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from mind.logic.engines.ast_gate.engine import ASTGateEngine


# ID: 7dd7b83e-6343-4fea-898e-e4b7c0256ced
def test_ASTGateEngine_verify(tmp_path: Path) -> None:
    source_file = tmp_path / "sample.py"
    source_file.write_text("x = 1\n", encoding="utf-8")

    path_resolver = MagicMock()

    with (
        patch("mind.logic.engines.ast_gate.engine.CapabilityChecks"),
        patch("mind.logic.engines.ast_gate.engine.ModularityChecker"),
        patch("mind.logic.engines.ast_gate.engine.PurityChecks") as mock_purity,
    ):
        mock_purity.check_future_annotations.return_value = []
        engine = ASTGateEngine(path_resolver)

        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            engine.verify(source_file, {"check_type": "future_annotations"})
        )

    assert result.ok is True
    assert result.violations == []


import pytest


@pytest.mark.asyncio
# ID: d0723bba-4eb3-4516-a6d8-9b058ef1ff7f
async def test_ASTGateEngine_verify_context():
    path_resolver = MagicMock()
    engine = ASTGateEngine(path_resolver)

    context = MagicMock()
    params = {"check_type": "duplicate_ids"}

    expected_findings = [MagicMock(), MagicMock()]

    with patch(
        "mind.logic.engines.ast_gate.engine.check_duplicate_ids",
        return_value=expected_findings,
    ) as mock_check:
        result = await engine.verify_context(context, params)

    mock_check.assert_called_once_with(context, params)
    assert result == expected_findings


# ID: 7c11b0f9-a4c1-4477-b0bb-60fce336e3bc
def test_ASTGateEngine(tmp_path: Path) -> None:
    path_resolver = MagicMock()
    source_file = tmp_path / "sample.py"
    source_file.write_text("import os\n", encoding="utf-8")

    engine = ASTGateEngine(path_resolver)
    assert engine.engine_id == "ast_gate"

    # metadata_only_diff is a special case returning ok=True without dispatch.
    import asyncio

    result = asyncio.run(
        engine.verify(source_file, {"check_type": "metadata_only_diff"})
    )
    assert result.ok is True
    assert result.engine_id == "ast_gate"
    assert result.violations == []


# ID: 624b6f6e-3f76-4229-977a-4f7eb8a0b4b1
def test_ASTGateEngine_fs_taxonomy() -> None:
    """fs_taxonomy is lazy and cached: construction does not load it, the
    first access loads it once, later accesses return the same object."""
    taxonomy = MagicMock(name="taxonomy")

    with patch(
        "mind.logic.engines.ast_gate.engine.load_filesystem_operations",
        return_value=taxonomy,
    ) as loader:
        engine = ASTGateEngine(MagicMock())
        loader.assert_not_called()

        first = engine.fs_taxonomy
        second = engine.fs_taxonomy

    assert first is taxonomy
    assert second is taxonomy
    loader.assert_called_once_with()


# ID: 97d78ebd-6332-4a4b-9844-c8dac36d39f5
def test_ASTGateEngine_fs_taxonomy_load_error_is_not_cached() -> None:
    """A loader error surfaces to the caller (fail-closed) and is not cached:
    the next access retries the load."""
    taxonomy = MagicMock(name="taxonomy")

    with patch(
        "mind.logic.engines.ast_gate.engine.load_filesystem_operations",
        side_effect=[RuntimeError("bad taxonomy"), taxonomy],
    ) as loader:
        engine = ASTGateEngine(MagicMock())
        with pytest.raises(RuntimeError, match="bad taxonomy"):
            engine.fs_taxonomy
        assert engine.fs_taxonomy is taxonomy

    assert loader.call_count == 2
