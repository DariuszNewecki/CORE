# tests/body/atomic/test_split_applier.py
"""Tests for refactor.apply_split atomic action (#672).

Covers:
  - Registry: action is registered with correct impact_level after risk overlay.
  - Dry-run: write=False returns ok=True, nothing written to file_handler.
  - Write mode: files_written + files_deleted populated; file_handler called.
  - Empty split_results: ok=False (no files produced) in write mode.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from body.atomic.split_applier import action_refactor_apply_split
from shared.governance_token import authorize_execution
from shared.infrastructure.intent.action_risk import load_action_risk_raw


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_context(repo_root: Path) -> MagicMock:
    ctx = MagicMock()
    ctx.git_service.repo_path = repo_root
    return ctx


def _make_split_entry(
    repo_root: Path,
    original_rel: str,
    new_files: list[tuple[str, str]],
    exists: bool = True,
) -> dict:
    """Build a code_generation-phase split_result dict."""
    split_result = MagicMock()
    split_result.files = [
        (repo_root / rel, content) for rel, content in new_files
    ]
    split_result.original_path = MagicMock()
    split_result.original_path.__str__ = lambda s: str(repo_root / original_rel)
    split_result.original_path.exists.return_value = exists
    # Support .relative_to(repo_root) on original_path
    split_result.original_path.relative_to = lambda base: Path(original_rel)
    return {"ok": True, "split_result": split_result}


# ── Registration test ─────────────────────────────────────────────────────────


# ID: e2d17724-71a9-4e79-9266-25da6699a4af
def test_refactor_apply_split_registered_with_dangerous_impact() -> None:
    """refactor.apply_split must appear in action_risk.yaml as dangerous."""
    from body.atomic.registry import action_registry

    raw = load_action_risk_raw()
    action_registry.apply_risk_config(raw)
    defn = action_registry.get("refactor.apply_split")
    assert defn is not None, "refactor.apply_split is not registered"
    assert defn.impact_level == "dangerous"
    assert "python" in defn.artifact_type


# ── Dry-run tests ─────────────────────────────────────────────────────────────


# ID: 67b534dd-5165-430a-a344-fcf24d152b9a
@pytest.mark.asyncio
async def test_dry_run_returns_ok_without_writing(tmp_path: Path) -> None:
    """write=False must return ok=True and call no file_handler write methods."""
    ctx = _make_context(tmp_path)
    entry = _make_split_entry(
        tmp_path,
        original_rel="src/big.py",
        new_files=[("src/part_a.py", "# a\n"), ("src/part_b.py", "# b\n")],
    )

    with authorize_execution("refactor.apply_split"):
        result = await action_refactor_apply_split(
            core_context=ctx,
            split_results=[entry],
            write=False,
        )

    assert result.ok is True
    assert result.data["files_written"] == []
    assert result.data["files_deleted"] == []
    ctx.file_handler.write_runtime_text.assert_not_called()
    ctx.file_handler.remove_file.assert_not_called()


# ── Write mode tests ──────────────────────────────────────────────────────────


# ID: ad318e27-16e8-4ce7-9714-fe702a83f138
@pytest.mark.asyncio
async def test_write_mode_calls_file_handler_and_returns_paths(
    tmp_path: Path,
) -> None:
    """write=True must write each new module and remove the original."""
    ctx = _make_context(tmp_path)
    entry = _make_split_entry(
        tmp_path,
        original_rel="src/big.py",
        new_files=[("src/part_a.py", "# a\n"), ("src/part_b.py", "# b\n")],
    )

    with authorize_execution("refactor.apply_split"):
        result = await action_refactor_apply_split(
            core_context=ctx,
            split_results=[entry],
            write=True,
        )

    assert result.ok is True
    assert set(result.data["files_written"]) == {"src/part_a.py", "src/part_b.py"}
    assert result.data["files_deleted"] == ["src/big.py"]
    assert set(result.data["files_produced"]) == {
        "src/part_a.py",
        "src/part_b.py",
        "src/big.py",
    }
    assert ctx.file_handler.write_runtime_text.call_count == 2
    ctx.file_handler.remove_file.assert_called_once_with("src/big.py")


# ID: 6e797ef0-7bf2-4de1-9e5d-47a4105625c7
@pytest.mark.asyncio
async def test_write_mode_skips_failed_entries(tmp_path: Path) -> None:
    """Entries with ok=False must be silently skipped."""
    ctx = _make_context(tmp_path)
    bad_entry = {"ok": False, "split_result": MagicMock()}
    good_entry = _make_split_entry(
        tmp_path,
        original_rel="src/big.py",
        new_files=[("src/part_a.py", "# a\n")],
    )

    with authorize_execution("refactor.apply_split"):
        result = await action_refactor_apply_split(
            core_context=ctx,
            split_results=[bad_entry, good_entry],
            write=True,
        )

    assert result.ok is True
    assert result.data["files_written"] == ["src/part_a.py"]
    bad_entry["split_result"].files.__iter__.assert_not_called()


# ID: f3c43fb7-227a-4cb0-a3b9-523fa5f77e67
@pytest.mark.asyncio
async def test_write_mode_empty_split_results_returns_not_ok(
    tmp_path: Path,
) -> None:
    """No ok=True entries in write mode → ok=False (nothing produced)."""
    ctx = _make_context(tmp_path)

    with authorize_execution("refactor.apply_split"):
        result = await action_refactor_apply_split(
            core_context=ctx,
            split_results=[],
            write=True,
        )

    assert result.ok is False
    assert result.data["files_written"] == []
